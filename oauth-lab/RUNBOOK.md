# 로컬 실행·시연 순서

## 1. 시작하기

두 저장소를 같은 부모 폴더에 두고 현재 코드가 있는 `main`을 사용합니다. 작업 브랜치 `oauth-focus`에도 동일한 문서·코드가 있습니다. 루트 앱 대신 각 저장소의 `oauth-lab/`을 실행합니다. Java 21·Python 3·Homebrew가 필요합니다. 현재 Mac에는 준비되어 있습니다.

다른 Mac에서 최초 설치할 때만:

```sh
brew install openldap
cd finadmin/oauth-lab
mkdir -p .local
curl -fL -o .local/keycloak.tar.gz https://github.com/keycloak/keycloak/releases/download/26.7.4/keycloak-26.7.4.tar.gz
tar -xzf .local/keycloak.tar.gz -C .local
```

이후 **finadmin/oauth-lab 폴더**에서:

```sh
python3 scripts/start-local.py
```

Keycloak, OpenLDAP, 옆 FinAccess와 FinAdmin을 시작합니다. Keycloak이 처음 뜨는 중이라면 `.local/keycloak.log`의 started를 확인한 후, 최초 한 번 다음 설정을 적용합니다. 기존 환경에는 이미 적용했습니다.

```sh
python3 scripts/configure-roles.py
python3 scripts/configure-auth.py
```

API7은 기존 Docker Desktop과 API7 설치를 사용합니다. 이미 등록된 그룹·라이선스·인증 정보가 필요하며, 위 JVM 실행 명령이 제품을 새로 설치하지는 않습니다. Gateway 컨테이너가 정지했다면 finadmin 저장소 루트에서 `docker compose -f compose.api7.yaml up -d`로 기존 Gateway를 실행합니다. Control Plane·관리 DB도 실행 중이어야 합니다.

`python3 scripts/init-api7.py`는 최초 등록용입니다. 기존 서비스·라우트가 있으면 **유지**합니다. `.local/api7`(저장소 루트 아래)의 관리자 정보·group.json·현재 로컬 제품 인증서 current-dashboard.pem을 사용합니다. 인증서를 자동으로 무검증 수집하거나 TLS 검증을 끄지 않습니다. 새 설치·인증서 교체 시 설치 원본을 확인하여 신뢰 파일을 다시 준비해야 합니다.

## 2. 일반 사용자 — FinAccess 화면

1. http://localhost:18100/ 에 접속합니다. 이전 앱 주소 18090의 루트 화면은 사용하지 않습니다.
2. **Keycloak에서 토큰 받기** → `ldap-user` 로그인.
3. **내 USER 권한 확인** → API7 경유 200. USER·Engineering과 `Gateway: api7-enterprise`, `Backend: finaccess` 확인.
4. **토큰 없이 호출** → API7에서 401. `Backend: 없음` 확인.
5. `ldap-admin`으로 새 로그인 후 같은 USER API 호출 → API7에서 403. ADMIN이 USER의 상위 역할인 구성은 아닙니다.

내부 계정 alice=USER, admin=ADMIN도 비교용으로 유지합니다. LDAP 계정은 ldap-user / ldap-admin입니다. 비밀번호는 `.local/credentials.json`과 데스크탑의 비공개 계정 문서에만 있습니다. 화면의 **토큰 지우기**는 Keycloak SSO 로그아웃이 아닙니다.

브라우저는 API7의 `GET http://localhost:18090/oauth-access/api/user/me`를 호출합니다. API7은 `http://localhost:18100` 화면의 CORS 사전 확인(OPTIONS)에 200으로 응답한 후, 실제 GET에서 JWT·USER 역할을 검사합니다. 프런트가 토큰 갱신·로그인 후 받은 토큰을 그대로 전달하며, Spring도 재검증합니다.

## 3. 관리자 — 로그인 UI 없이 CLI 시작

finadmin/oauth-lab 폴더 터미널에서:

```sh
python3 scripts/device-login.py
```

