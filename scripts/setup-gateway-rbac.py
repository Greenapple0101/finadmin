#!/usr/bin/env python3
"""기존 Realm을 지우지 않고 레거시 대상·역할·그룹 연결만 추가합니다."""
import json
import urllib.parse
from ldap_support import KeycloakAdmin, read_values, definition
from verify import ROOT, prepare_clients


def main():
    values = read_values()
    admin = KeycloakAdmin(values)
    realm = json.loads((ROOT / 'infra/keycloak/finlab-realm.json').read_text())
    desired = next(c for c in realm['clients'] if c['clientId'] == 'finlegacy-api')
    query = '/clients?' + urllib.parse.urlencode({'clientId': 'finlegacy-api'})
    found = admin.request(query)
    if not found:
        admin.request('/clients', 'POST', desired, 201)
        found = admin.request(query)
    cid = found[0]['id']
    existing = {r['name'] for r in admin.request('/clients/' + cid + '/roles')}
    for role in realm['roles']['client']['finlegacy-api']:
        if role['name'] not in existing:
            admin.request('/clients/' + cid + '/roles', 'POST', role, 201)
    # 프런트와 기존 검증용 Client의 audience/role mapper를 원본 설정에 맞춥니다.
    prepare_clients(values)
    def add_roles(path, names):
        present = {r['name'] for r in admin.request(path)}
        missing = [admin.request('/clients/' + cid + '/roles/' + name) for name in names if name not in present]
        if missing:
            admin.request(path, 'POST', missing, 204)
    for u in realm['users']:
        user = admin.user(u['username'])
        add_roles('/users/' + user['id'] + '/role-mappings/clients/' + cid, u['clientRoles']['finlegacy-api'])
    roots = [g for g in admin.request('/groups?search=ldap&exact=true') if g['path'] == '/ldap']
    if not roots:
        print('레거시 Client·내부 사용자 준비 완료. LDAP 그룹은 setup-ldap.py에서 연결합니다.')
        return
    if len(roots) != 1:
        raise RuntimeError('LDAP 루트 그룹이 중복되어 자동 연결할 수 없습니다.')
    children = {g['name']: g for g in admin.request('/groups/' + roots[0]['id'] + '/children')}
    for name, mapping in definition()['groupRoles'].items():
        add_roles('/groups/' + children[name]['id'] + '/role-mappings/clients/' + cid, mapping['finlegacy-api'])
    print('finlegacy-api audience/역할 및 내부·LDAP 사용자 연결 완료. 기존 사용자/그룹 삭제 없음.')


if __name__ == '__main__':
    main()
