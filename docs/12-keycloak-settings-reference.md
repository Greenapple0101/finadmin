# FinLab Keycloak 설정값 목록과 확인 기록

> **과거 설정 스냅샷:** 이 목록은 2026-09-29 기준입니다. 2026-10-01에 LDAP Provider·Group Mapper·직원 4명·그룹 역할 연결이 추가됐습니다. 추가 설정값과 검증 결과는 [13번 LDAP 보고서](13-ldap-federation-hands-on.md)를 확인하세요.

> 서버 설정 확인: **2026-09-29 17:55:39 KST** · 실제 API 확인: **2026-09-29 17:57:23 KST**

> 이 문서는 설정값을 빠르게 찾는 부록입니다. 이유와 실습 순서는 [핸즈온 보고서](11-keycloak-hands-on-report.md)를 먼저 읽습니다. 실제 비밀번호·액세스 토큰 원문·비밀 키는 포함하지 않았습니다.

## 1. 확인 방법과 버전

- Keycloak 관리 API의 실제 서버 버전: `26.7.4`.
- 관리 API로 현재 값을 읽고, 저장소에 명시한 Realm·Client 항목과 대조했습니다. 해당 비교 항목의 차이: **0개**.
- 보고서 작성 중 설정 변경·계좌 생성·이체 실행은 하지 않았습니다. 기존 계정으로 로그인하고 읽기 전용 API를 호출했습니다.
- 로그인 자체로 세션이 만들어질 수 있습니다. “읽기 전용 API 확인”은 업무 데이터와 인증 정책을 수정하지 않았다는 의미입니다.
- 사용자 역할은 관리 API 조회 결과와 저장소의 실습 계정 정의를 대조했습니다. 아래 값은 확인 시점의 스냅샷입니다.

## 2. Realm 값

출처의 **직접 지정**은 Realm JSON에 있는 항목입니다. **서버 기본 구성**은 이 프로젝트 JSON에서 지정하지 않은 현재 값이며, 모든 버전의 고정 기본값을 의미하지 않습니다.

| JSON 필드 | 현재 값 | 출처 |
| --- | --- | --- |
| `realm` | `finlab` | 직접 지정 |
| `enabled` | `true` | 직접 지정 |
| `displayName` | `FinAccess 인증·인가 실습` | 직접 지정 |
| `sslRequired` | `none` | 직접 지정 |
| `registrationAllowed` | `false` | 직접 지정 |
| `resetPasswordAllowed` | `false` | 직접 지정 |
| `loginWithEmailAllowed` | `false` | 직접 지정 |
| `duplicateEmailsAllowed` | `false` | 서버 기본 구성 |
| `rememberMe` | `false` | 서버 기본 구성 |
| `verifyEmail` | `false` | 서버 기본 구성 |
| `bruteForceProtected` | `true` | 직접 지정 |
| `permanentLockout` | `false` | 서버 기본 구성 |
| `failureFactor` | `30` | 서버 기본 구성 |
| `waitIncrementSeconds` | `60` | 서버 기본 구성 |
| `minimumQuickLoginWaitSeconds` | `60` | 서버 기본 구성 |
| `quickLoginCheckMilliSeconds` | `1000` | 서버 기본 구성 |
| `maxFailureWaitSeconds` | `900` | 서버 기본 구성 |
| `maxDeltaTimeSeconds` | `43200` | 서버 기본 구성 |
| `accessTokenLifespan` | `300` | 직접 지정 |
| `accessTokenLifespanForImplicitFlow` | `900` | 서버 기본 구성 |
| `ssoSessionIdleTimeout` | `1800` | 직접 지정 |
| `ssoSessionMaxLifespan` | `36000` | 서버 기본 구성 |
| `offlineSessionIdleTimeout` | `2592000` | 서버 기본 구성 |
| `revokeRefreshToken` | `false` | 서버 기본 구성 |
| `refreshTokenMaxReuse` | `0` | 서버 기본 구성 |
| `accessCodeLifespan` | `60` | 서버 기본 구성 |
| `accessCodeLifespanUserAction` | `300` | 서버 기본 구성 |
| `accessCodeLifespanLogin` | `1800` | 서버 기본 구성 |
| `defaultSignatureAlgorithm` | `RS256` | 서버 기본 구성 |
| `browserFlow` | `browser` | 서버 기본 구성 |
| `registrationFlow` | `registration` | 서버 기본 구성 |
| `directGrantFlow` | `direct grant` | 서버 기본 구성 |
| `resetCredentialsFlow` | `reset credentials` | 서버 기본 구성 |
| `clientAuthenticationFlow` | `clients` | 서버 기본 구성 |
| `eventsEnabled` | `false` | 서버 기본 구성 |
| `adminEventsEnabled` | `false` | 서버 기본 구성 |
| `adminEventsDetailsEnabled` | `false` | 서버 기본 구성 |
| `internationalizationEnabled` | `false` | 서버 기본 구성 |

