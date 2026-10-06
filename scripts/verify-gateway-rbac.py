#!/usr/bin/env python3
"""Gateway RBAC, 두 Spring 백엔드의 독립 검사를 실제 요청으로 확인합니다.

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
APIS = ('finaccess-api', 'finadmin-api')
REPORT_PATH = ROOT / '.local/api7-verification.json'
GATEWAY_CONTAINER = 'finlab-api7-gateway'


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
    # 기본 ACL/fault-injection의 고유 응답과 upstream 부재도 구분해서 기록합니다.
    signal = value.get('message') if isinstance(value, dict) else None
    native_denial = signal == 'Required application role missing (API7 ACL)'
    default_denial = isinstance(value, dict) and value.get('rejectedBy') == 'gateway-policy'
    # Gateway 정책의 거절과, 백엔드에 도착한 요청을 응답 이름표로 구별합니다.
    # 이름표는 인증 수단이 아닙니다. 아래에서 실제 접근 로그도 함께 확인합니다.
    if layer == 'gateway-policy':
        right_layer = (rejected == 'gateway-policy' or native_denial or default_denial) and backend is None
    elif layer in ('gateway-jwt', 'gateway-no-body'):
        right_layer = backend is None
    else:
        right_layer = backend == layer and rejected is None
    record(name, status == expected and right_layer, expected=expected, actual=status,
           expectedLayer=layer, backend=backend, rejectedBy=rejected,
           nativeAclDenied=native_denial, method=method,
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
    enterprise_ids = docker('ps', '-q', '--filter', 'name=^/finlab-api7-gateway$').strip()
    record('network: API7 Enterprise is the only FinLab gateway',
           bool(enterprise_ids) and not docker('ps', '-aq', '--filter', 'name=^/finlab-apisix-1$').strip())
    enterprise = json.loads(docker('inspect', enterprise_ids))[0]
    labels = enterprise['Config']['Labels']
    record('network: Enterprise gateway has expected Compose ownership',
           labels.get('com.docker.compose.project') == 'finlab-api7'
           and labels.get('com.docker.compose.service') == 'gateway')
    record('network: Enterprise serves only loopback port 18090',
           enterprise['HostConfig']['PortBindings'].get('9080/tcp') == [
               {'HostIp': '127.0.0.1', 'HostPort': '18090'}])
    record('network: Enterprise connects to control plane and application networks',
           set(enterprise['NetworkSettings']['Networks']) == {'api7-ee_api7', 'finlab_default'})


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
    record('fixture: role-free token targets both APIs',
           set(APIS).issubset(set(claims(no_roles).get('aud', []))))
    record('fixture: role-free token has no app roles', all(
        not claims(no_roles).get('resource_access', {}).get(api, {}).get('roles') for api in APIS))
    access_audience = claims(access_only).get('aud', [])
    record('fixture: audience-only client really excludes admin',
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
        allowed = name == 'admin'
        check(name + ': admin endpoint', 200 if allowed else 403,
              GATEWAY + '/admin/api/admin/summary', tokens[name],
              layer='finadmin' if allowed else 'gateway-policy')
    for label, base in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
        layer = 'gateway-policy' if label == 'gateway' else 'finadmin'
        check(label + ': ordinary user independently forbidden', 403,
              base + '/api/admin/summary', tokens['alice'], layer=layer)
        check(label + ': POST is not GET permission', 403,
              base + '/api/admin/summary', tokens['admin'], 'POST', layer=layer)
        check(label + ': unlisted route denied by default', 403,
              base + '/api/not-configured', tokens['admin'], layer=layer)
    for method, path in [('HEAD', '/admin/api/me'), ('OPTIONS', '/admin/api/me'),
                         ('GET', '/admin/api/me/'), ('GET', '/admin//api/me'),
                         ('GET', '/admin/api/%6de'), ('GET', '/admin/api/me;x=1'),
                         ('GET', '/admin/api/../api/me'), ('GET', '/admin')]:
        check('native route boundary: ' + method + ' ' + path, 403,
              GATEWAY + path, tokens['admin'], method, layer='gateway-policy' if method != 'HEAD' else 'gateway-no-body')
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
               'X-Finlab-Roles': 'admin'}
    for prefix, layer in [('/access', 'finaccess'), ('/admin', 'finadmin')]:
        body = check(layer + ': signed identity wins over forged headers', 200,
                     GATEWAY + prefix + '/api/me', tokens['alice'], layer=layer, extra_headers=spoofed)
        record(layer + ': subject and issuer come from JWT',
               body.get('sub', body.get('subject')) == claims(tokens['alice'])['sub']
               and body.get('issuer') == ISSUER)


def native_acl_checks(tokens):
    """실제 관리 API의 배포 상태와 기본 ACL이 차단한 요청의 로그를 확인합니다."""
    spec = importlib.util.spec_from_file_location('api7_setup', ROOT / 'scripts/setup-api7.py')
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    group = json.loads((setup.PRIVATE / 'group.json').read_text())['id']
    _, routes = setup.desired()
    for name, wanted in routes:
        status, response = setup.call('GET', '/apisix/admin/routes/' + name + '?gateway_group_id=' + group)
        actual = response.get('value', {})
        fields = ('paths', 'methods', 'vars', 'priority', 'service_id')
        same = all(actual.get(k) == wanted.get(k) for k in fields)
        for plugin in ('acl', 'fault-injection', 'serverless-post-function'):
            same = same and actual.get('plugins', {}).get(plugin) == wanted['plugins'].get(plugin)
        record('deployed native policy: ' + name, status == 200 and same)
    check('native route: query string does not change permission', 200,
          GATEWAY + '/admin/api/me?display=short', tokens['alice'], layer='finadmin')
    spoofed = {'X-Userinfo': b64(json.dumps({'sub': 'forged', 'resource_access': {
        'finadmin-api': {'roles': ['admin']}}}).encode()), 'X-Access-Token': tokens['admin']}
    check('native ACL: external userinfo and access-token headers cannot grant admin', 403,
          GATEWAY + '/admin/api/admin/summary', tokens['alice'], extra_headers=spoofed, layer='gateway-policy')
    record('native ACL: role denial came from the built-in ACL', CHECKS[-1]['nativeAclDenied'])
    # 무작위 ID라 이번 요청의 로그만 찾을 수 있습니다. 역할에서 막혀 계좌를 생성하지 않습니다.
    path = '/api/companies/' + str(uuid.uuid4()) + '/accounts'
    check('native ACL: unique forbidden account request', 403,
          GATEWAY + '/access' + path, tokens['alice'], 'POST', layer='gateway-policy')
    deadline, evidence = time.monotonic() + 5, None
    while evidence is None and time.monotonic() < deadline:
        output = docker('logs', '--tail', '100', '--since', STARTED.isoformat(), GATEWAY_CONTAINER)
        evidence = next((line for line in output.splitlines() if path in line
                         and re.search(r' 403 [0-9.]+ -\s*$', line)), None)
        if evidence is None:
            time.sleep(0.2)
    record('native ACL: denied request never reached upstream', evidence is not None,
           path=path, upstreamStatus='-' if evidence else None)


def ldap_group_checks(values):
    # 기존 스크립트의 membership 명령을 재사용합니다. main()은 호출하지 않습니다.
    # 기존 main()은 모의 이체까지 실행하므로 이번 검사에 불필요한 데이터가 생기기 때문입니다.
    spec = importlib.util.spec_from_file_location('verify_ldap_helpers', ROOT / 'scripts/verify-ldap.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for name, (password_key, _, group) in LDAP_USERS.items():
        token = login(name, values[password_key])
        mapping = json.loads((ROOT / 'infra/keycloak/ldap-federation.json').read_text())['groupRoles'][group]
        for app, roles in mapping.items():
            record(name + ': LDAP group becomes ' + app + ' roles',
                   set(roles).issubset(set(claims(token).get('resource_access', {}).get(app, {}).get('roles', []))))
        check(name + ': LDAP identity reads FinAdmin profile', 200,
              GATEWAY + '/admin/api/me', token, layer='finadmin')
    original = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    endpoints = [('gateway admin', GATEWAY + '/admin/api/admin/summary', 'finadmin'),
                 ('direct admin', ADMIN + '/api/admin/summary', 'finadmin')]
    for label, url, layer in endpoints:
        check(label + ': LDAP admin before removal', 200, url, original, layer=layer)
    # finally 범위 안에서 변경해야 변경 직후 오류가 나도 복원을 시도합니다.
    try:
        helper.change_membership('delete')
        reduced = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
        record('LDAP removal: new token loses admin in both APIs', all(
            'admin' not in claims(reduced).get('resource_access', {}).get(api, {}).get('roles', [])
            for api in APIS))
        for label, url, layer in endpoints:
            check(label + ': removed member new token denied', 403, url, reduced,
                  layer='gateway-policy' if label.startswith('gateway') else layer)
            check(label + ': old unexpired token still allowed', 200, url, original, layer=layer)
    finally:
        helper.change_membership('add')
    restored = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    record('LDAP restoration: new token restores admin in both APIs', all(
        'admin' in claims(restored).get('resource_access', {}).get(api, {}).get('roles', [])
        for api in APIS))
    for label, url, layer in endpoints:
        check(label + ': restored member new token allowed', 200, url, restored, layer=layer)


def access_log_checks(token):
    # 로그에 고유한 경로를 남겨 이전 실행의 403을 이번 결과로 잘못 재사용하지 않습니다.
    unique = '/api/verify-denied-' + uuid.uuid4().hex
    check('log evidence: unique unlisted admin route denied', 403,
          GATEWAY + '/admin' + unique, token, layer='gateway-policy')
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
    parser = argparse.ArgumentParser(description=__doc__)
    # 이전 명령도 동작하지만, 이제 옵션 없이도 Enterprise만 검사합니다.
    parser.add_argument('--enterprise', action='store_true', help=argparse.SUPPRESS)
    parser.parse_args()
    completed = False
    config_paths = ('compose.yaml', 'compose.api7.yaml', 'infra/api7/config.yaml',
                    'infra/keycloak/finlab-realm.json', 'scripts/setup-api7.py',
                    'infra/gateway/enterprise-identity.lua', 'infra/gateway/token-shape.lua',
                    'infra/gateway/policies.json')
    configuration = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in config_paths}
    try:
        values = read_values()
        for url in (ISSUER + '/.well-known/openid-configuration', GATEWAY + '/',
                    ACCESS + '/api/hello', ADMIN + '/api/hello'):
            wait_ready(url)
        print('준비된 로컬 환경에서 PKCE 로그인과 Gateway RBAC 검증을 시작합니다.', flush=True)
        tokens = {name: login(name, values['LAB_' + name.upper() + '_PASSWORD'])
                  for name in ('alice', 'bob', 'admin', 'outsider')}
        native_acl_checks(tokens)
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
                  'notCoveredHere': ['Enterprise의 동일 키·잘못된 issuer 독립 검사 미실행. 과거 OSS 격리 검사와 구분.'],
                  'note': '실제 PKCE 로그인. 업무 데이터 생성 없음. LDAP 그룹은 finally에서 복원. 비밀번호·토큰 원문 없음.'}
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'완료: {len(CHECKS)}개 검증. {REPORT_PATH.name}에 비밀값 없는 결과를 저장했습니다.')


if __name__ == '__main__':
    main()
