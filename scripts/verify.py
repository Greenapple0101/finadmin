#!/usr/bin/env python3
"""실제 Keycloak 로그인과 HTTP 호출로 전체 인증 흐름을 검증합니다. Python 표준 도구만 사용합니다."""
import base64
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from http.cookiejar import CookieJar, DefaultCookiePolicy
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
ISSUER = 'http://localhost:18080/realms/finlab'
GATEWAY = 'http://localhost:18090'
ACCESS = 'http://localhost:18082'
ADMIN = 'http://localhost:18083'
REDIRECT = GATEWAY + '/'
REPORT = []


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def claims(token):
    # 테스트에서 표식과 만료 시각을 읽을 뿐입니다. 이 함수로 인증 성공 여부를 판단하지 않습니다.
    payload = token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))


def http(url, token=None, method='GET', body=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read().decode()
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw
        return response.status, value, dict(response.headers)


def check(name, expected, url, token=None, method='GET', body=None):
    status, value, headers = http(url, token, method, body)
    # 토큰·비밀번호는 성공/실패 로그와 결과 문서에 넣지 않습니다.
    if status != expected:
        raise AssertionError(f'{name}: expected HTTP {expected}, got {status}')
    REPORT.append({'case': name, 'expected': expected, 'actual': status})
    print(f'PASS {status} {name}', flush=True)
    return value


def wait_ready(url):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            if http(url)[0] == 200:
                return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(1)
    raise RuntimeError('실습 서버 준비 시간 초과: ' + url)


class LoginForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.hidden = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'form' and values.get('id') == 'kc-form-login':
            self.action = values.get('action')
        if tag == 'input' and values.get('type') == 'hidden' and values.get('name'):
            self.hidden[values['name']] = values.get('value', '')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalhostCookiePolicy(DefaultCookiePolicy):
    def return_ok_secure(self, cookie, request):
        # 브라우저는 localhost를 특별 취급하지만 Python CookieJar는 HTTP의 Secure 쿠키를 보내지 않습니다.
        # 이 로컬 실습 주소 하나에서만 브라우저와 같은 동작을 재현합니다. 외부 주소에는 적용하지 않습니다.
        target = urllib.parse.urlsplit(request.full_url)
        if target.scheme == 'http' and target.hostname == 'localhost' and target.port == 18080:
            return True
        return super().return_ok_secure(cookie, request)


def login(username, password, client_id='finlab-web'):
    # 사용자 비밀번호를 token endpoint에 보내는 Password Grant가 아닙니다.
    # 브라우저처럼 Keycloak 로그인 폼을 제출한 뒤 Authorization Code + PKCE로 토큰을 받습니다.
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    jar = CookieJar(policy=LocalhostCookiePolicy())
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    query = urllib.parse.urlencode({'client_id': client_id, 'redirect_uri': REDIRECT,
        'response_type': 'code', 'scope': 'openid', 'state': state,
        'code_challenge': b64(hashlib.sha256(verifier.encode()).digest()),
        'code_challenge_method': 'S256', 'prompt': 'login'})
    with opener.open(ISSUER + '/protocol/openid-connect/auth?' + query, timeout=15) as response:
        form = LoginForm()
        form.feed(response.read().decode())
    if not form.action or urllib.parse.urlsplit(form.action).netloc != 'localhost:18080':
        raise RuntimeError('예상한 Keycloak 로그인 화면을 찾지 못했습니다.')
    form.hidden.update(username=username, password=password)
    submit = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
    request = urllib.request.Request(form.action, data=urllib.parse.urlencode(form.hidden).encode())
    try:
        with submit.open(request, timeout=15) as response:
            raise RuntimeError('Keycloak 로그인 후 예상한 리다이렉트가 없습니다: ' + username)
    except urllib.error.HTTPError as error:
        if error.code not in (302, 303):
            raise RuntimeError('Keycloak 로그인 실패: ' + username + ', HTTP ' + str(error.code)) from None
        location = error.headers['Location']
        error.close()
    target = urllib.parse.urlsplit(location)
    callback = urllib.parse.parse_qs(target.query)
    if target.scheme + '://' + target.netloc + target.path != REDIRECT or callback.get('state') != [state]:
        raise RuntimeError('로그인 응답 주소 또는 state 불일치')
    if callback.get('iss') != [ISSUER] or 'code' not in callback:
        raise RuntimeError('로그인 응답 발급자 또는 코드 불일치')
    exchange = urllib.request.Request(ISSUER + '/protocol/openid-connect/token',
        data=urllib.parse.urlencode({'grant_type': 'authorization_code', 'client_id': client_id,
            'redirect_uri': REDIRECT, 'code': callback['code'][0], 'code_verifier': verifier}).encode())
    with urllib.request.urlopen(exchange, timeout=15) as response:
        return json.load(response)['access_token']


def sql(statement):
    # 이번 실습 compose의 app-db에만 테스트용 회사·계좌를 준비합니다.
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'app-db', 'psql',
        '-U', 'finaccess', '-d', 'finaccess', '-v', 'ON_ERROR_STOP=1', '-At'],
        input=statement, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError('실습 DB 준비/조회에 실패했습니다: ' + result.stderr)
    return result.stdout.strip()