Keycloak 기본 브라우저 화면에서 `ldap-admin`으로 로그인하고 본인이 요청한 접근을 승인합니다. FinAdmin에는 로그인 HTML이 없습니다. **화면이 없는 CLI라도 사람의 인증은 Keycloak 브라우저에서 수행**합니다. 기존 SSO 세션이 있으면 그 계정으로 진행될 수 있으므로 계정을 확인합니다. 계정을 바꾸려면 먼저 Keycloak에서 로그아웃합니다.

성공하면 `.local/curl-header`에 짧은 수명의 토큰을 저장합니다. 터미널·명령 기록에 토큰 원문을 붙이지 않아도 됩니다.

```sh
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/me
curl -i -H @.local/curl-header 'http://localhost:18090/oauth-admin/api/admin/greeting?name=Demo'
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/greeting
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/demo-error
```

차례로 **200, 200, 400, 500**입니다. 유효기간 60초가 지나면 다시 발급합니다. Spring의 시계 오차 허용은 이 로컬 실습에서 0초입니다.

## 4. 두 검사 위치 비교

```sh
# Gateway 인증 검사: 401
curl -i http://localhost:18090/oauth-admin/api/admin/me
# Spring 인증 검사: 401
curl -i http://localhost:18101/api/admin/me
# 유효한 ADMIN 토큰: 두 경로 모두 200
curl -i -H @.local/curl-header http://localhost:18101/api/admin/me
# 허용하지 않은 메서드: Gateway 403
curl -i -X POST -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/me
```

Device 로그인 계정을 ldap-user로 바꾸면 관리자 API는 Gateway와 Spring 직접 호출 각각 403입니다. 같은 USER 토큰으로 FinAccess 두 경로를 비교합니다.

```sh
curl -i -H @.local/curl-header http://localhost:18090/oauth-access/api/user/me
curl -i -H @.local/curl-header http://localhost:18100/api/user/me
```

USER이면 둘 다 200이며 ADMIN만 있으면 둘 다 403입니다. 직접 호출 경로는 독립 검증을 보여주는 로컬 비교 경로로 유지합니다.

- `X-OAuth-Gateway: api7-enterprise`: API7 경유 응답.
- `X-Finlab-Backend: finaccess` 또는 `finadmin`: Spring 보안 필터까지 도달한 응답. Controller 실행을 항상 뜻하지는 않습니다.
- Gateway ACL 403은 Gateway 헤더만 있습니다. 정상 USER·ADMIN 경유 응답에는 두 헤더가 모두 있습니다.
- API7의 기본 오류 HTML에 APISIX 문구가 나타날 수 있지만 실행 제품은 응답의 `Server: API7/3.10.2`와 설치 이미지로 확인합니다.

## 5. API7 실제 관리 UI에서 바꾸기

https://localhost:7443/ 의 제품 콘솔을 사용합니다. 브라우저에서 로컬 인증서 경고가 나오면 사용자가 설치 출처를 확인해야 합니다. 이번 작업에서는 관리 API와 실제 Gateway 요청을 검증했으며, 현재 브라우저의 인증서 경고를 대신 넘기지는 않았습니다.

`finlab-rbac` Gateway Group에서 다음 이름으로 찾습니다. 메뉴 이름은 UI 표시 언어에 따라 다를 수 있습니다.

| 대상 | 현재 값 | 수정해서 관찰할 항목 |
|---|---|---|
| Service `oauth-finaccess` | upstream `host.docker.internal:18100` | USER API 서버 연결 |
| Route `oauth-access-get` | GET, OPTIONS `/oauth-access/api/user/me`, priority 300 | USER ACL·CORS·접두어 제거 확인 |
| USER Route의 `acl` | allow_labels.roles = USER | 검증된 JWT의 USER만 허용 |
| USER Route의 `cors` | origin `http://localhost:18100`, methods `GET,OPTIONS` | 사전 확인과 200·401·403 응답 헤더 확인 |
| Route `oauth-access-deny` | `/oauth-access/*`, priority 290 | 허용 경로 밖 요청 거절 |
| Service `oauth-finadmin` | upstream `host.docker.internal:18101` | 잘못된 포트로 바꾸면 upstream 오류. 즉시 원복 |
| Route `oauth-admin-get` | GET `/oauth-admin/api/admin/*`, priority 300 | 메서드·경로와 플러그인 확인 |
| `openid-connect` | bearer_only, use_jwks, RS256 | 발급자·audience 검사 |
| `acl` | allow_labels.roles = ADMIN | 검증된 JWT의 ADMIN만 허용 |
| `proxy-rewrite` | `/oauth-admin` 접두어 제거 | 실제 Spring URL과 연결 |
| Route `oauth-admin-deny` | `/oauth-admin/*`, priority 290 | 허용 경로 밖 요청을 403으로 거절 |

