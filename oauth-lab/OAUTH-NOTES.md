# 발표 전에 이해할 핵심

## 네 주체와 Grant

이 실습의 사용자는 Resource Owner, 브라우저·oauth-cli는 Client, Keycloak은 Authorization Server, FinAccess·FinAdmin은 Resource Server입니다. API7은 USER·ADMIN API 앞에서 같은 토큰을 검사하는 Gateway입니다. 화면은 FinAccess가 제공하고 API 호출은 두 앱 모두 API7을 경유합니다.

인증은 누구인지 확인하는 것이고, 인가는 그 신원이 어떤 API를 사용할 수 있는지 판단하는 것입니다. OAuth2는 API 접근 권한 위임의 틀이며 사용자 로그인 자체의 표준은 아닙니다. Keycloak은 토큰 발급 과정에서 사람을 인증합니다. OIDC는 OAuth2 위에 ID Token 등 로그인 결과를 표준화한 계층을 추가합니다. 현재 앱은 Access Token만 사용합니다.

| 방식 | 이해할 핵심 | 이번 상태 |
|---|---|---|
| Authorization Code + PKCE | 브라우저 로그인 후 code를 받고, 처음 만든 verifier와 함께 토큰으로 교환. 코드를 가로채기만 해서는 교환하기 어렵게 함 | FinAccess의 Keycloak 자체 계정 로그인 |
| Device Authorization Grant | CLI가 코드를 요청하고 사람이 Keycloak 기본 화면에서 로그인·승인. CLI는 서버가 정한 간격으로 결과 확인 | oauth-cli의 Keycloak Device Grant |
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
- `sub`: Keycloak 자체 사용자 식별자.
- `exp`: 만료 시각. `nbf`가 있으면 사용 가능한 시작 시각도 확인합니다.
- `resource_access.oauth-api.roles`: USER 또는 ADMIN. 토큰 검증 후에만 사용합니다.

`demo.read` scope와 USER Role은 다른 개념입니다. 현재 API 정책은 Role을 검사하며 scope별 API 권한 분리를 별도로 구현하지 않았습니다. 토큰이 없거나 검증에 실패하면 401, 토큰은 유효하지만 역할이 부족하면 403입니다.

API7은 `openid-connect` → `acl` → upstream 전달, Spring은 Bearer 추출 → JwtDecoder → 역할 변환 → 접근 규칙 → Controller 순서입니다. JWKS 조회·캐시는 있을 수 있지만 API 요청마다 사용자 비밀번호를 다시 확인하지는 않습니다.

근거: gateway/finaccess-route.json, gateway/finadmin-route.json, 두 앱 SecurityConfig.java. [API7 OIDC 설정](https://docs.api7.ai/hub/openid-connect/configuration), [ACL 설정](https://docs.api7.ai/hub/acl/configuration), [Spring Resource Server](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html).

## 계정·역할과 관리 콘솔 권한

Keycloak 자체 계정 alice에는 USER, admin에는 ADMIN 역할을 연결합니다. 발급된 토큰의 역할로 API7과 Spring이 API 접근을 판단합니다. 사용자 역할을 바꾼 뒤에는 새 토큰을 발급해 비교합니다. 기존 JWT는 발급 당시 역할을 유지합니다.

API7 관리 콘솔의 운영자 권한은 앱 사용자의 USER·ADMIN과 별개입니다. Keycloak에서 앱 계정을 만들었다고 API7 관리 운영자가 자동 생성되지는 않습니다. SCIM 운영자 자동 생성은 이번 실습에 구현하지 않았습니다.
