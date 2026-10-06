#!/usr/bin/env python3
"""실제 APISIX 정책을 별도 Docker 네트워크에서 검증합니다.

준비: Docker, Python 3.10+, cryptography (`python3 -m pip install cryptography`).
실행: python3 scripts/test-gateway-fixtures.py
결과: .local/gateway-fixture-verification.json (토큰·개인 키 없음)

기존 compose, Keycloak, LDAP, 업무 DB는 건드리지 않습니다. 실제 apisix.yaml의
Discovery/Upstream 주소만 시험 서버로 바꾸며, JWT 검증·Lua·역할표·실행 phase는
그대로 사용합니다. 같은 개인 키로 정상 토큰과 잘못된 issuer 토큰을 각각 서명하여
'내용을 고쳐 서명부터 깨진 토큰'과 '발급자만 잘못된 토큰'을 구분합니다.

공식 실행 순서 근거 (검사에는 아래 Docker 이미지의 실제 코드가 실행됩니다):
https://github.com/apache/apisix/blob/3.18.0/apisix/plugins/openid-connect.lua
https://github.com/apache/apisix/blob/3.18.0/apisix/plugins/serverless-post-function.lua
"""
import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
except ImportError:
    raise SystemExit('cryptography가 필요합니다: python3 -m pip install cryptography')