def prepare_clients(values):
    # 이번 실습의 finlab-* 공개 클라이언트를 저장소의 설정과 맞춥니다.
    # basic scope가 sub(사용자 식별자)를 넣습니다. 역할 mapper와 audience만 넣는 것으로는 부족합니다.
    # 관리용 admin-cli 토큰은 설정 작업에만 쓰고 저장하지 않습니다. 사용자 로그인은 계속 PKCE입니다.
    request = urllib.request.Request('http://localhost:18080/realms/master/protocol/openid-connect/token',
        data=urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli',
            'username': 'bootstrap-admin', 'password': values['KEYCLOAK_ADMIN_PASSWORD']}).encode())
    with urllib.request.urlopen(request, timeout=15) as response:
        management_token = json.load(response)['access_token']
    status, realm_scopes, _ = http('http://localhost:18080/admin/realms/finlab/client-scopes', management_token)
    assert status == 200
    scope_ids = {scope['name']: scope['id'] for scope in realm_scopes}
    clients = json.loads((ROOT / 'infra/keycloak/finlab-realm.json').read_text())['clients']
    for client in clients:
        if not client['clientId'].startswith('finlab-'):
            continue
        url = 'http://localhost:18080/admin/realms/finlab/clients'
        status, found, _ = http(url + '?' + urllib.parse.urlencode({'clientId': client['clientId']}), management_token)
        assert status == 200
        if not found:
            status, _, _ = http(url, management_token, 'POST', client)
            assert status == 201
            status, found, _ = http(url + '?' + urllib.parse.urlencode({'clientId': client['clientId']}), management_token)
            assert status == 200
        else:
            status, _, _ = http(url + '/' + found[0]['id'], management_token, 'PUT', client)
            assert status == 204
        # 이미 있는 Client의 기본 scope 연결은 Client 본문 수정과 별도 API입니다.
        for scope in client['defaultClientScopes']:
            status, _, _ = http(url + '/' + found[0]['id'] + '/default-client-scopes/' + scope_ids[scope],
                                management_token, 'PUT')
            assert status == 204


