#!/usr/bin/env python3
"""기존 API7의 finlab-rbac 그룹에 실습 경로 네 개만 추가합니다. 기존 경로는 삭제하지 않습니다."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
routes = json.loads((ROOT / 'gateway/routes.json').read_text())
if '--apply' not in sys.argv:
    print('추가할 Route:', ', '.join(route['name'] for route in routes))
    print('RUNBOOK의 실행 조건을 확인하고 --apply로 등록하세요.')
    raise SystemExit(0)

# API7 관리 인증과 로컬 인증서 검증은 기존 도구를 재사용합니다.
# 관리 비밀번호나 라이선스 파일을 이 실습 폴더나 JSON에 복사하지 않습니다.
spec = importlib.util.spec_from_file_location('api7_setup', ROOT.parent / 'scripts/setup-api7.py')
api7 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api7)
group = json.loads((api7.PRIVATE / 'group.json').read_text())
if group['name'] != 'finlab-rbac':
    raise SystemExit('FinLab 전용 그룹을 확인할 수 없어 중단합니다.')

for route in routes:
    status, _ = api7.call('PUT', '/apisix/admin/routes/' + route['name'] + '?gateway_group_id=' + group['id'], route)
    if status not in (200, 201):
        raise SystemExit(f"{route['name']}: HTTP {status}. 해당 Route 설정을 확인하세요.")
    print(route['name'], '등록 완료')
