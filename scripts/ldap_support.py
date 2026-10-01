"""LDAP 설정·검증에서 같이 쓰는 작은 도구입니다. 실제 토큰과 비밀번호는 출력하지 않습니다."""
import json
import time
import urllib.parse
import urllib.request

from verify import ROOT, http

ADMIN_URL = 'http://localhost:18080/admin/realms/finlab'
COMPANY_A = '20000000-0000-4000-8000-000000000001'
COMPANY_B = '20000000-0000-4000-8000-000000000002'
LDAP_USERS = {
    'ldap-alice': ('LDAP_ALICE_PASSWORD', COMPANY_A, 'developers'),
    'ldap-bob': ('LDAP_BOB_PASSWORD', COMPANY_A, 'approvers'),
    'ldap-admin': ('LDAP_ADMIN_USER_PASSWORD', COMPANY_A, 'admins'),
    'ldap-outsider': ('LDAP_OUTSIDER_PASSWORD', COMPANY_B, 'developers'),
}


def read_values():
    return dict(line.split('=', 1) for line in (ROOT / '.env').read_text().splitlines()
                if line and not line.startswith('#') and '=' in line)


class KeycloakAdmin:
    """사용자가 콘솔에서 저장하는 설정을 Admin REST API로 재현합니다."""
    def __init__(self, values):
        self.values = values
        self.token = None
        self.valid_until = 0

    def request(self, path, method='GET', body=None, expected=200):
        # 관리 토큰은 짧게 만료됩니다. 작업이 길어지면 메모리에서만 다시 발급합니다.
        if time.monotonic() >= self.valid_until:
            request = urllib.request.Request('http://localhost:18080/realms/master/protocol/openid-connect/token',
                data=urllib.parse.urlencode({'grant_type': 'password', 'client_id': 'admin-cli',
                    'username': 'bootstrap-admin', 'password': self.values['KEYCLOAK_ADMIN_PASSWORD']}).encode())
            with urllib.request.urlopen(request, timeout=15) as response:
                result = json.load(response)
            self.token = result['access_token']
            self.valid_until = time.monotonic() + max(1, result['expires_in'] - 10)
        status, value, _ = http(ADMIN_URL + path, self.token, method, body)
        if status != expected:
            # body/응답을 통째로 찍으면 bindCredential이 노출될 수 있습니다.
            raise RuntimeError(f'Keycloak {method} {path}: HTTP {status}, 예상 {expected}')
        return value

    def user(self, username):
        found = self.request('/users?' + urllib.parse.urlencode({'username': username, 'exact': 'true'}))
        if len(found) != 1:
            raise RuntimeError('LDAP 사용자 한 명을 찾지 못했습니다: ' + username)
        return found[0]


def definition():
    return json.loads((ROOT / 'infra/keycloak/ldap-federation.json').read_text())


def component(admin, name, parent):
    found = admin.request('/components?' + urllib.parse.urlencode({'name': name, 'parent': parent}))
    if len(found) > 1:
        raise RuntimeError('같은 이름의 설정이 여러 개 있습니다: ' + name)
    return found[0] if found else None