## 3. 앱·검증 Client 값

### finaccess-api

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finaccess-api` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `false` |
| `bearerOnly` | `true` |
| `standardFlowEnabled` | `false` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `없음` |
| `webOrigins` | `없음` |
| `defaultClientScopes` | `web-origins, acr, roles, profile, basic, email` |
| `optionalClientScopes` | `address, phone, organization, offline_access, microprofile-jwt` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `post.logout.redirect.uris` | `+` |


**Client Role:** `user`, `approver`, `admin`.

**전용 Mapper:**

없음.

### finadmin-api

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finadmin-api` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `false` |
| `bearerOnly` | `true` |
| `standardFlowEnabled` | `false` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `없음` |
| `webOrigins` | `없음` |
| `defaultClientScopes` | `web-origins, acr, roles, profile, basic, email` |
| `optionalClientScopes` | `address, phone, organization, offline_access, microprofile-jwt` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `post.logout.redirect.uris` | `+` |


**Client Role:** `user`, `admin`.

**전용 Mapper:**

없음.

### finlab-access-test

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finlab-access-test` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `true` |
| `bearerOnly` | `false` |
| `standardFlowEnabled` | `true` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `http://localhost:18090/` |
| `webOrigins` | `http://localhost:18090` |
| `defaultClientScopes` | `profile, basic, email` |
| `optionalClientScopes` | `없음` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `pkce.code.challenge.method` | `S256` |
| `post.logout.redirect.uris` | `http://localhost:18090/` |


**Client Role:** 없음.

**전용 Mapper:**

| 이름 | 타입 | 출력·설정 |
| --- | --- | --- |
| finadmin-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finadmin-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finadmin-api |
| finaccess-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finaccess-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finaccess-api |
| audience-finaccess-api | oidc-audience-mapper | included.client.audience=finaccess-api; id.token.claim=false; access.token.claim=true |


### finlab-expiry-test

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finlab-expiry-test` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `true` |
| `bearerOnly` | `false` |
| `standardFlowEnabled` | `true` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `http://localhost:18090/` |
| `webOrigins` | `http://localhost:18090` |
| `defaultClientScopes` | `profile, basic, email` |
| `optionalClientScopes` | `없음` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `pkce.code.challenge.method` | `S256` |
| `post.logout.redirect.uris` | `http://localhost:18090/` |
| `access.token.lifespan` | `2` |
| `backchannel.logout.session.required` | `true` |
| `backchannel.logout.revoke.offline.tokens` | `false` |


**Client Role:** 없음.

**전용 Mapper:**

| 이름 | 타입 | 출력·설정 |
| --- | --- | --- |
| audience-finadmin-api | oidc-audience-mapper | included.client.audience=finadmin-api; id.token.claim=false; access.token.claim=true |
| finadmin-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finadmin-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finadmin-api |
| finaccess-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finaccess-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finaccess-api |
| audience-finaccess-api | oidc-audience-mapper | included.client.audience=finaccess-api; id.token.claim=false; access.token.claim=true |


### finlab-not-before-test

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finlab-not-before-test` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `true` |
| `bearerOnly` | `false` |
| `standardFlowEnabled` | `true` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `http://localhost:18090/` |
| `webOrigins` | `http://localhost:18090` |
| `defaultClientScopes` | `profile, basic, email` |
| `optionalClientScopes` | `없음` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `pkce.code.challenge.method` | `S256` |
| `post.logout.redirect.uris` | `http://localhost:18090/` |
| `backchannel.logout.session.required` | `true` |
| `backchannel.logout.revoke.offline.tokens` | `false` |


**Client Role:** 없음.

**전용 Mapper:**

