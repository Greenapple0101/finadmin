# Keycloak 설정을 직접 따라 읽는 FinLab 실습 보고서

> **이 문서의 목표:** 콘솔의 설정을 보면서 “이걸 왜 만들었고, 토큰의 어느 부분을 바꾸며, 어느 코드가 사용하는지” 설명할 수 있게 되기.
>
> **대상:** Spring·OAuth·OIDC를 처음 배우는 개발자. 현재 실행 중인 `finlab` Realm을 기준으로 설명합니다.
>
> **확인일:** 2026-09-29. Keycloak 26.7.4의 실제 관리 API·콘솔과 두 저장소를 대조했습니다. 이번 작성 중에는 인증 설정과 업무 데이터를 수정하지 않았습니다. 로그인과 읽기 전용 API 검증은 수행했습니다.

## 먼저 읽는 순서

한 번에 모든 메뉴를 외울 필요는 없습니다. 다음 순서대로 콘솔을 옆에 열고 읽습니다.

| 순서 | 이 문서에서 읽을 부분 | 콘솔에서 확인할 곳 | 읽고 나면 답할 질문 |
| --- | --- | --- | --- |
| 1 | 1~3장 | 현재 Realm, Clients 목록 | 앱은 몇 개이며 Client는 왜 더 많을까? |
| 2 | 4~5장 | Realm settings, `finlab-web` Settings | 로그인과 토큰 발급은 어떻게 허용할까? |
| 3 | 6~7장 | API Client의 Roles, Users, Client scopes | 역할을 만든 뒤 토큰에 어떻게 넣을까? |
| 4 | 8~10장 | Scope Evaluate, 앱 화면, 소스 코드 | 토큰을 API가 어떻게 믿고 사용할까? |
| 5 | 11~14장 | 나머지 메뉴, 검증 기록 | 직접 재현하고 잘못된 설정을 찾을 수 있을까? |

짧게 구조를 먼저 보고 싶으면 [아키텍처 설명](10-architecture.md)을 읽습니다. 실제 값만 빨리 찾으려면 [설정값 목록과 이번 검증 결과](12-keycloak-settings-reference.md)를 봅니다.

---

## 1. 화면의 설정이 많아 보이는 이유

우리가 실제 서비스 흐름에 사용하는 Client는 세 개입니다.

- `finlab-web`: 브라우저에서 로그인하고 토큰을 받는 프런트엔드.
- `finaccess-api`: 회사·계좌·이체 업무를 처리하는 백엔드의 식별 이름.
- `finadmin-api`: 관리자 API를 제공하는 백엔드의 식별 이름.

이와 별도로 실패 상황을 확인하는 테스트 Client 세 개와, Keycloak이 기본으로 만든 Client 여섯 개가 있습니다. 그래서 **목록에는 12개가 보이지만, 우리가 구현한 Spring 백엔드는 두 개**입니다.

![FinLab 인증·인가 아키텍처](images/finlab-architecture.png)

### 1.1 용어를 우리 프로젝트에 대입하기

| 용어 | 쉬운 설명 | 우리 프로젝트의 예 |
| --- | --- | --- |
| 인증 Authentication | 누구인지 확인하기 | Keycloak에서 `alice`가 비밀번호로 로그인 |
| 인가 Authorization | 그 사람이 무엇을 할 수 있는지 판단하기 | `alice`는 관리자 요약을 볼 수 없고 `admin`은 볼 수 있음 |
| Realm | 사용자·Client·역할·로그인 정책을 묶어 관리하는 경계 | `finlab` |
| Client | Keycloak에 등록한 앱·서비스의 식별 정보 | `finlab-web`, `finadmin-api` |
| Client ID | 등록한 Client를 가리키는 이름 | 문자열 `finadmin-api` |
| Role | 사용자가 가진 권한의 이름표 | `user`, `approver`, `admin` |
| Claim | 토큰 안의 이름과 값 한 쌍 | `aud`, `sub`, `iss` |
| Mapper | 어떤 값을 토큰의 어디에 넣을지 정하는 설정 | `finadmin-api-roles` |
| Client scope | 여러 Mapper와 역할 범위 설정 등을 묶어 Client에 연결하는 단위 | `basic`, `profile`, `email` |
| Resource Server | 받은 액세스 토큰을 검사하고 API를 제공하는 서버 | FinAccess, FinAdmin |
| JWKS | 토큰 서명을 검사할 때 사용하는 공개 키 목록 | Keycloak의 `/certs` 주소 |

OAuth 2.0은 액세스 토큰으로 API 접근 권한을 전달하는 체계이고, OIDC는 그 위에 로그인 사용자의 신원을 표현하는 규칙을 더합니다. JWT는 여기서 사용하는 토큰의 표현 형식입니다. 세 이름은 같은 뜻이 아닙니다.

### 1.2 누가 무엇을 책임지는가

| 구성 요소 | 실제 담당하는 일 |
| --- | --- |
| Keycloak | 로그인, 사용자·역할 관리, 토큰 발급 |
| 브라우저 | 로그인 시작, 코드와 토큰 교환, 토큰을 붙인 API 요청 |
| APISIX | 요청 경로 선택, JWT 검증, 같은 Bearer 토큰 전달 |
| FinAccess | JWT 재검증, 앱 역할 확인, 회사 소속·이체 업무 규칙 확인 |
| FinAdmin | JWT 재검증, 관리자 역할 확인, 관리자 샘플 응답 |
| Keycloak DB | Keycloak의 사용자·역할·Client 설정 저장 |
| FinAccess DB | 회사·계좌·이체·업무 사용자 연결 정보 저장 |

Keycloak에 Client를 만든다고 Spring 서버가 생기지 않습니다. Spring 서버는 우리가 작성한 Java 앱을 따로 실행한 것입니다. Keycloak의 Client 등록과 실제 서버 실행을 나누어 생각하면 구조가 훨씬 명확해집니다.

## 2. `master`와 `finlab`, 두 관리자 계정 구분하기

### 콘솔에서 따라가기

