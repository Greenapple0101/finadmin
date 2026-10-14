#!/usr/bin/env python3
"""기존 oauth-lab의 업무 역할을 USER와 ADMIN 두 개로 맞춥니다.

Realm import는 이미 존재하는 Realm을 갱신하지 않으므로 기존 실습 환경에서 한 번 실행합니다.
Keycloak 관리용 설정 명령이며, 사용자의 앱 로그인은 계속 Authorization Code + PKCE입니다.
API7의 Route나 인증 설정은 바꾸지 않습니다.
"""
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
credentials = json.loads((ROOT / '.local/credentials.json').read_text())
base = 'http://localhost:18180'

# 설정용 관리 계정으로 Admin API를 호출합니다. 이 비밀번호를 프런트에 넣지 않습니다.
body = urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli',
    'username': 'bootstrap-admin', 'password': credentials['bootstrap-admin']}).encode()
request = urllib.request.Request(base + '/realms/master/protocol/openid-connect/token', data=body)
with urllib.request.urlopen(request) as response:
    token = json.load(response)['access_token']

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + '/admin/realms/oauth-lab' + path,
        data=data, method=method, headers={'Authorization': 'Bearer ' + token,
                                        'Content-Type': 'application/json'})
    with urllib.request.urlopen(request) as response:
        text = response.read()
        return json.loads(text) if text else None

clients = call('GET', '/clients?clientId=oauth-api')
if len(clients) != 1:
    raise SystemExit('oauth-api Client가 정확히 하나 있어야 합니다.')
client = clients[0]['id']
role_path = '/clients/' + client + '/roles'
existing = {role['name']: role for role in call('GET', role_path)}
for name in ('USER', 'ADMIN'):
    if name not in existing:
        call('POST', role_path, {'name': name})

roles = {role['name']: role for role in call('GET', role_path)}
for username, role in [('alice', 'USER'), ('admin', 'ADMIN')]:
    users = call('GET', '/users?username=' + username + '&exact=true')
    if len(users) != 1:
        raise SystemExit(username + ' 계정이 정확히 하나 있어야 합니다.')
    path = '/users/' + users[0]['id'] + '/role-mappings/clients/' + client
    previous = call('GET', path)
    # 먼저 새 역할을 연결한 뒤 이 실습에서 관리하던 이전 역할 연결만 제거합니다.
    call('POST', path, [roles[role]])
    remove = [r for r in previous if r['name'] in ('user', 'admin', 'USER', 'ADMIN') and r['name'] != role]
    if remove:
        call('DELETE', path, remove)

# 이 실습 전용 Client의 이전 소문자 역할 정의도 제거합니다.
for name in ('user', 'admin'):
    if name in roles:
        call('DELETE', role_path + '/' + name)
print('oauth-lab 설정 완료: alice=USER, admin=ADMIN. 새로 발급한 토큰부터 반영됩니다.')
