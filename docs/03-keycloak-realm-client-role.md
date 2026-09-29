# 03. Realm·Client·사용자·역할을 구분하기

Keycloak 관리 화면의 항목이 많아도 이번 실습에서 먼저 읽을 곳은 Realm, Clients, Users 세 곳입니다. 실제 초기 설정은 `infra/keycloak/finlab-realm.json`에 있습니다.

콘솔의 필드별 의미와 JWT·Spring 코드 연결까지 따라가려면 [Keycloak 핸즈온 보고서](11-keycloak-hands-on-report.md)를 읽습니다. 이 문서는 용어를 먼저 구분하는 짧은 안내입니다.

## Realm: 설정을 모으는 실습 영역

`finlab` Realm 안에 이번 앱의 사용자와 클라이언트를 둡니다. `master`는 Keycloak 자체를 관리하는 영역이며, 업무 앱의 사용자를 거기에 넣지 않습니다. Realm 이름은 토큰 발급자 주소 `http://localhost:18080/realms/finlab`에도 들어갑니다.

## Client: 로그인하거나 보호할 앱의 등록 정보

| Client ID | 의미 |
| --- | --- |
| `finlab-web` | 사용자 로그인 화면. 공개 클라이언트이며 Authorization Code + PKCE 사용 |
| `finaccess-api` | FinAccess가 받는 액세스 토큰의 대상과 역할을 정의 |
| `finadmin-api` | FinAdmin이 받는 액세스 토큰의 대상과 역할을 정의 |
| `finlab-access-test` | FinAccess만 대상인 토큰으로 FinAdmin 접근이 차단되는지 검증 |
| `finlab-expiry-test` | 수명 2초 토큰으로 만료 거절을 검증 |
| `finlab-not-before-test` | 미래 nbf를 넣어 아직 사용하면 안 되는 토큰의 거절을 검증 |

공개 클라이언트는 브라우저에 비밀키를 보관하지 않습니다. 코드 교환에는 일회용 PKCE 값을 사용합니다. 로그인 후 돌아올 주소는 `http://localhost:18090/` 하나로 제한하고 PKCE S256을 요구합니다. 사용자 로그인용 Password Grant와 Implicit Flow는 껐습니다.

시간 검증용 클라이언트는 테스트 목적이며 운영용 등록에 포함하지 않습니다. `verify.py`는 이번 실습에서 관리하는 `finlab-*` 공개 Client를 JSON 정의와 맞춥니다. 관리 화면에서 해당 Client 설정을 바꿨다면 검증 실행 시 저장소 설정으로 돌아옵니다. 이 설정 작업에만 관리용 `admin-cli` 토큰을 일시 사용하며 사용자 로그인 흐름과는 다릅니다.

## 사용자에게 앱별 역할 부여

| 사용자 | FinAccess 역할 | FinAdmin 역할 | 업무 회사 |
| --- | --- | --- | --- |
| alice | user | user | A |
| bob | approver | user | A |
| admin | user, approver, admin | admin | A |
| outsider | user | user | B |

Keycloak의 Users → 사용자 선택 → Role mapping에서 확인할 수 있습니다. 역할의 정의는 Clients → 대상 API → Roles에서 확인합니다.

앱 관리자 `admin`과 Keycloak 관리 계정 `bootstrap-admin`은 다른 계정입니다. 일반 앱 사용자가 Keycloak의 Realm이나 사용자 설정을 바꾸도록 권한을 주지 않습니다.

## 대상(aud)과 역할은 다른 정보

`aud`는 이 토큰을 어느 API에서 사용할 수 있는지 나타냅니다. 역할은 그 API 안에서 어떤 일을 할 수 있는지 나타냅니다.

예를 들어 FinAdmin 대상이면서 역할이 user인 토큰은 `/api/me` 조회는 가능하지만 `/api/admin/summary`는 거절됩니다. FinAccess만 대상인 토큰은 FinAdmin에서 아예 인증에 실패합니다.

기본 Client Scope의 `basic`은 `sub` 사용자 식별자를 토큰에 넣습니다. 실제 연동 중 이를 빼면 역할과 대상은 있어도 사용자 식별자가 없어 백엔드가 401로 거절했습니다.

초기 JSON의 audience mapper는 대상 API를 `aud`에 넣습니다. client role mapper는 사용자의 앱별 역할을 `resource_access.finaccess-api.roles`, `resource_access.finadmin-api.roles`에 넣습니다. Spring은 자기 앱의 역할만 읽습니다.

## 회사 소속은 어디에 있나요?

회사·계좌·이체 관계는 FinAccess DB에 있습니다. Keycloak은 로그인을 확인하고, FinAccess는 검증된 `iss + sub`로 자기 DB의 사용자를 찾습니다. 그래서 user 역할이 같아도 다른 회사 데이터는 볼 수 없습니다.

현재 실습 사용자의 DB 연결은 `scripts/verify.py`가 준비합니다. 일반 고객의 회원가입·자동 가입 처리까지 구현한 것은 아닙니다.

[Keycloak 관리 가이드](https://www.keycloak.org/docs/latest/server_admin/)