OIDC 설정의 client_id는 `oauth-api`, issuer는 `http://localhost:18180/realms/oauth-lab`입니다. 컨테이너 내부 discovery URL은 `http://host.docker.internal:18180/realms/oauth-lab/.well-known/openid-configuration`입니다. 발급자 식별값과 네트워크 접속 주소가 다른 이유입니다.

ACL 역할 위치는 `$.resource_access["oauth-api"].roles`, parser는 table, label key는 roles입니다. Role 검사 코드를 JavaScript/Lua로 새로 작성하지 않았습니다. ADMIN Route의 역할은 ADMIN, USER Route는 USER입니다. 역할 변경 실험은 해당 실습 Route 안에서만 하고 끝나면 원래 값으로 복원합니다. Gateway를 통과해도 해당 Spring이 요구하는 역할이 없으면 403입니다.

UI 수정 후 위 curl을 다시 실행하고 다음 명령으로 현재 상태를 보관합니다. 초기화 명령으로 UI 수정을 덮어쓰지 않습니다.

```sh
python3 scripts/export-api7.py
```

결과는 `.local/api7-export.json`이며 Git에 올리지 않습니다. 과거 `/access/*`, `/admin/*` 등 다른 Route는 이번에 수정하지 않았습니다.

## 6. JWT 변조 시연

USER로 Device 로그인한 뒤, 실습용 복사본의 역할만 ADMIN으로 바꿉니다. 서명은 그대로 두어 위조가 거절되는지 관찰합니다.

```sh
python3 scripts/tamper-token.py
curl -i -H @.local/tampered-header http://localhost:18090/oauth-admin/api/admin/me
curl -i -H @.local/tampered-header http://localhost:18101/api/admin/me
curl -i -H @.local/tampered-header http://localhost:18090/oauth-access/api/user/me
```

세 요청 모두 401입니다. 이 실험은 서명 검사 증거입니다. 만료 검사는 **정상 발급 토큰을 수정하지 않고 60초 넘게 기다려** 별도로 확인합니다.

## 7. 부서 변경과 새 토큰 비교

LDAP 관리자 암호는 파일로 전달합니다. 아래 명령은 **이 실습의 ldap-admin 한 명**의 ou만 바꿉니다.

```sh
/opt/homebrew/opt/openldap/bin/ldapmodify -x -H ldap://127.0.0.1:18389 \
  -D 'cn=admin,dc=oauth,dc=lab' -y .local/ldap/root-password <<'LDIF'
dn: uid=ldap-admin,ou=people,dc=oauth,dc=lab
changetype: modify
replace: ou
ou: Support
LDIF
```

Device 로그인으로 새 토큰을 받고 `/oauth-admin/api/admin/me`를 호출하면 department가 Support로 바뀝니다. 이전에 받은 미만료 토큰은 이전 부서를 유지합니다. 비교용 기존 헤더 파일도 .local 안에만 보관하세요.

**시연 후 위 명령의 `ou: Support`를 `ou: Operations`로 바꿔 다시 실행**합니다. 새 토큰에서 Operations 복원을 확인합니다. API7 관리 계정을 만드는 동기화 시험이 아니라 JWT 속성 전달 시험입니다.

## 8. 재시작·로그

로그: finadmin/oauth-lab/.local/keycloak.log, .local/ldap/slapd.log, .local/finadmin.log 및 finaccess/oauth-lab/.local/finaccess.log.

코드 수정 후에는 해당 앱의 `.local/*.pid`가 가리키는 프로세스의 JAR 경로를 확인하여 종료한 다음 시작 명령을 다시 실행합니다. 전체 Java 프로세스를 한꺼번에 종료하지 않습니다. LDAP와 Keycloak 데이터는 .local에 남으므로 삭제하지 않습니다.
