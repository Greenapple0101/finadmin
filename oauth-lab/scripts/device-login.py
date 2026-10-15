#!/usr/bin/env python3
"""Keycloak의 기본 화면에서 사람이 로그인한 뒤 curl용 토큰을 받습니다. 별도 로그인 UI는 없습니다."""
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local'
PRIVATE.mkdir(exist_ok=True, mode=0o700)
BASE = 'http://localhost:18180/realms/oauth-lab/protocol/openid-connect'

def post(endpoint, values):
    request = urllib.request.Request(BASE + endpoint, data=urllib.parse.urlencode(values).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        return json.load(error)

# USER 계정으로 로그인하면 USER 토큰, ADMIN 계정이면 ADMIN 토큰이 나옵니다.
# CLI가 비밀번호를 받지 않습니다. 비밀번호는 Keycloak 기본 로그인 화면에 입력합니다.
device = post('/auth/device', {'client_id': 'oauth-cli', 'scope': 'demo.read'})
if 'device_code' not in device:
    raise SystemExit('Device 요청 실패: ' + device.get('error', 'unknown'))
print('주소:', device['verification_uri'], flush=True)
print('본인이 시작한 요청의 코드인지 확인:', device['user_code'], flush=True)
webbrowser.open(device['verification_uri_complete'])
interval = device['interval']
deadline = time.monotonic() + device['expires_in']
while time.monotonic() < deadline:
    # 서버가 정한 간격보다 빨리 확인하지 않습니다. slow_down을 받으면 간격을 늘립니다.
    time.sleep(interval)
    result = post('/token', {'client_id': 'oauth-cli',
        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code', 'device_code': device['device_code']})
    if 'access_token' in result:
        path = PRIVATE / 'curl-header'
        path.touch(mode=0o600, exist_ok=True); path.chmod(0o600)
        path.write_text('Authorization: Bearer ' + result['access_token'] + '\n')
        print('토큰 발급 완료. 원문은 출력하지 않습니다. 유효기간:', result['expires_in'], '초')
        print('curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/me')
        break
    if result.get('error') == 'slow_down':
        interval += 5
    elif result.get('error') != 'authorization_pending':
        raise SystemExit('인증 종료: ' + result.get('error', 'unknown'))
else:
    raise SystemExit('로그인 시간이 만료됐습니다. 다시 시작하세요.')
