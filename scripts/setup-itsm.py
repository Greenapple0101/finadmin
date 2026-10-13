#!/usr/bin/env python3
"""ITSM 승인 역할과 실습 직원의 회사 연결을 준비합니다. 기존 소속·비밀번호는 덮어쓰지 않습니다.

--roles-only: 처음 LDAP 그룹 역할을 연결하기 전에 승인자 Role만 준비합니다.
인자 없음: 역할과 내부/LDAP 직원 8명의 ITSM 회사 연결을 모두 준비합니다.
이 JSON의 회사 배치는 실습용 온보딩 자료입니다. 실제 API의 권한 판단은 DB의 소속을 조회합니다.
"""
import argparse
import json
import subprocess
import urllib.parse
import uuid
from ldap_support import KeycloakAdmin, read_values
from verify import ROOT, ISSUER


def sql(statement):
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'itsm-db', 'psql', '-U', 'finadmin',
                             '-d', 'finadmin', '-v', 'ON_ERROR_STOP=1', '-At'],
                            input=statement, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError('ITSM DB 준비 실패. DB와 Flyway 적용 상태를 확인하세요.')
    return result.stdout.strip()


def quote(value):
    # SQL 문자열 안의 작은따옴표를 두 번 적습니다. 외부 사용자 이름을 SQL 코드로 실행하지 않습니다.
    return "'" + str(value).replace("'", "''") + "'"


def prepare_roles(admin):
    client = admin.request('/clients?' + urllib.parse.urlencode({'clientId': 'finadmin-api'}))[0]['id']
    roles_url = '/clients/' + client + '/roles'
    roles = {r['name']: r for r in admin.request(roles_url)}
    if 'approver' not in roles:
        admin.request(roles_url, 'POST', {'name': 'approver', 'description': 'ITSM service request approver'}, 201)
    role = admin.request(roles_url + '/approver')
    bob = admin.user('bob')
    mapping = '/users/' + bob['id'] + '/role-mappings/clients/' + client
    if 'approver' not in {r['name'] for r in admin.request(mapping)}:
        admin.request(mapping, 'POST', [role], 204)
    return client, role


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roles-only', action='store_true')
    args = parser.parse_args()
    admin = KeycloakAdmin(read_values())
    client, role = prepare_roles(admin)
    if args.roles_only:
        print('ITSM approver 역할과 내부 계정 bob의 역할을 준비했습니다.')
        return
    roots = [g for g in admin.request('/groups?search=ldap&exact=true') if g.get('path') == '/ldap']
    if len(roots) != 1:
        raise RuntimeError('먼저 setup-ldap.py로 LDAP 그룹을 준비하세요.')
    groups = {g['name']: g for g in admin.request('/groups/' + roots[0]['id'] + '/children')}
    mapping = '/groups/' + groups['approvers']['id'] + '/role-mappings/clients/' + client
    if 'approver' not in {r['name'] for r in admin.request(mapping)}:
        admin.request(mapping, 'POST', [role], 204)

    fixtures = json.loads((ROOT / 'infra/itsm/demo-users.json').read_text())
    companies = {c['name']: str(uuid.UUID(c['id'])) for c in fixtures['companies']}
    statements = ['BEGIN;']
    for company in fixtures['companies']:
        statements.append(f"INSERT INTO itsm_companies(id,name) VALUES({quote(company['id'])},{quote(company['name'])}) ON CONFLICT(id) DO NOTHING;")
    for person in fixtures['users']:
        user = admin.user(person['username'])
        subject = str(uuid.UUID(user['id']))
        company = companies[person['company']]
        # 기존 직원의 회사 변경은 최초 연결과 별개입니다. 자동으로 다른 회사에 옮기지 않습니다.
        existing = sql(f"SELECT company_id FROM itsm_users WHERE identity_issuer={quote(ISSUER)} AND identity_subject={quote(subject)};")
        if existing and existing != company:
            raise RuntimeError('기존 ITSM 회사 연결이 다릅니다. 자동 변경하지 않습니다: ' + person['username'])
        identity = str(uuid.uuid5(uuid.NAMESPACE_URL, 'itsm/' + ISSUER + '/' + subject))
        fields = [identity, company, person['username'], ISSUER, subject]
        statements.append('INSERT INTO itsm_users(id,company_id,display_name,identity_issuer,identity_subject) VALUES('
                          + ','.join(map(quote, fields)) + ') ON CONFLICT(identity_issuer,identity_subject) DO NOTHING;')
    statements.append('COMMIT;')
    sql('\n'.join(statements))
    print('ITSM 역할과 직원 8명의 회사 연결을 준비했습니다. 기존 요청·소속·비밀번호는 보존했습니다.')


if __name__ == '__main__':
    main()
