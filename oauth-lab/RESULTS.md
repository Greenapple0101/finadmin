> 최신 LDAP·FinAdmin·API7 실제 연동 결과는 [2026-10-14 기록](RESULTS-2026-10-14.md)을 확인하세요. 아래는 이전 단계 기록입니다.

> 프런트 이동 이후 결과는 [FinAccess 실행 기록](https://github.com/Greenapple0101/finaccess/blob/oauth-focus/oauth-lab/RESULTS.md)을 확인하세요. 아래는 이전 Gateway 모의 응답 단계의 기록입니다.

# OAuth2 실습 실행 기록

2026-10-14 새로 구성하는 실습입니다. 기존 FinLab의 검사 결과를 재사용하지 않습니다.

## 확인 완료

| 실행 | 실제 결과 | 확인 방법 |
|---|---|---|
| Keycloak 26.7.4 로컬 JVM 기동 | JDK 21.0.11, H2, localhost:18180 정상 응답 | 기동 로그와 HTTP |
| 화면 파일 제공 | JDK jwebserver, localhost:18100 정상 표시 | 브라우저 |
| alice Authorization Code + PKCE | 토큰 발급, scope=demo.read, aud=oauth-api, user 역할 | 실제 HTTP 코드 교환 |
| admin Authorization Code + PKCE | 토큰 발급, user와 admin 역할 | 실제 HTTP 코드 교환 |
| openid scope 제외 | 두 계정 모두 응답에 id_token 없음 | 토큰 응답 필드 확인 |
| 잘못된 PKCE verifier | HTTP 400, invalid_grant | 별도 인증 코드로 교환 시도 |
| 브라우저 alice 인증과 코드 교환 | 발급 성공, Bearer, 수명 60초, ID Token 없음 | 실제 Keycloak 화면에서 인증 |
| 브라우저 토큰 갱신 | 새 토큰 발급 성공 | 화면의 토큰 갱신 버튼 |

시작 과정에서 중복 실행이 H2 파일 잠금으로 실패한 것을 확인했습니다. 시작 도구에 실행 중 PID 확인을 추가했으며, 정상 기동한 한 프로세스를 사용합니다.

## 준비했지만 실행하지 않은 것

API7 설정 JSON과 적용 명령은 작성했습니다. API7은 현재 중지되어 있고, Docker 사용 허용 또는 Linux 실행 환경 선택이 필요합니다. 아래 항목을 완료로 간주하지 않습니다.

- 설정 JSON이 설치된 API7 버전에서 수용되는지 확인
- mocking 응답보다 JWT 검증과 ACL이 먼저 적용되는지 확인
- alice 일반 경로 200, 관리자 경로 403
- admin 관리자 경로 200
- 토큰 없음·잘못된 서명·만료 401
- 브라우저의 Gateway 호출과 CORS

Gateway 예상 결과는 아직 실측하지 않았습니다. 기존 FinLab의 과거 검증 개수와 합산하지 않습니다.
