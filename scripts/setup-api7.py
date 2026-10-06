#!/usr/bin/env python3
"""공통 FinLab 정책을 API7 Enterprise의 서비스·라우트로 등록합니다.

실행: python3 scripts/setup-api7.py --apply --start
.local/api7의 기존 관리자 정보·인증서·그룹·DP 등록 정보를 사용합니다.
제품 설치/라이선스 신청/계정 생성은 하지 않으며, 다른 Gateway Group은 수정하지 않습니다.
"""
import argparse
import base64
import http.client
import importlib.util
import json
import copy
import re
from pathlib import Path
import socket
import ssl
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.local/api7'


class DashboardConnection(http.client.HTTPSConnection):
    def connect(self):
        # 로컬 설치의 공개 인증서를 이 연결에서만 신뢰합니다. TLS 검증을 끄지 않습니다.
        # 실제 연결은 loopback이며, 인증서의 서버 이름 api7ee-dashboard를 검사합니다.
        raw = socket.create_connection(('127.0.0.1', 7443), timeout=20)
        self.sock = self._context.wrap_socket(raw, server_hostname='api7ee-dashboard')


def call(method, path, payload=None):
    credentials = json.loads((PRIVATE / 'admin.json').read_text())
    context = ssl.create_default_context(cafile=str(PRIVATE / 'control-plane-ca.pem'))
    connection = DashboardConnection('api7ee-dashboard', 7443, context=context, timeout=20)
    credential = credentials['username'] + ':' + credentials['password']
    headers = {'Authorization': 'Basic ' + base64.b64encode(credential.encode()).decode(),
               'Content-Type': 'application/json'}
    connection.request(method, path, json.dumps(payload).encode() if payload is not None else None, headers)
    response = connection.getresponse()
    status, raw = response.status, response.read()
    connection.close()
    return status, json.loads(raw) if raw else {}


def desired():
    spec = importlib.util.spec_from_file_location('render_gateway', ROOT / 'scripts/render-gateway.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policies = json.loads((ROOT / 'infra/gateway/policies.json').read_text())
    identity = (ROOT / 'infra/gateway/enterprise-identity.lua').read_text()
    services, routes = [], []
    for source in module.configuration()['routes']:
        name = 'finlab-' + source['id']
        nodes = []
        for address, weight in source['upstream']['nodes'].items():
            host, port = address.rsplit(':', 1)
            nodes.append({'host': host, 'port': int(port), 'weight': weight})
        services.append((name, {'name': name, 'upstream': {'type': 'roundrobin', 'scheme': 'http', 'nodes': nodes}}))
        plugins = source['plugins']
        plugins['response-rewrite']['headers']['set']['X-Finlab-Gateway'] = 'api7-enterprise'
        routes.append((name, {'name': name, 'service_id': name,
            'paths': source.get('uris', [source.get('uri')]), 'priority': source['priority'], 'plugins': plugins}))
        app = source['id'].removesuffix('-api')
        if app not in policies:
            continue  # 로그인 전에도 화면 파일은 읽을 수 있습니다.
        policy = policies[app]
        plugins['serverless-post-function']['functions'] = [identity.replace(
            '__AUDIENCE__', policy['audience']).replace('__LEGACY__', str(app == 'legacy').lower())]
        # 넓은 /admin/* Route는 표에 없는 요청을 막는 안전망으로만 남깁니다.
        # OIDC rewrite 이후 access 단계에서 실행되므로 토큰 없는 요청은 먼저 401입니다.
        plugins['fault-injection'] = {'abort': {'http_status': 403,
            'body': json.dumps({'message': 'No policy for this method and path', 'rejectedBy': 'gateway-policy'})}}
        for rule in policy['rules']:
            path = policy['prefix'] + rule['path']
            route_name = 'finlab-' + app + '-' + rule['method'].lower() + '-' + re.sub(
                '[^a-z0-9]+', '-', rule['path'].lower()).strip('-')
            selected = copy.deepcopy(plugins)
            selected.pop('fault-injection')
            selected['acl'] = {
                'external_user_label_field': '$.resource_access["' + policy['audience'] + '"].roles',
                'external_user_label_field_key': 'roles', 'external_user_label_field_parser': 'table',
                'allow_labels': {'roles': rule['roles']}, 'rejected_code': 403,
                'rejected_msg': 'Required application role missing (API7 ACL)'}
            # Native Route가 메서드와 원래 URI를 검사합니다. 인코딩/중복 슬래시 우회를 막습니다.
            pattern = '^' + re.escape(path).replace(r'\{id\}', '[A-Za-z0-9-]+') + r'(?:\?.*)?$'
            routes.append((route_name, {'name': route_name, 'service_id': name,
                'paths': [path.split('{id}')[0] + '*' if '{id}' in path else path],
                'methods': [rule['method']], 'vars': [['real_request_uri', '~~', pattern]],
                'priority': 200, 'plugins': selected}))
    return services, routes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    group = json.loads((PRIVATE / 'group.json').read_text())
    if group['name'] != 'finlab-rbac':
        raise SystemExit('FinLab 전용 그룹이 아닙니다.')
    services, routes = desired()
    if not args.apply:
        print(f'적용 예정: finlab-rbac 그룹 / 서비스 {len(services)}개 / 경로 {len(routes)}개. --apply로 적용합니다.')
        return
    for kind, entries in [('services', services), ('routes', routes)]:
        for name, payload in entries:
            status, value = call('PUT', '/apisix/admin/' + kind + '/' + name + '?gateway_group_id=' + group['id'], payload)
            if status not in (200, 201):
                # 관리 응답 전체에는 민감한 정보가 있을 수 있으므로 오류 설명만 제한해 표시합니다.
                raise RuntimeError(f'{kind}/{name}: HTTP {status}: ' + str(value.get('error_msg', 'registration failed'))[:1200])
            print('적용 완료:', kind, name)
    # 이전에 이 스크립트가 만든 Route만 정리합니다. 다른 운영자의 Route는 건드리지 않습니다.
    manifest = PRIVATE / 'managed-routes.json'
    current = {name for name, _ in routes}
    previous = set(json.loads(manifest.read_text())) if manifest.exists() else set()
    for name in sorted(previous - current):
        status, _ = call('DELETE', '/apisix/admin/routes/' + name + '?gateway_group_id=' + group['id'])
        if status not in (200, 204, 404):
            raise RuntimeError(f'이전 관리 Route 정리 실패: {name}: HTTP {status}')
    manifest.write_text(json.dumps(sorted(current)))
    if args.start:
        subprocess.run(['docker', 'compose', '-f', 'compose.api7.yaml', 'up', '-d'], cwd=ROOT, check=True)
    print('API7 Enterprise http://localhost:18091 설정 등록 완료. 실제 요청 검증은 별도로 실행하세요.')


if __name__ == '__main__':
    main()
