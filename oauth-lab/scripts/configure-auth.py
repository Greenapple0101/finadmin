#!/usr/bin/env python3
"""브라우저 PKCE와 CLI Device Grant의 Client·토큰 설정을 원본에 맞춥니다."""
import json
from keycloak_admin import call, ROOT

# 기존 사용자와 Realm은 유지합니다. 이름이 같은 실습 Client만 설정 원본과 맞춥니다.
realm = json.loads((ROOT / 'keycloak/realm.json').read_text(encoding='utf-8'))
for client in realm['clients']:
    if client['clientId'] == 'oauth-api':
        continue
    found = call('GET', '/clients?clientId=' + client['clientId'])
    if found:
        path = '/clients/' + found[0]['id']
        # 기존 Realm에서도 원본에서 제거한 토큰 Mapper가 남지 않게 맞춥니다.
        desired_mappers = {mapper['name'] for mapper in client['protocolMappers']}
        for mapper in call('GET', path + '/protocol-mappers/models'):
            if mapper['name'] not in desired_mappers:
                call('DELETE', path + '/protocol-mappers/models/' + mapper['id'])
        call('PUT', path, client)
    else:
        call('POST', '/clients', client)
    print('Client 준비:', client['clientId'])

print('Keycloak Client 설정 완료: 브라우저 PKCE · CLI Device Grant · audience/roles/subject.')