def save_tokens(tokens):
    # 사용자가 요청한 로컬 문서에만 실제 토큰을 기록합니다. Git 문서에는 넣지 않습니다.
    path = Path.home() / 'Desktop' / 'finadmin-local-secrets.md'
    previous = path.read_text()
    start, end = '<!-- finlab-tokens:start -->', '<!-- finlab-tokens:end -->'
    lines = [start, '## 실제 발급한 실습용 액세스 토큰', '',
             '토큰은 기본 5분 후 만료됩니다. 갱신하려면 `python3 scripts/verify.py`를 다시 실행합니다.',
             '검증 실행은 모의 이체 데이터도 추가합니다. 토큰을 GitHub나 채팅에 붙이지 마세요.', '']
    for name, token in tokens.items():
        data = claims(token)
        expiry = datetime.fromtimestamp(data['exp'], timezone.utc).isoformat()
        lines += ['### ' + name, '- 만료 시각(UTC): ' + expiry,
                  '- 대상: ' + json.dumps(data['aud']), '', '```text', token, '```', '']
    lines.append(end)
    block = '\n'.join(lines)
    if start in previous and end in previous:
        before, rest = previous.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before + block + after
    else:
        updated = previous.rstrip() + '\n\n' + block + '\n'
    fd = os.open(path, os.O_WRONLY | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(updated)


def main():
    values = dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                  if line and not line.startswith('#') and '=' in line)
    for url in (ISSUER + '/.well-known/openid-configuration', ACCESS + '/api/hello',
                ADMIN + '/api/hello', GATEWAY + '/'):
        wait_ready(url)
    print('서버 준비 완료. Authorization Code + PKCE로 사용자별 로그인합니다.', flush=True)
    prepare_clients(values)
    tokens = {name: login(name, values['LAB_' + name.upper() + '_PASSWORD'])
              for name in ('alice', 'bob', 'admin', 'outsider')}
    short_lived = login('admin', values['LAB_ADMIN_PASSWORD'], 'finlab-expiry-test')
    future_token = login('admin', values['LAB_ADMIN_PASSWORD'], 'finlab-not-before-test')
    assert claims(future_token)['nbf'] == 4102444800
    access_only = login('admin', values['LAB_ADMIN_PASSWORD'], 'finlab-access-test')
    assert claims(access_only)['aud'] == 'finaccess-api' or claims(access_only)['aud'] == ['finaccess-api']
    save_tokens(tokens)

    for name, base, path in [('gateway-admin', GATEWAY + '/admin', '/api/admin/summary'),
                             ('direct-admin', ADMIN, '/api/admin/summary'),
                             ('gateway-access', GATEWAY + '/access', '/api/me'),
                             ('direct-access', ACCESS, '/api/me')]:
        check(name + ': no token', 401, base + path)
        token = tokens['admin']
        pieces = token.split('.')
        payload = claims(token)
        payload['sub'] = 'forged-user'
        pieces[1] = b64(json.dumps(payload).encode())
        check(name + ': tampered token', 401, base + path, '.'.join(pieces))
        check(name + ': signed future nbf', 401, base + path, future_token)
        identity = check(name + ': valid admin', 200, base + path, token)
        if path == '/api/me':
            assert identity.get('sub', identity.get('subject')) == claims(token)['sub']
            assert identity['issuer'] == ISSUER
    for base in (GATEWAY + '/admin', ADMIN):
        check('ordinary user cannot read admin at ' + base, 403, base + '/api/admin/summary', tokens['alice'])
        me = check('ordinary user identity at ' + base, 200, base + '/api/me', tokens['alice'])
        assert me['subject'] == claims(tokens['alice'])['sub']
    for base in (GATEWAY + '/access', ACCESS):
        check('access-only audience accepted at ' + base, 200, base + '/api/me', access_only)
    check('gateway rejects other API audience', 403, GATEWAY + '/admin/api/admin/summary', access_only)
    check('backend rejects other API audience independently', 401, ADMIN + '/api/admin/summary', access_only)

    company_a = '20000000-0000-4000-8000-000000000001'
    company_b = '20000000-0000-4000-8000-000000000002'
    sql(f"INSERT INTO companies(id,name) VALUES ('{company_a}','FinLab A'),('{company_b}','FinLab B') ON CONFLICT DO NOTHING;")
    users = {}
    for index, name in enumerate(tokens, 1):
        subject = claims(tokens[name])['sub']
        uuid.UUID(subject)  # SQL로 넣기 전에 Keycloak의 UUID 형식인지 검사합니다.
        company = company_b if name == 'outsider' else company_a
        user_id = f'30000000-0000-4000-8000-{index:012d}'
        sql(f"INSERT INTO app_users(id,company_id,identity_issuer,identity_subject) VALUES ('{user_id}','{company}','{ISSUER}','{subject}') ON CONFLICT DO NOTHING;")
        users[name] = user_id
    for base in (GATEWAY + '/access', ACCESS):
        check('own company readable at ' + base, 200, base + '/api/companies/' + company_a, tokens['alice'])
        check('other company forbidden at ' + base, 403, base + '/api/companies/' + company_b, tokens['alice'])
    source = check('admin opens A account', 201, GATEWAY + '/access/api/companies/' + company_a + '/accounts', tokens['admin'], 'POST')['id']
    destination = check('admin opens B account', 201, GATEWAY + '/access/api/companies/' + company_b + '/accounts', tokens['admin'], 'POST')['id']
    sql(f"UPDATE accounts SET balance_won=10000 WHERE id='{uuid.UUID(source)}';")
    transfer_body = {'sourceAccountId': source, 'destinationAccountId': destination, 'amountWon': 1000}
    check('cannot spoof requester in body', 400, GATEWAY + '/access/api/transfers', tokens['alice'], 'POST', {**transfer_body, 'requesterId': users['admin']})
    check('other-company requester blocked', 403, GATEWAY + '/access/api/transfers', tokens['outsider'], 'POST', transfer_body)
    transfer = check('request identity comes from JWT', 201, GATEWAY + '/access/api/transfers', tokens['alice'], 'POST', transfer_body)
    assert transfer['requesterId'] == users['alice']
    url = GATEWAY + '/access/api/transfers/' + transfer['id']
    check('ordinary user cannot approve', 403, url + '/approve', tokens['alice'], 'POST')
    check('cannot spoof reviewer in body', 400, url + '/approve', tokens['bob'], 'POST', {'actorId': users['admin']})
    approved = check('approver accepts transfer', 200, url + '/approve', tokens['bob'], 'POST')
    assert approved['reviewerId'] == users['bob']
    completed = check('approver executes transfer', 200, url + '/execute', tokens['bob'], 'POST')
    assert completed['executedBy'] == users['bob'] and completed['status'] == 'COMPLETED'
    check('second execution blocked', 409, url + '/execute', tokens['bob'], 'POST')
    balances = sql(f"SELECT balance_won FROM accounts WHERE id='{source}' UNION ALL SELECT balance_won FROM accounts WHERE id='{destination}';")
    assert balances.splitlines() == ['9000', '1000'], balances
    self_transfer = check('admin requests own transfer', 201, GATEWAY + '/access/api/transfers', tokens['admin'], 'POST', transfer_body)
    check('admin cannot approve own request', 403, GATEWAY + '/access/api/transfers/' + self_transfer['id'] + '/approve', tokens['admin'], 'POST')
    other = check('another request for rejection', 201, GATEWAY + '/access/api/transfers', tokens['alice'], 'POST', transfer_body)
    rejected = check('approver rejects transfer', 200, GATEWAY + '/access/api/transfers/' + other['id'] + '/reject', tokens['bob'], 'POST')
    assert rejected['status'] == 'REJECTED'
    # Spring은 기본 60초의 시계 오차를 허용합니다. 실제 서명된 짧은 토큰으로 그 시간도 넘겨 검사합니다.
    deadline = claims(short_lived)['exp'] + 65
    if time.time() < deadline:
        print('실제 만료 토큰 검증: Spring 시계 오차 허용 시간이 지날 때까지 대기합니다.', flush=True)
    while time.time() < deadline:
        time.sleep(min(5, deadline - time.time()))
    for name, base, path in [('gateway-admin', GATEWAY + '/admin', '/api/admin/summary'),
                             ('direct-admin', ADMIN, '/api/admin/summary'),
                             ('gateway-access', GATEWAY + '/access', '/api/me'),
                             ('direct-access', ACCESS, '/api/me')]:
        check(name + ': genuinely signed expired token', 401, base + path, short_lived)
    directory = ROOT / '.local'
    directory.mkdir(exist_ok=True)
    report = {'verifiedAt': datetime.now(timezone.utc).isoformat(), 'checks': REPORT,
              'balanceCheck': {'source': 9000, 'destination': 1000},
              'note': '실제 Keycloak 코드+PKCE 로그인. 토큰·비밀번호는 이 보고서에 포함하지 않음.'}
    (directory / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'완료: HTTP 검증 {len(REPORT)}개와 실제 DB 잔액 확인. 토큰은 데스크탑 MD에만 기록했습니다.', flush=True)


if __name__ == '__main__':
    main()
