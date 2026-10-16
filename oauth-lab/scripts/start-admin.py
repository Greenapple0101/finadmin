#!/usr/bin/env python3
"""FinAdmin ADMIN API를 하나의 로컬 Spring JVM으로 실행합니다."""
import os
from pathlib import Path
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
PRIVATE.mkdir(exist_ok=True, mode=0o700)
environment = os.environ.copy()
java_home = subprocess.check_output(['/usr/libexec/java_home', '-v', '21'], text=True).strip()
environment['JAVA_HOME'] = java_home
environment['PATH'] = java_home + '/bin:' + environment.get('PATH', '')

# 다른 앱이 쓰는 포트를 빼앗지 않습니다. 이전 실행은 PID와 실행 파일을 함께 확인합니다.
pid_file = PRIVATE / 'finadmin.pid'
if pid_file.exists():
    previous = subprocess.run(['ps', '-p', pid_file.read_text().strip(), '-o', 'command='], capture_output=True, text=True)
    if str(ROOT / 'build/libs/finadmin-oauth.jar') in previous.stdout:
        print('FinAdmin이 이미 실행 중입니다: http://localhost:18101/')
        raise SystemExit(0)
with socket.socket() as connection:
    if connection.connect_ex(('127.0.0.1', 18101)) == 0:
        raise SystemExit('18101 포트를 사용 중입니다. 기존 실습 서버를 중지한 뒤 실행하세요.')

# -p는 빌드할 폴더입니다. oauth-lab의 소스와 설정으로 실행 JAR을 만듭니다.
subprocess.run([str(ROOT.parent / 'gradlew'), '-p', str(ROOT), 'bootJar', '--console=plain'], env=environment, check=True)
with (PRIVATE / 'finadmin.log').open('a') as log:
    process = subprocess.Popen([str(Path(java_home) / 'bin/java'), '-Xms64m', '-Xmx256m', '-jar',
        str(ROOT / 'build/libs/finadmin-oauth.jar')], cwd=ROOT, env=environment,
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
pid_file.write_text(str(process.pid))
print('FinAdmin 시작 요청: http://localhost:18101/')
print('기동 결과 로그:', PRIVATE / 'finadmin.log')
