#!/usr/bin/env python3
"""실제 Keycloak 로그인 → API7 → ITSM 업무 흐름을 검증합니다.

실행마다 실습 요청 4건을 추가합니다. 3건을 완료하고 B회사 1건은 접수 상태로 남깁니다.
기존 데이터는 삭제하지 않습니다.
--restart를 붙이면 FinAdmin만 재시작하여 저장된 이력을 다시 조회합니다.
결과는 .local/itsm-verification.json에 저장하며 토큰·비밀번호는 남기지 않습니다.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import re
import subprocess
import time
import uuid
from ldap_support import read_values, LDAP_USERS, COMPANY_A, COMPANY_B
from verify import ROOT, GATEWAY, ACCESS, ADMIN, login, http, wait_ready

# 기존 검증 도구의 응답 출처 검사와 결과 형식을 재사용합니다.
spec = importlib.util.spec_from_file_location('gateway_checks', ROOT / 'scripts/verify-gateway-rbac.py')
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)
check, record = gateway.check, gateway.record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    completed, request_ids = False, []
    run = uuid.uuid4().hex[:8]
    try:
        values = read_values()
        tokens = {name: login(name, values['LAB_' + name.upper() + '_PASSWORD'])
                  for name in ('alice', 'bob', 'admin', 'outsider')}
        tokens.update({name: login(name, values[info[0]]) for name, info in LDAP_USERS.items()})
        base = GATEWAY + '/admin/api/itsm'
        people = {}
        for name, token in tokens.items():
            people[name] = check(name + ': verified identity and company', 200, base + '/me', token, layer='finadmin')
            record(name + ': expected onboarding company', people[name]['companyId'] == (COMPANY_B if 'outsider' in name else COMPANY_A))
        for label, root in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
            denied = 'gateway-policy' if label == 'gateway' else 'finadmin'
            check(label + ': missing token', 401, root + '/api/itsm/me', layer='gateway-jwt' if label == 'gateway' else 'finadmin')
            check(label + ': real summary requires operator', 403, root + '/api/itsm/summary', tokens['alice'], layer=denied)
        for prefix in ('', 'ldap-'):
            owner, reviewer, operator = (prefix + n for n in ('alice', 'bob', 'admin'))
            request = check(prefix + 'create request', 201, base + '/requests', tokens[owner], 'POST',
                            {'serviceName': 'ITSM 검증 ' + run + ' ' + owner, 'reason': '요청·승인·처리 완료 실습',
                             'companyId': COMPANY_B, 'requesterId': people[operator]['userId'], 'status': 'COMPLETED'}, layer='finadmin')
            request_ids.append(request['id'])
            path = '/api/itsm/requests/' + request['id']
            record(prefix + 'body cannot replace company, requester or state',
                   request['companyId'] == COMPANY_A and request['requesterId'] == people[owner]['userId'] and request['status'] == 'REQUESTED')
            for label, root in [('gateway', GATEWAY + '/admin'), ('direct', ADMIN)]:
                denied = 'gateway-policy' if label == 'gateway' else 'finadmin'
                check(prefix + label + ': user cannot approve', 403, root + path + '/approve', tokens[owner], 'POST', layer=denied)
                check(prefix + label + ': approver cannot complete', 403, root + path + '/complete', tokens[reviewer], 'POST', {'note': '권한 부족 검사'}, layer=denied)
                check(prefix + label + ': other company cannot view request', 403, root + path, tokens['outsider'], layer='finadmin')
            check(prefix + 'cannot complete before approval', 409, GATEWAY + '/admin' + path + '/complete', tokens[operator], 'POST', {'note': '순서 검사'}, layer='finadmin')
            approved = check(prefix + 'approve', 200, GATEWAY + '/admin' + path + '/approve', tokens[reviewer], 'POST', layer='finadmin')
            record(prefix + 'approval actor and time recorded', approved['status'] == 'APPROVED' and approved['approverId'] == people[reviewer]['userId'] and bool(approved['approvedAt']))
            check(prefix + 'duplicate approval rejected', 409, GATEWAY + '/admin' + path + '/approve', tokens[reviewer], 'POST', layer='finadmin')
            check(prefix + 'empty completion rejected', 400, GATEWAY + '/admin' + path + '/complete', tokens[operator], 'POST', {'note': ' '}, layer='finadmin')
            done = check(prefix + 'complete', 200, GATEWAY + '/admin' + path + '/complete', tokens[operator], 'POST', {'note': '테스트 환경 이용 방법을 안내했습니다. 자동 발급 없음.'}, layer='finadmin')
            record(prefix + 'completion actor, time and result persisted', done['status'] == 'COMPLETED' and done['completedBy'] == people[operator]['userId'] and bool(done['completedAt']) and bool(done['completionNote']))
            check(prefix + 'duplicate completion rejected', 409, GATEWAY + '/admin' + path + '/complete', tokens[operator], 'POST', {'note': '중복 검사'}, layer='finadmin')

        # admin에게도 자기 승인 금지와 회사 경계가 적용됩니다. B회사에 요청을 만들어 직접 확인합니다.
        for owner, reviewer in [('admin', 'bob'), ('outsider', 'outsider')]:
            request = check(owner + ': create boundary example', 201, base + '/requests', tokens[owner], 'POST',
                            {'serviceName': 'ITSM 경계 검증 ' + run + ' ' + owner, 'reason': '회사 경계 또는 자기 승인 검사'}, layer='finadmin')
            request_ids.append(request['id'])
            url = base + '/requests/' + request['id']
            if owner == 'admin':
                check('admin: self approval forbidden by business rule', 403, url + '/approve', tokens['admin'], 'POST', layer='finadmin')
                check('bob: approves operator request', 200, url + '/approve', tokens[reviewer], 'POST', layer='finadmin')
                check('admin: completes independently approved request', 200, url + '/complete', tokens['admin'], 'POST', {'note': '승인된 작업 결과를 기록했습니다.'}, layer='finadmin')
            else:
                for suffix, method, body in [('', 'GET', None), ('/approve', 'POST', None), ('/complete', 'POST', {'note': '회사 경계 검사'})]:
                    check('admin: other company forbidden ' + (suffix or 'detail'), 403, url + suffix, tokens['admin'], method, body, layer='finadmin')
                # B회사 처리자는 이 실습에 준비하지 않았으므로 B 요청은 접수 상태로 남깁니다.

        for name in ('alice', 'outsider', 'admin'):
            page = check(name + ': scoped request list', 200, base + '/requests', tokens[name], layer='finadmin')
            record(name + ': list has no other company', all(r['companyId'] == people[name]['companyId'] for r in page['items']))
            if name != 'admin':
                record(name + ': ordinary employee sees only own requests', all(r['requesterId'] == people[name]['userId'] for r in page['items']))
        summary = check('operator: actual company summary', 200, base + '/summary', tokens['admin'], layer='finadmin')
        record('summary is persisted company data, not fixed sample', summary['sampleData'] is False and summary['companyId'] == COMPANY_A and summary['completed'] >= 3)
        check('FinAccess still accepts same user token', 200, GATEWAY + '/access/api/me', tokens['alice'], layer='finaccess')
        sample = check('old diagnostic sample remains compatible', 200, GATEWAY + '/admin/api/admin/summary', tokens['admin'], layer='finadmin')
        record('old sample explicitly marked', sample['sampleData'] is True)

        # HTTP 응답의 이름표 외에도 이번 요청의 접근 로그에서 upstream 유무를 대조합니다.
        pattern = re.compile(r'\] (?P<method>[A-Z]+) (?P<path>/\S*) (?P<status>\d{3}) [0-9.]+ (?P<upstream>[0-9, :\-]+)\s*$')
        deadline, role_row, company_row = time.monotonic() + 10, None, None
        while time.monotonic() < deadline:
            lines = gateway.docker('logs', '--since', started.isoformat(), '--tail', '500', 'finlab-api7-gateway')
            rows = [match.groupdict() for line in lines.splitlines() if (match := pattern.search(line))]
            role_row = next((r for r in rows if r['path'].endswith(request_ids[0] + '/approve') and r['status'] == '403' and r['upstream'] == '-'), None)
            company_row = next((r for r in rows if r['path'].endswith(request_ids[0]) and r['status'] == '403' and r['upstream'] == '403'), None)
            if role_row and company_row: break
            time.sleep(0.5)
        record('access log: role denial stops at gateway', bool(role_row), evidence=role_row)
        record('access log: company denial comes from backend', bool(company_row), evidence=company_row)
        if args.restart:
            subprocess.run(['docker', 'compose', 'restart', 'finadmin'], cwd=ROOT, check=True, capture_output=True)
            wait_ready(ADMIN + '/api/hello')
            fresh = login('admin', values['LAB_ADMIN_PASSWORD'])
            detail = check('after backend restart: request still readable', 200, base + '/requests/' + request_ids[0], fresh, layer='finadmin')
            record('after backend restart: completion history retained', detail['status'] == 'COMPLETED' and bool(detail['approvedAt']) and bool(detail['completedAt']))
        completed = True
    finally:
        report = {'startedAt': started.isoformat(), 'verifiedAt': datetime.now(timezone.utc).isoformat(),
                  'completed': completed, 'total': len(gateway.CHECKS), 'passed': sum(c['passed'] for c in gateway.CHECKS),
                  'restartChecked': args.restart, 'requestIds': request_ids, 'checks': gateway.CHECKS,
                  'note': 'Actual PKCE login, API7 and Spring HTTP checks. Four requests added: three completed, one company-B request remains REQUESTED. No token or password retained. No LDAP group mutation.'}
        (ROOT / '.local/itsm-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'ITSM 검증 {len(gateway.CHECKS)}개 통과. .local/itsm-verification.json 저장')


if __name__ == '__main__':
    main()
