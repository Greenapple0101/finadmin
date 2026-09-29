# 07. APISIX에서 검사하고, 백엔드에서도 다시 검사하기

이번 단계에서는 프런트와 두 백엔드 사이에 **Apache APISIX Gateway**를 둡니다. Gateway는 요청을 먼저 받는 서버입니다. 주소를 보고 요청을 알맞은 백엔드로 보내고, 보내기 전에 JWT를 검사합니다.

기존 Controller를 APISIX 안으로 옮기는 것은 아닙니다. FinAccess와 FinAdmin은 계속 각자 실행되고, 각자 Spring Security로 JWT를 검사합니다. APISIX를 통과했다고 해서 백엔드의 검사를 생략하지 않습니다.

## 먼저 주소를 따라가 보기

```text
브라우저가 액세스 토큰을 붙여 요청
  → localhost:18090의 APISIX
  → 서명·발급자·대상·시간 검사
  → 같은 액세스 토큰을 Authorization 헤더에 넣어 전달
  → FinAccess 또는 FinAdmin의 Spring Security가 다시 JWT 검사
  → 역할과 업무 조건 검사
  → Controller가 응답
```

`compose.yaml`의 APISIX 서비스는 내 컴퓨터의 `18090`번 포트를 컨테이너의 `9080`번과 연결합니다. 컨테이너는 별도의 실행 공간이므로, 안에서 사용하는 번호와 밖에서 접속하는 번호가 다를 수 있습니다.

| 브라우저에서 호출하는 주소 | APISIX가 보내는 주소 | 담당 앱 |
| --- | --- | --- |
| `/access/api/hello` | `http://finaccess:8080/api/hello` | FinAccess |
| `/admin/api/admin/summary` | `http://finadmin:8081/api/admin/summary` | FinAdmin |
| `/`와 실제 프런트 파일 주소 | `http://web:80/`와 해당 파일 주소 | 프런트 정적 파일 서버 |

`finaccess`, `finadmin`, `web`은 `compose.yaml`의 서비스 이름입니다. Docker 안에서는 같은 네트워크의 서버를 이 이름으로 찾을 수 있습니다.

Gateway에서는 `/access/*`, `/admin/*` 전체에 JWT 검사를 적용합니다. **`/access/api/hello`, `/admin/api/hello`도 예외가 아닙니다.** 백엔드에 직접 접속하는 인사 API의 규칙과 Gateway의 규칙은 각각 따로 설정되어 있습니다.

## 1. config.yaml: Gateway 프로그램을 켜는 방법

파일 위치는 `infra/apisix/config.yaml`입니다.

이번에는 별도의 설정 저장 서버인 etcd를 추가하지 않고, APISIX가 파일을 직접 읽도록 합니다. 이를 **standalone의 file-driven 방식**이라고 합니다.

```yaml
deployment:
  role: data_plane
  role_data_plane:
    config_provider: yaml
```

- `data_plane`: 실제 요청을 받아 처리하는 역할입니다.
- `config_provider: yaml`: 실행할 규칙을 YAML 파일에서 읽으라는 뜻입니다.
- `enable_admin: false`: 설정을 바꾸는 Admin API는 열지 않습니다.