| 이름 | 타입 | 출력·설정 |
| --- | --- | --- |
| audience-finaccess-api | oidc-audience-mapper | included.client.audience=finaccess-api; id.token.claim=false; access.token.claim=true |
| audience-finadmin-api | oidc-audience-mapper | included.client.audience=finadmin-api; id.token.claim=false; access.token.claim=true |
| finadmin-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finadmin-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finadmin-api |
| finaccess-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finaccess-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finaccess-api |
| future-not-before | oidc-hardcoded-claim-mapper | id.token.claim=false; access.token.claim=true; claim.name=nbf; jsonType.label=long; claim.value=4102444800 |


### finlab-web

| 항목 | 현재 값 |
| --- | --- |
| `clientId` | `finlab-web` |
| `enabled` | `true` |
| `protocol` | `openid-connect` |
| `publicClient` | `true` |
| `bearerOnly` | `false` |
| `standardFlowEnabled` | `true` |
| `implicitFlowEnabled` | `false` |
| `directAccessGrantsEnabled` | `false` |
| `serviceAccountsEnabled` | `false` |
| `fullScopeAllowed` | `true` |
| `consentRequired` | `false` |
| `redirectUris` | `http://localhost:18090/` |
| `webOrigins` | `http://localhost:18090` |
| `defaultClientScopes` | `profile, basic, email` |
| `optionalClientScopes` | `없음` |

**추가 속성:**

| attributes의 키 | 값 |
| --- | --- |
| `pkce.code.challenge.method` | `S256` |
| `post.logout.redirect.uris` | `http://localhost:18090/` |


**Client Role:** 없음.

**전용 Mapper:**

| 이름 | 타입 | 출력·설정 |
| --- | --- | --- |
| finadmin-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finadmin-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finadmin-api |
| finaccess-api-roles | oidc-usermodel-client-role-mapper | multivalued=true; userinfo.token.claim=false; id.token.claim=false; access.token.claim=true; claim.name=resource_access.finaccess-api.roles; jsonType.label=String; usermodel.clientRoleMapping.clientId=finaccess-api |
| audience-finadmin-api | oidc-audience-mapper | included.client.audience=finadmin-api; id.token.claim=false; access.token.claim=true |
| audience-finaccess-api | oidc-audience-mapper | included.client.audience=finaccess-api; id.token.claim=false; access.token.claim=true |


API Client에 기본 연결된 Scope와 로그인 Client의 Scope 목록이 다른 것은 정상입니다. 현재 사용자 토큰은 `finlab-web` 또는 지정한 테스트 로그인 Client 기준으로 발급됩니다.

## 4. Realm에 있는 공용 Scope 15개

모든 Scope가 finlab-web에 연결되어 있는 것은 아닙니다. 다음 목록은 Realm 전체의 목록입니다.

| Scope | Protocol | finlab-web 연결 | Mapper 수 |
| --- | --- | --- | --- |
| AuthnContextClassRef | saml | 연결 안 함 | 1 |
| acr | openid-connect | 연결 안 함 | 1 |
| address | openid-connect | 연결 안 함 | 1 |
| basic | openid-connect | Default | 2 |
| email | openid-connect | Default | 2 |
| microprofile-jwt | openid-connect | 연결 안 함 | 2 |
| offline_access | openid-connect | 연결 안 함 | 0 |
| organization | openid-connect | 연결 안 함 | 1 |
| phone | openid-connect | 연결 안 함 | 2 |
| profile | openid-connect | Default | 14 |
| role_list | saml | 연결 안 함 | 1 |
| roles | openid-connect | 연결 안 함 | 3 |
| saml_organization | saml | 연결 안 함 | 1 |
| service_account | openid-connect | 연결 안 함 | 3 |
| web-origins | openid-connect | 연결 안 함 | 1 |

## 5. 사용자와 직접 할당된 역할

| 사용자 | Keycloak ID / sub | FinAccess 역할 | FinAdmin 역할 | 직접 Realm 역할 |
| --- | --- | --- | --- | --- |
| admin | 10000000-0000-4000-8000-000000000003 | user, approver, admin | admin | 없음 |
| alice | 10000000-0000-4000-8000-000000000001 | user | user | 없음 |
| bob | 10000000-0000-4000-8000-000000000002 | approver | user | 없음 |
| outsider | 10000000-0000-4000-8000-000000000004 | user | user | 없음 |

