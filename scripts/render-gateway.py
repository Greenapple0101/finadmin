#!/usr/bin/env python3
"""읽기 쉬운 정책표와 Lua 검사 함수를 실제 APISIX YAML로 조립합니다. 외부 라이브러리 불필요."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configuration():
    policies = json.loads((ROOT / 'infra/gateway/policies.json').read_text())
    template = (ROOT / 'infra/gateway/rbac.lua').read_text()
    routes = []
    for name, policy in policies.items():
        runtime = {'audience': policy['audience'], 'legacy': name == 'legacy', 'rules': []}
        for rule in policy['rules']:
            # 한 경로 조각만 일치합니다. {id}에 /, %, ; 등을 넣어 범위를 넓힐 수 없습니다.
            pattern = '^' + policy['prefix'] + rule['path'].replace('{id}', '[%w%-]+') + '$'
            runtime['rules'].append({**rule, 'pattern': pattern})
        routes.append({
            'id': name + '-api', 'uris': [policy['prefix'], policy['prefix'] + '/*'], 'priority': 100,
            'plugins': {
                'serverless-pre-function': {'phase': 'rewrite', 'functions': [(ROOT / 'infra/gateway/token-shape.lua').read_text()]},
                'openid-connect': {
                    'client_id': policy['audience'],
                    'discovery': 'http://keycloak:8080/realms/finlab/.well-known/openid-configuration',
                    'bearer_only': True, 'use_jwks': True, 'unauth_action': 'deny',
                    'token_signing_alg_values_expected': 'RS256', 'accept_none_alg': False,
                    'accept_unsupported_alg': False, 'iat_slack': 0,
                    'set_access_token_header': True, 'access_token_in_authorization_header': True,
                    'set_id_token_header': False, 'set_raw_id_token_header': False,
                    'set_userinfo_header': False, 'set_refresh_token_header': False,
                    'claim_validator': {
                        'issuer': {'valid_issuers': ['http://localhost:18080/realms/finlab']},
                        'audience': {'claim': 'aud', 'required': True, 'match_with_client_id': True}}},
                'serverless-post-function': {'phase': 'rewrite', 'functions': [
                    template.replace('__POLICY_JSON__', json.dumps(runtime, ensure_ascii=False))]},
                'proxy-rewrite': {'regex_uri': ['^' + policy['prefix'] + '/(.*)$', '/$1']},
                'response-rewrite': {'headers': {'set': {
                    'X-Finlab-Gateway': 'apisix', 'X-Finlab-Upstream': name}}}
            },
            'upstream': {'type': 'roundrobin', 'nodes': {policy['upstream']: 1}}
        })
    routes.append({'id': 'frontend', 'uri': '/*', 'priority': 0,
                   'plugins': {'response-rewrite': {'headers': {'set': {'X-Finlab-Gateway': 'apisix'}}}},
                   'upstream': {'type': 'roundrobin', 'nodes': {'web:80': 1}}})
    return {'routes': routes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='생성 결과와 저장된 YAML의 차이만 검사')
    args = parser.parse_args()
    # JSON도 YAML의 문법입니다. Python 표준 json으로 정확하게 이스케이프한 뒤 종료 표시를 붙입니다.
    text = '# 자동 생성: scripts/render-gateway.py / 원본: infra/gateway/policies.json, rbac.lua\n'
    text += json.dumps(configuration(), ensure_ascii=False, indent=2) + '\n#END\n'
    target = ROOT / 'infra/apisix/apisix.yaml'
    if args.check:
        if target.read_text() != text:
            raise SystemExit('정책표와 APISIX 설정이 다릅니다. render-gateway.py를 실행하세요.')
        print('Gateway 정책표와 생성 설정 일치')
    else:
        target.write_text(text)
        print('Gateway 설정 생성 완료')


if __name__ == '__main__':
    main()
