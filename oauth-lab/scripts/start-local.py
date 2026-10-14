#!/usr/bin/env python3
"""Keycloak과 실습 화면만 로컬 JVM에서 시작합니다. Docker는 조작하지 않습니다."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
PRIVATE.mkdir(exist_ok=True, mode=0o700)
home = PRIVATE / 'keycloak-26.7.4'
if not (home / 'bin/kc.sh').exists():
    raise SystemExit('RUNBOOK.md의 Keycloak 다운로드를 먼저 실행하세요.')

# 비밀번호는 처음 한 번만 만들고, 공개 설정 파일과 분리합니다.
credentials = PRIVATE / 'credentials.json'
if not credentials.exists():
    credentials.write_text(json.dumps({name: secrets.token_urlsafe(18) for name in ['bootstrap-admin', 'alice', 'admin']}))
    credentials.chmod(0o600)
values = json.loads(credentials.read_text())
environment = os.environ.copy()
java_home = subprocess.check_output(['/usr/libexec/java_home', '-v', '21'], text=True).strip()
environment['JAVA_HOME'] = java_home
environment['PATH'] = java_home + '/bin:' + environment.get('PATH', '')
environment.update({'KC_BOOTSTRAP_ADMIN_USERNAME': 'bootstrap-admin',
    'KC_BOOTSTRAP_ADMIN_PASSWORD': values['bootstrap-admin'],
    'LAB_ALICE_PASSWORD': values['alice'], 'LAB_ADMIN_PASSWORD': values['admin'],
    'JAVA_OPTS_KC_HEAP': '-Xms128m -Xmx512m'})

# Keycloak import는 이미 존재하는 Realm을 덮어쓰지 않습니다.
imports = home / 'data/import'
imports.mkdir(parents=True, exist_ok=True)
(imports / 'oauth-lab-realm.json').write_text((ROOT / 'keycloak/realm.json').read_text())

def start(name, port, command):
    pid_file = PRIVATE / (name + '.pid')
    if pid_file.exists():
        old_pid = int(pid_file.read_text())
        previous = subprocess.run(['ps', '-p', str(old_pid), '-o', 'command='], capture_output=True, text=True)
        if str(ROOT) in previous.stdout:
            print(name, '프로세스가 이미 실행 중입니다. 기동 중에는 로그를 확인하세요.')
            return
    with socket.socket() as connection:
        if connection.connect_ex(('127.0.0.1', port)) == 0:
            print(f'{port} 포트가 사용 중입니다. {name}은 새로 실행하지 않습니다.')
            return
    with (PRIVATE / (name + '.log')).open('a') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log,
            stderr=subprocess.STDOUT, start_new_session=True)
    pid_file.write_text(str(process.pid))
    print(name, '시작 요청. 로그:', PRIVATE / (name + '.log'))

# localhost로 제한합니다. 컨테이너 API7 연결이 필요하면 승인된 실행 구성에서 별도 조정합니다.
start('keycloak', 18180, [str(home / 'bin/kc.sh'), 'start-dev', '--db=dev-file',
    '--http-host=127.0.0.1', '--http-port=18180', '--hostname=http://localhost:18180',
    '--hostname-backchannel-dynamic=true', '--import-realm'])
start('frontend', 18100, ['jwebserver', '-b', '127.0.0.1', '-p', '18100', '-d', str(ROOT / 'frontend')])
print('실습 화면: http://localhost:18100/ · Keycloak: http://localhost:18180/admin/')
print('계정 정보 파일:', credentials)
