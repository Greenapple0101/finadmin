# FinAdmin · 현재 프로젝트 문서

**2026-10-15 기준: OAuth2·JWT·Role을 보여 주는 최소 PoC입니다.** FinAccess의 USER API와 FinAdmin의 ADMIN API 모두 API7 Enterprise를 경유합니다. 현재 코드는 두 저장소의 `oauth-lab/`에 있습니다. `main`에도 현재 코드가 병합되어 있으므로 main 전체를 과거 구현이라고 부르지 않습니다.

## 처음 읽는 순서

| 순서 | 문서 | 알 수 있는 것 |
|---|---|---|
| 1 | [범위·유즈케이스](current/01-scope-use-cases.md) | 무엇을 만들었고 무엇은 아직 안 했는지 |
| 2 | [아키텍처·시퀀스](current/02-architecture.md) | 화면·로그인·Gateway·두 API의 연결과 요청 순서 |
| 3 | [API 명세·권한표](current/03-api-spec.md) | 경로·메서드·USER/ADMIN·200/400/500 |
| 4 | [Keycloak·LDAP 설정](current/04-keycloak-ldap.md) | Realm·Client·Role·부서·새 토큰과 기존 토큰 |
| 5 | [API7 설정·UI 실습 안내](current/05-api7-authorization.md) | 실제 제품의 Service·Route·JWT·ACL·CORS |
| 6 | [검증 결과·실제 화면](current/06-verification.md) | 실행 날짜별 근거와 200·403 캡처 |
| 7 | [초보자 코드 읽기](current/07-code-guide.md) | Application → SecurityConfig → Controller |

## 실행·발표 준비

- [실행·시연 RUNBOOK](../oauth-lab/RUNBOOK.md): 로컬 시작, 브라우저, Device Grant, curl, 변경 후 복원.
- [OAuth2·JWT 학습 메모](../oauth-lab/OAUTH-NOTES.md): 현재 쓰는 흐름과 개념만 공부한 흐름 구분.
- [API7 AI 기능 조사](../oauth-lab/AI-GATEWAY.md): 10/14 조사 문서. 실제 모델 호출은 미실행.
- [10/15 USER API7 연결 결과](../oauth-lab/RESULTS-2026-10-15.md): HTTP 관찰 19건.
- [10/14 초기 통합 결과](../oauth-lab/RESULTS-2026-10-14.md): HTTP 관찰 23건. 당시 USER API는 직접 호출.

업무 Role은 대문자 USER·ADMIN 두 개, 공통 audience는 oauth-api입니다. 부서는 JWT 속성 전달이며 회사·부서별 데이터 인가나 SCIM 운영자 생성이 아닙니다. 현재 앱에 업무 DB·JPA·금융·ITSM·레거시 기능은 포함하지 않습니다.

## 이전 학습 기록

아래 링크는 학습 과정과 당시 검증 근거를 보관합니다. **현재 구성을 설치하거나 시연할 때는 위 문서만 사용합니다.** 옛 링크를 깨뜨리지 않도록 파일 위치를 유지하고 각 문서 맨 위에도 같은 구분을 표시했습니다.

<details>
<summary>과거 금융·ITSM·인증 학습 문서 펼치기</summary>

- [01. 두 번째 백엔드를 만드는 순서](01-first-application.md)
- [02. Keycloak을 실행하는 순서](02-keycloak-setup.md)
- [03. Realm·Client·사용자·역할을 구분하기](03-keycloak-realm-client-role.md)
- [04. 로그인에서 API 호출까지 토큰 따라가기](04-access-token.md)
- [05. FinAdmin이 받은 JWT를 직접 검증하기](05-jwt-validation.md)
- [06. 관리자 역할이 있어야 데이터를 보내기](06-admin-authorization.md)
- [07. APISIX에서 검사하고, 백엔드에서도 다시 검사하기](07-apisix-gateway.md)
- [08. 실제 로그인부터 두 백엔드와 모의 이체까지 검증하기](08-end-to-end-verification.md)
- [Keycloak · Apache APISIX · Spring Resource Server 인증·인가 검증](09-internal-sharing.md)
- [FinLab 인증·인가 아키텍처](10-architecture.md)
- [Keycloak 설정을 직접 따라 읽는 FinLab 실습 보고서](11-keycloak-hands-on-report.md)
- [FinLab Keycloak 설정값 목록과 확인 기록](12-keycloak-settings-reference.md)
- [OpenLDAP → Keycloak → JWT → 두 Spring 앱 실습 보고서](13-ldap-federation-hands-on.md)
- [Gateway와 백엔드의 역할 정책](14-gateway-rbac-policy.md)
- [API7 Enterprise 연동과 검증 보고서](15-api7-enterprise-integration.md)
- [실제 API7 Enterprise 콘솔 읽는 법](16-api7-console-walkthrough.md)
- [인증·인가를 API7 기본 기능으로 모으기](17-api7-native-authorization.md)
- [FinAdmin을 ITSM 서비스 요청 앱으로 발전시키기](18-itsm-service-requests.md)

</details>
