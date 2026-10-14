# OAuth2 실습 진행 가이드

먼저 [기획](README.md)을 읽고, 아래 순서로 실습합니다. 현재 완료 여부는 [실행 기록](RESULTS.md)을 기준으로 봅니다.

## 1 로컬 서버 시작

이 컴퓨터에 설치된 JDK 21과 Python 3을 사용합니다. Keycloak 26.7.4는 기존 실습과 같은 버전이며 이 JDK에서 실행을 확인했습니다. 최신 Keycloak의 JDK 요구 조건과 혼동하지 않습니다.

터미널에서 `oauth-lab` 폴더로 이동한 뒤 실행합니다. 이 컴퓨터에는 다운로드와 압축 해제가 완료되어 있습니다.

```sh
# 다른 컴퓨터에서 처음 받을 때만 실행합니다.
mkdir -p .local
curl -fL -o .local/keycloak.tar.gz https://github.com/keycloak/keycloak/releases/download/26.7.4/keycloak-26.7.4.tar.gz
tar -xzf .local/keycloak.tar.gz -C .local

# 이후에는 이것만 실행합니다. 이미 실행 중인 프로세스는 재실행하지 않습니다.
python3 scripts/start-local.py
```

Keycloak은 `http://localhost:18180`, 화면은 `http://localhost:18100`입니다. 기동 직후에는 `.local/keycloak.log`의 `started` 메시지를 기다립니다. 시작 스크립트가 출력하는 것은 실행 요청이며 HTTP 응답까지 자동 검증하지는 않습니다.

실습용 비밀번호는 `.local/credentials.json`에 생성됩니다. `bootstrap-admin`은 Keycloak 설정용, `alice`와 `admin`은 API 접근 비교용입니다. 비밀번호와 토큰 원문은 공유 자료에 붙이지 않습니다.

## 2 Keycloak에서 확인할 설정

`http://localhost:18180/admin/`에서 bootstrap-admin으로 들어가 `oauth-lab` Realm을 선택합니다. 기존 `finlab` Realm을 수정하지 않습니다.

| 화면 | 설정 | 왜 필요한가 |
|---|---|---|
| Clients → oauth-browser → Settings | Client authentication Off, Standard flow On | 브라우저에 비밀키 없이 Authorization Code 사용 |
| 같은 Client → Advanced | PKCE S256 | 인증 코드를 교환할 때 verifier 확인 |
| Settings → Valid redirect URIs | `http://localhost:18100/` | 코드가 돌아갈 주소를 정확히 제한 |
| Settings → Web origins | `http://localhost:18100` | 이 화면의 브라우저 토큰 교환 허용 |
| Client scopes → demo.read | optional scope | 인증 요청에서 `demo.read` 요청 |
| oauth-browser의 전용 Client scope → Mappers | api-audience, api-roles | Access Token에 대상 API와 역할 포함 |
| Clients → oauth-api → Roles | user, admin | 보호된 API의 접근 조건 |
| Users → alice / admin → Role mapping | alice=user, admin=user+admin | 같은 API에 서로 다른 결과 확인 |
| Realm settings → Tokens | Access Token 60초 | 토큰 만료를 짧게 기다려 관찰 |

Realm JSON은 처음 실행할 때 가져옵니다. 기존 Realm이 있으면 import가 건너뛰므로, 이후 파일을 고친 것만으로 실행 중인 설정이 자동 변경되지는 않습니다. 변경은 관리 콘솔에서 해당 설정에 적용합니다.

## 3 API7에서 확인할 설정

API7 실행 방식 결정이 선행되어야 합니다. 이 가이드의 `gateway/routes.json`은 **기존 Docker API7이 Mac의 Keycloak에 연결하는 주소**인 `host.docker.internal:18180`을 사용하도록 준비했습니다. Linux API7을 쓴다면 실제로 도달 가능한 주소와 브라우저에서 사용하는 발급자 주소를 함께 정해야 합니다.

Mac Keycloak은 현재 `127.0.0.1`에만 열려 있습니다. Docker 연결 허용 후 연결 경로를 점검해야 하며, 현재 파일만 등록했다고 Gateway 연동이 끝난 것은 아닙니다. 제품 내부 DB와 라이선스는 기존 설치 것을 사용합니다.

