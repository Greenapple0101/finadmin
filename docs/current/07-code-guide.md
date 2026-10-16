# 처음 읽는 코드와 설정의 순서

[문서 목차](../README.md) · 현재 실행 코드만 설명합니다.

## 폴더부터 구분하기

두 저장소에서 **oauth-lab/src/main**을 펼칩니다. 각 앱의 Java 파일 3개부터 읽습니다. 루트의 `settings.gradle`은 이 앱 하나만 선택하며, API7 제품의 `compose.api7.yaml`과 `infra/api7/config.yaml`은 RUNBOOK에서 별도로 안내합니다.

| 순서 | 파일 | 먼저 이해할 내용 |
|---|---|---|
| 1 | [FinAdminApplication.java](../../oauth-lab/src/main/java/io/github/greenapple0101/finadmin/oauth/FinAdminApplication.java) | JVM의 main이 Spring 서버를 시작 |
| 2 | [application.properties](../../oauth-lab/src/main/resources/application.properties) | 18101 포트, 신뢰할 issuer와 JWKS 주소 |
| 3 | [SecurityConfig.java](../../oauth-lab/src/main/java/io/github/greenapple0101/finadmin/oauth/SecurityConfig.java) | 요청이 Controller에 오기 전 토큰·역할 검사 |
| 4 | [AdminController.java](../../oauth-lab/src/main/java/io/github/greenapple0101/finadmin/oauth/AdminController.java) | 검사를 통과한 요청에 200·400·500 응답 |
| 5 | [FinAccess 읽는 순서](https://github.com/Greenapple0101/finaccess/blob/main/docs/current/01-code-reading.md) | 화면이 토큰을 얻고 API7에 보내는 과정 |
| 6 | [Gateway 설정](05-api7-authorization.md) | 그 앞에서 API7이 같은 토큰·역할을 검사 |
| 7 | [Keycloak 설정](04-keycloak.md) | 자체 계정·역할과 토큰 Mapper |

각 Spring 앱의 Java 파일은 Application·SecurityConfig·Controller 3개입니다. 이번 최소 앱에는 Entity·Repository·JPA·업무 DB·Flyway가 없습니다.

## SecurityConfig의 세 부분

`securityFilterChain`은 검사 순서를 정합니다. FinAdmin은 GET `/api/admin/**`에 `hasRole("ADMIN")`을 요구하고 나머지는 거절합니다. 쿠키 로그인 세션 대신 요청마다 Bearer 토큰을 받도록 stateless로 구성했습니다. ERROR·FORWARD 허용은 오류 응답을 처리하는 내부 dispatch 규칙이며 공개 관리자 API를 추가하는 설정이 아닙니다.

`jwtDecoder`는 서명과 `iss`, `aud=oauth-api`, 시간, 필수 `exp`·`sub`를 검사합니다. Spring의 시간 오차 허용은 현재 실습에서 0초입니다. 공개 키를 가져오는 주소와 신뢰할 issuer는 서로 다른 설정 항목입니다.

`readRoles`는 **검증된 JWT**의 `resource_access → oauth-api → roles`를 읽습니다. USER·ADMIN만 Spring의 `ROLE_USER`·`ROLE_ADMIN`으로 바꿉니다. `hasRole("ADMIN")`은 이 내부 이름을 찾습니다. 역할이 없으면 빈 권한 목록이 되어 해당 API를 통과하지 못합니다.

CSRF 비활성화는 이 API가 브라우저의 자동 전송 인증 쿠키를 쓰지 않고 명시적 Bearer 헤더로 인증하는 구성과 함께 이해합니다. “JWT만 있으면 모든 앱에서 CSRF를 꺼도 된다”는 일반 규칙은 아닙니다.

## Controller를 읽을 때

- `me`: 검증된 Jwt에서 sub를 읽어 응답합니다. 요청자가 쓴 사용자 ID 헤더를 믿지 않습니다.
- `greeting`: name 입력을 검사해 200 또는 400을 만듭니다. DB 저장은 하지 않습니다.
- `demoError`와 `handleDemoError`: 발표용 예외 하나를 500으로 바꿉니다. 시스템의 모든 예외를 숨겨 성공으로 바꾸는 처리가 아닙니다.

비밀번호 검사는 이 Controller에 없습니다. Keycloak이 자체 계정으로 로그인할 때 처리합니다. Spring이 확인하는 것은 그 결과로 발급된 Access Token입니다.

## Python 도구는 무엇인가

| 도구 | 역할·주의점 |
|---|---|
| start-local.py | Keycloak·두 JVM 앱 기동. 기존 API7 제품 설치를 대신하지 않음 |
| configure-roles.py / configure-auth.py | 실습 Realm의 자체 계정 역할·Client·토큰 Mapper 설정. 관리 대상 값을 변경함 |
| init-api7.py | 없는 실습 Service·Route만 생성, 기존 UI 변경은 유지 |
| export-api7.py | 현재 제품 설정을 읽어 비공개 로컬 파일로 저장 |
| device-login.py | 사람이 Keycloak에서 승인한 결과를 기다려 CLI 토큰 저장 |
| tamper-token.py | 테스트용 복사본 JWT의 역할을 바꿔 서명 실패 관찰 |

도구 내부의 관리용 인증은 사용자 앱의 로그인 Grant와 구분합니다. 실제 계정·토큰·API7 라이선스는 공개 코드나 문서에 적지 않습니다.

다음 학습은 [유즈케이스](01-scope-use-cases.md)의 요청 한 건을 고르고, [시퀀스](02-architecture.md) → SecurityConfig → Controller → 응답 순서로 따라가면 됩니다.
