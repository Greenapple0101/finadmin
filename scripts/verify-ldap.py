#!/usr/bin/env python3
"""LDAP의 비밀번호·그룹이 실제 JWT와 업무 권한으로 이어지는지 처음부터 끝까지 확인합니다."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from ldap_support import KeycloakAdmin, LDAP_USERS, COMPANY_A, COMPANY_B, component, definition, read_values
from verify import ROOT, ISSUER, GATEWAY, ACCESS, ADMIN, REPORT, check, claims, login, sql, wait_ready


def record(name, passed):
    if not passed:
        raise AssertionError(name)
    REPORT.append({'case': name, 'passed': True})
    print('PASS ' + name, flush=True)


def directory_checks():
    # Docker 내부에서 검사하므로 LDAP 호스트 포트를 추가로 열 필요가 없습니다.
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'ldap', 'python3', '-'],
        input=(ROOT / 'scripts/check-ldap-directory.py').read_text(), cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('LDAP 비밀번호/읽기 전용 ACL 검사 실패: ' + result.stderr)
    for item in json.loads(result.stdout):
        record(item['case'], item['passed'])


def verify_identities(admin, provider_id, tokens):
    roles = definition()['groupRoles']
    user_ids = {}
    for name, token in tokens.items():
        _, company, group = LDAP_USERS[name]
        user = admin.user(name)
        data = claims(token)
        record(name + ': imported identity still points to LDAP',
               user.get('federationLink') == provider_id and data['sub'] == user['id'] and data['iss'] == ISSUER)
        # Credentials API의 password 표시는 '지원하는 인증 수단'도 포함합니다.
        # 그래서 비밀번호 복사 여부는 DB의 저장된 credential 개수만 조회해 확인합니다.
        subject = str(uuid.UUID(user['id']))
        stored = subprocess.run(['docker', 'compose', 'exec', '-T', 'keycloak-db', 'psql',
            '-U', 'keycloak', '-d', 'keycloak', '-v', 'ON_ERROR_STOP=1', '-At'],
            input=f"SELECT count(*) FROM credential WHERE user_id='{subject}' AND type='password';",
            cwd=ROOT, text=True, capture_output=True)
        record(name + ': no local Keycloak password copy', stored.returncode == 0 and stored.stdout.strip() == '0')
        memberships = admin.request('/users/' + user['id'] + '/groups')
        record(name + ': LDAP group is visible in Keycloak', '/ldap/' + group in {g['path'] for g in memberships})
        for client, expected in roles[group].items():
            actual = data.get('resource_access', {}).get(client, {}).get('roles', [])
            record(name + ': JWT roles for ' + client, set(actual) == set(expected))
            client_id = admin.request('/clients?clientId=' + client)[0]['id']
            assigned = admin.request('/users/' + user['id'] + '/role-mappings/clients/' + client_id)
            record(name + ': ' + client + ' roles inherited, not assigned directly', not assigned)
        subject = str(uuid.UUID(data['sub']))
        row = sql(f"SELECT id,company_id FROM app_users WHERE identity_issuer='{ISSUER}' AND identity_subject='{subject}';")
        fields = row.split('|')
        record(name + ': company connection exists', len(fields) == 2 and fields[1] == company)
        user_ids[name] = str(uuid.UUID(fields[0]))
    return user_ids


def api_checks(tokens, user_ids):
    # Gateway 경유와 백엔드 직접 호출을 모두 검사합니다. 뒷단도 스스로 권한을 판단해야 합니다.
    for label, access, admin in [('gateway', GATEWAY + '/access', GATEWAY + '/admin'),
                                  ('direct', ACCESS, ADMIN)]:
        check(label + ': missing JWT', 401, admin + '/api/admin/summary')
        for name, token in tokens.items():
            check(label + ': ' + name + ' access identity', 200, access + '/api/me', token)
            check(label + ': ' + name + ' admin identity', 200, admin + '/api/me', token)
            check(label + ': ' + name + ' admin authorization', 200 if name == 'ldap-admin' else 403,
                  admin + '/api/admin/summary', token)
        check(label + ': LDAP employee reads own company', 200, access + '/api/companies/' + COMPANY_A, tokens['ldap-alice'])
        check(label + ': LDAP employee cannot read other company', 403, access + '/api/companies/' + COMPANY_B, tokens['ldap-alice'])

    source = check('LDAP admin opens source account', 201,
        GATEWAY + '/access/api/companies/' + COMPANY_A + '/accounts', tokens['ldap-admin'], 'POST')['id']
    destination = check('LDAP admin opens destination account', 201,
        GATEWAY + '/access/api/companies/' + COMPANY_B + '/accounts', tokens['ldap-admin'], 'POST')['id']
    source, destination = str(uuid.UUID(source)), str(uuid.UUID(destination))
    # 실제 돈이 아닙니다. 테스트에서만 전용 실습 DB의 새 계좌에 잔액을 준비합니다.
    sql(f"UPDATE accounts SET balance_won=10000 WHERE id='{source}';")
    body = {'sourceAccountId': source, 'destinationAccountId': destination, 'amountWon': 1000}
    check('other-company LDAP employee cannot request transfer', 403,
        GATEWAY + '/access/api/transfers', tokens['ldap-outsider'], 'POST', body)
    transfer = check('LDAP developer requests transfer', 201,
        GATEWAY + '/access/api/transfers', tokens['ldap-alice'], 'POST', body)
    record('requester comes from LDAP JWT and app_users', transfer['requesterId'] == user_ids['ldap-alice'])
    path = '/api/transfers/' + transfer['id']
    for base in (GATEWAY + '/access', ACCESS):
        check('LDAP developer cannot approve at ' + base, 403, base + path + '/approve', tokens['ldap-alice'], 'POST')
    approved = check('LDAP approver approves transfer', 200,
        GATEWAY + '/access' + path + '/approve', tokens['ldap-bob'], 'POST')
    record('reviewer comes from LDAP JWT and app_users', approved['reviewerId'] == user_ids['ldap-bob'])
    completed = check('LDAP approver executes transfer', 200,
        GATEWAY + '/access' + path + '/execute', tokens['ldap-bob'], 'POST')
    record('transfer completed by LDAP approver', completed['status'] == 'COMPLETED' and completed['executedBy'] == user_ids['ldap-bob'])
    check('repeated LDAP transfer execution rejected', 409,
        GATEWAY + '/access' + path + '/execute', tokens['ldap-bob'], 'POST')
    balances = sql(f"SELECT balance_won FROM accounts WHERE id='{source}' UNION ALL SELECT balance_won FROM accounts WHERE id='{destination}';")
    record('LDAP transfer balances are 9000 and 1000 won', balances.splitlines() == ['9000', '1000'])


def change_membership(action):
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'ldap', 'python3', '/opt/finlab/directory.py',
        'membership', action, 'admins', 'admin'], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('LDAP 관리자 그룹 구성원 ' + action + ' 실패')


def group_change_checks(values, tokens):
    # '퇴사 처리 즉시 모든 JWT 무효화'라고 잘못 설명하지 않도록 두 토큰을 비교합니다.
    # 테스트 직전에 원래 토큰을 발급해서 만료 시간 때문에 우연히 실패하지 않게 합니다.
    original = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    change_membership('delete')
    try:
        reduced = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
        record('new login after LDAP group removal loses admin role',
               'admin' not in claims(reduced).get('resource_access', {}).get('finadmin-api', {}).get('roles', []))
        for label, base in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
            check(label + ': removed member new JWT forbidden', 403, base + '/api/admin/summary', reduced)
            check(label + ': old unexpired JWT still carries admin', 200, base + '/api/admin/summary', original)
    finally:
        # 중간 검사가 실패하거나 Ctrl+C로 끊어져도 그룹은 돌려놓습니다. 강제 종료 시 복구 명령은 문서에 있습니다.
        change_membership('add')
    restored = login('ldap-admin', values['LDAP_ADMIN_USER_PASSWORD'])
    record('restored group returns admin role to new JWT',
           'admin' in claims(restored)['resource_access']['finadmin-api']['roles'])
    for label, base in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
        check(label + ': restored member new JWT allowed', 200, base + '/api/admin/summary', restored)
    tokens['ldap-admin'] = restored


def save_ldap_tokens(tokens):
    # 기존 내부 계정의 토큰 구역과 분리해서 추가합니다. 이 파일은 Git 저장소 밖에 있습니다.
    path = Path.home() / 'Desktop/finadmin-local-secrets.md'
    previous = path.read_text()
    start, end = '<!-- finlab-ldap-tokens:start -->', '<!-- finlab-ldap-tokens:end -->'
    lines = [start, '## LDAP 계정 액세스 토큰', '',
             '기본 5분 후 만료됩니다. `python3 scripts/verify-ldap.py`는 토큰을 다시 발급하고 모의 이체를 추가합니다.', '']
    for name, token in tokens.items():
        expiry = datetime.fromtimestamp(claims(token)['exp'], timezone.utc).isoformat()
        lines += ['### ' + name, '- 만료 시각(UTC): ' + expiry, '', '```text', token, '```', '']
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
    REPORT.clear()
    values = read_values()
    for url in (ISSUER + '/.well-known/openid-configuration', GATEWAY + '/', ACCESS + '/api/hello', ADMIN + '/api/hello'):
        wait_ready(url)
    directory_checks()
    admin = KeycloakAdmin(values)
    realm_id = admin.request('')['id']
    provider = component(admin, 'finlab-openldap', realm_id)
    if not provider:
        raise RuntimeError('먼저 python3 scripts/setup-ldap.py를 실행하세요.')
    tokens = {name: login(name, values[key]) for name, (key, _, _) in LDAP_USERS.items()}
    user_ids = verify_identities(admin, provider['id'], tokens)
    api_checks(tokens, user_ids)
    group_change_checks(values, tokens)
    # Federation 추가 이후에도 원래 쓰던 내부 계정이 계속 동작해야 합니다.
    local_admin = login('admin', values['LAB_ADMIN_PASSWORD'])
    check('original local admin still works', 200, GATEWAY + '/admin/api/admin/summary', local_admin)
    save_ldap_tokens(tokens)
    directory = ROOT / '.local'
    directory.mkdir(exist_ok=True)
    report = {'verifiedAt': datetime.now(timezone.utc).isoformat(), 'checks': REPORT,
              'note': 'LDAP 구성원 삭제 후 finally로 복원. 기존 JWT는 만료 전까지 유효. 비밀번호·토큰 원문 없음.'}
    (directory / 'ldap-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'완료: LDAP·Keycloak·두 API 검증 {len(REPORT)}개. ldap-admin 그룹 복원 및 데스크탑 토큰 갱신 완료.')


if __name__ == '__main__':
    main()