실제 경로 규칙은 옆의 `apisix.yaml`에 적습니다. 이 파일 끝의 `#END`는 APISIX가 설정 파일이 완성되었음을 확인하는 표시입니다. 일반 주석처럼 보여도 지우면 안 됩니다. [APISIX 배포 방식 문서](https://apisix.apache.org/docs/apisix/deployment-modes/)

접근 로그에는 요청 방식·주소 경로·결과 상태 등을 남깁니다. `Authorization` 헤더, 본문, 쿼리 문자열을 기록하도록 설정하지 않습니다. 로그인 후 돌아오는 URL에 붙는 `code`도 접근 로그에 담지 않도록 전체 요청 문자열 대신 `$uri`를 사용합니다. 인증 라이브러리가 토큰을 출력할 수 있는 DEBUG 로그도 켜지 않습니다.

## 2. apisix.yaml: 어떤 주소를 어느 앱에 보낼지 정하기

파일 위치는 `infra/apisix/apisix.yaml`입니다. `routes` 아래의 묶음 하나가 하나의 길 안내 규칙입니다.

FinAccess 규칙을 예로 보면 다음과 같습니다.

```yaml
uri: /access/*
priority: 100
```

`/access/`로 시작하는 요청을 잡습니다. `priority`가 큰 규칙을 먼저 선택하도록 하여, 우선순위가 0인 프런트 경로 `/*`보다 API 경로가 먼저 선택되게 합니다. 인증에 실패했다고 프런트 경로로 다시 보내지는 않습니다.

```yaml
proxy-rewrite:
  regex_uri: ["^/access/(.*)$", "/$1"]
```

`proxy-rewrite`는 백엔드에 보낼 주소를 바꿉니다. `/access/api/hello`에서 앞의 `/access`를 제거하면 `/api/hello`가 됩니다. `$1`은 괄호 `(.*)`로 잡은 뒷부분을 다시 넣으라는 뜻입니다. 백엔드의 기존 API 주소를 바꿀 필요가 없어집니다. [주소 변경 플러그인 문서](https://apisix.apache.org/docs/apisix/plugins/proxy-rewrite/)

프런트용 `/*`는 로그인 전에도 화면 파일을 받을 수 있도록 열어 둡니다. 존재하지 않는 파일은 정적 파일 서버가 404로 처리합니다. 없는 API를 호출했는데 로그인 화면이 성공 응답처럼 나타나도록 모든 주소를 `index.html`로 바꾸지 않습니다.

## 3. openid-connect: 토큰이 믿을 만한지 확인하기

여기서는 APISIX의 `openid-connect` 플러그인을 사용합니다. 이름에 OpenID Connect가 들어가지만, 이번 Gateway 설정은 로그인 화면을 띄우는 방식이 아닙니다. 프런트가 이미 받은 **액세스 토큰**을 요청에 붙이면 그 토큰을 검사하는 방식입니다.

| 설정 | 이번 실습에서의 뜻 |
| --- | --- |
| `bearer_only: true` | 요청에 Bearer 액세스 토큰이 있어야 합니다. |
| `use_jwks: true` | Keycloak의 공개 키 목록으로 JWT 서명을 검증합니다. |
| `discovery` | Keycloak의 공개 키 주소 등을 알려 주는 안내 문서의 주소입니다. |
| `token_signing_alg_values_expected: RS256` | 허용하는 서명 알고리즘을 RS256으로 정합니다. |
| `valid_issuers` | 우리 Keycloak Realm이 발급한 토큰만 받습니다. |
| `audience.required: true` | 토큰의 대상 정보인 `aud`가 있어야 합니다. |
| `audience.match_with_client_id: true` | `aud`에 이 경로의 `client_id`가 들어 있어야 합니다. |

FinAccess 경로의 `client_id`는 `finaccess-api`, FinAdmin 경로의 값은 `finadmin-api`입니다. 여기에서는 “이 토큰을 어느 API가 사용할 수 있는가”를 확인하는 값입니다. 로그인하는 프런트의 Client ID와 구분해서 읽어야 합니다.

이 설정은 APISIX 3.18.0의 Bearer 토큰·JWKS 방식입니다. 공개 키로 검증하므로 플러그인에 Client Secret을 넣지 않습니다. 공개 키는 다른 사람이 알아도 되는 검증용 키이며, 토큰을 만들어 서명하는 개인 키는 Keycloak 쪽에 남아 있습니다. [OIDC 플러그인 문서](https://apisix.apache.org/docs/apisix/plugins/openid-connect/), [3.18.0 플러그인 구현](https://github.com/apache/apisix/blob/3.18.0/apisix/plugins/openid-connect.lua)

## 4. 왜 Keycloak 주소가 localhost와 keycloak 두 가지인가

브라우저에서 사용하는 Keycloak 주소는 `http://localhost:18080`입니다. 하지만 **APISIX 컨테이너 안의 localhost는 내 Mac이나 Keycloak이 아니라 APISIX 컨테이너 자신**입니다. APISIX가 공개 키를 받으려고 `localhost:18080`에 접속하면 다른 장소를 찾게 됩니다.

그래서 `compose.yaml`에서 다음 두 값을 함께 설정합니다.

```yaml
KC_HOSTNAME: http://localhost:18080
KC_HOSTNAME_BACKCHANNEL_DYNAMIC: "true"
```

첫 줄은 브라우저가 알고 있는 공개 주소와 토큰의 발급자 주소를 고정합니다. 둘째 줄은 서버끼리 통신하는 주소를 요청이 들어온 주소에 맞게 만들도록 합니다. 여기서 **backchannel**은 브라우저 화면 이동 대신 서버끼리 통신하는 경로라고 이해하면 됩니다.

APISIX가 `http://keycloak:8080/realms/finlab/.well-known/openid-configuration`을 읽으면 다음처럼 서로 다른 목적의 주소를 받습니다.

| 안내 문서의 항목 | 기대하는 값 |
| --- | --- |
| `issuer` | `http://localhost:18080/realms/finlab` |
| `jwks_uri` | `http://keycloak:8080/realms/finlab/protocol/openid-connect/certs` |

발급자를 확인할 때는 공개 주소를 그대로 비교하고, 공개 키를 내려받을 때는 Docker 내부 주소를 사용합니다. 발급자 검사만 통과시키려고 신뢰할 주소 목록에 내부·외부 주소를 마구 추가하지 않습니다. [Keycloak hostname 설정 문서](https://www.keycloak.org/server/hostname)

## 5. 만료 시각과 사용 시작 시각을 추가로 확인하기

JWT의 `exp`는 만료 시각, `nbf`는 사용을 시작할 수 있는 시각입니다. 값은 사람이 읽는 날짜 문자열이 아니라 UTC 기준 초 단위 숫자입니다.

APISIX 3.18.0의 기본 OIDC Bearer 검증 경로는 라이브러리에 발급자 검사 옵션을 넘깁니다. 이 경로에서는 JWT 라이브러리의 기본 `nbf` 검사가 적용된다고 가정할 수 없어서, 별도의 작은 시간 검사를 둡니다. 기본 OpenIDC 라이브러리에도 만료 검사가 있지만, 우리 실습은 `exp`가 반드시 있고 정확히 만료 시각에 차단되도록 추가 확인합니다. [OpenIDC 검증 구현](https://github.com/zmartzone/lua-resty-openidc/blob/v1.9.0/lib/resty/openidc.lua), [JWT 라이브러리의 검사 옵션 구현](https://github.com/api7/lua-resty-jwt/blob/v0.2.6/lib/resty/jwt.lua)

```text
먼저 openid-connect가 서명·발급자·대상을 확인
  → serverless-post-function이 exp와 nbf를 추가 확인
  → 둘 다 통과해야 백엔드로 전달
```

`serverless-post-function`은 설정에 적은 작은 Lua 함수를 실행하는 플러그인입니다. 여기서 `phase: rewrite`는 요청을 백엔드로 보내기 전에 실행하는 단계입니다. OIDC 플러그인의 우선순위는 2599이고 post 함수의 우선순위는 -2000이므로 같은 단계에서 OIDC 검사가 먼저 실행됩니다. [Serverless 플러그인 문서](https://apisix.apache.org/docs/apisix/plugins/serverless/)

시간 검사의 규칙은 두 가지입니다.

1. `exp`는 숫자로 반드시 존재하고 현재 시각보다 커야 합니다.
2. `nbf`는 생략할 수 있지만, 있다면 숫자여야 하고 현재 시각보다 미래이면 안 됩니다.

**이 Lua 함수는 JWT의 내용을 읽을 뿐, 서명을 검증하지 않습니다.** 따라서 `openid-connect`를 지우고 이 함수만 남기면 안 됩니다. 시간 검사는 기본 인증에 덧붙이는 조건입니다. 백엔드에도 독립적인 JWT 검증이 있어야 합니다.

## 6. 백엔드에 무엇을 전달하는가

```yaml
set_access_token_header: true
access_token_in_authorization_header: true
```

APISIX가 검사한 액세스 토큰을 `Authorization: Bearer ...` 형태로 백엔드에 전달합니다. 백엔드는 이 토큰을 자신의 공개 키·발급자·대상 설정으로 다시 확인합니다.

ID Token, 사용자 정보, Refresh Token을 별도의 헤더로 전달하는 옵션은 끕니다. FinAdmin의 `admin` 역할 검사나 FinAccess의 회사·이체 권한 검사는 백엔드가 검증된 토큰과 업무 데이터를 기준으로 처리합니다. 요청자가 직접 쓴 역할 헤더를 믿지 않습니다.

`X-Finlab-Gateway: apisix`는 응답이 Gateway 경로를 거쳤는지 보기 위한 표시입니다. `X-Finlab-Upstream`은 어느 백엔드 경로가 선택되었는지 알려 줍니다. Gateway에서 거절된 응답에도 선택된 경로가 표시될 수 있으므로, 이 헤더만으로 백엔드까지 도착했다고 판단하면 안 됩니다. 응답 헤더를 설정하는 기능은 `response-rewrite`가 담당합니다. [응답 변경 플러그인 문서](https://apisix.apache.org/docs/apisix/plugins/response-rewrite/)

## 7. 결과를 읽는 방법

아래는 각 상황의 기대 결과입니다. 실행 후 실제 검증 결과는 전체 실습 검증 문서와 함께 확인합니다.

| 상황 | 요청을 거절하는 곳과 결과 |
| --- | --- |
| `/admin/api/admin/summary`에 토큰 없이 요청 | APISIX에서 401 |
| 서명을 바꾸거나 만료된 토큰으로 요청 | APISIX에서 401 |
| 발급자가 다른 토큰 | APISIX에서 401 |
| FinAccess 전용 토큰으로 FinAdmin 경로 요청 | APISIX의 audience 검사에서 403 |
| 정상적인 FinAdmin 대상 토큰이지만 관리자 역할이 없음 | FinAdmin에서 403 |
| 정상적인 FinAdmin 대상 토큰이며 관리자 역할이 있음 | FinAdmin에서 관리자 응답 |
| Gateway를 우회해 FinAdmin 직접 호출 시 잘못된 토큰 | FinAdmin 자체 검증에서 401 |

APISIX의 audience 불일치는 기본 플러그인이 **403**을 반환합니다. Spring의 JWT audience 불일치는 **401**입니다. 따라서 모든 잘못된 토큰의 응답이 무조건 같은 번호라고 설명하지 않습니다. 실패가 Gateway에서 발생했는지, 백엔드에서 발생했는지도 함께 확인합니다.

토큰이 없는 상황은 비밀값 없이 확인할 수 있습니다.

```bash
curl -i http://localhost:18090/admin/api/admin/summary
```

정상 토큰의 확인은 프런트에서 로그인한 다음 API 호출 버튼으로 진행합니다. 실제 비밀번호와 토큰은 공개 문서나 Git 커밋에 넣지 않습니다. 데스크탑의 별도 로컬 비밀값 문서는 Git 저장소 밖에 보관합니다.

## 이번 구성이 보여 주는 것

하나의 로그인 서버가 발급한 토큰을 Gateway와 두 개의 독립적인 Spring 백엔드가 사용합니다. Gateway에서는 요청이 올바른 API를 위한 것인지 확인하고, 각 백엔드에서는 JWT 검증에 더해 역할과 업무 규칙을 적용합니다.

현재 주소와 포트, HTTP, 로컬 직접 호출 경로는 재현 가능한 로컬 실습을 위한 설정입니다. 운영 환경에서는 HTTPS, 백엔드 네트워크 격리, 비밀값 관리, 모니터링 등을 배포 환경에 맞게 별도로 구성해야 합니다.
