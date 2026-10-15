# 발표 전에 이해할 핵심

## 네 주체와 Grant

이 실습의 사용자는 Resource Owner, 브라우저·oauth-cli는 Client, Keycloak은 Authorization Server, FinAccess·FinAdmin은 Resource Server입니다. API7은 USER·ADMIN API 앞에서 같은 토큰을 검사하는 Gateway입니다. 화면은 FinAccess가 제공하고 API 호출은 두 앱 모두 API7을 경유합니다.

인증은 누구인지 확인하는 것이고, 인가는 그 신원이 어떤 API를 사용할 수 있는지 판단하는 것입니다. OAuth2는 API 접근 권한 위임의 틀이며 사용자 로그인 자체의 표준은 아닙니다. Keycloak은 토큰 발급 과정에서 사람을 인증합니다. OIDC는 OAuth2 위에 ID Token 등 로그인 결과를 표준화한 계층을 추가합니다. 현재 앱은 Access Token만 사용합니다.

| 방식 | 이해할 핵심 | 이번 상태 |
|---|---|---|
| Authorization Code + PKCE | 브라우저 로그인 후 code를 받고, 처음 만든 verifier와 함께 토큰으로 교환. 코드를 가로채기만 해서는 교환하기 어렵게 함 | FinAccess 실제 구현·LDAP 로그인 확인 |
| Device Authorization Grant | CLI가 코드를 요청하고 사람이 Keycloak 기본 화면에서 로그인·승인. CLI는 서버가 정한 간격으로 결과 확인 | oauth-cli 실제 구현·ADMIN curl 200 확인 |
| Client Credentials | 사람 대신 서비스 자신이 Client 인증 정보로 토큰을 받음 | 개념 학습. 사람인 관리자의 로그인 대체로 사용하지 않음 |
| Implicit | 토큰을 브라우저 리다이렉트 응답으로 바로 전달하던 방식 | 개념만 학습. 비활성화 |
| Password Grant | 앱이 사람의 비밀번호를 직접 받아 토큰 서버로 전달 | 사용자 앱·CLI에서 비활성화. 설정 도우미의 로컬 master 관리용 호출과 구분 |
| Refresh Token | 새 로그인 없이 Access Token을 재발급받는 자격 증명 | FinAccess의 수동 갱신 버튼. 자동 갱신 미구현 |

PKCE가 비밀번호나 토큰을 암호화하는 것은 아닙니다. 전송 암호화는 TLS의 역할입니다. 현재 localhost HTTP는 개발 실습 설정입니다.

출처: [OAuth2 RFC 6749](https://www.rfc-editor.org/rfc/rfc6749), [PKCE RFC 7636](https://www.rfc-editor.org/rfc/rfc7636), [Device Grant RFC 8628](https://www.rfc-editor.org/rfc/rfc8628), [보안 권고 RFC 9700](https://www.rfc-editor.org/rfc/rfc9700).

## JWT와 Role

JWT는 Header.Payload.Signature의 세 부분으로 표현됩니다. Base64URL 인코딩은 암호화가 아니므로 내용은 읽을 수 있습니다. Keycloak의 개인 키로 만든 RS256 서명을 API7과 Spring이 공개 키로 검증합니다. Payload를 USER에서 ADMIN으로 바꿔도 올바른 서명이 없으면 거절됩니다.

- `iss`: 신뢰하는 발급자 oauth-lab Realm인지.
- `aud`: 우리 실습 API인 oauth-api용인지. 역할과는 별개입니다.
- `sub`: Keycloak 사용자 식별자. LDAP의 entryUUID를 이용한 사용자 연결과 함께 유지됩니다.
- `exp`: 만료 시각. `nbf`가 있으면 사용 가능한 시작 시각도 확인합니다.
- `resource_access.oauth-api.roles`: USER 또는 ADMIN. 토큰 검증 후에만 사용합니다.
- `department`: LDAP의 ou에서 온 부서명. Role을 늘리거나 부서별 접근 규칙을 만든 것은 아닙니다.

`demo.read` scope와 USER Role은 다른 개념입니다. 현재 API 정책은 Role을 검사하며 scope별 API 권한 분리를 별도로 구현하지 않았습니다. 토큰이 없거나 검증에 실패하면 401, 토큰은 유효하지만 역할이 부족하면 403입니다.

API7은 `openid-connect` → `acl` → upstream 전달, Spring은 Bearer 추출 → JwtDecoder → 역할 변환 → 접근 규칙 → Controller 순서입니다. JWKS 조회·캐시는 있을 수 있지만 API 요청마다 LDAP 비밀번호를 조회하지는 않습니다.

근거: gateway/finaccess-route.json, gateway/finadmin-route.json, 두 앱 SecurityConfig.java. [API7 OIDC 설정](https://docs.api7.ai/hub/openid-connect/configuration), [ACL 설정](https://docs.api7.ai/hub/acl/configuration), [Spring Resource Server](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html).

## LDAP 사용자·부서가 API7에 간다는 뜻

**이번에 확인한 경로**는 LDAP의 uid·ou·그룹 → Keycloak User Federation → JWT의 sub·department·roles → API7 검증·전달 → FinAdmin 응답입니다. Keycloak은 조회용 Bind 계정으로 명부를 읽고, 직원의 비밀번호 확인은 LDAP에서 수행합니다. 비밀번호를 JWT나 Keycloak 사용자 속성으로 복사하지 않습니다.

LDAP는 Mac에서 네이티브 실행하며, READ_ONLY·Import users·NO_CACHE와 department mapper의 always.read.value.from.ldap를 설정했습니다. LDAP 그룹 USER/ADMIN은 Keycloak /ldap/USER·/ldap/ADMIN 그룹을 통해 같은 이름의 Client Role로 연결합니다. 부서는 LDAP ou → Keycloak department → 토큰 department로 전달합니다.

실제 실험에서 ldap-admin의 부서를 Operations→Support로 바꾼 뒤 새 로그인한 토큰에는 Support가, 이미 발급한 토큰에는 Operations가 남았습니다. 실험 뒤 Operations로 복원했습니다. **기존 JWT는 디렉터리의 실시간 조회 결과가 아니라 발급 당시 정보**입니다.

[Keycloak LDAP 공식 문서](https://www.keycloak.org/docs/latest/server_admin/index.html#_ldap).

**다른 의미의 동기화**는 API7 관리 콘솔에 로그인할 운영자 계정을 만드는 것입니다. API7의 [SCIM Provisioning for Dashboard](https://docs.api7.ai/api7-gateway/security-and-compliance/authenticate/scim)는 이 관리 사용자 수명주기를 다룹니다. 서비스 API 호출자의 JWT Role과 관리 콘솔 RBAC를 같은 대상으로 보면 안 됩니다.

LDAP→Keycloak 연결만으로 API7의 SCIM 호출이 자동 생기지는 않습니다. 관리 사용자 프로비저닝이 목표라면 전달할 사용자 범위·관리 역할·비활성화 정책과 별도 SCIM 연계 주체를 정해야 합니다. 이번에는 구조를 검토했고, **SCIM 브리지·관리자 계정 자동 생성·자동 퇴사 처리는 구현하지 않았습니다.**
