# 현재 구성 검증

[문서 목차](../README.md) · 기준: 2026-10-16

현재 계정은 Keycloak 자체 사용자 `alice=USER`, `admin=ADMIN`입니다. 이전 구성에서 수집한 화면과 실행 결과는 현재 계정 구성의 검증 근거로 사용하지 않습니다.

## 재현할 요청

| 요청 | 예상 결과 |
|---|---|
| alice → USER API | 200, 사용자 식별자·USER 역할 |
| admin → ADMIN API | 200, 사용자 식별자 |
| USER → ADMIN API / ADMIN → USER API | API7에서 403, 직접 Spring 호출도 403 |
| 토큰 없음·서명 변조·실제 만료 | 401 |
| 허용 Origin의 OPTIONS | 200, `Access-Control-Allow-Origin: http://localhost:18100` |
| ADMIN greeting 정상 / 입력 누락 | 200 / 400 |
| ADMIN demo-error / 없는 핸들러 | 500 / 404 |

1. [RUNBOOK](../../oauth-lab/RUNBOOK.md)으로 Keycloak·두 앱·API7을 준비합니다.
2. 브라우저에서 alice로 로그인하고 USER API를 호출합니다.
3. 새 로그인에서 admin으로 바꾸고 같은 USER API의 거절을 확인합니다.
4. Device Grant로 admin 토큰을 받아 관리자 API를 호출합니다.
5. 같은 토큰으로 Spring을 직접 호출하여 권한 검사 결과를 비교합니다.
6. 복사본 JWT 변조와 정상 토큰의 실제 만료를 별도로 확인합니다.

위 표는 재현 기준입니다. 비밀번호·토큰·비공개 export는 Git에 올리지 않습니다.

## 2026-10-16 실행 확인

Windows의 Docker에서 임시 Keycloak 26.7.4와 Java 21 기반의 두 앱을 실행하고, 기존 API7 3.10.2 게이트웨이로 요청했습니다. 저장소의 Realm 원본을 새로 import하고 매번 생성한 임시 비밀번호로 검증했습니다. 검증용 서버와 계정은 종료 후 보관하지 않습니다.

| 검사 | 실제 결과 |
|---|---|
| 두 저장소의 Gradle bootJar | 모두 성공 |
| Python 구문·JSON·문서 링크·현재 설정 참조 | 검사 통과 |
| Keycloak 사용자 저장소 | 자체 사용자 alice·admin만 존재, 외부 User Storage Provider 없음 |
| configure-auth / configure-roles 두 번 실행 | 성공, 두 Client의 Mapper가 audience·roles·subject로 일치 |
| 원본에서 빠진 시험용 Mapper 정리 | 재설정 후 제거 확인 |
| alice·admin Code+PKCE | 각각 비밀번호 로그인·state·issuer·code 교환·토큰 역할 확인 |
| USER→USER / ADMIN→ADMIN | API7 경유와 Spring 직접 호출 모두 200 |
| USER→ADMIN / ADMIN→USER | 두 검사 위치 모두 403 |
| 토큰 누락·서명 변조·정상 토큰 실제 만료 | 두 검사 위치 모두 401 |
| USER Refresh | 역할을 유지한 새 Access Token 발급 |
| CORS 사전 요청 | 200 및 허용 Origin 확인 |
| Device Grant 시작 요청 | device_code 발급 확인 |

로그인은 HTTP 클라이언트로 재현했습니다. 실제 브라우저 화면 조작, Device Grant의 사람 승인부터 최종 토큰 발급까지의 전체 흐름, greeting·demo-error 응답은 이번 변경 검증에서 다시 실행하지 않았습니다. 임시 검증은 JUnit 테스트 개수로 계산하지 않습니다.
