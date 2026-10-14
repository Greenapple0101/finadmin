#!/usr/bin/env python3
"""LDAP Federation과 CLI용 Device Grant를 설정합니다. API7 설정은 건드리지 않습니다."""
import json
from keycloak_admin import call, ROOT, credentials

# 기존 사용자와 Realm은 유지합니다. 이름이 같은 실습 Client만 설정 원본과 맞춥니다.
realm = json.loads((ROOT / 'keycloak/realm.json').read_text())
for client in realm['clients']:
    if client['clientId'] == 'oauth-api':
        continue
    found = call('GET', '/clients?clientId=' + client['clientId'])
    if found:
        call('PUT', '/clients/' + found[0]['id'], client)
    else:
        call('POST', '/clients', client)
    print('Client 준비:', client['clientId'])

# 부서 속성은 관리자만 수정할 수 있습니다. 직원이 자기 권한처럼 바꾸는 값이 아닙니다.
profile = call('GET', '/users/profile')
if not any(a['name'] == 'department' for a in profile['attributes']):
    profile['attributes'].append({'name': 'department', 'displayName': 'Department',
        'permissions': {'view': ['admin'], 'edit': ['admin']}, 'validations': {}})
    call('PUT', '/users/profile', profile)

def component(desired, parent):
    desired['parentId'] = parent
    found = [v for v in call('GET', '/components?parent=' + parent) if v.get('name') == desired['name']]
    if found:
        if found[0]['providerId'] != desired['providerId']:
            raise SystemExit('동일한 이름의 다른 Provider가 있어 중단합니다.')
        call('PUT', '/components/' + found[0]['id'], desired)
        return found[0]['id']
    call('POST', '/components', desired)
    return next(v['id'] for v in call('GET', '/components?parent=' + parent) if v.get('name') == desired['name'])

groups = call('GET', '/groups?search=ldap&exact=true')
if not groups:
    call('POST', '/groups', {'name': 'ldap'})
    groups = call('GET', '/groups?search=ldap&exact=true')
root = next(g['id'] for g in groups if g['path'] == '/ldap')
settings = json.loads((ROOT / 'keycloak/ldap.json').read_text())
settings['provider']['config']['bindCredential'] = [credentials['ldap-bind']]
provider = component(settings['provider'], call('GET', '')['id'])
for mapper in settings['mappers']:
    mapper_id = component(mapper, provider)
    if mapper['providerId'] == 'group-ldap-mapper':
        call('POST', f'/user-storage/{provider}/mappers/{mapper_id}/sync?direction=fedToKeycloak')
result = call('POST', f'/user-storage/{provider}/sync?action=triggerFullSync')
if result.get('failed', 0):
    raise SystemExit('LDAP 사용자 동기화 실패')
client = call('GET', '/clients?clientId=oauth-api')[0]['id']
for group in call('GET', '/groups/' + root + '/children'):
    if group['name'] in ('USER', 'ADMIN'):
        role = call('GET', '/clients/' + client + '/roles/' + group['name'])
        call('POST', '/groups/' + group['id'] + '/role-mappings/clients/' + client, [role])
print('LDAP → 그룹 USER/ADMIN → Client Role 연결 완료. 부서는 department 속성입니다.')
