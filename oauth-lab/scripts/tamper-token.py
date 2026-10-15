#!/usr/bin/env python3
"""학습용 복사본의 USER를 ADMIN으로 바꿉니다. 서명은 고치지 않으므로 반드시 거절돼야 합니다."""
import base64
import json
from pathlib import Path

private = Path(__file__).resolve().parents[1] / '.local'
header = (private / 'curl-header').read_text().strip()
head, payload, signature = header.removeprefix('Authorization: Bearer ').split('.')
claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
if claims.get('resource_access', {}).get('oauth-api', {}).get('roles') != ['USER']:
    raise SystemExit('USER 계정으로 Device 로그인한 뒤 실행하세요. 원본은 변경하지 않습니다.')
claims['resource_access']['oauth-api']['roles'] = ['ADMIN']
changed = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
path = private / 'tampered-header'
path.touch(mode=0o600, exist_ok=True); path.chmod(0o600)
path.write_text('Authorization: Bearer ' + head + '.' + changed + '.' + signature + '\n')
print('변조 복사본 준비 완료. Gateway와 Spring의 예상 응답은 401입니다.')
