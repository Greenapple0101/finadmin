# 현재 범위와 유즈케이스

[문서 목차](../README.md) · 기준: 2026-10-15 `oauth-lab/` 코드·설정과 날짜별 실행 기록

## 무엇을 확인하는 프로젝트인가

**Keycloak이 발급한 Access Token을 API7과 Spring이 각각 검증하고, USER와 ADMIN 역할에 따라 서로 다른 API를 허용하는 로컬 OAuth2 PoC입니다.** 금융·ITSM 업무 대신 작은 API로 인증 과정과 HTTP 응답을 관찰합니다.

| 요구 | 현재 구현 | 근거·확인 범위 |
|---|---|---|
| 일반 사용자 로그인 화면 | FinAccess가 HTML·JavaScript 제공, Keycloak Code + PKCE 연동 | 10/15 LDAP USER 브라우저 로그인·API7 경유 200 |
| 관리자 curl 호출 | FinAdmin에 별도 화면 없음. CLI에서 Device Grant 시작, Keycloak 화면에서 사람 인증·승인 | 10/14 Device 로그인, 10/15 ADMIN API 200 재확인 |
| Gateway 역할 검사 | API7 Enterprise의 JWT 검증 + ACL | 10/15 USER→ADMIN API, ADMIN→USER API 각각 Gateway 403 |
| 백엔드의 독립 검사 | 각 Spring의 JwtDecoder + hasRole | 10/15 직접 호출에서도 200·401·403 구분 |
| LDAP 연동 | 사용자·그룹·부서를 Keycloak에 연결 | 10/14 부서 변경 전·후 JWT 비교, 10/15 LDAP 두 계정 로그인 |
| 응답 코드 실습 | 정상 200, 입력 오류 400, 시연 예외 500 | 10/14 FinAdmin 실제 응답. 500은 upstream 장애가 아님 |
| 관리 UI 활용 | 실제 API7 제품 콘솔 사용, 수정할 Service·Route·Plugin 안내 | 이번 최소 구성은 관리 API 등록·조회와 트래픽 검증 완료. UI 클릭 변경 검증은 미완료 |
| 사용자·부서 정보의 API7 전달 | 서명된 JWT에 Role·department 포함 | API7을 거쳐 Spring 응답으로 확인. API7 운영자 계정 SCIM 생성은 미구현 |
| AI Gateway | 공식 기능 조사 문서 | LLM 호출·요금·fallback 검증은 미실행 |

## 등장인물과 역할

| 주체 | 실제 예 | 하는 일 |
|---|---|---|
| API 사용자 | ldap-user / USER | FinAccess에서 로그인 후 자기 토큰 정보 조회 |
| API 관리자 역할 사용자 | ldap-admin / ADMIN | CLI로 토큰을 받아 FinAdmin API 호출 |
| 인증 서버 | Keycloak oauth-lab Realm | 사람을 인증하고 토큰 발급 |
| 사용자 디렉터리 | 로컬 OpenLDAP | 직원 비밀번호·그룹·부서의 원천 |
| API Gateway | API7 Enterprise | 경로·메서드 선택, 토큰·역할 검사, 백엔드 전달 |
| Resource Server | FinAccess, FinAdmin | 토큰·역할 재검증 후 API 응답 |
| 제품 설정 운영자 | API7·Keycloak 관리 콘솔 사용자 | 제품 설정 관리. 앱의 ADMIN 역할과 다른 권한 체계 |

FinAdmin은 전체 시스템의 RBAC를 관리하는 서버가 아닙니다. **ADMIN 역할이 필요한 API를 제공하는 예제 서버**입니다. 현재는 회사 A/B 데이터나 실제 관리자 업무를 처리하지 않습니다.

## 유즈케이스

| ID | 누가·무엇을 | 성공 흐름 | 실패·비교 흐름 |
|---|---|---|---|
| UC-01 | USER가 브라우저로 API 호출 | 18100 화면 → Keycloak → 토큰 → API7 → FinAccess 200 | 토큰 없으면 401, ADMIN만 있으면 403 |
| UC-02 | ADMIN이 curl로 API 호출 | Device Grant → Keycloak 승인 → 헤더 파일 → API7 → FinAdmin 200 | USER 토큰이면 Gateway 403 |
| UC-03 | 백엔드의 자체 검사 확인 | 같은 토큰으로 18100·18101 직접 호출 | Gateway를 생략해도 잘못된 토큰·역할 거절 |
| UC-04 | JWT 내용 위조 실험 | 정상 토큰 복사본의 역할만 수정 | 기존 서명과 내용이 맞지 않아 401 |
| UC-05 | LDAP 부서 변경 확인 | ou 변경 → 새 토큰 → department 변경 | 기존 토큰 내용은 그대로. 변경 후 Operations 복원 |
| UC-06 | HTTP 오류 구분 | ADMIN greeting 정상 입력 200 | 잘못된 name 400, 의도적 예외 500 |
| UC-07 | API7 정책을 직접 확인·수정 | 제품 UI에서 해당 Route 확인 → 수정 → curl 확인 → 복원 | UI 조작 완료와 서버 설정 존재를 구분하여 기록 |

## 범위 경계

- 현재 구현: 로컬 OAuth2 Code + PKCE·Device Grant, 수동 Refresh, JWT·Role 검사, LDAP Federation, 두 API의 API7 연결.
- 개념 학습: OAuth2와 OIDC의 차이, Client Credentials, Implicit·Password Grant의 한계. 앱은 `openid` scope와 ID Token을 사용하지 않습니다.
- 미구현·미검증: SCIM 운영자 프로비저닝, 부서별 접근 정책, 기존 JWT 즉시 폐기, 운영 TLS/LDAPS, 실제 AD, Kubernetes·고가용성·부하, AI 모델 호출.
- 소스 범위: 각 저장소의 `oauth-lab/`만 실행합니다. 업무 DB·JPA·자동화 테스트 소스는 포함하지 않습니다.

모든 구성요소는 같은 Mac에서 실행합니다. 두 Spring·Keycloak은 JVM, LDAP는 Mac 프로세스, API7 및 제품 관리 DB는 Docker입니다. 업무 DB가 없다는 말은 API7 제품 DB나 Keycloak의 개발용 H2까지 없다는 뜻이 아닙니다.

다음: [아키텍처·시퀀스](02-architecture.md) → [API 명세](03-api-spec.md) → [실행·시연](../../oauth-lab/RUNBOOK.md).
