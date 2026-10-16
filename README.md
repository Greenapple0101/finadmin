# FinAdmin · OAuth2 ADMIN 실습

별도 프런트 없이 ADMIN API를 제공합니다. Device Grant로 토큰을 받은 뒤 curl로 API7을 거쳐 호출합니다. 전체 시스템의 RBAC를 관리하는 서버는 아닙니다. Keycloak 로그인·토큰 발급, API7과 Spring의 독립적인 JWT·Role 검사를 확인하는 로컬 PoC입니다.

**[현재 문서 목차](docs/README.md)** · **[현재 실행 코드](oauth-lab/README.md)** · **[아키텍처](https://github.com/Greenapple0101/finadmin/blob/main/docs/current/02-architecture.md)**

```text
FinAccess 화면 :18100 ── Code + PKCE ── Keycloak :18180 ── LDAP :18389
FinAccess 화면 ── Bearer ── API7 :18090 /oauth-access/* ── FinAccess USER API
관리자 CLI     ── Bearer ── API7 :18090 /oauth-admin/*  ── FinAdmin ADMIN API :18101
관리자 토큰: Device Grant → Keycloak 기본 화면에서 사람의 로그인·승인
API7 실제 제품 관리 UI: https://localhost:7443
```

| 현재 구성 | 내용 |
|---|---|
| 실행 | 두 Spring·Keycloak은 로컬 JVM, OpenLDAP는 Mac 프로세스, API7 제품은 Docker |
| 역할 | oauth-api Client의 USER·ADMIN. ADMIN이 USER를 자동 포함하지 않음 |
| 토큰 | Code + PKCE / Device Grant, Access Token 사용, ID Token 미사용 |
| 인가 | API7 JWT·ACL → 각 Spring JWT·Role 재검증 |
| LDAP | 사용자·그룹·부서 → Keycloak → JWT. SCIM 계정 생성은 미구현 |
| 현재 범위 제외 | 금융 이체·ITSM·업무 DB·JPA·레거시·신규 자동화 테스트 |

[실행·시연](https://github.com/Greenapple0101/finadmin/blob/main/oauth-lab/RUNBOOK.md) · [API 명세](https://github.com/Greenapple0101/finadmin/blob/main/docs/current/03-api-spec.md) · [10/15 검증·화면](https://github.com/Greenapple0101/finadmin/blob/main/docs/current/06-verification.md)

## 폴더를 읽는 순서

| 위치 | 내용 |
|---|---|
| `docs/README.md` | 현재 설명 문서의 시작점 |
| `oauth-lab/src/main` | 실제 실행하는 작은 Spring 앱 |
| `oauth-lab/scripts` | 로컬 시작과 시연에 필요한 명령 |
| `oauth-lab/build.gradle` | 현재 앱의 의존성과 JAR 빌드 설정 |
| 루트 `settings.gradle`·`gradlew` | 현재 앱만 선택하는 Gradle 실행 도구 |

현재 실행 코드는 `main`과 `oauth-focus`의 `oauth-lab/`에 있습니다. 저장소 루트에서 `./gradlew bootJar`를 실행해도 이 앱 하나만 빌드합니다. 실행은 위 RUNBOOK을 따릅니다. 검증 결과의 실행 날짜는 각 기록에 표시하며 문서 정리일과 구분합니다.
