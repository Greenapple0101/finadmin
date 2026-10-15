# API7 Enterprise 설정과 직접 확인할 곳

[문서 목차](../README.md) · 기준: 2026-10-15 · 제품: API7 Enterprise 3.10.2

## 제품 콘솔과 사용자 화면

| 주소 | 무엇을 하는 화면인가 |
|---|---|
| https://localhost:7443 | **실제 API7 제품 관리 UI**: Service·Route·Plugin 설정 |
| http://localhost:18100 | **FinAccess 사용자 화면**: Keycloak 로그인·API 응답 확인 |
| http://localhost:18090 | Gateway의 API 진입 주소. 현재 프런트 페이지 주소가 아님 |

현재 최소 구성은 제품 관리 API로 등록·조회했고 실제 트래픽으로 검증했습니다. **이 설정에 대한 브라우저 UI 클릭 수정까지 완료했다는 기록은 아닙니다.** 이전 docs/images/api7 캡처는 이전 금융·ITSM 구성의 화면이며 현재 oauth-* Route의 증거로 쓰지 않습니다.

## Service와 Route

제품 콘솔에서 Gateway Group **finlab-rbac** 안의 이름으로 찾습니다. Service는 전달할 서버, Route는 어떤 요청을 그 서버에 보낼지 정하는 규칙입니다.

| Service | upstream | 설정 파일 |
|---|---|---|
| oauth-finaccess | host.docker.internal:18100 | [finaccess-service.json](../../oauth-lab/gateway/finaccess-service.json) |
| oauth-finadmin | host.docker.internal:18101 | [finadmin-service.json](../../oauth-lab/gateway/finadmin-service.json) |

