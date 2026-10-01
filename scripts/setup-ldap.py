#!/usr/bin/env python3
"""LDAP 조회 설정 → 그룹 역할 → 회사 사용자 연결 순서로 준비합니다. 재실행해도 중복 생성하지 않습니다."""
import uuid
import urllib.parse

from ldap_support import KeycloakAdmin, LDAP_USERS, COMPANY_A, COMPANY_B, component, definition, read_values
from verify import ISSUER, wait_ready, sql


def save_component(admin, desired, parent):
    # 설정의 ID를 새로 만들지 않고 이름으로 찾습니다. 사용자의 federationLink도 유지됩니다.
    existing = component(admin, desired['name'], parent)
    desired['parentId'] = parent
    if existing:
        if existing['providerId'] != desired['providerId']:
            raise RuntimeError('이름이 같은 다른 종류의 Provider가 있습니다.')
        desired['id'] = existing['id']
        admin.request('/components/' + existing['id'], 'PUT', desired, 204)
    else:
        admin.request('/components', 'POST', desired, 201)
    return component(admin, desired['name'], parent)['id']


def prepare_groups(admin):
    # LDAP 그룹을 /ldap 밑으로 모읍니다. 기존 앱 그룹과 이름이 겹치지 않게 하는 폴더입니다.
    groups = admin.request('/groups?search=ldap&exact=true')
    roots = [group for group in groups if group['path'] == '/ldap']
    if not roots:
        admin.request('/groups', 'POST', {'name': 'ldap'}, 201)
        roots = [group for group in admin.request('/groups?search=ldap&exact=true') if group['path'] == '/ldap']
    if len(roots) != 1:
        raise RuntimeError('/ldap 그룹 경로를 하나로 정할 수 없습니다.')
    return roots[0]['id']


def assign_group_roles(admin, root_id, groups):
    children = {group['name']: group for group in admin.request('/groups/' + root_id + '/children')}
    for group_name, clients in groups.items():
        group_id = children[group_name]['id']
        for client_name, roles in clients.items():
            client_id = admin.request('/clients?' + urllib.parse.urlencode({'clientId': client_name}))[0]['id']
            path = '/groups/' + group_id + '/role-mappings/clients/' + client_id
            assigned = {role['name'] for role in admin.request(path)}
            missing = [admin.request('/clients/' + client_id + '/roles/' + name)
                       for name in roles if name not in assigned]
            if missing:
                admin.request(path, 'POST', missing, 204)
        # 역할은 사용자 개인에게 붙이지 않습니다. 그룹 구성원이 그룹 역할을 물려받습니다.
        print('그룹 역할 연결 완료: /ldap/' + group_name)


def link_business_users(admin, provider_id):
    # LDAP은 직원 명부이고, 어느 금융 회사의 데이터를 볼지는 FinAccess의 업무 DB가 결정합니다.
    # 아래 두 회사와 네 연결은 이 로컬 실습의 온보딩 자료입니다. 범용 자동 입사 처리 API는 아닙니다.
    sql(f"INSERT INTO companies (id,name) VALUES ('{COMPANY_A}','FinLab A'), ('{COMPANY_B}','FinLab B') ON CONFLICT (id) DO NOTHING;")
    for name, (_, company, _) in LDAP_USERS.items():
        user = admin.user(name)
        if user.get('federationLink') != provider_id:
            raise RuntimeError('같은 ID의 로컬 사용자와 충돌합니다: ' + name)
        subject = str(uuid.UUID(user['id']))
        identity = str(uuid.uuid5(uuid.NAMESPACE_URL, ISSUER + '/' + subject))
        sql(f"INSERT INTO app_users (id,company_id,identity_issuer,identity_subject) "
            f"VALUES ('{identity}','{company}','{ISSUER}','{subject}') "
            "ON CONFLICT (identity_issuer,identity_subject) DO NOTHING;")
        actual = sql(f"SELECT company_id FROM app_users WHERE identity_issuer='{ISSUER}' AND identity_subject='{subject}';")
        if actual != company:
            raise RuntimeError('이미 다른 회사로 연결된 사용자를 자동으로 옮기지 않습니다: ' + name)
        print('FinAccess 회사·신원 연결 완료: ' + name)


def main():
    values = read_values()
    wait_ready(ISSUER + '/.well-known/openid-configuration')
    admin = KeycloakAdmin(values)
    desired = definition()
    realm_id = admin.request('')['id']
    # Git JSON에는 비밀번호가 없습니다. 실행할 때만 .env에서 읽어 관리 요청에 넣습니다.
    desired['provider']['config']['bindCredential'] = [values['LDAP_BIND_PASSWORD']]
    root_id = prepare_groups(admin)
    provider_id = save_component(admin, desired['provider'], realm_id)
    mapper_id = save_component(admin, desired['groupMapper'], provider_id)
    for path in (f'/user-storage/{provider_id}/mappers/{mapper_id}/sync?direction=fedToKeycloak',
                 f'/user-storage/{provider_id}/sync?action=triggerFullSync'):
        result = admin.request(path, 'POST')
        if result.get('failed', 0):
            raise RuntimeError('LDAP 동기화 실패. LDAP 상태와 Bind 설정을 확인하세요.')
    assign_group_roles(admin, root_id, desired['groupRoles'])
    link_business_users(admin, provider_id)
    print('LDAP Federation 준비 완료. 기존 내부 계정과 LDAP 명부는 삭제하거나 초기화하지 않았습니다.')


if __name__ == '__main__':
    main()
