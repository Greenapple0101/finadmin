# Keycloak OAuth2 로컬 PoC

[현재 문서 목차](../docs/README.md) · [전체 아키텍처](https://github.com/Greenapple0101/finadmin/blob/main/docs/current/02-architecture.md)

현재 실행 위치는 두 저장소의 `oauth-lab/`입니다. `main`과 `oauth-focus`에 현재 코드가 있습니다. 금융·ITSM 업무, 업무 DB, Kubernetes, 자동화 테스트를 새 실습에 포함하지 않습니다.

## 실행 구성

| 구성요소 | 실행 방식·주소 | 책임 |
|---|---|---|
| FinAccess | 로컬 JVM, http://localhost:18100 | 프런트 제공, API7에서 전달받은 USER API 재검증 |
| FinAdmin | 로컬 JVM, http://localhost:18101 | ADMIN API만 제공. 로그인 UI 없음 |
| Keycloak 26.7.4 | 로컬 JVM, http://localhost:18180 | 로그인, LDAP 조회, OAuth2 토큰 발급. 개발용 내장 H2 |
| OpenLDAP 2.7.1 | Mac 프로세스, ldap://127.0.0.1:18389 | 직원 계정·비밀번호·그룹·부서 원천 |
| API7 Enterprise 3.10.2 | Docker, http://localhost:18090 | USER·ADMIN 경로의 JWT·Role 검사와 전달 |
| API7 실제 관리 UI | https://localhost:7443 | Service·Route·openid-connect·ACL 수정 |

API7 제품의 관리 DB 등 기존 제품 컨테이너도 사용합니다. Spring과 Keycloak·LDAP를 Docker로 실행하는 구성은 아닙니다.

- 일반 사용자: **브라우저 → Keycloak Code+PKCE → API7 → FinAccess USER API**
- 관리자: **CLI Device Grant 시작 → Keycloak 기본 화면에서 로그인 → curl → API7 → FinAdmin ADMIN API**
- 신원 원천: **LDAP → Keycloak 그룹/속성 → 서명된 JWT → API7 → Spring**

업무 Role은 `oauth-api` Client의 `USER`, `ADMIN` 두 개입니다. ADMIN이 자동으로 USER를 포함하지 않습니다. 두 앱을 하나의 실습 API 리소스 `aud=oauth-api`로 묶고 Role로 분리했습니다. 독립 audience 분리는 이번 최소 구성에 포함하지 않았습니다.

## 유즈케이스와 API 명세

| 메서드·API | 호출 위치 | 역할 | 응답 |
|---|---|---|---|
| GET `/api/user/me` | API7 경유(직접 호출도 검증용 유지) | USER | 200: 검증된 신원·부서·역할 |
| GET `/api/admin/me` | FinAdmin, API7 경유 가능 | ADMIN | 200: 검증된 신원·부서 |
| GET `/api/admin/greeting?name=Demo` | FinAdmin, API7 경유 가능 | ADMIN | 200: 정상 입력 |
| GET `/api/admin/greeting` | FinAdmin, API7 경유 가능 | ADMIN | 400: name 누락·공백·40자 초과 |
| GET `/api/admin/demo-error` | FinAdmin, API7 경유 가능 | ADMIN | 500: 의도적인 시연 예외 |
| GET `/api/admin/missing` | FinAdmin, API7 경유 가능 | ADMIN | 404: 없는 핸들러 |

공통: 토큰 없음·변조·만료는 401, 필요한 Role이 없으면 403. Gateway에서는 USER URL 앞에 `/oauth-access`, ADMIN URL 앞에 `/oauth-admin`을 붙입니다. `POST /oauth-admin/api/admin/me`처럼 허용되지 않은 메서드는 API7에서 403입니다. FinAdmin 루트(`/`)에 화면은 없습니다.

## 실행과 학습

1. [RUNBOOK.md](RUNBOOK.md): 실행·로그인·curl·API7 UI 수정 순서
2. [OAUTH-NOTES.md](OAUTH-NOTES.md): Grant·JWT·부서 전달·SCIM의 차이
3. [AI-GATEWAY.md](AI-GATEWAY.md): API7 AI 기능 조사, 현장 적용 여부 구분
4. [RESULTS-2026-10-15.md](RESULTS-2026-10-15.md): FinAccess API7 연결 검증
5. [RESULTS-2026-10-14.md](RESULTS-2026-10-14.md): 연결 변경 전의 검증 기록

`src`는 Application → SecurityConfig → Controller 순서로 읽습니다. `scripts`는 로컬 준비·실행·CLI 토큰 발급 도구이며 업무 코드가 아닙니다. 프런트 소스는 옆 `finaccess/oauth-lab/src/main/resources/static`에 있습니다.

로그인에서는 `scope=demo.read`를 사용하며 ID Token은 발급·사용하지 않습니다. `demo.read`는 요청한 OAuth scope를 관찰하는 값이고, 현재 API 접근 규칙은 Role입니다. API7의 플러그인 이름이 `openid-connect`인 것과 OIDC 로그인 결과를 앱에서 구현하는 것은 별개입니다.

LDAP 부서 변경의 새 JWT 반영은 확인했습니다. API7 관리 콘솔 사용자를 자동 생성하는 SCIM 연결은 **구조 검토만 했으며 미구현**입니다. 운영 TLS/LDAPS·고가용성·실제 AD·AI 유료 API 호출은 이번 실행 범위 밖입니다.

`gateway/routes.json`, `scripts/apply-api7.py`, `RESULTS.md`는 이전 모의 Gateway 단계의 자료입니다. 새 실습에는 사용하지 않습니다. 현재 설정은 `gateway/finaccess-*.json`과 `gateway/finadmin-*.json`입니다. 과거 금융·ITSM 자료는 [이전 학습 기록](../docs/README.md#이전-학습-기록)으로 구분합니다. main에도 현재 oauth-lab 코드가 있습니다.

## API7에서 두 앱 연결

| Service / Route | 외부 요청 | Gateway 역할 | 실제 서버 |
|---|---|---|---|
| oauth-finaccess / oauth-access-get | GET /oauth-access/api/user/me | USER | host.docker.internal:18100/api/user/me |
| oauth-finadmin / oauth-admin-get | GET /oauth-admin/api/admin/* | ADMIN | host.docker.internal:18101/api/admin/* |

각 앱은 JWT·Role을 다시 검사합니다. `oauth-access-deny`·`oauth-admin-deny`는 허용하지 않은 경로·메서드를 거절합니다. USER 경로의 OPTIONS는 API7 CORS가 직접 처리하고 백엔드로 보내지 않습니다. 화면 주소는 18100으로 유지하며 Nginx나 새 중계 서버는 추가하지 않았습니다.

CORS 허용은 `http://localhost:18100`, `GET,OPTIONS`, 요청 헤더 `Authorization`으로 한정했습니다. `X-OAuth-Gateway`와 `X-Finlab-Backend`는 화면에서 검사 위치를 보여주기 위해 노출합니다. CORS가 허용되어도 JWT와 Role 검사는 생략되지 않습니다.