| Route | 경로 | 메서드 | priority | 필요 역할 |
|---|---|---|---|---|
| oauth-access-get | 정확한 /oauth-access/api/user/me | GET, OPTIONS | 300 | GET은 USER, OPTIONS는 CORS 사전 요청 |
| oauth-access-deny | /oauth-access, /oauth-access/* | 메서드 제한 없이 포착 | 290 | USER 검사 후 fallback 거절 |
| oauth-admin-get | /oauth-admin/api/admin/* | GET | 300 | ADMIN |
| oauth-admin-deny | /oauth-admin, /oauth-admin/* | 메서드 제한 없이 포착 | 290 | ADMIN 검사 후 fallback 거절 |

현재 최소 실습에서 관리하는 범위는 **2개 Service와 4개 Route**입니다. 기존 제품에 남아 있는 과거 Route까지 포함한 전체 개수가 아닙니다. 우선순위가 높은 허용 Route가 맞지 않을 때 낮은 fallback이 포착합니다.

## 인증 다음에 인가

| 플러그인 | 현재 하는 일 | 확인할 값 |
|---|---|---|
| openid-connect | Bearer JWT 검증 | bearer_only=true, use_jwks=true, RS256, issuer·audience 조건 |
| acl | 검증된 외부 사용자 역할 검사 | USER 또는 ADMIN을 allow_labels.roles에 지정 |
| proxy-rewrite | Gateway 접두어 제거 | /oauth-access 또는 /oauth-admin을 제거 |
| response-rewrite | 경유 표식 응답 헤더 | X-OAuth-Gateway: api7-enterprise |
| cors | FinAccess 브라우저 호출 허용 | USER 허용 Route에만 설정 |
| fault-injection | fallback의 의도적인 403 반환 | 두 deny Route의 abort.http_status=403 |

JWT 검증의 주요 값은 다음과 같습니다. 상세 원본: [USER Route](../../oauth-lab/gateway/finaccess-route.json), [ADMIN Route](../../oauth-lab/gateway/finadmin-route.json).

```text
client_id = oauth-api
discovery = http://host.docker.internal:18180/realms/oauth-lab/.well-known/openid-configuration
claim_validator.issuer.valid_issuers = [http://localhost:18180/realms/oauth-lab]
claim_validator.audience.claim = aud
claim_validator.audience.required = true
claim_validator.audience.match_with_client_id = true
token_signing_alg_values_expected = RS256
accept_none_alg = false
accept_unsupported_alg = false
iat_slack = 0
```

`set_access_token_header=true`와 `access_token_in_authorization_header=true`로 같은 Access Token을 백엔드에 전달합니다. ID Token·userinfo·refresh token을 백엔드용 헤더로 추가하지 않습니다. JWT를 단순 디코딩한 결과나 외부 X-Role 헤더를 권한 근거로 사용하지 않습니다.

ACL은 아래 경로에서 역할 배열을 읽습니다.

```text
external_user_label_field = $.resource_access["oauth-api"].roles
external_user_label_field_key = roles
external_user_label_field_parser = table
allow_labels.roles = [USER] 또는 [ADMIN]
rejected_code = 403
```

여기서 ACL은 **API를 호출하는 사람의 역할** 검사입니다. API7 관리 콘솔의 운영자 RBAC와는 다릅니다. 현재 Route에는 별도 Lua 권한 코드를 넣지 않았습니다. Spring은 Gateway 허용 결과만 믿지 않고 같은 JWT와 자기 Role 조건을 다시 검사합니다.

## 브라우저 CORS

화면 18100과 Gateway 18090은 포트가 달라 서로 다른 Origin입니다. Authorization 헤더를 사용하는 브라우저 요청을 위해 USER 허용 Route에 다음을 설정했습니다.

| 값 | 설정 |
|---|---|
| allow_origins | http://localhost:18100 |
| allow_methods | GET,OPTIONS |
| allow_headers | Authorization |
| expose_headers | X-OAuth-Gateway,X-Finlab-Backend |
| allow_credential | false |
| max_age | 5초 |

OPTIONS는 API7이 직접 응답하며 USER API를 실행하지 않습니다. 실제 GET에는 JWT·USER 검사가 적용됩니다. 다른 Origin의 OPTIONS도 200일 수 있지만 허용 Origin 헤더가 없어서 브라우저가 응답 사용을 허용하지 않습니다. CORS는 curl을 막는 네트워크 접근 통제가 아닙니다.

## UI에서 실습하는 순서

1. 실제 관리 UI에 로그인하고 finlab-rbac에서 위 Service·Route 이름을 찾습니다. 로컬 인증서 신뢰는 설치한 제품의 인증서를 기준으로 확인합니다.
2. Service의 upstream과 Route의 경로·메서드를 파일과 비교합니다.
3. USER Route의 JWT 검증·ACL·CORS 값을 확인합니다. ADMIN Route의 ACL은 ADMIN입니다.
4. 실험하려면 실습 Route 한 곳의 값을 기록한 뒤 변경합니다. 예: USER Route의 허용 역할을 잠시 ADMIN으로 바꾸면 USER는 Gateway 403, ADMIN은 Gateway를 통과해도 FinAccess에서 403입니다. 이는 예상 비교 시나리오이며 이번 UI 실험을 실행했다는 기록은 아닙니다.
5. 변경을 저장·적용한 뒤 [curl](../../oauth-lab/RUNBOOK.md)과 응답 헤더로 실제 검사 위치를 확인합니다. 끝나면 USER를 복원하고 USER 200을 재확인합니다.
6. `finadmin/oauth-lab`에서 `python3 scripts/export-api7.py`로 읽기 전용 내보내기를 실행합니다. 결과 `.local/api7-export.json`은 비공개 로컬 기록입니다.

`init-api7.py`는 없는 리소스만 최초 생성하고 기존 설정은 유지합니다. UI 수정 후 이 명령을 다시 실행해도 파일 내용으로 덮어쓰지 않습니다. 파일은 기준 설정, export는 조회 당시 실행 설정이므로 수정 후 둘을 비교해야 합니다. 이전 `apply-api7.py`·`gateway/routes.json`은 새 실습의 적용 도구가 아닙니다.

설정 존재 확인과 요청의 실제 통과·차단은 별개입니다. [10/15 결과](../../oauth-lab/RESULTS-2026-10-15.md)에서 두 앱 정상 요청, 잘못된 역할, 변조·만료, CORS를 구분했습니다.

공식 설명: [API7 ACL](https://docs.api7.ai/hub/acl), [JWT 검증 플러그인 설정](https://docs.api7.ai/hub/openid-connect/configuration), [CORS 설정](https://docs.api7.ai/hub/cors/configuration). 공식 문서의 최신 옵션 전체를 설치된 3.10.2에서 검증했다는 뜻은 아닙니다.