모든 실습 사용자는 Enabled=true, Email verified=true이고 Required actions가 비어 있습니다. 자격 증명 종류는 password이며 그 값은 수집·출력하지 않았습니다.

## 6. 기본 Flow·키·외부 연동

| Flow | 기본 제공 여부 | Provider |
| --- | --- | --- |
| browser | true | basic-flow |
| direct grant | true | basic-flow |
| registration | true | basic-flow |
| reset credentials | true | basic-flow |
| clients | true | client-flow |
| first broker login | true | basic-flow |
| docker auth | true | basic-flow |

| 키 알고리즘 | 종류 | 용도 | 상태 |
| --- | --- | --- | --- |
| AES | OCT | ENC | ACTIVE |
| RSA-OAEP | RSA | ENC | ACTIVE |
| HS512 | OCT | SIG | ACTIVE |
| RS256 | RSA | SIG | ACTIVE |

Realm Role: `offline_access`, `uma_authorization`, `default-roles-finlab`.

Groups 0개 · 외부 Identity providers 0개 · User federation providers 0개.

## 7. OIDC 주소

| Discovery 필드 | 현재 호스트 조회 값 |
| --- | --- |
| issuer | `http://localhost:18080/realms/finlab` |
| authorization_endpoint | `http://localhost:18080/realms/finlab/protocol/openid-connect/auth` |
| token_endpoint | `http://localhost:18080/realms/finlab/protocol/openid-connect/token` |
| jwks_uri | `http://localhost:18080/realms/finlab/protocol/openid-connect/certs` |
| end_session_endpoint | `http://localhost:18080/realms/finlab/protocol/openid-connect/logout` |
| userinfo_endpoint | `http://localhost:18080/realms/finlab/protocol/openid-connect/userinfo` |
| introspection_endpoint | `http://localhost:18080/realms/finlab/protocol/openid-connect/token/introspect` |
| code_challenge_methods_supported | `plain, S256` |

위 주소는 호스트에서 조회한 discovery 결과입니다. 컨테이너에서 사용할 내부 discovery·JWKS 주소는 [Compose](../compose.yaml)와 [APISIX 설정](../infra/apisix/apisix.yaml)에 따로 지정했습니다.

## 8. 이번에 새로 실행한 HTTP 확인 32건

기존 업무 데이터에 쓰기를 하지 않는 확인입니다. 사용자 로그인은 실제 Authorization Code + PKCE로 수행했습니다. 모든 내 정보 응답에서는 subject와 issuer도 발급받은 토큰과 일치함을 확인했습니다.

| 번호 | 사용자 / 토큰 | 요청 주소 | 예상 | 실제 |
| --- | --- | --- | --- | --- |
| 1 | alice | `http://localhost:18090/access/api/me` | 200 | 200 |
| 2 | alice | `http://localhost:18082/api/me` | 200 | 200 |
| 3 | alice | `http://localhost:18090/admin/api/me` | 200 | 200 |
| 4 | alice | `http://localhost:18083/api/me` | 200 | 200 |
| 5 | alice | `http://localhost:18090/admin/api/admin/summary` | 403 | 403 |
| 6 | alice | `http://localhost:18083/api/admin/summary` | 403 | 403 |
| 7 | bob | `http://localhost:18090/access/api/me` | 200 | 200 |
| 8 | bob | `http://localhost:18082/api/me` | 200 | 200 |
| 9 | bob | `http://localhost:18090/admin/api/me` | 200 | 200 |
| 10 | bob | `http://localhost:18083/api/me` | 200 | 200 |
| 11 | bob | `http://localhost:18090/admin/api/admin/summary` | 403 | 403 |
| 12 | bob | `http://localhost:18083/api/admin/summary` | 403 | 403 |
| 13 | admin | `http://localhost:18090/access/api/me` | 200 | 200 |
| 14 | admin | `http://localhost:18082/api/me` | 200 | 200 |
| 15 | admin | `http://localhost:18090/admin/api/me` | 200 | 200 |
| 16 | admin | `http://localhost:18083/api/me` | 200 | 200 |
| 17 | admin | `http://localhost:18090/admin/api/admin/summary` | 200 | 200 |
| 18 | admin | `http://localhost:18083/api/admin/summary` | 200 | 200 |
| 19 | outsider | `http://localhost:18090/access/api/me` | 200 | 200 |
| 20 | outsider | `http://localhost:18082/api/me` | 200 | 200 |
| 21 | outsider | `http://localhost:18090/admin/api/me` | 200 | 200 |
| 22 | outsider | `http://localhost:18083/api/me` | 200 | 200 |
| 23 | outsider | `http://localhost:18090/admin/api/admin/summary` | 403 | 403 |
| 24 | outsider | `http://localhost:18083/api/admin/summary` | 403 | 403 |
| 25 | anonymous | `http://localhost:18090/access/api/me` | 401 | 401 |
| 26 | anonymous | `http://localhost:18082/api/me` | 401 | 401 |
| 27 | anonymous | `http://localhost:18090/admin/api/me` | 401 | 401 |
| 28 | anonymous | `http://localhost:18083/api/me` | 401 | 401 |
| 29 | admin/access-only | `http://localhost:18090/access/api/me` | 200 | 200 |
| 30 | admin/access-only | `http://localhost:18082/api/me` | 200 | 200 |
| 31 | admin/access-only | `http://localhost:18090/admin/api/admin/summary` | 403 | 403 |
| 32 | admin/access-only | `http://localhost:18083/api/admin/summary` | 401 | 401 |