1. [Keycloak 관리 콘솔](http://localhost:18080/admin/)을 엽니다.
2. `bootstrap-admin`으로 로그인합니다. 비밀번호는 데스크탑의 `finadmin-local-secrets.md`에서 확인합니다.
3. 현재 Realm이 `finlab`인지 확인합니다. 현재 콘솔에는 표시 이름인 **FinAccess 인증·인가 실습**이 보입니다.
4. Realm을 바꿀 때는 왼쪽 **Manage realms**에서 선택합니다.

현재 URL이 `/admin/master/console/#/finlab/...`처럼 보여도 이상하지 않습니다. `master` 계정으로 관리 콘솔에 로그인했고, `#/finlab` 아래의 Realm을 관리하고 있는 것입니다.

| 구분 | 소속 | 용도 |
| --- | --- | --- |
| `bootstrap-admin` | `master` | Keycloak 자체 설정을 관리하는 초기 관리자 |
| `admin` | `finlab` | 우리가 만든 앱의 관리자 API를 호출하는 실습 사용자 |
| `alice`, `bob`, `outsider` | `finlab` | 일반 사용자·승인자·다른 회사 사용자 검증 |

`admin`이라는 사용자 이름 자체가 권한을 주지는 않습니다. 그 사용자에게 어떤 Client Role이 연결되어 있고, Spring이 그것을 어떻게 검사하느냐가 중요합니다.

콘솔 상단의 temporary admin 안내는 초기 관리자 계정을 사용한다는 뜻입니다. 현재 로컬 실습의 상태를 설명하는 표시이며, 앱의 `admin` 역할과는 별개입니다. 이번 보고서 작성에서는 관리자 계정을 교체하지 않았습니다.

**직접 확인:** `finlab → Users`에는 실습 사용자 네 명이 있고 `bootstrap-admin`은 없습니다. 계정이 사라진 것이 아니라 소속 Realm이 다릅니다.

## 3. Clients 목록 12개를 분류하기

**경로:** 왼쪽 `Clients → Clients list`.

| 이름 | 구분 | 만든 이유 | 지금 학습할 우선순위 |
| --- | --- | --- | --- |
| `finlab-web` | 우리가 추가 | 브라우저 로그인·토큰 발급 | 가장 먼저 |
| `finaccess-api` | 우리가 추가 | 금융 업무 API의 audience·역할 구분 | 필수 |
| `finadmin-api` | 우리가 추가 | 관리자 API의 audience·역할 구분 | 필수 |
| `finlab-access-test` | 검증용으로 추가 | FinAccess 전용 토큰을 FinAdmin이 거절하는지 확인 | 핵심 흐름 다음 |
| `finlab-expiry-test` | 검증용으로 추가 | 실제 Keycloak 서명이 있는 만료 토큰 만들기 | 핵심 흐름 다음 |
| `finlab-not-before-test` | 검증용으로 추가 | 아직 사용할 수 없는 토큰을 거절하는지 확인 | 핵심 흐름 다음 |
| `account` | Keycloak 기본 | 사용자 계정 관리 기능 | 존재 이유만 이해 |
| `account-console` | Keycloak 기본 | 사용자 계정 관리 화면 | 존재 이유만 이해 |
| `admin-cli` | Keycloak 기본 | 관리 명령·관리 API 작업용 Client | 자동화 설명에서 확인 |
| `broker` | Keycloak 기본 | 외부 로그인 제공자 연동 관련 기능 | 현재 별도 연동 없음 |
| `realm-management` | Keycloak 기본 | Realm 관리 권한을 표현하는 Client | 앱의 admin과 구분 |
| `security-admin-console` | Keycloak 기본 | 지금 보고 있는 관리 콘솔 | 앱 프런트와 구분 |

**헷갈리는 점:** `admin-cli`는 Realm마다 존재할 수 있습니다. 우리 검증 스크립트가 설정 동기화에 사용하는 것은 `master` Realm의 `admin-cli`입니다. `finlab` 목록에 있는 동일한 이름의 Client와 호출 주소를 혼동하지 않습니다.

Client 목록에서 긴 UUID가 URL에 나타나면 그것은 Keycloak 내부 ID입니다. 앱 설정에서 사용하는 `client_id=finlab-web`의 값은 그 UUID가 아니라 **Client ID 문자열**입니다.

## 4. Realm settings: 실습 전체의 기본 규칙

**경로:** `Realm settings`. 아래의 “직접 지정”은 저장소의 Realm JSON에 적어 둔 값입니다. “서버 기본”은 해당 값을 JSON에 지정하지 않았고 현재 서버가 가진 기본 구성이라는 뜻입니다. 다른 버전의 보편적 기본값이라고 단정하지 않습니다.

### 4.1 Realm 이름과 로그인 옵션

| 설정/JSON 이름 | 현재 값 | 출처 | 의미와 선택 이유 |
| --- | --- | --- | --- |
| Realm name / `realm` | `finlab` | 직접 지정 | 토큰 발급자 URL에도 들어가는 실습 영역 이름 |
| Display name | FinAccess 인증·인가 실습 | 직접 지정 | 콘솔·로그인 화면에 보일 사람이 읽는 이름 |
| Enabled | On | 직접 지정 | Realm 사용 가능 |
| Require SSL / `sslRequired` | `none` | 직접 지정 | 로컬 HTTP 실습을 허용. 운영 HTTPS 구성은 별도 |
| User registration | Off | 직접 지정 | 실습 계정 네 명을 준비했으므로 회원가입 화면을 제공하지 않음 |
| Forgot password / `resetPasswordAllowed` | Off | 직접 지정 | 메일 기반 비밀번호 초기화 흐름을 구성하지 않음 |
| Login with email | Off | 직접 지정 | `alice` 같은 username으로 로그인 |
| Remember me | Off | 서버 기본 | 기억하기 옵션 사용 안 함 |
| Verify email | Off | 서버 기본 | 가입 후 이메일 확인 절차를 이번 실습에 추가하지 않음 |
| Duplicate emails | Off | 서버 기본 | 같은 이메일의 중복 사용을 허용하지 않는 현재 정책 |

주로 `General`, `Login`, `Security defenses`에서 확인합니다. UI 표시 이름과 JSON 이름이 완전히 같지 않아서 두 이름을 같이 적었습니다.

사용자의 `Email verified: On`과 Realm의 `Verify email: Off`는 다른 설정입니다. 전자는 **그 사용자에 저장된 확인 상태**, 후자는 **로그인 과정에서 이메일 확인을 요구할 정책**입니다. 우리는 실습 데이터를 확인된 상태로 준비했습니다. 실제 메일을 보내 검증했다는 뜻은 아닙니다.

### 4.2 토큰 시간과 로그인 세션 시간

**확인 위치:** `Realm settings → Tokens`, `Sessions`.

| 항목 | 현재 값 | 출처 | 이 프로젝트에서의 의미 |
| --- | --- | --- | --- |
| Access Token Lifespan | 300초, 5분 | 직접 지정 | 일반 실습 토큰의 유효 기간 |
| SSO Session Idle | 1,800초, 30분 | 직접 지정 | Keycloak 로그인 세션의 비활성 시간 제한 |
| SSO Session Max | 36,000초, 10시간 | 서버 기본 | 로그인 세션의 최대 유지 시간 |
| Access Code Lifespan | 60초 | 서버 기본 | 발급받은 코드를 토큰으로 교환할 수 있는 시간 |
| Login action timeout에 해당하는 값 | 1,800초 | 서버 기본 | `accessCodeLifespanLogin`의 현재 값 |
| User action timeout에 해당하는 값 | 300초 | 서버 기본 | `accessCodeLifespanUserAction`의 현재 값 |
| Offline Session Idle | 2,592,000초, 30일 | 서버 기본 | 현재 앱이 사용하지 않는 오프라인 세션 관련 값 |
| Revoke Refresh Token | Off | 서버 기본 | 현재 갱신 토큰 정책. 프런트는 갱신 기능 자체를 구현하지 않음 |

**5분이 지나면 무엇이 끝나는가?** API에 보낼 액세스 토큰의 유효 기간이 끝납니다. Keycloak의 로그인 세션과 같은 시계가 아닙니다. 현재 프런트는 자동 갱신하지 않고 다시 로그인하도록 안내합니다. 또한 로그인 요청에 `prompt=login`을 넣어 로그인 화면을 다시 보여 주도록 요청합니다.

메뉴에 SSO라는 단어가 있어도 여러 프런트 앱 간 SSO 시연을 구현했다는 뜻은 아닙니다. Keycloak의 세션 기능이 존재하는 것과 우리 실습의 검증 범위는 구분합니다.

### 4.3 반복 로그인 실패 방어

**경로:** `Realm settings → Security defenses → Brute force detection`.

`bruteForceProtected=true`는 우리가 켰습니다. 나머지 세부 값은 현재 서버 기본 구성을 사용합니다. `permanentLockout=false`, `failureFactor=30`, 대기 증가 60초, 최대 대기 900초 등의 값은 [설정값 목록](12-keycloak-settings-reference.md)에 적었습니다.

이 옵션은 비밀번호를 계속 추측하는 로그인 시도를 제한합니다. 관리자 API의 `admin` 역할 검사와는 다른 단계입니다. “정확히 30번까지는 언제나 로그인 가능하다”는 식으로 단순화하면 안 됩니다. 빠른 반복 실패에 대한 조건도 함께 적용되기 때문입니다.

**직접 확인:** 값을 읽고, “로그인 단계의 방어”라고 설명해 봅니다. 확인 목적으로 비밀번호를 계속 틀리게 넣을 필요는 없습니다.

## 5. `finlab-web`: 브라우저 로그인 설정을 하나씩 읽기

**경로:** `Clients → finlab-web → Settings`.

현재 26.7.4 콘솔에서 **Require PKCE와 PKCE Method는 Settings의 Capability config에 있습니다.** 예전 글의 다른 메뉴 위치와 달라도 현재 화면을 기준으로 찾습니다.

### 5.1 General settings와 Access settings

| 콘솔 필드 | 현재 값 | 쉬운 의미 | 맞지 않으면 생기는 일 |
| --- | --- | --- | --- |
| Client ID | `finlab-web` | 로그인 요청이 어느 앱에서 왔는지 표시 | 프런트의 `client_id`와 다르면 다른 Client를 찾거나 요청 실패 |
| Protocol | OpenID Connect | 이번 로그인에 쓰는 규약 | 현재 OIDC 프런트와 맞지 않음 |
| Name / Description | 비어 있음 | 선택적인 표시용 정보 | 비어 있어도 로그인 가능 |
| Root URL / Home URL / Admin URL | 비어 있음 | 상대 주소 기준·홈·관리 연동 등에 쓰는 별도 필드 | 우리는 절대 redirect 주소를 직접 지정하여 사용 |
| Valid redirect URIs | `http://localhost:18090/` | 로그인 후 코드와 함께 돌아올 허용 주소 | 불일치 시 `Invalid parameter: redirect_uri` 등으로 거절 |
| Valid post logout redirect URIs | `http://localhost:18090/` | 로그아웃 후 돌아올 허용 주소 | 허용되지 않은 복귀 주소가 거절될 수 있음 |
| Web origins | `http://localhost:18090` | 브라우저 JS의 교차 출처 요청을 허용할 출처 | 토큰 교환 시 브라우저 CORS 오류 가능 |

Redirect URI에는 마지막 `/`까지 있습니다. Origin은 `스킴 + 호스트 + 포트`이므로 경로와 마지막 `/`를 넣지 않습니다. `localhost`와 `127.0.0.1`은 같은 컴퓨터를 가리켜도 브라우저 출처와 문자열 주소 비교에서는 다릅니다. 이 실습은 안내된 `localhost` 주소로 열어야 합니다.

Web origins는 관리자 권한 목록이 아닙니다. 브라우저가 다른 출처의 응답을 읽을 수 있게 하는 CORS 설정입니다. 브라우저 밖의 프로그램에 대한 인증·인가를 대신하지 못합니다.

### 5.2 Capability config

| 콘솔 필드 | 현재 상태 | 저장소 값 | 이유 |
| --- | --- | --- | --- |
| Client authentication | Off | `publicClient=true` | 브라우저 코드는 사용자에게 보이므로 Client Secret을 비밀로 보관할 수 없음 |
| Standard flow | On | `standardFlowEnabled=true` | Authorization Code 방식으로 로그인 |
| Direct access grants | Off | `directAccessGrantsEnabled=false` | 사용자 비밀번호를 token endpoint에 직접 보내는 방식을 앱에서 사용하지 않음 |
| Implicit flow | Off | `implicitFlowEnabled=false` | 코드를 거치지 않고 브라우저로 토큰을 받는 흐름 사용 안 함 |
| Service account roles | Off/비활성 | `serviceAccountsEnabled=false` | 이 프런트는 사용자 없이 자기 자격으로 토큰을 발급받는 서버 앱이 아님 |
| Require PKCE | On | `pkce.code.challenge.method=S256` | 코드를 교환하는 주체가 로그인을 시작한 주체인지 증명 |
| PKCE Method | S256 | 위 값과 동일 | 검증값의 SHA-256 해시를 로그인 시작 시 전송 |
| Authorization | Off/비활성 | Authorization Services 미사용 | Keycloak의 별도 정책 엔진은 사용하지 않고 역할을 Spring에서 검사 |
| Consent required | Off | 현재 서버 값 | 실습 중 별도 동의 화면을 추가하지 않음 |
| DPoP / Device Grant / CIBA / Standard Token Exchange / JWT Authorization Grant | Off 또는 비활성 | 현재 콘솔 확인 | 이번 브라우저 로그인에 사용하지 않는 기능 |

**Client authentication Off는 사용자 인증을 끈다는 뜻이 아닙니다.** Client Secret으로 “앱 자신”을 인증하지 않는다는 뜻입니다. 사용자는 계속 Keycloak에서 로그인하고, 앱은 Code + PKCE를 사용합니다.

**Authorization Off인데 인가는 어떻게 되는가?** 이 스위치는 Keycloak Authorization Services 사용 여부입니다. 우리가 구현한 `hasRole("admin")` 같은 Spring 역할 검사는 별도로 작동합니다. 스위치가 꺼져 있다고 모든 API가 공개되는 것이 아닙니다.

### 5.3 PKCE를 실제 코드로 연결하기

관련 파일: [frontend/app.js](../frontend/app.js)의 `login()`과 `finishLogin()`.

1. 브라우저가 일회용 무작위 `verifier`를 만듭니다.
2. `SHA-256(verifier)`를 URL에 넣기 좋은 형태로 바꾸어 `challenge`를 만듭니다.
3. 로그인 시작 요청에는 `code_challenge`와 `code_challenge_method=S256`을 보냅니다.
4. 로그인 성공 후 브라우저는 `code`를 받습니다.
5. 토큰 교환 요청에는 `code`와 원래의 `code_verifier`를 보냅니다.
6. Keycloak은 두 값이 맞는지 확인한 후 토큰을 발급합니다.

누군가 코드만 가져갔다고 해도 원래 verifier가 없으면 올바른 교환을 완료하기 어렵게 하는 장치입니다. `state`는 별도로 로그인 요청과 응답이 연결되는지 확인하는 값입니다. 우리 프런트는 state, 콜백의 issuer, 10분의 임시 로그인 정보 보관 시간도 확인합니다. PKCE의 표준 동작은 [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636)에 정의되어 있습니다.

### 5.4 토큰과 로그아웃의 실제 구현 범위

액세스 토큰은 JavaScript 메모리에만 보관합니다. 로그인 왕복 중의 `state`·`verifier`만 잠시 `sessionStorage`에 두었다가 콜백에서 지웁니다. ID Token이나 Refresh Token이 응답에 포함되더라도 현재 프런트는 이를 API 호출·자동 갱신에 사용하지 않습니다.

로그아웃하면 프런트가 보관한 토큰을 지우고 Keycloak의 로그아웃 주소로 이동합니다. 그러나 이미 다른 곳에 복사된 JWT까지 즉시 무효화하는 기능은 구현하지 않았습니다. 별도의 취소 정책을 조회하지 않는 공개 키 검증 서버에서는 토큰의 만료까지 유효할 수 있습니다.

현재 `finlab-web`의 Backchannel logout URL은 비어 있고 Front channel logout도 꺼져 있습니다. 메뉴가 보인다는 이유만으로 앱 서버에 즉시 로그아웃 알림이 전달된다고 생각하면 안 됩니다.

## 6. 두 API Client와 사용자 역할

### 6.1 API Client는 어떤 설정인가

**경로:** `Clients → finaccess-api` 또는 `finadmin-api`.

두 Client는 Realm JSON에 `bearerOnly=true`로 등록했습니다. 브라우저 로그인을 시작하는 Client가 아니라, API의 대상 이름과 역할을 구분하는 데 사용합니다. Standard flow·Direct access grants·Implicit flow·Service account는 꺼져 있으며 Redirect URI와 Web origin도 비어 있습니다.

새 콘솔에서 예전 버전의 `Access Type: bearer-only` 드롭다운을 찾으려 하지 않아도 됩니다. 이 프로젝트의 등록 근거는 [Realm JSON](../infra/keycloak/finlab-realm.json)의 `bearerOnly`이며, 실제 Spring 앱도 Bearer 토큰을 받는 Resource Server로 구현했습니다.

여기서 세 가지를 구분합니다.

| 설정 | 어느 프로그램의 설정인가 | 의미 |
| --- | --- | --- |
| `bearerOnly=true` | Keycloak Client 등록 | 해당 Client를 Bearer 전용으로 표현 |
| `bearer_only=true` | APISIX 플러그인 | 토큰 없는 요청을 로그인 화면으로 보내지 않고 거절 |
| `.oauth2ResourceServer(...jwt...)` | Spring 코드 | 도착한 JWT를 검증하는 보안 기능 연결 |

Keycloak Client 하나를 설정하는 것만으로 나머지 두 설정이 자동으로 만들어지지는 않습니다.

### 6.2 역할 정의

**경로:** `Clients → finaccess-api → Roles`, `Clients → finadmin-api → Roles`.

| Client | Role | 우리 코드에서 사용하는 뜻 |
| --- | --- | --- |
| finaccess-api | `user` | 이체 요청 가능 |
| finaccess-api | `approver` | 이체 승인·반려·실행 가능 |
| finaccess-api | `admin` | 회사·계좌 생성 및 역할 규칙에서 허용한 관리 작업 |
| finadmin-api | `user` | 일반 사용자 구분용. 현재 `/api/me`는 이 역할 자체가 아니라 유효한 인증을 요구 |
| finadmin-api | `admin` | `/api/admin/**` 접근 가능 |

현재 다섯 Role은 모두 Composite가 아닙니다. `admin`이 이름 때문에 자동으로 `user`·`approver`를 상속하는 것이 아닙니다. 실습 사용자 `admin`에게 FinAccess의 세 역할을 각각 할당했습니다. 또한 Spring의 일부 규칙은 `hasAnyRole("approver", "admin")`처럼 admin을 별도로 허용합니다.

**Realm roles 메뉴에서 이 역할이 안 보이면?** 정상입니다. 앱별 **Client Role**로 만들었기 때문입니다. `finaccess-api`의 `admin`과 `finadmin-api`의 `admin`은 이름이 같아도 소속 Client가 다른 역할입니다.

### 6.3 사용자에게 역할 할당

**경로:** `Users → 사용자 선택 → Role mapping`. Client Role은 `Assign role`에서 Client 역할 필터로 찾는 형태입니다. 현재 값을 읽는 동안 새 역할을 할당할 필요는 없습니다.

| 사용자 | FinAccess 역할 | FinAdmin 역할 | FinAccess 업무 DB의 회사 |
| --- | --- | --- | --- |
| alice | user | user | FinLab A |
| bob | approver | user | FinLab A |
| admin | user, approver, admin | admin | FinLab A |
| outsider | user | user | FinLab B |

네 사용자는 Enabled와 Email verified가 켜져 있고, Required actions는 비어 있으며 비밀번호 자격 증명이 있습니다. 비밀번호는 최초 import에 환경 변수로 전달했고 `temporary=false`로 지정했습니다. 따라서 최초 로그인에서 강제 비밀번호 변경을 요구하지 않습니다.

회사 소속 열은 **Keycloak Role mapping에 저장된 값이 아닙니다.** `scripts/verify.py`가 FinAccess DB의 `app_users.company_id`에 준비한 업무 데이터입니다. Keycloak에는 별도의 company Mapper·Group·Organization을 만들지 않았습니다.

### 6.4 역할 생성, 역할 할당, Mapper는 다른 작업

아래 세 단계가 모두 있어야 우리가 기대한 역할 정보가 API에서 쓰입니다.

1. **Role 생성:** `finadmin-api`에 `admin`이라는 역할 이름을 준비합니다.
2. **사용자에 할당:** `admin` 사용자에게 그 역할을 연결합니다.
3. **Mapper로 토큰에 출력:** 로그인할 때 역할 목록이 JWT에 들어가도록 합니다.

이후 **Spring이 그 토큰의 역할을 읽고 해당 API 규칙을 적용**해야 실제 접근 제한이 완성됩니다. Keycloak에서 역할을 만든 것만으로 임의의 Spring Controller가 보호되지는 않습니다.

## 7. Client scopes와 Mapper: 토큰 내용이 만들어지는 곳

### 7.1 어느 메뉴를 열어야 하는가

왼쪽의 `Client scopes`는 Realm의 공용 Scope 목록입니다. 반면 `Clients → finlab-web → Client scopes`는 **이 Client에 무엇을 연결했는지** 보여 줍니다. 이름은 비슷하지만 보는 대상이 다릅니다.

현재 `finlab-web → Client scopes → Setup`에는 다음 네 행이 보입니다.

| 행 | 표시 유형 | 실제 역할 |
| --- | --- | --- |
| `finlab-web-dedicated` | None | 이 Client에만 속한 Mapper와 역할 범위 설정을 모아 보여 주는 전용 항목 |
| `basic` | Default | 사용자 식별자 등 기본 Claim |
| `profile` | Default | 사용자 이름 등 프로필 Claim |
| `email` | Default | 이메일 관련 Claim |

Dedicated의 None은 “안 쓰는 설정”이라는 뜻이 아닙니다. 공용 Scope의 Default/Optional 연결 방식과 다르게 Client 자체의 설정을 보여 주는 항목입니다. 현재 `finlab-web`에 연결한 Optional Scope는 없습니다.

Default Scope는 로그인 요청의 `scope`에 매번 이름을 적지 않아도 적용됩니다. 실제 프런트는 `scope=openid`만 보내지만, 이번 토큰의 `scope` 문자열에는 `openid email profile`이 나타났습니다. `basic`의 Mapper는 적용되었지만 `basic`이라는 이름은 그 문자열에 없었습니다. **Scope 이름이 토큰에 보이는지와 해당 Mapper가 적용되는지는 동일한 질문이 아닙니다.**

### 7.2 `basic`, `profile`, `email`에서 확인할 것

**경로:** 왼쪽 `Client scopes → 이름 선택 → Mappers`.

| Scope | 실제 Mapper 예 | 결과 | 우리 프로젝트에서의 중요도 |
| --- | --- | --- | --- |
| basic | `sub`, `auth_time` | 사용자 식별자·인증 시각 | `sub`는 두 백엔드가 필수로 요구 |
| profile | `username`, `given name`, `family name`, `full name` 등 | `preferred_username`, 이름 관련 Claim | 표시·사용자 이해에 도움 |
| email | `email`, `email verified` | `email`, `email_verified` | 현재 관리자 권한 판단 기준은 아님 |

`basic`에 있는 `sub` Mapper의 타입은 현재 서버에서 `oidc-sub-mapper`이고 액세스 토큰 출력이 켜져 있습니다. 이전 연동 과정에서 이 Scope 연결이 빠지면 `sub` 없는 토큰 때문에 백엔드 인증이 실패할 수 있음을 확인하여 명시적으로 연결했습니다.

프로필 Scope에 Mapper가 많이 보여도 모든 필드가 항상 토큰에 채워지는 것은 아닙니다. 사용자에 해당 값이 있어야 출력할 수 있는 항목도 있습니다. 현재 앱은 이름이나 이메일로 권한을 결정하지 않습니다.

### 7.3 전용 Mapper 네 개

**정확한 경로:** `Clients → finlab-web → Client scopes → finlab-web-dedicated → Mappers`.

| Mapper 이름 | 콘솔의 Type | 넣는 내용 |
| --- | --- | --- |
| audience-finaccess-api | Audience | 액세스 토큰 `aud`에 `finaccess-api` 추가 |
| audience-finadmin-api | Audience | 액세스 토큰 `aud`에 `finadmin-api` 추가 |
| finaccess-api-roles | User Client Role | `resource_access.finaccess-api.roles` |
| finadmin-api-roles | User Client Role | `resource_access.finadmin-api.roles` |

**왜 로그인 Client 쪽에 두는가?** 브라우저가 `client_id=finlab-web`으로 토큰을 발급받기 때문입니다. 그때 적용할 토큰 출력 설정을 `finlab-web`에 연결합니다. API Client에 역할이 존재한다는 사실만으로 원하는 토큰 모양이 항상 만들어지는 것은 아닙니다.

### 7.4 Audience Mapper의 각 필드

`audience-finadmin-api`를 선택하여 읽습니다. FinAccess용 Mapper는 이름과 대상만 바뀝니다.

| 필드 | 현재 값 | 의미 |
| --- | --- | --- |
| Mapper Type | Audience | 토큰을 사용할 대상 이름을 추가하는 Mapper |
| Name | audience-finadmin-api | 관리자가 구별하기 위한 설정 이름 |
| Included Client Audience | finadmin-api | `aud`에 넣을 Client ID |
| Add to access token | On | API 호출용 액세스 토큰에 대상 포함 |
| Add to ID token | Off | 이 Mapper의 API 대상 값을 ID Token에는 추가하지 않음 |

결과는 다음과 같은 모양입니다. 배열 순서는 중요하지 않습니다.

```json
{
  "aud": ["finadmin-api", "finaccess-api"]
}
```

이 값은 “이 사용자가 관리자다”라는 뜻이 아닙니다. **이 토큰이 두 API를 대상으로 발급되었다**는 뜻입니다. alice의 토큰에도 두 대상이 있지만, FinAdmin의 관리자 API에서는 역할 부족으로 403을 받습니다.

### 7.5 Role Mapper의 각 필드

`finadmin-api-roles`를 선택합니다.

| 콘솔 필드 | 현재 값 | 쉬운 설명 |
| --- | --- | --- |
| Mapper type | User Client Role | 사용자의 특정 Client 역할을 읽음 |
| Name | finadmin-api-roles | 설정 이름 |
| Client ID | finadmin-api | 어느 앱에 속한 역할을 가져올지 선택 |
| Client Role prefix | 비어 있음 | Keycloak에서 역할 문자열 앞에 별도 접두사를 붙이지 않음 |
| Multivalued | On | 역할이 여러 개일 수 있으므로 배열로 출력 |
| Token Claim Name | resource_access.finadmin-api.roles | JSON 안에서 값을 넣을 위치 |
| Claim JSON Type | String | 배열의 각 역할 값은 문자열 |
| Add to access token | On | API가 읽을 액세스 토큰에 포함 |
| Add to ID token | Off | 이 역할 Mapper의 출력은 ID Token에 넣지 않음 |
| Add to userinfo | Off | 이 Mapper의 출력은 UserInfo 응답에 넣지 않음 |
| Add to lightweight access token | Off | 현재 콘솔에서 확인한 상태. 이번 API 흐름은 일반 JWT 액세스 토큰 사용 |
| Add to token introspection | On으로 표시 | 현재 콘솔의 유효 표시값. Realm JSON에는 별도로 지정하지 않았고, 이번 API 경로는 introspection을 사용하지 않음 |

`String`인데 왜 배열인가 하는 의문이 들 수 있습니다. **한 역할의 자료형은 문자열**이고 **Multivalued가 켜져 있으므로 문자열 여러 개를 배열에 담는 것**입니다.

alice와 admin은 같은 Mapper를 사용하지만 결과가 다릅니다.

```jsonc
// 설명용 비교: 실제 JSON 파일에는 이 주석을 넣지 않습니다.
// alice
"resource_access": { "finadmin-api": { "roles": ["user"] } }
// admin
"resource_access": { "finadmin-api": { "roles": ["admin"] } }
```

Mapper가 모두에게 admin을 만들어 주는 것이 아니라, **그 사용자가 실제로 가진 역할을 읽어서 적습니다.**

### 7.6 Full scope allowed와 공용 `roles` Scope

**경로:** `finlab-web-dedicated → Scope`에서 Full scope allowed를 확인합니다. 현재 값은 On입니다.

이는 Client의 역할 범위 제한을 좁히지 않은 상태입니다. 사용자에게 없는 역할을 새로 부여한다는 뜻은 아닙니다. 이번 구성에서는 각 역할 Mapper가 `finaccess-api`, `finadmin-api`를 명시하므로 그 두 Client의 역할을 출력합니다. 운영에서 더 좁은 토큰 권한 범위가 필요하면 사용자 역할·Client Scope·역할 범위를 함께 설계해야 합니다.

공용 `roles` Scope는 Realm에 존재하지만 **finlab-web에는 연결하지 않았습니다.** 해당 공용 Scope 안에는 client roles·realm roles·audience resolve Mapper가 있습니다. 이번 구성은 두 API용 역할 Mapper와 명시적인 Audience Mapper를 전용 Scope에 두었습니다. 따라서 “roles Scope를 안 붙였으니 역할이 없다”는 결론은 틀립니다.

API Client 쪽에 보이는 기본 Scope 목록은 로그인 Client인 finlab-web의 목록과 다를 수 있습니다. 지금 발급받는 토큰은 `finlab-web`을 기준으로 설명해야 합니다.

## 8. 발급된 JWT를 읽는 법

아래는 이번에 실제 alice 토큰에서 확인한 **Claim 일부만** 옮긴 것입니다. 헤더·서명·토큰 원문을 제외한 설명용 자료라 API 인증에 사용할 수 없습니다. `aud`와 역할 배열의 순서는 달라질 수 있습니다.

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "10000000-0000-4000-8000-000000000001",
  "aud": ["finadmin-api", "finaccess-api"],
  "azp": "finlab-web",
  "scope": "openid email profile",
  "resource_access": {
    "finaccess-api": { "roles": ["user"] },
    "finadmin-api": { "roles": ["user"] }
  }
}
```

| 항목 | 답하는 질문 | 어디서 연결되는가 |
| --- | --- | --- |
| `iss` | 누가 발급했는가? | Keycloak Realm URL ↔ APISIX valid_issuers ↔ Spring issuer |
| `sub` | 어느 사용자인가? | Keycloak 사용자 ID ↔ FinAccess 업무 사용자 연결 |
| `aud` | 어느 API를 대상으로 발급했는가? | Audience Mapper ↔ Gateway 경로별 Client ID ↔ Spring audience |
| `azp` | 토큰 발급을 요청한 Client는 누구인가? | 브라우저 로그인 Client `finlab-web` |
| `resource_access` | 이 사용자가 각 앱에서 가진 역할은? | Client Role 할당 + Role Mapper ↔ Spring 역할 변환기 |
| `scope` | 토큰에 표시된 Scope 문자열은? | 로그인 요청과 연결한 Scope 설정 |
| `iat` | 언제 발급했는가? | Keycloak의 발급 시각 |
| `exp` | 언제 만료되는가? | 이번 일반 토큰은 `exp - iat = 300초` |
| `nbf` | 언제부터 사용할 수 있는가? | 있으면 시간 검사. 검증 Client에서 미래 값 생성 |

`azp=finlab-web`과 `aud=finadmin-api`는 모순이 아닙니다. **토큰을 받은 앱**과 **토큰을 제시할 API**가 다른 것입니다. 우리 두 백엔드는 `azp`로 대상 API를 판단하지 않고 `aud`를 검사합니다.

### 8.1 JWT를 읽는 것과 검증하는 것은 다릅니다

JWT는 일반적으로 헤더·본문·서명의 세 부분으로 전달됩니다. 헤더의 `alg`는 서명 방식, `kid`는 어떤 키를 사용할지 찾는 표식입니다. 본문을 디코딩하면 Claim을 읽을 수 있지만, 읽혔다는 사실만으로 믿어서는 안 됩니다.

예를 들어 본문을 조작해서 `roles: ["admin"]`으로 바꿀 수는 있어도, 원래 서명과 맞지 않으면 APISIX와 Spring이 거절합니다. 실제 검증은 신뢰하는 Keycloak의 공개 키로 서명을 확인한 뒤 발급자·유효 시간·대상 등을 확인하는 과정입니다.

### 8.2 ID Token과 Access Token

| 종류 | 목적 | 현재 프런트의 사용 |
| --- | --- | --- |
| ID Token | 로그인 결과와 사용자 신원을 Client에 전달 | API에 보내지 않음 |
| Access Token | 보호된 API에 접근할 때 제시 | `Authorization: Bearer ...`로 전송 |
| Refresh Token | 액세스 토큰을 다시 받는 데 사용 | 보관·자동 갱신 기능 미구현 |

두 토큰이 모두 JWT 모양일 수 있어도 목적은 다릅니다. 이번 Audience·Role Mapper의 `Add to ID token=Off`는 API 대상과 역할을 이 Mapper로 ID Token에 추가하지 않는다는 뜻입니다. OIDC의 기본 ID Token 자체를 발급하지 않는다는 뜻은 아닙니다.

### 8.3 콘솔 Evaluate로 미리 보기

**경로:** `Clients → finlab-web → Client scopes → Evaluate`.

화면의 **Scope parameter**는 `openid`로 두고, **Users**에서 alice를 선택한 다음 **Generated access token** 탭을 엽니다. **Target audience**는 이번 기본 토큰 비교에서는 따로 지정하지 않습니다. 같은 화면에서 Users를 admin으로 바꾸면 `resource_access.finadmin-api.roles`가 어떻게 달라지는지 비교할 수 있습니다. **Effective protocol mappers** 탭은 전용 Mapper와 공용 Scope에서 상속된 Mapper를 함께 이해하는 데 도움이 됩니다.

다만 콘솔 미리 보기가 200 응답을 보장하지는 않습니다. 실제 API에는 서명 검증, 시간, audience, Spring 역할 규칙, FinAccess 회사 소속까지 영향을 줍니다. 다음 장처럼 실제 앱 화면의 응답을 함께 확인합니다. 콘솔 Evaluate 기능의 배경은 [Keycloak 관리 문서](https://www.keycloak.org/docs/26.7.0/server_admin/)에 있습니다.

## 9. 로그인 한 번과 API 요청 한 번을 끝까지 따라가기

### 9.1 로그인 과정

| 순서 | 누가 → 어디로 | 요청·응답의 핵심 | 관련 설정·코드 |
| --- | --- | --- | --- |
| 1 | 브라우저 → APISIX → Nginx | 앱 HTML·JS·CSS 요청 | APISIX의 공개 `/*` 경로 |
| 2 | 브라우저 → Keycloak `/auth` | client_id, redirect_uri, scope, state, challenge | finlab-web Settings, `login()` |
| 3 | 사용자 → Keycloak 로그인 화면 | username·비밀번호 입력 | Users, 기본 browser flow |
| 4 | Keycloak → 브라우저의 redirect 주소 | code, state, iss | Valid redirect URIs |
| 5 | 브라우저 → Keycloak `/token` | code + verifier 교환 | PKCE S256, `finishLogin()` |
| 6 | Keycloak → 브라우저 | Access Token 등 발급 | Scope·Mapper·역할·유효 기간 |

코드는 토큰 그 자체가 아닙니다. 4번에서 받은 코드를 5번에서 교환합니다. 앱의 Java 서버가 사용자 비밀번호를 받아 대신 로그인하는 구조도 아닙니다.

### 9.2 alice가 관리자 요약을 요청하는 과정

1. 브라우저가 `/admin/api/admin/summary`에 액세스 토큰을 붙입니다.
2. APISIX가 `/admin/*` 규칙을 선택합니다.
3. APISIX가 서명, 발급자, 대상 `finadmin-api`, 유효 시간을 확인합니다. alice도 이 조건은 통과할 수 있습니다.
4. `/admin` 접두사를 제거하여 FinAdmin의 `/api/admin/summary`로 같은 토큰을 전달합니다.
5. FinAdmin이 JWT를 다시 검증합니다.
6. `KeycloakRoleConverter`가 `resource_access.finadmin-api.roles`를 읽어 `ROLE_user`로 바꿉니다.
7. `SecurityConfiguration`의 `hasRole("admin")` 조건에 맞지 않아 **403**을 반환합니다.
8. Controller의 관리자 데이터 응답은 실행되지 않습니다.

admin 사용자의 토큰이면 6번에서 `ROLE_admin`이 생기고, 7번을 통과하여 **200**과 샘플 통계를 받습니다. 숫자는 현재 고정 예시이고 `sampleData=true`로 표시됩니다. FinAccess DB에서 집계한 실제 통계가 아닙니다.

### 9.3 공개 키는 언제 쓰는가

Keycloak은 개인 키로 서명합니다. APISIX와 두 Spring 앱은 공개 키 목록 JWKS를 조회·캐시하여 서명을 확인합니다. 회사·계좌·이체 요청을 Keycloak으로 보내서 매번 허가받는 구조는 아닙니다.

| 주소 | 현재 역할 |
| --- | --- |
| `http://localhost:18080/realms/finlab` | 토큰 속 issuer와 서버가 기대하는 issuer |
| `http://localhost:18080/realms/finlab/.well-known/openid-configuration` | 브라우저/호스트에서 보는 OIDC 주소 안내 문서 |
| `http://keycloak:8080/realms/finlab/.well-known/openid-configuration` | APISIX가 Docker 내부에서 읽는 안내 문서 |
| `http://keycloak:8080/realms/finlab/protocol/openid-connect/certs` | 두 Spring 컨테이너가 공개 키를 받는 내부 주소 |

`localhost`는 “지금 실행 중인 그 컴퓨터/컨테이너 자신”을 뜻합니다. FinAdmin 컨테이너에서 `localhost:18080`로 통신하려 하면 Keycloak 컨테이너를 가리키지 않습니다. 그래서 **신뢰할 issuer는 외부 주소로 유지하고, 공개 키를 가져오는 통신 주소는 내부 주소로 분리**했습니다.

Compose의 `KC_HOSTNAME=http://localhost:18080`, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`가 이 구성을 돕습니다. [Keycloak hostname 설명](https://www.keycloak.org/server/hostname)도 외부 주소와 내부 통신 주소를 구분합니다.

## 10. Keycloak 설정을 실제 Spring·APISIX 코드에 연결하기

### 10.1 FinAdmin은 이 순서로 읽습니다

| 읽는 순서 | 파일·메서드 | 무엇을 이해하면 되는가 |
| --- | --- | --- |
| 1 | [application.properties](../src/main/resources/application.properties) | 신뢰할 issuer·JWKS·audience 값의 출처 |
| 2 | [SecurityConfiguration.java](../src/main/java/io/github/greenapple0101/finadmin/security/SecurityConfiguration.java)의 `jwtDecoder()` | 서명과 Claim 검사 |
| 3 | [KeycloakRoleConverter.java](../src/main/java/io/github/greenapple0101/finadmin/security/KeycloakRoleConverter.java)의 `convert()` | Keycloak 역할을 Spring 권한으로 변환 |
| 4 | `SecurityConfiguration.java`의 `securityFilterChain()` | 어떤 URL에 어떤 권한이 필요한지 |
| 5 | [CurrentUserController.java](../src/main/java/io/github/greenapple0101/finadmin/security/CurrentUserController.java) | 검증된 사용자 정보 응답 |
| 6 | [AdminSummaryController.java](../src/main/java/io/github/greenapple0101/finadmin/admin/AdminSummaryController.java) | 관리자 검사 통과 후 실행되는 샘플 응답 |

`NimbusJwtDecoder.withJwkSetUri(...).build()`는 공개 키로 JWT를 검증하는 객체를 준비합니다. 현재 기본 신뢰 서명 알고리즘은 RS256입니다. `JwtValidators.createDefaultWithIssuer(issuer)`와 추가 Validator를 묶어 issuer·시간·audience·sub·exp 존재 여부를 검사합니다.

Spring은 `resource_access.finadmin-api.roles`를 자동으로 우리 의도대로 해석해 주지 않습니다. 그래서 역할 변환기를 연결했습니다.

```text
Keycloak Client Role: admin
        ↓ Role Mapper
JWT: resource_access.finadmin-api.roles = ["admin"]
        ↓ KeycloakRoleConverter
Spring GrantedAuthority: ROLE_admin
        ↓ hasRole("admin")
/api/admin/** 허용
```

Role Mapper의 Client Role prefix가 비어 있는 이유도 여기서 이해할 수 있습니다. `ROLE_`는 현재 Java 변환기가 붙입니다. Keycloak에서도 동일한 접두사를 붙이도록 바꾸면 `ROLE_ROLE_admin`처럼 코드가 기대하지 않은 이름이 될 수 있습니다.

현재 `.anyRequest().authenticated()`인 FinAdmin과 `.anyRequest().denyAll()`인 FinAccess는 마지막 기본 규칙이 다릅니다. 새 API를 추가할 때 두 앱이 같은 규칙이라고 가정하지 말고 해당 파일을 확인해야 합니다.

JWT 검증·권한 변환의 배경은 [Spring Resource Server JWT 문서](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html)에 있습니다. 이 보고서의 구체적인 규칙은 위 프로젝트 파일을 기준으로 했습니다.

### 10.2 APISIX는 이 설정을 읽습니다

파일: [infra/apisix/apisix.yaml](../infra/apisix/apisix.yaml).

| 설정 | 현재 값·동작 | Keycloak과의 연결 |
| --- | --- | --- |
| Plugin | openid-connect | Keycloak의 OIDC 메타데이터·JWKS 활용 |
| discovery | 내부 Keycloak의 well-known 주소 | 공개 키 위치 등 서버 정보 조회 |
| bearer_only | true | 로그인 리다이렉트를 맡지 않고 Bearer 토큰 요구 |
| use_jwks | true | 공개 키로 서명 검증 |
| client_id | 경로별 finaccess-api / finadmin-api | 이번 설정에서는 audience 검사에 사용 |
| expected signing algorithm | RS256 | 기대하는 서명 방식 제한 |
| issuer.valid_issuers | 외부 finlab issuer | 다른 발급자의 토큰 거절 |
| audience.required | true | aud 필수 |
| audience.match_with_client_id | true | 해당 API Client ID가 aud에 있어야 함 |
| set_access_token_header + access_token_in_authorization_header | true | 같은 액세스 토큰을 Authorization 헤더로 전달 |
| ID·UserInfo·Refresh Token 헤더 | false | 업무 API에 해당 헤더를 별도로 전달하지 않음 |
| serverless-post-function | exp·nbf 추가 검사 | OIDC 검증 이후 토큰의 시간 조건 확인 |

서명 검증을 하는 `openid-connect`와, 검증 뒤 본문에서 시간을 읽는 추가 함수의 역할을 구분해야 합니다. 추가 함수는 JWT를 파싱할 뿐이므로 그것만으로 인증을 처리할 수 없습니다. 현재 APISIX 설정은 `nbf` 등 시간 조건을 명시적으로 검사하도록 함께 구성했습니다.

Gateway는 관리자 역할을 판정하지 않습니다. `/admin/*` 경로를 사용할 수 있는 유효한 대상 토큰인지 검사하고, `/api/admin/**`의 admin 역할 판정은 FinAdmin이 합니다. [APISIX 플러그인 문서](https://apisix.apache.org/docs/apisix/plugins/openid-connect/)는 bearer-only·JWKS 옵션의 의미를 설명합니다.

### 10.3 FinAccess는 로그인 신원을 업무 사용자에 연결합니다

관련 파일: [CurrentAppUser.java](https://github.com/Greenapple0101/finaccess/blob/main/src/main/java/io/github/greenapple0101/finaccess/security/CurrentAppUser.java).

```text
검증된 JWT의 iss + sub
        ↓
app_users의 identity_issuer + identity_subject 조회
        ↓
우리 앱의 userId와 companyId 확보
        ↓
이체 요청자·승인자 신원, 회사 소속과 업무 규칙 확인
```

Keycloak의 사용자 UUID와 FinAccess 업무 DB의 사용자 UUID는 별개입니다. 실습에서 Keycloak ID는 `10000000-...`, 업무 사용자 ID는 `30000000-...` 형태로 준비했습니다. 둘을 연결하는 열이 issuer와 subject입니다.

username은 표시·로그인에 사용하고, 현재 업무 사용자 연결에는 `iss + sub`를 사용합니다. 요청 본문에 아무 `requesterId`를 적어서 다른 사람으로 이체를 요청할 수 없도록 API를 변경한 이유입니다.

alice와 outsider는 같은 `user` 역할을 가지고 있습니다. 하지만 업무 DB의 소속 회사가 다르므로 회사 데이터 접근 결과가 다릅니다. **역할 검사만으로 모든 금융 업무 인가가 끝나는 것이 아니라, 데이터의 소유·소속 관계도 확인**하는 예입니다.

## 11. 나머지 메뉴는 무엇이며 어디까지 구현했는가

### 11.1 Realm roles, Groups, Identity providers, User federation

| 메뉴 | 현재 확인한 상태 | 이해할 내용 |
| --- | --- | --- |
| Realm roles | offline_access, uma_authorization, default-roles-finlab | 기본 Realm 역할. 앱 역할은 API Client 안에 따로 존재 |
| Groups | 없음 | 이번 실습은 사용자에게 Client Role을 직접 할당 |
| Identity providers | 없음 | Google·다른 OIDC 서버 등 외부 로그인 연동을 추가하지 않음 |
| User federation | 없음 | LDAP/AD 등 외부 사용자 저장소 연동 없음 |
| Organizations | Realm General에서 Off | FinAccess의 회사 엔티티는 이 기능으로 구현한 것이 아님 |

현재 네 사용자의 직접 Realm Role 매핑은 비어 있습니다. `default-roles-finlab`이라는 역할 객체가 존재하는 것과 특정 사용자에게 실제로 할당된 것은 따로 확인해야 합니다.

### 11.2 Authentication의 Flow가 많은 이유

현재 최상위 Flow 일곱 개는 모두 `builtIn=true`입니다.

| Flow | 이번 구성에서 읽는 방법 |
| --- | --- |
| browser | 사용자 브라우저 로그인에 연결한 기본 Flow |
| direct grant | 기본 제공되지만 finlab-web의 Direct access grants는 Off |
| registration | 기본 제공되지만 이번 Realm의 회원가입은 Off |
| reset credentials | 기본 제공되지만 비밀번호 찾기는 Off |
| clients | Client 인증을 처리하는 기본 Flow |
| first broker login | 외부 IdP 연동 시 사용하는 기본 Flow. 현재 별도 IdP 없음 |
| docker auth | 기본 제공 Flow. 이번 실습의 Docker Compose 실행과 동일한 기능이 아님 |

Flow는 로그인 과정에서 어떤 인증 단계를 수행할지 정하는 구성입니다. 이번에는 커스텀 Flow나 OTP 강제·패스키 로그인 절차를 만들지 않았습니다. 메뉴가 많다고 모두 우리가 설계했다는 뜻은 아닙니다.

### 11.3 Keys에는 왜 여러 알고리즘이 보이는가

**경로:** `Realm settings → Keys`.

실제 서버에 AES/ENC, RSA-OAEP/ENC, HS512/SIG, RS256/SIG 키 정보가 있습니다. 이것은 서버가 여러 내부 용도의 키를 관리한다는 뜻입니다. 모든 액세스 토큰이 모든 방식으로 서명된다는 뜻은 아닙니다. 이번 기본 토큰 서명 방식은 **RS256**이고 Gateway와 두 앱도 이 경로를 사용합니다.

공개 JWKS는 서명을 확인하는 데 필요한 공개 정보를 제공합니다. 비밀번호나 개인 키를 API 서버에 복사하는 구성이 아닙니다. 키가 여러 개 보일 때는 `alg`, `use`, 활성 상태를 함께 읽습니다.

### 11.4 Sessions, Events와 미사용 옵션

`Sessions`는 Keycloak이 관리하는 로그인 세션을 보여 줍니다. Spring 앱의 `SessionCreationPolicy.STATELESS`와 모순되지 않습니다. Keycloak의 로그인 세션과 API 서버가 요청을 인증하는 방법이 서로 다르기 때문입니다.

현재 Realm의 `eventsEnabled`, `adminEventsEnabled`, `adminEventsDetailsEnabled`는 모두 false입니다. 따라서 콘솔에서 과거 로그인·설정 변경 이력이 모두 보존된다고 기대하지 않습니다. 이번 검증 결과는 앱의 검증 스크립트 결과 파일로 확인했습니다.

Theme·Localization·User profile·Client policies·Workflows 등도 콘솔에 보입니다. 이번 프로젝트에서 여기에 별도 학습용 정책·화면·워크플로를 구성한 변경은 없습니다. 먼저 Client·Scope·역할·토큰 경로를 이해한 후 필요한 기능을 확장하는 순서가 적절합니다.

## 12. 내가 처음 만들었다면 어떤 순서로 작업했을까

현재 Realm은 이미 구성되어 있으므로 아래는 **만드는 순서를 이해하기 위한 재현 안내**입니다. 기존 동일 이름 항목을 또 만들 필요는 없습니다. 콘솔에서 한 단계씩 찾아보고 현재 값과 비교하면 됩니다.

### 12.1 작업 순서와 완성되는 결과

| 순서 | 했던 일 | 콘솔에서 대응되는 작업 | 이 단계가 끝나면 생기는 것 |
| --- | --- | --- | --- |
| 1 | Keycloak와 전용 DB 실행 | 서버 실행은 콘솔 밖의 Compose | 관리 콘솔 접속 가능 |
| 2 | finlab Realm 준비 | Manage realms → Create realm / import | 앱용 사용자·설정 영역 |
| 3 | API Client 두 개 등록 | Clients → Client 등록 / import | API별 이름과 역할 보관 위치 |
| 4 | API별 Role 생성 | 각 API Client → Roles → Create role | user·approver·admin 정의 |
| 5 | 실습 사용자 준비 | Users → Add user, Credentials | 로그인 가능한 계정 |
| 6 | 사용자 역할 연결 | Users → 사용자 → Role mapping | 누가 어느 앱에서 무슨 역할인지 결정 |
| 7 | finlab-web 등록 | Clients → Create client | 브라우저 로그인 Client |
| 8 | Code + PKCE·주소 설정 | finlab-web → Settings | 허용된 프런트에서 코드 교환 가능 |
| 9 | Default Scope 연결 | finlab-web → Client scopes → Add client scope | basic·profile·email 적용 |
| 10 | Mapper 네 개 준비 | dedicated → Mappers → Add mapper → By configuration | API 대상과 역할이 토큰에 출력 |
| 11 | 토큰 미리 보기 | Client scopes → Evaluate | 기대한 Claim 확인 |
| 12 | 두 Spring 앱 Resource Server 구성 | Java 설정·properties | JWT 검증과 API 인가 |
| 13 | APISIX 경로·JWT 검사 구성 | YAML 설정 | Gateway 경유 경로 완성 |
| 14 | 브라우저 로그인 코드 연결 | frontend/app.js | 실제 로그인·API 호출 가능 |
| 15 | 실패 검증 Client 추가 | Client 등록과 Mapper 설정 | 대상 불일치·만료·미래 nbf 검증 |

실제 프로젝트는 일일이 수동 클릭한 대신 **Realm JSON import와 일부 관리 API 동기화로 재현 가능하게 구성**했습니다. 이 표는 코드로 준비한 설정을 사람이 콘솔에서 만든다면 어떤 작업에 해당하는지 보여 줍니다.

### 12.2 Public Client를 수동으로 만드는 과정을 더 잘게 보기

새 실습 환경에서 같은 구성을 만든다고 가정하면 다음 순서입니다.

1. Clients의 Create client에서 Protocol을 OpenID Connect, Client ID를 `finlab-web`로 정합니다.
2. Capability 설정에서 Client authentication Off, Standard flow On, 나머지 사용하지 않는 로그인 흐름 Off를 선택합니다.
3. 로그인 복귀 주소와 Web origins를 5장 표대로 입력합니다.
4. 생성 후 Settings에서 Require PKCE On, PKCE Method S256과 로그아웃 복귀 주소를 확인합니다.
5. Client scopes에서 basic·profile·email이 Default인지 확인합니다. 현재 구성처럼 비교하려면 자동으로 붙은 공용 Scope와 우리가 선택한 Scope를 구분합니다.
6. `finlab-web-dedicated → Mappers → Add mapper → By configuration`에서 Audience 두 개와 User Client Role 두 개를 7장 값대로 준비합니다.
7. 전용 Scope의 Scope 탭에서 Full scope allowed 값을 확인합니다.
8. Evaluate와 실제 로그인으로 `aud`, `sub`, 역할 Claim이 예상대로 들어가는지 확인합니다.

API Client의 bearer-only 등록은 이번 프로젝트가 import JSON으로 준비한 부분입니다. 콘솔에서 Public Client를 만드는 절차를 그대로 복사하여 API Client를 동일하게 설정하면 이번 구성과 달라집니다. 두 API Client의 JSON과 현재 상태를 따로 비교합니다.

### 12.3 파일과 콘솔 값은 언제 동기화되는가

| 위치 | 실제 역할 |
| --- | --- |
| [compose.yaml](../compose.yaml) | 서버 실행, 환경 변수, 포트, 볼륨, import 파일 연결 |
| [finlab-realm.json](../infra/keycloak/finlab-realm.json) | 최초 Realm·Client·역할·사용자 설정의 재현 자료 |
| [.env.example](../.env.example) | 필요한 환경 변수 이름 |
| `.env` | 로컬의 실제 비밀번호. Git 제외 |
| [init-local.py](../scripts/init-local.py) | 초기 비밀번호와 로컬 인증 문서 준비 |
| [verify.py](../scripts/verify.py)의 prepare_clients | `finlab-*` 로그인·검증 Client 설정과 기본 Scope 연결을 맞춤 |
| Keycloak DB | 실행 중인 콘솔에서 저장한 실제 설정 |

현재 `start-dev --import-realm`은 처음 Realm을 준비할 때 사용됩니다. **이미 존재하는 Realm은 시작 시 import를 건너뛰므로, JSON을 수정하고 재시작하는 것만으로 모든 설정이 바뀌지는 않습니다.** [Keycloak import 문서](https://www.keycloak.org/server/importExport)에서 이 동작을 설명합니다.

`prepare_clients`도 전체 Realm 동기화 도구는 아닙니다. 사용자 역할·비밀번호·Realm 정책·API Client 전체를 매번 초기화하는 코드가 아닙니다. 관리하는 `finlab-*` Client 정의를 생성/수정하고 필요한 Default Scope를 추가합니다. 모든 추가 Scope나 수동 변경을 제거하는 완전한 정합성 관리도 아닙니다.

**이번 확인 결과:** 저장소에서 명시한 Realm·Client 설정 항목과 실제 서버가 일치했고, 사용자 네 명의 역할도 위 표와 일치했습니다. 콘솔에서 이후 수정하면 보고서 작성 시점과 달라질 수 있습니다.

## 13. 직접 해보는 읽기 중심 실습

### 실습 A — 목록에서 앱과 테스트 도구를 구분하기

1. Clients 목록에서 `fin`을 검색합니다.
2. 로그인 프런트 하나, API Client 둘, 테스트 Client 셋을 구분합니다.
3. 왜 Client 여섯 개가 Spring 앱 여섯 개를 뜻하지 않는지 말로 설명합니다.

**확인 기준:** 프런트 한 개와 독립 Spring 앱 두 개이며, 테스트 Client는 토큰 조건을 바꾸기 위한 등록 정보라고 설명할 수 있습니다.

### 실습 B — alice와 admin의 권한 차이 보기

1. Users에서 alice의 Role mapping을 읽습니다.
2. admin의 Role mapping과 비교합니다.
3. [앱 화면](http://localhost:18090/)에서 alice로 로그인합니다.
4. FinAdmin 내 정보는 200, 관리자 요약은 403인지 봅니다.
5. 로그아웃 후 admin으로 로그인하면 관리자 요약이 200인지 봅니다.

**확인 기준:** alice의 audience도 finadmin-api를 포함하지만 admin 역할은 없어서 차단된다고 설명할 수 있습니다. 사용자 이름과 역할을 혼동하지 않습니다.

### 실습 C — 같은 사람이 두 앱에서 확인되는지 보기

1. 앱에서 FinAccess 내 정보와 FinAdmin 내 정보를 각각 누릅니다.
2. FinAccess의 `sub`와 FinAdmin의 `subject`가 같은지 비교합니다.
3. 두 응답의 `issuer`도 비교합니다.
4. 각 앱이 반환한 역할 목록이 서로 다를 수 있다는 점을 봅니다.

**확인 기준:** 하나의 토큰을 두 앱에 전달하면서 각 앱이 자기 audience와 자기 역할을 검사한다고 설명할 수 있습니다.

### 실습 D — 토큰이 없으면 어떻게 되는가

앱의 **토큰 없이 관리자 요약 요청**을 누릅니다. 예상 응답은 401입니다. 로그인 중이어도 이 버튼은 Authorization 헤더를 빼고 호출합니다. 화면 로그인 상태만으로 API 요청이 인증되는 것이 아니라 요청의 Bearer 토큰이 필요하다는 것을 확인합니다.

### 실습 E — 공개 정보만으로 discovery와 JWKS 보기

다음 명령은 비밀번호나 토큰이 필요 없는 조회입니다.

```bash
curl -s http://localhost:18080/realms/finlab/.well-known/openid-configuration | python3 -m json.tool
curl -s http://localhost:18080/realms/finlab/protocol/openid-connect/certs | python3 -m json.tool
```

첫 결과에서 issuer·authorization_endpoint·token_endpoint·jwks_uri를 찾습니다. 둘째 결과에서는 `kid`, `kty`, `alg`, `use`를 찾아봅니다. 키 목록을 조회할 수 있다고 토큰을 임의로 발급할 수 있는 것은 아닙니다. 공개 키와 개인 키의 용도가 다릅니다.

### 실습 F — 기존 실패 검증용 Client를 읽기

| Client | 바꾼 조건 | 기대하는 관찰 |
| --- | --- | --- |
| finlab-access-test | Audience는 finaccess-api 하나만 추가 | admin 사용자라도 FinAdmin에서 대상 불일치로 거절 |
| finlab-expiry-test | Client별 access.token.lifespan=2초 | 충분한 시간이 지나면 실제 서명 토큰도 만료로 거절 |
| finlab-not-before-test | future-not-before Mapper가 nbf=4102444800 추가 | 2100-01-01 UTC 전에는 사용 시작 시각 조건 불충족 |

`finlab-access-test`에는 두 API의 Role Mapper가 있지만 FinAdmin audience가 없습니다. 따라서 “admin 역할이 있어도 대상 API가 맞지 않으면 안 된다”를 분리해 검증할 수 있습니다.

`future-not-before`는 Hardcoded claim Mapper이고 Claim JSON Type은 `long`입니다. 일반 finlab-web에 넣을 설정이 아닙니다. Realm이나 Client의 세션 취소용 Not Before 정책과 달리 **JWT의 nbf Claim을 직접 넣어 검사하기 위한 테스트 설정**입니다.

전체 자동 검증을 직접 다시 수행하려면 finadmin 폴더에서 `python3 scripts/verify.py`를 실행할 수 있습니다. 이 명령은 단순 조회가 아닙니다. 관리 대상 Client 설정을 맞추고, 실습 회사·업무 사용자와 새 계좌·모의 이체 데이터를 준비하며, 데스크탑 MD의 검증용 토큰을 갱신합니다. 상세 범위는 [기존 검증 문서](08-end-to-end-verification.md)를 먼저 확인합니다.

## 14. 설정을 잘못 이해했을 때 나타나는 증상

아래는 코드와 현재 설정으로 설명한 원인 후보입니다. 모든 실패를 이번 보고서 작성 중 일부러 재현한 것은 아닙니다. 실제 실행으로 확인한 항목은 15장에 구분했습니다.

| 증상 | 먼저 확인할 항목 | 이유 |
| --- | --- | --- |
| Invalid username or password | Realm, 계정, 로컬 인증 MD, 로그인 실패 제한 | master 관리자와 finlab 앱 계정을 구분 |
| redirect_uri 오류 | finlab-web의 허용 주소와 실제 요청 문자열 | 호스트·포트·경로가 다르면 거절 |
| 로그인 후 토큰 교환 실패 | Standard flow, PKCE S256, code_verifier, 코드 유효 기간 | 코드 교환 조건이 충족되어야 함 |
| 브라우저 CORS 오류 | Web origins, 실제 접속 주소 | 인증 성공 여부와 별개로 브라우저가 응답 읽기를 제한할 수 있음 |
| 서명 정상인데 백엔드 401 | iss, aud, exp, nbf, sub | 서명만 맞는다고 유효한 API 토큰이 아님 |
| basic 연결 누락 후 sub 없음 | finlab-web의 Default Scope와 basic의 sub Mapper | 현재 Spring은 sub를 필수로 요구 |
| admin인데 403 | 해당 Client의 역할, Role Mapper, 새 토큰인지 | 다른 Client의 admin이나 오래된 토큰은 조건을 충족하지 않을 수 있음 |
| Keycloak에서 역할 바꿨는데 응답 그대로 | 현재 요청이 변경 전 JWT를 쓰는지 | 이미 발급된 JWT의 Claim은 설정 변경으로 다시 작성되지 않음 |
| API 한 곳만 대상 불일치 | Audience Mapper, 경로별 audience 기대값 | finaccess-api와 finadmin-api는 별개 대상 |
| 컨테이너에서 JWKS 조회 실패 | keycloak 서비스 이름·포트·네트워크 | 컨테이너 안 localhost와 호스트 localhost는 다름 |
| 로그아웃했는데 복사한 토큰이 계속 사용됨 | 토큰 만료 시각과 즉시 취소 구현 여부 | 현재 공개 키 검증 경로에는 실시간 세션 취소 조회가 없음 |
| 이체·회사 요청 403, 내 정보는 200 | 업무 사용자 연결과 companyId, 업무 규칙 | 토큰 인증과 업무 데이터 인가는 다른 단계 |
| JSON을 바꾸고 재시작했는데 설정 그대로 | 기존 Realm import 건너뛰기, 스크립트 동기화 범위 | 파일 수정이 전체 live 설정을 자동 덮어쓰지 않음 |
| admin에게 역할을 더 줬는데 자기 승인 실패 | 자기 승인 금지 업무 규칙 | 역할 통과 후에도 업무 규칙 적용 |

**401·403을 단순 암기하지 않기:** Spring에서는 토큰 검증 실패가 주로 401, 역할 부족이 403입니다. 하지만 현재 APISIX의 audience 불일치는 403입니다. 숫자 하나만 보고 “반드시 역할 문제다”라고 결론 내리지 말고, 어느 서버에서 어떤 조건으로 거절했는지 봅니다.

## 15. 이번에 실제 확인한 것과 이전 검증 기록

### 15.1 이번 보고서 작성 중 새로 확인

- Keycloak 서버 버전 26.7.4와 finlab Realm 설정을 관리 API로 조회했습니다.
- Client 12개, 공용 Scope 15개, 실습 사용자 네 명과 앱별 역할을 확인했습니다.
- 저장소가 명시한 Realm·Client 필드와 실제 서버를 비교하여 차이가 없음을 확인했습니다. 비밀번호 원문·비밀 키의 비교나 전체 서버 설정 동일성 검증을 뜻하지 않습니다.
- 실제 콘솔의 finlab-web Settings, Client scopes, Dedicated Mappers, 역할 Mapper 필드, Realm settings를 읽어 메뉴 위치와 표시를 확인했습니다.
- 실제 PKCE 로그인 후 **읽기 전용 HTTP 확인 32건을 새로 통과**했습니다. 사용자별 두 앱 내 정보, 관리자 API 허용·거절, 토큰 누락, 다른 API 대상 토큰을 확인했습니다.
- 토큰 원문·비밀번호·개인 키는 이 보고서나 공개 부록에 넣지 않았습니다. Claim 예시는 실습 사용자의 일부 필드만 사용했습니다.

### 15.2 앞선 구현 단계에서 남긴 검증 기록

2026-09-29 16:41 KST의 기존 전체 검증 기록은 HTTP 46건 통과와 모의 이체 잔액 9,000원/1,000원 확인입니다. FinAccess Java 테스트 149개와 FinAdmin Java 테스트 19개 통과도 이전 구현 완료 시의 결과입니다.

이번에는 문서 작성을 위해 모의 이체나 Java 전체 테스트를 다시 실행하지 않았습니다. 만료·미래 nbf·위조 토큰·자기 승인 금지·중복 이체 등 전체 검증 범위는 [08번 문서](08-end-to-end-verification.md)를 참고합니다.

현재 Spring 시간 검사에는 기본 60초의 시계 오차 허용 범위가 있습니다. 기존 만료 테스트는 `exp + 65초`가 지난 뒤 확인합니다. Gateway의 추가 시간 검사는 exp·nbf를 엄격하게 검사하므로 경계 시점의 응답까지 두 서버가 초 단위로 완전히 같다는 뜻은 아닙니다.

## 16. 이해했는지 스스로 확인하기

다음 질문에 자기 말로 답할 수 있으면 콘솔 설정과 API 동작을 연결해서 이해한 것입니다.

| 질문 | 답에 들어가야 할 핵심 |
| --- | --- |
| Client가 12개인데 왜 백엔드는 두 개인가? | Client는 등록 정보이며 기본·검증 Client도 존재 |
| Client authentication Off면 비밀번호 없이 로그인하는가? | 앱의 Secret 인증과 사용자의 로그인을 구분 |
| alice의 aud에 finadmin-api가 있는데 왜 관리자 API가 403인가? | 대상 API 허용과 admin 역할이 별개 |
| Role을 만들면 자동으로 모든 사용자 토큰에 들어가는가? | 사용자 할당·유효 역할 범위·Mapper가 필요 |
| finlab-web의 Client scopes에 roles가 없는데 역할은 어떻게 들어가는가? | dedicated의 앱별 Role Mapper |
| JWT의 sub와 requesterId는 같은 값인가? | Keycloak 사용자 ID와 업무 사용자 ID는 연결되지만 별개 |
| Gateway가 검사했는데 뒤에서 왜 또 검사하는가? | 각 API가 자체 신뢰 기준과 권한을 적용 |
| Keycloak이 모든 이체 요청을 승인하는가? | 토큰 발급은 Keycloak, 업무 인가는 FinAccess |
| 역할을 지우면 기존 토큰 안의 역할도 바로 사라지는가? | 새 토큰에 반영되며 기존 JWT는 별도 취소 정책 없으면 남을 수 있음 |
| 기본 Flow가 보여도 Direct access grants를 사용 중인가? | Flow 존재와 해당 Client의 사용 허용은 다름 |
| 회사는 Keycloak Organizations에 저장되는가? | 이번 프로젝트는 FinAccess 업무 DB에서 관리 |
| 이 구성이 곧바로 운영 완료를 뜻하는가? | 로컬 HTTP 실습이며 운영 구성과 검증은 별도 |

회사에서 설명할 때는 다음처럼 말할 수 있습니다.

> Keycloak에서 프런트 로그인 Client와 두 API의 Client·역할을 분리했습니다. Authorization Code + PKCE로 발급한 토큰에 대상 API와 앱별 역할을 넣고, APISIX와 각 Spring Resource Server가 독립적으로 검증하도록 구성했습니다. FinAdmin은 관리자 역할을, FinAccess는 사용자 신원과 회사 소속까지 연결해 접근을 제한했습니다. 설정이 토큰과 API 응답에 어떻게 영향을 주는지 정상·실패 사례로 확인했습니다.

이 문장을 읽는 데서 끝내지 않고, `Audience Mapper → aud 검사`, `Role mapping → Role Mapper → hasRole`, `iss + sub → 업무 사용자` 세 연결을 콘솔과 코드에서 직접 찾아 설명해 봅니다.

## 참고 자료와 확인 범위

이 문서의 현재 값·사용자 역할·Mapper 구성·라우팅·권한 규칙은 실행 중인 로컬 서버와 저장소를 직접 확인한 결과입니다. 공식 문서는 아래 개념과 제품 동작을 교차 확인하는 데 사용했습니다. 메뉴는 실제 26.7.4 화면을 우선했습니다.

- [프로젝트 Realm 설정](../infra/keycloak/finlab-realm.json), [Compose](../compose.yaml), [APISIX 설정](../infra/apisix/apisix.yaml), [브라우저 로그인 코드](../frontend/app.js)
- [Keycloak 26.7 관리 가이드](https://www.keycloak.org/docs/26.7.0/server_admin/): Realm·Client·Scope와 콘솔 기능
- [Keycloak Realm import](https://www.keycloak.org/server/importExport): 기존 Realm의 시작 시 import 동작
- [Keycloak hostname](https://www.keycloak.org/server/hostname): 외부 주소와 내부 통신 주소
- [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636): PKCE 코드 교환 증명
- [Apache APISIX openid-connect](https://apisix.apache.org/docs/apisix/plugins/openid-connect/): Gateway OIDC·JWKS 설정
- [Spring Resource Server JWT](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html): JWT 검증과 권한 변환

운영 TLS·고가용성·로그 감사 정책·영구 관리자 전환·비밀값 관리·사용자 프로비저닝 자동화·즉시 토큰 취소는 이 보고서에서 구현 완료로 주장하지 않습니다. 현재 상태를 이해한 후 확장할 주제입니다.
