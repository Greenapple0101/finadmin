# OAuth 실습 구성과 FinAccess 화면 분리

**프런트는 옆 FinAccess 저장소로 이동했습니다.** 이 폴더에는 Keycloak 설정과 실행 보조 도구를 둡니다. 현재 사용자 화면과 USER API의 코드는 [FinAccess OAuth 실습](https://github.com/Greenapple0101/finaccess/tree/oauth-focus/oauth-lab)에 있습니다.

## 구성과 진행 상태

| 영역 | 화면 | 요청 경로 | 상태 |
|---|---|---|---|
| FinAccess | 있음, Spring이 직접 제공 | 브라우저 → FinAccess USER API | 현재 구현 |
| FinAdmin | 없음 | curl → API7 → FinAdmin ADMIN API | 새 최소 구성 연동 예정 |
| Keycloak | 제품 로그인·관리 화면 | Authorization Code + PKCE | 기존 OAuth2 실습 사용 |
| API7 Enterprise | 제품 관리 UI | 관리자가 Service·Route·JWT·ACL 설정 | Docker 실행, 신규 경로 수동 실습 예정 |

업무 역할은 `USER`, `ADMIN` 두 개입니다. 회사·부서 이름을 Role로 만들지 않습니다. API7 관리 콘솔의 운영자 권한은 이 업무 역할과 별개입니다.

## 현재 기획과 유즈케이스

목적은 일반 사용자가 Keycloak 토큰을 받고 FinAccess에 직접 접근하는 흐름을 확인하는 것입니다.

| 사용자 | 하는 일 | 결과 |
|---|---|---|
| alice, USER | FinAccess 화면에서 토큰 발급 후 USER API 호출 | 200 |
| 토큰 없는 사용자 | 같은 API 호출 | 401 |
| admin, ADMIN만 보유 | USER API 호출 | 403 |

API 명세는 `GET http://localhost:18100/api/user/me`입니다. Bearer Access Token을 요구하며 `oauth-lab` 발급자, `oauth-api` audience와 USER 역할을 확인합니다. 화면은 `GET /`, `GET /app.js`로 로그인 전에도 제공됩니다.

## 실행

두 저장소를 같은 부모 폴더에 두고 `oauth-focus` 브랜치를 사용합니다.

```sh
# finadmin 저장소에서
python3 oauth-lab/scripts/start-local.py
```

이 명령은 로컬 JVM Keycloak과 옆 FinAccess의 Spring을 시작합니다. FinAdmin이 프런트를 제공하는 것이 아니며, 이전 `jwebserver`는 사용하지 않습니다. 상세 순서는 [실행 가이드](RUNBOOK.md)를 확인하세요.

기존 Realm을 소문자 역할로 만들었다면 Keycloak 기동 후 다음 명령을 한 번 실행합니다. 신규 Realm import에는 처음부터 대문자 역할이 들어 있습니다.

```sh
python3 oauth-lab/scripts/configure-roles.py
```

## 이전 단계와 향후 범위

`gateway/routes.json`과 `scripts/apply-api7.py`는 **이전 Gateway 모의 응답 실습의 보관 자료**입니다. 새 구성의 FinAccess는 Gateway를 경유하지 않으므로 지금 이 스크립트를 적용하지 않습니다. 새 ADMIN 경로는 실제 API7 관리 UI에서 직접 구성하는 방식으로 진행합니다.

[이전 실행 기록](RESULTS.md)은 해당 날짜의 OAuth 전용 결과입니다. OIDC·LDAP 및 새 FinAdmin·API7 연동과 SCIM을 이번에 모두 검증한 기록이 아닙니다. Kubernetes는 향후 배포 대상이고 현재는 구축하지 않습니다.

비밀번호와 토큰, Keycloak H2 DB는 Git에서 제외한 `.local`에 있습니다. 기존 금융·ITSM 코드는 저장소의 과거 구현으로 보존합니다.
