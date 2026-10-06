#!/usr/bin/env python3
"""Gateway RBAC, Spring의 독립 검사, 레거시 신뢰 경계를 실제 요청으로 확인합니다.

준비된 로컬 환경을 대상으로 합니다. 회사·계좌·이체 데이터는 만들지 않습니다.
LDAP 관리자 그룹만 잠시 변경하고 finally에서 복원합니다. 토큰은 메모리에서만 씁니다.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from ldap_support import COMPANY_A, COMPANY_B, LDAP_USERS, read_values
from verify import ROOT, ISSUER, GATEWAY, ACCESS, ADMIN, b64, claims, http, login, wait_ready


CHECKS = []
STARTED = datetime.now(timezone.utc)
LEGACY = GATEWAY + '/legacy'
APIS = ('finaccess-api', 'finadmin-api', 'finlegacy-api')
REPORT_PATH = ROOT / '.local/gateway-rbac-verification.json'


def record(name, passed, **details):
    # 결과에는 토큰·비밀번호·응답 본문을 통째로 넣지 않습니다.
    CHECKS.append({'case': name, 'passed': bool(passed), **details})
    print(('PASS ' if passed else 'FAIL ') + name, flush=True)
    if not passed:
        raise AssertionError(name)


def request_with_headers(url, token, headers):
    # 기존 http()는 일반 요청에 재사용하고, 이 함수는 헤더 위조 검사에만 씁니다.
    request = urllib.request.Request(url, headers={
        **headers, 'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read().decode()
        try:
            body = json.loads(raw)
        except ValueError:
            body = raw
        return response.status, body, dict(response.headers)


def check(name, expected, url, token=None, method='GET', body=None, *, layer, extra_headers=None):
    result = (request_with_headers(url, token, extra_headers) if extra_headers is not None
              else http(url, token, method, body))
    status, value, headers = result
    lower = {key.lower(): value for key, value in headers.items()}
    backend = lower.get('x-finlab-backend')
    rejected = lower.get('x-finlab-rejected-by')
    # Gateway 정책의 거절과, 백엔드에 도착한 요청을 응답 이름표로 구별합니다.
    # 이름표는 인증 수단이 아닙니다. 아래에서 실제 접근 로그도 함께 확인합니다.
    if layer == 'gateway-policy':
        right_layer = rejected == 'gateway-policy' and backend is None
    elif layer == 'gateway-jwt':
        right_layer = backend is None
    else:
        right_layer = backend == layer and rejected is None
    record(name, status == expected and right_layer, expected=expected, actual=status,
           expectedLayer=layer, backend=backend, rejectedBy=rejected, method=method,
           path=urllib.parse.urlsplit(url).path)
    return value


def docker(*arguments, timeout=30):
    # inspect에 비밀번호 환경 변수가 있어도 출력하지 않고 필요한 필드만 메모리에서 읽습니다.
    result = subprocess.run(['docker', *arguments], cwd=ROOT, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Docker read-only inspection failed')
    return result.stdout


def network_checks():
    ids = {name: docker('compose', 'ps', '-q', name).strip() for name in ('legacy', 'apisix', 'web')}
    record('network: three expected services are running', all(ids.values()))
    info = {name: json.loads(docker('inspect', container))[0] for name, container in ids.items()}
    legacy = info['legacy']
    # EXPOSE와 호스트 포트 공개는 다릅니다. PortBindings가 비어 있는지 확인합니다.
    bindings = legacy['HostConfig'].get('PortBindings') or {}
    published = legacy['NetworkSettings'].get('Ports') or {}
    record('network: legacy publishes no host port', not bindings and not any(published.values()))
    networks = legacy['NetworkSettings']['Networks']
    record('network: legacy belongs to one isolated network', len(networks) == 1)
    network_name, address = next(iter(networks.items()))
    network = json.loads(docker('network', 'inspect', network_name))[0]
    allowed = {ids['legacy'], ids['apisix']}
    # API7도 같은 신뢰 경계를 사용합니다. 이름뿐 아니라 Compose 소유와 서비스 라벨을 확인합니다.
    enterprise_ids = docker('ps', '-q', '--filter', 'name=^/finlab-api7-gateway$').strip()
    if enterprise_ids:
        enterprise = json.loads(docker('inspect', enterprise_ids))[0]
        labels = enterprise['Config']['Labels']
        record('network: Enterprise gateway has expected Compose ownership',
               labels.get('com.docker.compose.project') == 'finlab-api7'
               and labels.get('com.docker.compose.service') == 'gateway')
        allowed.add(enterprise['Id'])
    record('network: private network is internal and has only gateway plus legacy',
           network.get('Internal') is True and set(network.get('Containers', {})) == allowed)
    record('network: web is outside the private network',
           network_name not in info['web']['NetworkSettings']['Networks'])
    # DNSで見つからないだけでは隔離の証明が弱いので、レガシーの実IPを指定します。
    # /healthzには認証がないため、到達できたら必ず200になります。
    probe = subprocess.run(['docker', 'compose', 'exec', '-T', 'web',
        'wget', '-q', '-T', '3', '-O', '/dev/null',
        'http://' + address['IPAddress'] + ':8082/healthz'],
        cwd=ROOT, text=True, capture_output=True, timeout=10)
    record('network: web cannot call legacy health endpoint by container IP', probe.returncode != 0)
    # サーバー停止を誤って「隔離成功」と判断しないため、生存も別経路で確認します。
    record('network: legacy container is healthy during isolation test',
           json.loads(docker('inspect', ids['legacy']))[0]['State']['Health']['Status'] == 'healthy')


def token_checks(values, tokens):
    # 실제 Keycloak 로그인으로 시간 조건이 다른 토큰을 발급합니다. exp/nbf를
    # 손으로 바꾸면 서명부터 깨지므로 그 방법으로 시간 검사를 증명하지 않습니다.
    # 다른 issuer 검사는 같은 RSA 키로 서명하는 별도 격리 fixture에서 수행합니다.
    # Keycloak hardcoded mapper는 예약 필드 iss를 덮어쓰지 않아 여기서 사용하지 않습니다.
    password = values['LAB_ADMIN_PASSWORD']
    short_lived = login('admin', password, 'finlab-expiry-test')
    future = login('admin', password, 'finlab-not-before-test')
    no_roles = login('admin', password, 'finlab-no-roles-test')
    access_only = login('admin', password, 'finlab-access-test')
    record('fixture: Keycloak issued a future nbf', claims(future).get('nbf', 0) > time.time() + 120)
    record('fixture: role-free token targets all three APIs',
           set(APIS).issubset(set(claims(no_roles).get('aud', []))))
    record('fixture: role-free token has no app roles', all(
        not claims(no_roles).get('resource_access', {}).get(api, {}).get('roles') for api in APIS))
    access_audience = claims(access_only).get('aud', [])
    record('fixture: audience-only client really excludes admin and legacy',
           access_audience == 'finaccess-api' or access_audience == ['finaccess-api'])

    # 이 경우만 payload를 고칩니다. 목적이 '서명 변조 거절'이기 때문입니다.
    pieces = tokens['admin'].split('.')
    changed = claims(tokens['admin'])
    changed['sub'] = 'not-the-signed-subject'
    pieces[1] = b64(json.dumps(changed).encode())
    tampered = '.'.join(pieces)
    endpoints = [
        ('gateway-access', GATEWAY + '/access/api/me', 'gateway-jwt'),
        ('gateway-admin', GATEWAY + '/admin/api/admin/summary', 'gateway-jwt'),
        ('gateway-legacy', LEGACY + '/api/reports', 'gateway-jwt'),
        ('direct-access', ACCESS + '/api/me', 'finaccess'),
        ('direct-admin', ADMIN + '/api/admin/summary', 'finadmin'),
    ]
    for label, url, layer in endpoints:
        check(label + ': missing token', 401, url, layer=layer)
        check(label + ': signature tampering', 401, url, tampered, layer=layer)
        check(label + ': genuinely signed future nbf', 401, url, future, layer=layer)
        check(label + ': valid token but missing application role', 403, url, no_roles,
              layer='gateway-policy' if label.startswith('gateway') else layer)
    check('gateway admin: wrong audience', 403, GATEWAY + '/admin/api/admin/summary', access_only,
          layer='gateway-jwt')
    check('gateway legacy: wrong audience', 403, LEGACY + '/api/reports', access_only, layer='gateway-jwt')
    check('direct admin: wrong audience independently rejected', 401,
          ADMIN + '/api/admin/summary', access_only, layer='finadmin')
    check('gateway access: correct audience is accepted', 200,
          GATEWAY + '/access/api/me', access_only, layer='finaccess')
    return short_lived, endpoints


def role_and_method_checks(tokens):
    # 실패시키는 입력과 존재하지 않는UUID를 써서, 통과 여부를 확인하면서 업무 데이터는 만들지 않습니다.
    missing = str(uuid.uuid4())
    for name in ('alice', 'bob', 'admin', 'outsider'):
        for prefix, layer in [('/access', 'finaccess'), ('/admin', 'finadmin')]:
            check(name + ': gateway identity ' + prefix, 200,
                  GATEWAY + prefix + '/api/me', tokens[name], layer=layer)
        check(name + ': legacy reports', 200, LEGACY + '/api/reports', tokens[name], layer='legacy')
        for prefix in ('/admin', '/legacy'):
            allowed = name == 'admin'
            check(name + ': admin endpoint ' + prefix, 200 if allowed else 403,
                  GATEWAY + prefix + '/api/admin/summary', tokens[name],
                  layer=('finadmin' if prefix == '/admin' else 'legacy') if allowed else 'gateway-policy')
    for label, base in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
        layer = 'gateway-policy' if label == 'gateway' else 'finadmin'
        check(label + ': ordinary user independently forbidden', 403,
              base + '/api/admin/summary', tokens['alice'], layer=layer)
        check(label + ': POST is not GET permission', 403,
              base + '/api/admin/summary', tokens['admin'], 'POST', layer=layer)
        check(label + ': unlisted route denied by default', 403,
              base + '/api/not-configured', tokens['admin'], layer=layer)
    check('legacy: POST reports is denied before upstream', 403,
          LEGACY + '/api/reports', tokens['admin'], 'POST', layer='gateway-policy')
    for label, base in [('gateway', GATEWAY + '/access'), ('direct', ACCESS)]:
        denied = 'gateway-policy' if label == 'gateway' else 'finaccess'
        check(label + ': reader cannot create company', 403,
              base + '/api/companies', tokens['alice'], 'POST', {}, layer=denied)
        check(label + ': admin company request reaches input validation', 400,
              base + '/api/companies', tokens['admin'], 'POST', {}, layer='finaccess')
        check(label + ': reader cannot open account', 403,
              base + '/api/companies/' + missing + '/accounts', tokens['alice'], 'POST', layer=denied)
        check(label + ': admin account request reaches missing-company rule', 404,
              base + '/api/companies/' + missing + '/accounts', tokens['admin'], 'POST', layer='finaccess')
        check(label + ': user transfer request reaches input validation', 400,
              base + '/api/transfers', tokens['alice'], 'POST', {}, layer='finaccess')
        check(label + ': approver cannot create transfer without user role', 403,
              base + '/api/transfers', tokens['bob'], 'POST', {}, layer=denied)
        for action in ('approve', 'reject', 'execute'):
            path = '/api/transfers/' + missing + '/' + action
            check(label + ': user cannot ' + action, 403, base + path,
                  tokens['alice'], 'POST', layer=denied)
            check(label + ': approver ' + action + ' reaches missing-transfer rule', 404,
                  base + path, tokens['bob'], 'POST', layer='finaccess')
        check(label + ': own company readable', 200,
              base + '/api/companies/' + COMPANY_A, tokens['alice'], layer='finaccess')
        check(label + ': other company denied by backend business rule', 403,
              base + '/api/companies/' + COMPANY_B, tokens['alice'], layer='finaccess')


def forged_header_checks(tokens):
    spoofed = {'X-Finlab-Subject': 'forged-person', 'X-Finlab-Issuer': 'https://forged.invalid',
               'X-Finlab-Roles': 'admin', 'X-Finlab-Backend': 'finadmin',
               'X-Finlab-Rejected-By': 'gateway-policy'}
    body = check('legacy: external identity headers replaced by verified token claims', 200,
                 LEGACY + '/api/reports', tokens['alice'], layer='legacy', extra_headers=spoofed)
    record('legacy: response subject and issuer belong to signed identity',
           body.get('subject') == claims(tokens['alice'])['sub'] and body.get('issuer') == ISSUER
           and body.get('sampleData') is True and body.get('backend') == 'legacy')
    check('legacy: forged admin header cannot escalate role', 403,
          LEGACY + '/api/admin/summary', tokens['alice'], layer='gateway-policy', extra_headers=spoofed)


def ldap_group_checks(values):
    # 기존 스크립트의 membership 명령을 재사용합니다. main()은 호출하지 않습니다.
    # 기존 main()은 모의 이체까지 실행하므로 이번 검사에 불필요한 데이터가 생기기 때문입니다.
    spec = importlib.util.spec_from_file_location('verify_ldap_helpers', ROOT / 'scripts/verify-ldap.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for name, (password_key, _, group) in LDAP_USERS.items():
        token = login(name, values[password_key])
        expected = 'admin' if group == 'admins' else 'reader'
        record(name + ': LDAP group becomes legacy client role',
               expected in claims(token).get('resource_access', {}).get('finlegacy-api', {}).get('roles', []))
        check(name + ': LDAP identity reads legacy report', 200,
              LEGACY + '/api/reports', token, layer='legacy')
    original = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    endpoints = [('gateway admin', GATEWAY + '/admin/api/admin/summary', 'finadmin'),
                 ('gateway legacy', LEGACY + '/api/admin/summary', 'legacy'),
                 ('direct admin', ADMIN + '/api/admin/summary', 'finadmin')]
    for label, url, layer in endpoints:
        check(label + ': LDAP admin before removal', 200, url, original, layer=layer)
    # finally 범위 안에서 변경해야 변경 직후 오류가 나도 복원을 시도합니다.
    try:
        helper.change_membership('delete')
        reduced = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
        record('LDAP removal: new token loses admin in both APIs', all(
            'admin' not in claims(reduced).get('resource_access', {}).get(api, {}).get('roles', [])
            for api in ('finadmin-api', 'finlegacy-api')))
        for label, url, layer in endpoints:
            check(label + ': removed member new token denied', 403, url, reduced,
                  layer='gateway-policy' if label.startswith('gateway') else layer)
            check(label + ': old unexpired token still allowed', 200, url, original, layer=layer)
    finally:
        helper.change_membership('add')
    restored = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    record('LDAP restoration: new token restores admin in both APIs', all(
        'admin' in claims(restored).get('resource_access', {}).get(api, {}).get('roles', [])
        for api in ('finadmin-api', 'finlegacy-api')))
    for label, url, layer in endpoints:
        check(label + ': restored member new token allowed', 200, url, restored, layer=layer)


def access_log_checks(token):
    # 로그에 고유한 경로를 남겨 이전 실행의 403을 이번 결과로 잘못 재사용하지 않습니다.
    unique = '/api/verify-denied-' + uuid.uuid4().hex
    check('log evidence: unique unlisted legacy route denied', 403,
          LEGACY + unique, token, layer='gateway-policy')
    pattern = re.compile(r'\] (?P<method>[A-Z]+) (?P<path>/\S*) (?P<status>\d{3}) '
                         r'(?P<seconds>[0-9.]+) (?P<upstream>[0-9, :\-]+)\s*$')
    # 응답이 먼저 도착하고 버퍼에 있던 접근 로그가 조금 뒤에 출력될 수 있습니다.
    # 무조건 오래 쉬지 않고, 이번 고유 경로의 로그가 보일 때까지만 짧게 재조회합니다.
    deadline = time.monotonic() + 10
    denied, rows = None, []
    while denied is None and time.monotonic() < deadline:
        output = docker('logs', '--tail', '600', '--since', STARTED.isoformat(), GATEWAY_CONTAINER)
        rows = []
        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                row = match.groupdict()
                row.pop('seconds')
                rows.append(row)
        denied = next((r for r in reversed(rows) if r['path'].endswith(unique)
                       and r['status'] == '403' and r['upstream'] == '-'), None)
        if denied is None:
            time.sleep(0.5)
    record('log evidence: gateway denial has no upstream status', denied is not None,
           evidence=denied)
    domain_path = '/api/companies/' + COMPANY_B
    downstream = next((r for r in reversed(rows) if r['path'].endswith(domain_path)
                       and r['status'] == '403' and r['upstream'] == '403'), None)
    record('log evidence: company denial comes from upstream 403', downstream is not None,
           evidence=downstream)


def main():
    global GATEWAY, LEGACY, REPORT_PATH, GATEWAY_CONTAINER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enterprise', action='store_true', help='API7 Enterprise 18091 검사')
    args = parser.parse_args()
    GATEWAY_CONTAINER = 'finlab-api7-gateway' if args.enterprise else 'finlab-apisix-1'
    if args.enterprise:
        GATEWAY = 'http://localhost:18091'
        LEGACY = GATEWAY + '/legacy'
        REPORT_PATH = ROOT / '.local/api7-verification.json'
    completed = False
    config_paths = ('compose.yaml', 'infra/apisix/config.yaml', 'infra/apisix/apisix.yaml',
                    'infra/keycloak/finlab-realm.json', 'infra/gateway/rbac.lua')
    if args.enterprise:
        config_paths += ('compose.api7.yaml', 'infra/api7/config.yaml', 'scripts/setup-api7.py')
    configuration = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in config_paths}
    try:
        values = read_values()
        for url in (ISSUER + '/.well-known/openid-configuration', GATEWAY + '/',
                    ACCESS + '/api/hello', ADMIN + '/api/hello'):
            wait_ready(url)
        print('준비된 로컬 환경에서 PKCE 로그인과 Gateway RBAC 검증을 시작합니다.', flush=True)
        tokens = {name: login(name, values['LAB_' + name.upper() + '_PASSWORD'])
                  for name in ('alice', 'bob', 'admin', 'outsider')}
        short_lived, endpoints = token_checks(values, tokens)
        role_and_method_checks(tokens)
        forged_header_checks(tokens)
        network_checks()
        ldap_group_checks(values)
        # Spring 기본 시계 오차 60초까지 지난 뒤 확인합니다. exp를 임의로 고치지 않습니다.
        deadline = claims(short_lived)['exp'] + 65
        if time.time() < deadline:
            print('실제 서명된 짧은 토큰의 만료 및 Spring 시계 오차 허용 시간이 지나기를 기다립니다.', flush=True)
        while time.time() < deadline:
            time.sleep(min(5, deadline - time.time()))
        for label, url, layer in endpoints:
            check(label + ': genuinely signed expired token', 401, url, short_lived, layer=layer)
        # 로그인 세션과 무관하게 방금 발급한 토큰을 써서 로그 확인 단계의 만료 혼동을 피합니다.
        fresh = login('admin', values['LAB_ADMIN_PASSWORD'])
        access_log_checks(fresh)
        record('configuration: checked files stayed unchanged during verification',
               all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
                   for path, digest in configuration.items()))
        completed = True
    finally:
        REPORT_PATH.parent.mkdir(exist_ok=True)
        report = {'startedAt': STARTED.isoformat(), 'verifiedAt': datetime.now(timezone.utc).isoformat(),
                  'gateway': GATEWAY, 'completed': completed, 'total': len(CHECKS),
                  'passed': sum(c['passed'] for c in CHECKS),
                  'failed': sum(not c['passed'] for c in CHECKS), 'checks': CHECKS,
                  'configurationSha256': configuration,
                  'notCoveredHere': ['잘못된 issuer의 유효 서명 토큰: 별도 격리 fixture에서 검증'],
                  'note': '실제 PKCE 로그인. 업무 데이터 생성 없음. LDAP 그룹은 finally에서 복원. 비밀번호·토큰 원문 없음.'}
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'완료: {len(CHECKS)}개 검증. {REPORT_PATH.name}에 비밀값 없는 결과를 저장했습니다.')


if __name__ == '__main__':
    main()
