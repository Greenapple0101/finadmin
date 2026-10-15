#!/usr/bin/env python3
"""Mac의 OpenLDAP을 127.0.0.1:18389에서 실행합니다. Docker나 시스템 서비스를 사용하지 않습니다."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
LDAP = PRIVATE / 'ldap'
LDAP.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(LDAP, 0o700)
prefix = Path(subprocess.check_output(['brew', '--prefix', 'openldap'], text=True).strip())
homebrew = Path(subprocess.check_output(['brew', '--prefix'], text=True).strip())
slapd = prefix / 'libexec/slapd'
if not slapd.exists():
    raise SystemExit('brew install openldap 명령을 먼저 실행하세요.')
credentials_path = PRIVATE / 'credentials.json'
values = json.loads(credentials_path.read_text())
for name in ('ldap-root', 'ldap-bind', 'ldap-user', 'ldap-admin'):
    values.setdefault(name, secrets.token_urlsafe(18))
credentials_path.write_text(json.dumps(values))
credentials_path.chmod(0o600)

# LDAP에는 비밀번호 원문 대신 소금을 섞은 해시를 저장합니다. 파일은 .local 안에만 둡니다.
def password_hash(value):
    salt = secrets.token_bytes(16)
    return '{SSHA}' + base64.b64encode(hashlib.sha1(value.encode() + salt).digest() + salt).decode()

pid_file = LDAP / 'process.pid'
if pid_file.exists():
    command = subprocess.run(['ps', '-p', pid_file.read_text().strip(), '-o', 'command='], capture_output=True, text=True).stdout
    if str(LDAP / 'slapd.conf') in command:
        print('이 실습의 LDAP가 이미 실행 중입니다: 127.0.0.1:18389')
        raise SystemExit(0)
with socket.socket() as connection:
    if connection.connect_ex(('127.0.0.1', 18389)) == 0:
        raise SystemExit('18389 포트가 사용 중입니다. 다른 LDAP는 변경하지 않습니다.')
(LDAP / 'data').mkdir(exist_ok=True, mode=0o700)
config = '\n'.join(f'include "{homebrew}/etc/openldap/schema/{name}.schema"' for name in ('core', 'cosine', 'inetorgperson'))
config += f'''
pidfile "{LDAP}/slapd.pid"
argsfile "{LDAP}/slapd.args"
database mdb
maxsize 104857600
suffix "dc=oauth,dc=lab"
rootdn "cn=admin,dc=oauth,dc=lab"
rootpw {password_hash(values['ldap-root'])}
directory "{LDAP}/data"
index objectClass,uid,cn,entryUUID eq
index member eq
# 검색용 계정도 비밀번호를 읽을 수는 없습니다. 로그인 시 맞는지만 확인합니다.
access to attrs=userPassword
    by anonymous auth
    by * none
# Keycloak 계정에는 조회만 허용합니다. 관리자는 별도 rootdn을 사용합니다.
access to *
    by dn.exact="cn=keycloak,ou=services,dc=oauth,dc=lab" read
    by * none
'''
(LDAP / 'slapd.conf').write_text(config)
(LDAP / 'slapd.conf').chmod(0o600)
with (LDAP / 'slapd.log').open('a') as log:
    process = subprocess.Popen([str(slapd), '-f', str(LDAP / 'slapd.conf'), '-h', 'ldap://127.0.0.1:18389', '-d', '0'], stdout=log, stderr=log, start_new_session=True)
pid_file.write_text(str(process.pid))
for _ in range(40):
    if process.poll() is not None:
        raise SystemExit('LDAP 기동 실패. .local/ldap/slapd.log를 확인하세요.')
    with socket.socket() as connection:
        if connection.connect_ex(('127.0.0.1', 18389)) == 0:
            break
    time.sleep(.2)
else:
    raise SystemExit('LDAP 기동 대기 시간 초과')

# 첫 실행에만 명부를 만듭니다. 이후 재시작에서는 사용자가 바꾼 부서·그룹을 유지합니다.
root_password = LDAP / 'root-password'
root_password.write_text(values['ldap-root']); root_password.chmod(0o600)
args = ['-x', '-H', 'ldap://127.0.0.1:18389', '-D', 'cn=admin,dc=oauth,dc=lab', '-y', str(root_password)]
exists = subprocess.run([str(prefix / 'bin/ldapsearch'), *args, '-b', 'dc=oauth,dc=lab', '-s', 'base', 'dn'], capture_output=True)
if exists.returncode not in (0, 32):
    raise SystemExit('LDAP 기존 명부 조회 실패')
if exists.returncode == 32:
    entries = ['dn: dc=oauth,dc=lab\nobjectClass: domain\ndc: oauth']
    entries += [f'dn: ou={ou},dc=oauth,dc=lab\nobjectClass: organizationalUnit\nou: {ou}' for ou in ('people','groups','services')]
    entries += [f"dn: cn=keycloak,ou=services,dc=oauth,dc=lab\nobjectClass: organizationalRole\nobjectClass: simpleSecurityObject\ncn: keycloak\nuserPassword: {password_hash(values['ldap-bind'])}"]
    for user, department, role in [('ldap-user','Engineering','USER'), ('ldap-admin','Operations','ADMIN')]:
        entries += [f'dn: uid={user},ou=people,dc=oauth,dc=lab\nobjectClass: inetOrgPerson\nuid: {user}\ncn: {user}\nsn: Lab\ngivenName: {user}\nmail: {user}@example.invalid\nou: {department}\nuserPassword: {password_hash(values[user])}']
        entries += [f'dn: cn={role},ou=groups,dc=oauth,dc=lab\nobjectClass: groupOfNames\ncn: {role}\nmember: uid={user},ou=people,dc=oauth,dc=lab']
    result = subprocess.run([str(prefix / 'bin/ldapadd'), *args], input='\n\n'.join(entries)+'\n', text=True, capture_output=True)
    if result.returncode:
        raise SystemExit('LDAP 명부 등록 실패: ' + result.stderr[:250])
print('로컬 LDAP 준비 완료: ldap://127.0.0.1:18389 · ldap-user / ldap-admin · 부서는 ou 속성')
