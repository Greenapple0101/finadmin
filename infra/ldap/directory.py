#!/usr/bin/env python3
"""LDAP 컨테이너 안에서 실행합니다. 빈 명부는 한 번 만들고, 다음 시작부터 보존합니다."""
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

BASE = 'dc=finlab,dc=com'
BIND_DN = 'cn=keycloak,ou=services,' + BASE
ADMIN_DN = 'cn=admin,' + BASE
USERS = {'alice': 'LDAP_ALICE_PASSWORD', 'bob': 'LDAP_BOB_PASSWORD',
         'admin': 'LDAP_ADMIN_USER_PASSWORD', 'outsider': 'LDAP_OUTSIDER_PASSWORD'}


def run(command, data=None):
    # 입력 LDIF에 비밀번호 해시가 들어갈 수 있으므로 오류에도 본문은 출력하지 않습니다.
    result = subprocess.run(command, input=data, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f'{command[0]} 실패 (종료 코드 {result.returncode})')
    return result.stdout


def secret_command(command, password, data=None):
    # -w 비밀번호를 쓰면 프로세스 목록에 노출됩니다. 권한 600의 임시 파일을 사용합니다.
    with tempfile.NamedTemporaryFile(mode='w', dir='/run') as handle:
        handle.write(password)
        handle.flush()
        return run(command + [handle.name], data)


def password_hash(key):
    return secret_command(['slappasswd', '-T'], os.environ[key]).strip()


def user_dn(name):
    return 'uid=ldap-' + name + ',ou=users,' + BASE


def seed():
    # LDIF는 명부의 내용을 텍스트로 적는 형식입니다. 빈 줄마다 사람/그룹 하나가 끝납니다.
    entries = [f'dn: {BASE}\nobjectClass: dcObject\nobjectClass: organization\no: FinLab\ndc: finlab']
    for unit in ('users', 'groups', 'services'):
        entries.append(f'dn: ou={unit},{BASE}\nobjectClass: organizationalUnit\nou: {unit}')
    entries.append(f'dn: {BIND_DN}\nobjectClass: organizationalRole\nobjectClass: simpleSecurityObject\n'
                   f'cn: keycloak\nuserPassword: {password_hash("LDAP_BIND_PASSWORD")}')
    for name, key in USERS.items():
        entries.append(f'dn: {user_dn(name)}\nobjectClass: inetOrgPerson\nuid: ldap-{name}\n'
                       f'cn: LDAP {name}\nsn: {name}\ngivenName: LDAP\nmail: ldap-{name}@finlab.test\n'
                       f'userPassword: {password_hash(key)}')
    for group, members in {'developers': ['alice', 'outsider'], 'approvers': ['bob'], 'admins': ['admin']}.items():
        # groupOfNames는 구성원이 1명 이상 있어야 합니다. 조회 서비스 DN을 자리 유지용으로 둡니다.
        # 이 DN은 ou=users 밖에 있고 직원 객체도 아니므로 Keycloak 로그인 사용자로 가져오지 않습니다.
        values = [BIND_DN] + [user_dn(name) for name in members]
        entries.append(f'dn: cn={group},ou=groups,{BASE}\nobjectClass: groupOfNames\ncn: {group}\n' +
                       '\n'.join('member: ' + dn for dn in values))
    return '\n\n'.join(entries) + '\n'


def start():
    os.umask(0o077)
    runtime = Path('/run/slapd')
    runtime.mkdir(parents=True, exist_ok=True)
    config = runtime / 'slapd.conf'
    template = Path('/opt/finlab/slapd.conf').read_text()
    config.write_text(template.replace('__ROOT_PASSWORD_HASH__', password_hash('LDAP_ADMIN_PASSWORD')))
    data = Path('/var/lib/ldap')
    data.mkdir(exist_ok=True)
    marker = data / '.finlab-initialized'
    if not marker.exists():
        # 도중에 실패한 DB를 덮어쓰면 원인과 기존 자료를 잃습니다. 이 경우 멈춥니다.
        if (data / 'data.mdb').exists():
            raise RuntimeError('초기화 표시 없는 LDAP DB가 있습니다. 자동으로 덮어쓰지 않습니다.')
        run(['slapadd', '-f', str(config)], seed())
        marker.touch()
        print('FinLab LDAP: 직원 4명과 그룹 3개를 최초 생성했습니다.', flush=True)
    else:
        print('FinLab LDAP: 저장된 직원·그룹·비밀번호를 그대로 사용합니다.', flush=True)
    generated = runtime / 'config'
    generated.mkdir(exist_ok=True)
    run(['slaptest', '-f', str(config), '-F', str(generated)])
    # 초기화만 root로 하고, 실제 LDAP 서버는 권한이 작은 openldap 계정으로 실행합니다.
    account = pwd.getpwnam('openldap')
    for directory in (runtime, data):
        for path in [directory, *directory.rglob('*')]:
            os.chown(path, account.pw_uid, account.pw_gid)
    config.unlink()
    os.execvp('slapd', ['slapd', '-F', str(generated), '-h', 'ldap://0.0.0.0:389/',
                         '-u', 'openldap', '-g', 'openldap', '-d', '0'])


def membership(action, group, name):
    # 실습 중 '직원 한 명을 그룹에서 빼고 다시 넣는' 명령입니다. 명부 전체를 초기화하지 않습니다.
    if action not in ('add', 'delete') or group not in ('developers', 'approvers', 'admins') or name not in USERS:
        raise ValueError('허용된 동작·실습 그룹·사용자를 지정하세요.')
    change = f'dn: cn={group},ou=groups,{BASE}\nchangetype: modify\n{action}: member\nmember: {user_dn(name)}\n'
    secret_command(['ldapmodify', '-x', '-H', 'ldap://localhost:389', '-D', ADMIN_DN, '-y'],
                   os.environ['LDAP_ADMIN_PASSWORD'], change)
    print(f'LDAP {group}: ldap-{name} {action} 완료')


if __name__ == '__main__':
    if len(sys.argv) == 1:
        start()
    elif len(sys.argv) == 5 and sys.argv[1] == 'membership':
        membership(*sys.argv[2:])
    else:
        raise SystemExit('사용법: directory.py [membership add|delete developers|approvers|admins alice|bob|admin|outsider]')