설정 적용은 기존 finadmin 저장소 안의 도구와 로컬 API7 관리 자격 증명을 재사용합니다. `oauth-lab`만 다른 위치에 복사하면 적용 도구의 부모 경로도 맞춰야 합니다.

```sh
python3 scripts/apply-api7.py          # 추가할 Route 이름만 확인
python3 scripts/apply-api7.py --apply  # 실행 환경 준비 후 실제 등록
```

실제 관리 콘솔 `https://localhost:7443` → Gateway Groups → `finlab-rbac`의 Routes에서 아래 이름을 확인합니다. 기존 업무 Route는 보존하며 이번 학습에서는 사용하지 않습니다.

| Route | 담당 |
|---|---|
| oauth-lab-read | GET 일반 API, user 역할 필요 |
| oauth-lab-admin | GET 관리자 API, admin 역할 필요 |
| oauth-lab-preflight | 브라우저가 보내는 OPTIONS 허용, 업무 데이터 없음 |
| oauth-lab-fallback | 그 외 실습 경로·메서드는 404로 종료 |

두 보호 Route의 Plugins에서 다음을 봅니다.

| 설정 | 읽을 핵심 |
|---|---|
| openid-connect | bearer_only=true, RS256, issuer, audience=oauth-api |
| acl | 검증된 `resource_access.oauth-api.roles`에서 user 또는 admin 검사 |
| mocking | 검사를 통과하면 JSON 200 반환, 실제 업무 서버 없음 |
| cors | localhost:18100에서 Authorization 헤더를 보내도록 허용 |
| serverless-pre-function | 외부 사용자 정보 헤더 제거 |
| serverless-post-function | 검증된 토큰의 exp·nbf 조건 엄격하게 확인 |

이름이 `openid-connect`인 제품 플러그인을 **Access Token 검증에만 사용**합니다. Gateway가 브라우저 로그인 세션을 만들거나 ID Token·UserInfo를 사용하는 구성은 아닙니다. ACL은 단순히 디코딩한 토큰이나 외부 헤더가 아니라 인증 플러그인이 검증한 결과를 사용해야 합니다.

## 4 화면에서 직접 확인

1. 실습 화면의 **Keycloak에서 토큰 받기**를 누르고 alice로 인증합니다.
2. 발급 성공, Bearer, demo.read, ID Token 없음 표시를 확인합니다.
3. **일반 API**를 누릅니다. 기대값은 200입니다.
4. **관리자 API**를 누릅니다. 기대값은 403입니다.
5. **토큰 없이 호출**을 누릅니다. 기대값은 401입니다.
6. 토큰 발급 후 60초 이상 기다리고 일반 API를 다시 누릅니다. 기대값은 401입니다.
7. **토큰 갱신** 후 일반 API를 누릅니다. 기대값은 200입니다.
8. 토큰 받기를 다시 누르고 admin으로 인증합니다. 관리자 API 기대값은 200입니다.

401은 토큰 검증 실패, 403은 이 요청에 필요한 권한 부족을 구별하는 데 사용합니다. 실제 제품의 특정 오류 상태는 이번 실행 기록을 따릅니다. `Failed to fetch`는 401이나 403이 아니라 연결 또는 CORS 문제일 수 있습니다.

## 5 설명할 수 있어야 하는 네 문장

- Keycloak은 사용자를 확인하고 Access Token을 발급합니다.
- 브라우저는 비밀번호 대신 Access Token을 API7에 보냅니다.
- API7은 토큰이 유효한지 검사한 다음 경로에 필요한 역할을 확인합니다.
- 이번에는 업무 서버를 개발하지 않고 API7의 모의 응답으로 허용 여부만 확인합니다.

비밀번호를 API7에 보내는 방식, 브라우저에 Client Secret을 넣는 방식, JWT를 읽기만 하고 신뢰하는 방식은 사용하지 않습니다. 자동화 테스트 파일을 만들지 않아도 위 요청 결과는 직접 확인하고 기록합니다.
