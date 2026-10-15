"""기존 로컬 API7 관리 API 연결입니다. 인증서와 암호는 Git 밖에서 읽습니다."""
import base64
import http.client
import json
from pathlib import Path
import socket
import ssl

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT.parent / '.local/api7'

class LocalConnection(http.client.HTTPSConnection):
    def connect(self):
        # 설치된 로컬 제품의 인증서 CN을 검사합니다. TLS 검증을 끄는 옵션은 사용하지 않습니다.
        raw = socket.create_connection(('127.0.0.1', 7443), timeout=10)
        self.sock = self._context.wrap_socket(raw, server_hostname='api7ee-dashboard')

def call(method, kind, name, payload=None):
    credentials = json.loads((PRIVATE / 'admin.json').read_text())
    group = json.loads((PRIVATE / 'group.json').read_text())
    if group['name'] != 'finlab-rbac':
        raise ValueError('FinLab 실습 그룹이 아닙니다.')
    context = ssl.create_default_context(cafile=str(PRIVATE / 'current-dashboard.pem'))
    connection = LocalConnection('api7ee-dashboard', 7443, context=context, timeout=10)
    basic = base64.b64encode((credentials['username'] + ':' + credentials['password']).encode()).decode()
    path = '/apisix/admin/' + kind + '/' + name + '?gateway_group_id=' + group['id']
    connection.request(method, path, json.dumps(payload) if payload is not None else None,
        {'Authorization': 'Basic ' + basic, 'Content-Type': 'application/json'})
    response = connection.getresponse(); body = response.read(); status = response.status
    connection.close()
    return status, json.loads(body) if body else {}

ENTRIES = [('services','oauth-finadmin','finadmin-service.json'),
           ('routes','oauth-admin-get','finadmin-route.json'),
           ('routes','oauth-admin-deny','finadmin-deny.json'),
           ('services','oauth-finaccess','finaccess-service.json'),
           ('routes','oauth-access-get','finaccess-route.json'),
           ('routes','oauth-access-deny','finaccess-deny.json')]