**결과: 32/32 통과.** `admin/access-only`는 admin 사용자로 `finlab-access-test` Client에서 받은 토큰입니다. 사용자 역할과 별개로 audience 차이를 확인합니다.

## 9. 실제 토큰에서 확인한 Claim 일부

아래는 서명·토큰 원문이 없는 설명용 발췌입니다. API 호출에 사용할 수 없습니다. 배열 순서는 의미가 없으며 발급 때 달라질 수 있습니다.

### alice

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "10000000-0000-4000-8000-000000000001",
  "aud": [
    "finadmin-api",
    "finaccess-api"
  ],
  "azp": "finlab-web",
  "scope": "openid email profile",
  "resource_access": {
    "finaccess-api": {
      "roles": [
        "user"
      ]
    },
    "finadmin-api": {
      "roles": [
        "user"
      ]
    }
  },
  "tokenLifetimeSeconds": 300
}
```

### bob

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "10000000-0000-4000-8000-000000000002",
  "aud": [
    "finadmin-api",
    "finaccess-api"
  ],
  "azp": "finlab-web",
  "scope": "openid email profile",
  "resource_access": {
    "finaccess-api": {
      "roles": [
        "approver"
      ]
    },
    "finadmin-api": {
      "roles": [
        "user"
      ]
    }
  },
  "tokenLifetimeSeconds": 300
}
```

### admin

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "10000000-0000-4000-8000-000000000003",
  "aud": [
    "finadmin-api",
    "finaccess-api"
  ],
  "azp": "finlab-web",
  "scope": "openid email profile",
  "resource_access": {
    "finaccess-api": {
      "roles": [
        "approver",
        "admin",
        "user"
      ]
    },
    "finadmin-api": {
      "roles": [
        "admin"
      ]
    }
  },
  "tokenLifetimeSeconds": 300
}
```

### outsider

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "10000000-0000-4000-8000-000000000004",
  "aud": [
    "finadmin-api",
    "finaccess-api"
  ],
  "azp": "finlab-web",
  "scope": "openid email profile",
  "resource_access": {
    "finaccess-api": {
      "roles": [
        "user"
      ]
    },
    "finadmin-api": {
      "roles": [
        "user"
      ]
    }
  },
  "tokenLifetimeSeconds": 300
}
```

`tokenLifetimeSeconds`는 JWT Claim 이름이 아니라 이 보고서가 `exp - iat`로 계산한 설명용 값입니다. 일반 토큰 네 개 모두 300초였습니다.

## 10. 이번 확인의 한계

- 32건은 역할·기본 인증·대상 구분을 확인한 읽기 전용 API 결과입니다. 모든 기능·모든 공격 조건을 새로 검증했다는 뜻이 아닙니다.
- 기존 46건 전체 시나리오와 Java 테스트 결과는 별도의 구현 단계 기록이며 [전체 검증 문서](08-end-to-end-verification.md)에 있습니다.
- UI에서 값을 저장하거나 새 Client를 만들지 않았습니다. 보고서는 조회 시점 이후의 변경을 자동 반영하지 않습니다.
- 실제 비밀번호와 필요할 때 갱신한 토큰은 Git 밖의 데스크탑 `finadmin-local-secrets.md`에서 관리합니다.
