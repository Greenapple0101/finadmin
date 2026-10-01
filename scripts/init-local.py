#!/usr/bin/env python3
"""실습 비밀번호를 만들고, Git 밖의 데스크탑 문서에 기록합니다. 기존 값은 보존합니다."""
from pathlib import Path
import os
import secrets
import string

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / '.env'
DESKTOP = Path.home() / 'Desktop' / 'finadmin-local-secrets.md'
KEYS = ('KEYCLOAK_DB_PASSWORD', 'KEYCLOAK_ADMIN_PASSWORD', 'APP_DB_PASSWORD',
        'LAB_ALICE_PASSWORD', 'LAB_BOB_PASSWORD', 'LAB_ADMIN_PASSWORD', 'LAB_OUTSIDER_PASSWORD',
        'LDAP_ADMIN_PASSWORD', 'LDAP_BIND_PASSWORD', 'LDAP_ALICE_PASSWORD',
        'LDAP_BOB_PASSWORD', 'LDAP_ADMIN_USER_PASSWORD', 'LDAP_OUTSIDER_PASSWORD')


def read_env():
    # .env 내용을 셸 명령으로 실행하지 않고 이름=값으로 읽습니다.
    if not ENV.exists():
        return {}
    return dict(line.split('=', 1) for line in ENV.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith('#') and '=' in line)


def main():
    values = read_env()
    missing = [key for key in KEYS if not values.get(key)]
    for key in missing:
        values[key] = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
    # 새 파일은 처음 생성하는 순간부터 소유자에게만 읽기·쓰기 권한을 줍니다.
    fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write('# 로컬 실습 비밀번호입니다. Git에 올리지 않습니다.\n')
        output.write(''.join(key + '=' + value + '\n' for key, value in values.items()))

    start, end = '<!-- finlab-passwords:start -->', '<!-- finlab-passwords:end -->'
    previous = DESKTOP.read_text() if DESKTOP.exists() else '# FinAdmin 로컬 인증 정보\n'
    previous = previous.replace('아직 Keycloak을 설정하지 않았습니다. 아래 값은 실제 설정 후 기록합니다.',
                                '실제 생성된 값은 아래의 생성된 실습 계정 및 액세스 토큰 구역을 확인하세요.')
    block = [start, '## 생성된 실습 계정', '',
             '- Keycloak 관리 화면: http://localhost:18080/admin/',
             '- 관리 계정: `bootstrap-admin`',
             '- 앱 화면: http://localhost:18090/',
             '- Realm: `finlab`',
             '- 사용자 로그인 Client: `finlab-web` (공개 클라이언트, Client Secret 없음)',
             '- API Client: `finaccess-api`, `finadmin-api`', '',
             '| 항목 | 비밀번호 |', '| --- | --- |']
    labels = {'KEYCLOAK_ADMIN_PASSWORD': 'bootstrap-admin (Keycloak 관리)',
              'KEYCLOAK_DB_PASSWORD': 'Keycloak DB', 'APP_DB_PASSWORD': 'FinAccess 실습 DB',
              'LAB_ALICE_PASSWORD': 'alice (A회사 담당자)', 'LAB_BOB_PASSWORD': 'bob (A회사 결재자)',
              'LAB_ADMIN_PASSWORD': 'admin (A회사 / 앱 관리자)',
              'LAB_OUTSIDER_PASSWORD': 'outsider (B회사 담당자)',
              'LDAP_ADMIN_PASSWORD': 'cn=admin,dc=finlab,dc=com (LDAP 관리 전용)',
              'LDAP_BIND_PASSWORD': 'cn=keycloak,ou=services,dc=finlab,dc=com (조회 전용)',
              'LDAP_ALICE_PASSWORD': 'ldap-alice (LDAP / A회사 담당자)',
              'LDAP_BOB_PASSWORD': 'ldap-bob (LDAP / A회사 결재자)',
              'LDAP_ADMIN_USER_PASSWORD': 'ldap-admin (LDAP / A회사 앱 관리자)',
              'LDAP_OUTSIDER_PASSWORD': 'ldap-outsider (LDAP / B회사 담당자)'}
    block += ['| ' + labels[key] + ' | `' + values[key] + '` |' for key in KEYS]
    block += ['', '서버 최초 생성에 사용한 값입니다. .env 변경만으로 이미 저장된 계정 비밀번호가 바뀌지 않습니다.', end]
    replacement = '\n'.join(block)
    if start in previous and end in previous:
        before, rest = previous.split(start, 1)
        _, after = rest.split(end, 1)
        updated = before + replacement + after
    else:
        updated = previous.rstrip() + '\n\n' + replacement + '\n'
    fd = os.open(DESKTOP, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write(updated)
    print('로컬 .env와 데스크탑 인증 문서를 준비했습니다. 비밀번호는 화면에 출력하지 않습니다.')


if __name__ == '__main__':
    main()
