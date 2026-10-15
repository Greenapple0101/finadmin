#!/usr/bin/env python3
"""API7 UI에서 바꾼 USER·ADMIN 실습 설정을 읽습니다. 제품 설정을 수정하지 않습니다."""
import json
from api7_admin import ROOT, call, ENTRIES

values = {}
for kind, name, _ in ENTRIES:
    status, result = call('GET', kind, name)
    if status != 200:
        raise SystemExit(name + ': 읽기 실패 HTTP ' + str(status))
    values[name] = result
# 추후 UI에 비밀값을 추가할 가능성까지 고려하여 내보내기는 .local에만 저장합니다.
path = ROOT / '.local/api7-export.json'
path.touch(mode=0o600, exist_ok=True); path.chmod(0o600)
path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + '\n')
print('API7 현재 설정 저장:', path)
