#!/usr/bin/env python3
"""verify-ldap.py가 LDAP 컨테이너 안으로 보내 실행하는 검사입니다. 호스트에서 직접 실행하지 않습니다."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, '/opt/finlab')
from directory import BASE, BIND_DN, ADMIN_DN, USERS, user_dn

checks = []


def record(name, passed):
    if not passed:
        raise AssertionError(name)
    checks.append({'case': name, 'passed': True})


def ldap(tool, dn, password, arguments, data=None):
    # 명령 목록과 출력에 비밀번호를 남기지 않습니다. 임시 파일도 자동으로 닫고 삭제합니다.
    with tempfile.NamedTemporaryFile(mode='w', dir='/run') as handle:
        handle.write(password)
        handle.flush()
        return subprocess.run([tool, '-x', '-H', 'ldap://localhost:389', '-D', dn, '-y', handle.name] + arguments,
                              input=data, text=True, capture_output=True)


for name, key in USERS.items():
    result = ldap('ldapwhoami', user_dn(name), os.environ[key], [])
    record('LDAP password authenticates ldap-' + name, result.returncode == 0 and user_dn(name) in result.stdout)
wrong = ldap('ldapwhoami', user_dn('alice'), 'intentionally-wrong-password', [])
record('LDAP rejects incorrect password with code 49', wrong.returncode == 49)

result = ldap('ldapsearch', BIND_DN, os.environ['LDAP_BIND_PASSWORD'],
              ['-LLL', '-b', 'ou=users,' + BASE, '(objectClass=inetOrgPerson)', 'uid', 'entryUUID', 'userPassword'])
record('bind account reads four employees', result.returncode == 0 and result.stdout.count('\nuid: ldap-') == 4)
record('bind account cannot read password hashes', 'userPassword:' not in result.stdout)

# description이라는 무해한 메모 변경도 거절되어야 합니다. 만약 잘못 허용되면 즉시 원상 복구합니다.
change = f'dn: {user_dn("alice")}\nchangetype: modify\nadd: description\ndescription: finlab-acl-probe\n'
result = ldap('ldapmodify', BIND_DN, os.environ['LDAP_BIND_PASSWORD'], [], change)
if result.returncode == 0:
    undo = change.replace('add: description', 'delete: description')
    ldap('ldapmodify', ADMIN_DN, os.environ['LDAP_ADMIN_PASSWORD'], [], undo)
record('bind account cannot modify employees (LDAP 50)', result.returncode == 50)
anonymous = subprocess.run(['ldapsearch', '-x', '-LLL', '-H', 'ldap://localhost:389',
    '-b', 'ou=users,' + BASE, '(objectClass=inetOrgPerson)', 'uid'], text=True, capture_output=True)
record('anonymous client cannot list employees', anonymous.returncode in (0, 32) and 'uid: ldap-' not in anonymous.stdout)
print(json.dumps(checks))
