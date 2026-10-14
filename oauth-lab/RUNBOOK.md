# FinAccess 화면으로 OAuth 실습하기

## 1 실행 준비

두 저장소를 같은 부모 폴더에 두고 모두 `oauth-focus` 브랜치를 사용합니다. Java 21과 Python 3이 필요합니다. 이 컴퓨터에는 Keycloak 26.7.4가 이미 다운로드되어 있습니다.

다른 컴퓨터에서 처음 받을 때만 finadmin의 `oauth-lab` 안에서 다음 명령을 실행합니다.

```sh
mkdir -p .local
curl -fL -o .local/keycloak.tar.gz https://github.com/keycloak/keycloak/releases/download/26.7.4/keycloak-26.7.4.tar.gz
tar -xzf .local/keycloak.tar.gz -C .local
```

finadmin 저장소에서 실행합니다.

```sh
python3 oauth-lab/scripts/start-local.py
```

이 명령은 Keycloak을 실행하고 옆 `finaccess/oauth-lab/scripts/start-local.py`를 호출합니다. Spring JAR이 화면과 API를 함께 제공합니다. FinAccess 빌드는 `../gradlew -p . bootJar`이며 자동화 테스트를 실행하지 않습니다.

| 대상 | 주소 |
|---|---|
| FinAccess 화면과 USER API | http://localhost:18100/ |
| Keycloak 제품 관리 화면 | http://localhost:18180/admin/ |
| API7 제품 관리 화면 | https://localhost:7443/ |

Keycloak 로그는 `finadmin/oauth-lab/.local/keycloak.log`, FinAccess 로그는 `finaccess/oauth-lab/.local/finaccess.log`입니다. Keycloak의 `started`, Spring의 `Started FinAccessApplication` 메시지로 기동 완료를 확인합니다.

## 2 역할 확인

Keycloak `oauth-lab` → Clients → `oauth-api` → Roles에서 USER와 ADMIN을 확인합니다. Users → Role mapping에서 alice=USER, admin=ADMIN입니다. 기존 소문자 설정에서 이동할 때만 Keycloak 기동 후 `python3 oauth-lab/scripts/configure-roles.py`를 실행합니다.

브라우저 Client는 기존 `oauth-browser`입니다. Redirect URI는 `http://localhost:18100/`, PKCE는 S256입니다. scope는 이번 이동 단계에서 기존 `demo.read`를 유지합니다. OIDC 로그인 결과 처리는 이후 새 전체 요구사항 단계에서 적용합니다.

## 3 사용자 화면 확인

1. FinAccess 화면에서 **Keycloak에서 토큰 받기**를 누릅니다.
2. alice로 로그인하여 발급 성공을 확인합니다.
3. **내 USER 권한 확인**을 누릅니다. 기대 결과는 200이며 응답의 application은 FinAccess입니다.
4. **토큰 없이 호출**을 누릅니다. 기대 결과는 401입니다.
5. **이 페이지의 토큰 지우기** 후 같은 API를 호출하면 다시 401입니다.

화면에는 관리자 API 버튼이 없습니다. FinAdmin은 별도 화면 없이 curl로 호출하는 대상입니다. 일반 사용자의 FinAccess 요청은 API7을 통과하지 않습니다.

## 4 curl로 직접 확인

```sh
curl -i http://localhost:18100/api/user/me
curl -i -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:18100/api/user/me
```

USER 토큰은 200, ADMIN만 있는 토큰은 403, 변조한 토큰은 401을 기대합니다. 응답의 `X-Finlab-Backend: finaccess`로 어느 앱이 응답했는지 확인합니다.

Access Token 수명은 Keycloak에서 60초입니다. Spring 기본 시간 오차 허용은 별도로 적용되므로 exp 직후 바로 거절된다고 단정하지 않습니다. 새 토큰은 **토큰 갱신**으로 받을 수 있습니다. 새로고침하면 메모리의 토큰이 사라집니다.

## 5 수정 후 다시 실행

FinAccess의 `.local/finaccess.pid`에 적힌 PID와 실행 JAR 경로가 맞는지 확인한 뒤 해당 Java 프로세스를 중지합니다. 다시 `python3 oauth-lab/scripts/start-local.py`를 실행하면 수정한 코드로 JAR을 빌드합니다. VS Code에서는 `finaccess/oauth-lab` 폴더를 열고 같은 명령을 실행하면 됩니다.

API7은 별도 Docker 실행 대상입니다. 이번 화면 이동은 API7의 Route·인증·ACL 설정을 덮어쓰지 않습니다. 이전 모의 응답용 `apply-api7.py --apply`는 새 구성에 사용하지 않습니다.
