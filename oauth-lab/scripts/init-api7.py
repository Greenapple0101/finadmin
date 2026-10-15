#!/usr/bin/env python3
"""최초 실습 Route만 만듭니다. 이후 실제 API7 UI에서 수정한 설정은 덮어쓰지 않습니다."""
import json
from api7_admin import ROOT, call, ENTRIES

for kind, name, file in ENTRIES:
    status, _ = call('GET', kind, name)
    if status == 200:
        print('이미 존재하므로 유지:', name)
        continue
    if status != 404:
        raise SystemExit('기존 설정 확인 실패 HTTP ' + str(status))
    status, result = call('PUT', kind, name, json.loads((ROOT / 'gateway' / file).read_text()))
    if status not in (200, 201):
        raise SystemExit('등록 실패 HTTP ' + str(status))
    print('최초 등록:', name)
