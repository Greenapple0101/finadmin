# FinAdmin · 현재 프로젝트 문서

**2026-10-16 정리 기준: OAuth2·JWT·Role을 보여 주는 최소 PoC입니다.** FinAccess의 USER API와 FinAdmin의 ADMIN API 모두 API7 Enterprise를 경유합니다. 현재 코드는 두 저장소의 `oauth-lab/`에 있습니다.

## 처음 읽는 순서

| 순서 | 문서 | 알 수 있는 것 |
|---|---|---|
| 1 | [범위·유즈케이스](current/01-scope-use-cases.md) | 무엇을 만들었고 무엇은 아직 안 했는지 |
| 2 | [아키텍처·시퀀스](current/02-architecture.md) | 화면·로그인·Gateway·두 API의 연결과 요청 순서 |
| 3 | [API 명세·권한표](current/03-api-spec.md) | 경로·메서드·USER/ADMIN·200/400/500 |
| 4 | [Keycloak 설정](current/04-keycloak.md) | 자체 계정·Realm·Client·Role·토큰 |
| 5 | [API7 설정·UI 실습 안내](current/05-api7-authorization.md) | 실제 제품의 Service·Route·JWT·ACL·CORS |
| 6 | [검증 기록](current/06-verification.md) | 현재 구성의 실제 확인 범위와 재현 절차 |
| 7 | [초보자 코드 읽기](current/07-code-guide.md) | Application → SecurityConfig → Controller |

## 실행·발표 준비

- [실행·시연 RUNBOOK](../oauth-lab/RUNBOOK.md): 로컬 시작, 브라우저, Device Grant, curl, 변경 후 복원.
- [OAuth2·JWT 학습 메모](../oauth-lab/OAUTH-NOTES.md): 현재 쓰는 흐름과 개념만 공부한 흐름 구분.
- [API7 AI 기능 조사](../oauth-lab/AI-GATEWAY.md): 10/14 조사 문서. 실제 모델 호출은 미실행.
- [현재 검증 기록](current/06-verification.md): 실행 환경과 실제 확인 범위.

업무 Role은 대문자 USER·ADMIN 두 개, 공통 audience는 oauth-api입니다. 계정·비밀번호·역할은 Keycloak이 직접 관리합니다. 현재 앱에 업무 DB·JPA·금융·ITSM·레거시 기능은 포함하지 않습니다.