ROOT = Path(__file__).resolve().parents[1]
ISSUER = 'http://localhost:18080/realms/finlab'
IMAGE = 'apache/apisix:3.18.0-debian'
STUB_IMAGE = 'python:3.12-slim'


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError('Docker 작업 실패: ' + result.stderr.strip()[:1200])
    return result.stdout.strip()


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def integer64(number):
    return b64(number.to_bytes((number.bit_length() + 7) // 8, 'big'))


def token(key, claims):
    header = {'alg': 'RS256', 'typ': 'JWT', 'kid': 'fixture-key'}
    signing_input = '.'.join(b64(json.dumps(part, separators=(',', ':')).encode())
                             for part in (header, claims)).encode()
    return signing_input.decode() + '.' + b64(key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))


def request(base, path, bearer=None, method='GET', extra=None):
    headers = dict(extra or {})
    if bearer is not None:
        headers['Authorization'] = 'Bearer ' + bearer
    req = urllib.request.Request(base + path, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read()
        # 실패 응답은 인증 라이브러리의 진단 문구를 포함할 수 있어 저장하지 않습니다.
        value = json.loads(body) if response.status == 200 and body else None
        return response.status, value, response.headers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0, help='0이면 Docker가 비어 있는 loopback 포트를 고릅니다.')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('port는 0부터 65535 사이여야 합니다.')

    # 개인 키는 Python 메모리에만 존재하며 임시 디렉터리에도 쓰지 않습니다.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    source = ROOT / 'infra/apisix/apisix.yaml'
    main_config = ROOT / 'infra/apisix/config.yaml'
    source_bytes = source.read_bytes()
    runtime_bytes = main_config.read_bytes()
    config = json.loads('\n'.join(line for line in source_bytes.decode().splitlines()
                                  if not line.lstrip().startswith('#')))
    fixture_config = copy.deepcopy(config)
    for route in fixture_config['routes']:
        oidc = route.get('plugins', {}).get('openid-connect')
        if oidc:
            assert oidc['claim_validator']['issuer']['valid_issuers'] == [ISSUER]
            oidc['discovery'] = 'http://fixture:8080/discovery'
        route['upstream']['nodes'] = {'fixture:8080': 1}
    # 실제 정책과 다른 것은 연결 주소뿐인지 역변환해서 확인합니다.
    restored = copy.deepcopy(fixture_config)
    for original, changed in zip(config['routes'], restored['routes']):
        changed['upstream']['nodes'] = original['upstream']['nodes']
        if 'openid-connect' in original.get('plugins', {}):
            changed['plugins']['openid-connect']['discovery'] = original['plugins']['openid-connect']['discovery']
    assert restored == config

    suffix = uuid.uuid4().hex[:12]
    network, stub, gateway = [f'finlab-fixture-{kind}-{suffix}' for kind in ('net', 'stub', 'gateway')]
    report = {
        'executedAt': datetime.now(timezone.utc).isoformat(),
        'kind': 'isolated APISIX integration with synthetic signed JWT and fixture upstream',
        'notLiveKeycloakOrBusinessFlow': True,
        'sourceSha256': hashlib.sha256(source_bytes).hexdigest(),
        'runtimeConfigSha256': hashlib.sha256(runtime_bytes).hexdigest(),
        'overrides': ['OIDC discovery URL', 'upstream node addresses'],
        'image': IMAGE,
        'checks': [],
    }
    cleanup_failures = []
    failure = None
    with tempfile.TemporaryDirectory(prefix='finlab-gateway-fixtures-') as directory:
        temp = Path(directory)
        (temp / 'config.yaml').write_bytes(runtime_bytes)
        (temp / 'apisix.yaml').write_text(json.dumps(fixture_config, ensure_ascii=False, indent=2) + '\n#END\n')
        (temp / 'jwks.json').write_text(json.dumps({'keys': [{'kty': 'RSA', 'kid': 'fixture-key',
            'use': 'sig', 'alg': 'RS256', 'n': integer64(public.n), 'e': integer64(public.e)}]}))
        (temp / 'discovery.json').write_text(json.dumps({'issuer': ISSUER,
            'jwks_uri': 'http://fixture:8080/jwks', 'authorization_endpoint': ISSUER + '/auth',
            'token_endpoint': 'http://fixture:8080/token', 'id_token_signing_alg_values_supported': ['RS256']}))
        shutil.copy(ROOT / 'scripts/gateway_fixture_server.py', temp / 'server.py')
        try:
            docker('network', 'create', network)
            docker('run', '-d', '--name', stub, '--network', network, '--network-alias', 'fixture',
                   '--mount', f'type=bind,src={temp},dst=/fixture,readonly', STUB_IMAGE,
                   'python', '/fixture/server.py')
            port = str(args.port) if args.port else ''
            docker('run', '-d', '--name', gateway, '--network', network, '-p', f'127.0.0.1:{port}:9080',
                   '--mount', f'type=bind,src={temp}/config.yaml,dst=/usr/local/apisix/conf/config.yaml,readonly',
                   '--mount', f'type=bind,src={temp}/apisix.yaml,dst=/usr/local/apisix/conf/apisix.yaml,readonly', IMAGE)
            report['imageId'] = docker('inspect', gateway, '--format', '{{.Image}}')
            actual_port = docker('port', gateway, '9080/tcp').split(':')[-1]
            base = 'http://127.0.0.1:' + actual_port
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                try:
                    if request(base, '/fixture-ready')[0] == 200:
                        break
                except (OSError, urllib.error.URLError):
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError('격리 APISIX 준비 시간 초과')

            def claims(client='finadmin-api', roles=None):
                now = int(time.time())
                return {'iss': ISSUER, 'sub': 'fixture-user', 'aud': client, 'iat': now - 10,
                        'nbf': now - 10, 'exp': now + 300,
                        'resource_access': {client: {'roles': roles if roles is not None else ['admin']}}}

            def check(name, expected, payload=None, path='/admin/api/admin/summary', method='GET',
                      signing_key=key, extra=None, anonymous=False):
                case = f'case-{len(report["checks"]) + 1:03d}'
                headers = dict(extra or {})
                headers['X-Fixture-Case'] = case
                signed = None if anonymous else token(signing_key, payload if payload is not None else claims())
                status, body, returned_headers = request(base, path, signed, method, headers)
                reached = returned_headers.get('X-Fixture-Upstream') == 'reached'
                item = {'caseId': case, 'name': name, 'method': method, 'path': path,
                        'expected': expected, 'actual': status, 'upstreamReached': reached,
                        'rejectedBy': returned_headers.get('X-Finlab-Rejected-By'),
                        'passed': status == expected and reached == (expected == 200)}
                report['checks'].append(item)
                print(f'{"PASS" if item["passed"] else "FAIL"} {status} {name}', flush=True)
                # 한 실패 때문에 뒤의 독립적인 검사를 생략하지 않습니다. 마지막에 전체 실패를 알립니다.
                return body

            check('valid baseline signed by trusted fixture key', 200)
            check('missing bearer token', 401, anonymous=True)
            changed = claims(); changed['iss'] = 'https://other-issuer.example/realms/finlab'
            check('same trusted signing key but wrong issuer', 401, changed)
            for field in ('iss', 'exp', 'sub'):
                changed = claims(); changed.pop(field)
                check('missing ' + field + ' with valid signature', 401, changed)
            for field, value in (('sub', ''), ('sub', 123), ('exp', 'tomorrow'),
                                 ('exp', int(time.time()) - 300), ('nbf', int(time.time()) + 300),
                                 ('nbf', 'tomorrow')):
                changed = claims(); changed[field] = value
                check('invalid ' + field + ' ' + str(value), 401, changed)
            changed = claims(); changed['aud'] = 'finaccess-api'
            check('valid signature with wrong audience', 403, changed)
            changed = claims(); changed.pop('aud')
            check('valid signature without audience', 401, changed)
            check('different private key with same kid', 401, signing_key=wrong_key)
            for malformed in (None, {}, {'finaccess-api': {'roles': ['admin']}},
                              {'finadmin-api': {'roles': []}}, {'finadmin-api': {'roles': 'admin'}},
                              {'finadmin-api': {'roles': {'0': 'admin'}}},
                              {'finadmin-api': {'roles': ['admin', 123]}}):
                changed = claims(); changed['resource_access'] = malformed
                check('missing/wrong/malformed own-client roles ' + str(malformed), 403, changed)
            changed = claims(); changed.pop('resource_access'); changed['realm_access'] = {'roles': ['admin']}
            check('realm admin alone does not grant client admin', 403, changed)
            check('ordinary finadmin user cannot read admin summary', 403, claims(roles=['user']))
            check('ordinary finadmin user can read me', 200, claims(roles=['user']), path='/admin/api/me')

            # 각 실제 권한표의 모든 허용 역할을 하나씩 검증합니다. 모의 Upstream만 호출하므로 DB는 바뀌지 않습니다.
            policies = json.loads((ROOT / 'infra/gateway/policies.json').read_text())
            for app, policy in policies.items():
                for rule in policy['rules']:
                    path = policy['prefix'] + rule['path'].replace('{id}', 'fixture-id')
                    for role in rule['roles']:
                        check(app + ' ' + rule['method'] + ' ' + rule['path'] + ' role=' + role,
                              200, claims(policy['audience'], [role]), path=path, method=rule['method'])
                    check(app + ' forbidden role on ' + rule['path'], 403,
                          claims(policy['audience'], ['not-allowed']), path=path, method=rule['method'])
            for method, path in [('POST', '/admin/api/admin/summary'), ('HEAD', '/admin/api/me'),
                                 ('OPTIONS', '/admin/api/me'), ('GET', '/admin/api/unknown'),
                                 ('GET', '/admin/api/admin/summary/extra'), ('GET', '/admin/api/me/'),
                                 ('GET', '/admin//api/me'), ('GET', '/admin/api/%6de'),
                                 ('GET', '/admin/api/me;x=1'), ('GET', '/admin'),
                                 ('GET', '/admin/api/../api/me')]:
                check('unlisted method/path ' + method + ' ' + path, 403, path=path, method=method)

            spoofed = {name: 'forged-value' for name in ('X-Finlab-Subject', 'X-Finlab-Issuer',
                       'X-Finlab-Roles', 'X-Userinfo', 'X-ID-Token', 'X-Access-Token',
                       'X-Refresh-Token', 'X-Raw-ID-Token')}
            body = check('legacy receives replacement identity and no bearer token', 200,
                         claims('finlegacy-api', ['reader']), path='/legacy/api/reports', extra=spoofed)
            assert body['subject'] == 'fixture-user' and body['issuer'] == ISSUER
            assert not body['authorizationPresent'] and not body['roleHeaderPresent'] and not body['extraIdentityHeaderPresent']
            body = check('Spring upstream receives bearer but no forged identity headers', 200,
                         path='/admin/api/me', extra=spoofed)
            assert body['authorizationPresent'] and body['subject'] is None and body['issuer'] is None
            assert not body['roleHeaderPresent'] and not body['extraIdentityHeaderPresent']
            # 상태 코드만 믿지 않고 Upstream이 실제로 받은 case 목록과 대조합니다.
            stats = json.loads(docker('exec', stub, 'python', '-c',
                'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/fixture-stats").read().decode())'))
            received = {entry['case'] for entry in stats if entry['case']}
            expected_received = {item['caseId'] for item in report['checks'] if item['expected'] == 200}
            report['upstreamRequestRecordsMatched'] = received == expected_received
            report['upstreamReceivedCaseCount'] = len(received)
            failed = [item['name'] for item in report['checks'] if not item['passed']]
            if received != expected_received:
                failed.append('Upstream 도착 목록이 허용 예상 목록과 일치하지 않음')
            if failed:
                raise AssertionError('실패한 검사: ' + ', '.join(failed))
        except Exception as error:
            # 예외에 토큰/응답 원문을 붙이지 않습니다.
            failure = f'{type(error).__name__}: {error}'
            report['failure'] = failure
        finally:
            for container in (gateway, stub):
                docker('rm', '-f', container, check=False)
                if docker('ps', '-a', '-q', '--filter', 'name=^/' + container + '$'):
                    cleanup_failures.append(container)
            docker('network', 'rm', network, check=False)
            if docker('network', 'ls', '-q', '--filter', 'name=^' + network + '$'):
                cleanup_failures.append(network)
    report['temporaryResourcesRemoved'] = not cleanup_failures
    report['sourceUnchangedDuringRun'] = source.read_bytes() == source_bytes and main_config.read_bytes() == runtime_bytes
    report['passed'] = failure is None and not cleanup_failures
    destination = ROOT / '.local/gateway-fixture-verification.json'
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(report["checks"])} checks; passed={report["passed"]}; report={destination}', flush=True)
    if failure or cleanup_failures:
        raise SystemExit(failure or '임시 Docker 자원을 정리하지 못했습니다.')


if __name__ == '__main__':
    main()
