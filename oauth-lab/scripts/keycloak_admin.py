"""실습 Realm 설정에 쓰는 작은 Admin API 도우미입니다. 앱의 로그인에는 사용하지 않습니다."""
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

