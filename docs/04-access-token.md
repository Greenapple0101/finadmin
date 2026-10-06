# 04. 로그인에서 API 호출까지 토큰 따라가기

이번 실습의 실제 화면은 <http://localhost:18090/>입니다. `frontend/index.html`이 버튼을 보여주고 `frontend/app.js`가 로그인과 API 호출을 연결합니다.

## 실행 순서

1. 로그인 버튼을 누르면 브라우저가 무작위 `state`와 PKCE `verifier`를 만듭니다.
2. verifier의 SHA-256 결과인 challenge를 Keycloak에 보냅니다.
3. 사용자는 Keycloak 화면에서 아이디와 비밀번호를 입력합니다.
4. 로그인에 성공하면 Keycloak은 원래 화면으로 일회용 `code`를 보냅니다.
5. 화면은 state와 발급자, 요청 시간을 확인하고 code와 원래 verifier를 토큰 endpoint에 보냅니다.
6. Keycloak이 돌려준 액세스 토큰을 메모리에 보관합니다.
7. API 요청의 `Authorization: Bearer ...` 헤더에 액세스 토큰을 붙입니다.
8. API7 Enterprise와 목적지 Spring 앱이 각각 토큰을 검증합니다.

비밀번호를 우리 프런트 코드나 백엔드에 넘겨 로그인시키지 않습니다. 비밀번호 입력은 Keycloak이 담당합니다. 자동 검증 스크립트도 같은 로그인 폼과 Code + PKCE 흐름을 따라갑니다.

state는 내가 시작한 로그인에 대한 응답인지 확인하기 위한 값입니다. PKCE는 코드를 토큰으로 바꾸는 요청자가 로그인 시작 때의 verifier를 가지고 있는지 증명합니다. 코드가 주소창에 계속 남지 않도록 화면은 콜백 처리 시 URL을 정리합니다.

## JWT 안의 정보 읽기

JWT는 점으로 구분된 세 부분이며, 내용이 암호화되어 숨겨진 비밀번호 보관함은 아닙니다. 내용을 읽을 수 있다는 것과 신뢰할 수 있다는 것은 다릅니다.

| 항목 | 뜻 |
| --- | --- |
| iss | 발급한 Realm의 주소 |
| sub | Keycloak 사용자 식별자 |
| aud | 이 토큰을 사용할 수 있는 API |
| exp | 만료 시각 |
| nbf | 값이 있으면 사용을 시작할 수 있는 시각 |
| resource_access | 앱별 역할 |

API 호출에 쓰는 것은 액세스 토큰입니다. ID 토큰은 API 접근용으로 사용하지 않습니다. 이번 화면은 사용자 표시도 ID 토큰을 직접 믿어서 만들지 않고, `/api/me`에서 백엔드가 검증한 신원을 받아 보여줍니다.

## 토큰 보관과 로그아웃

화면은 액세스 토큰을 메모리에만 보관합니다. 새로고침하면 토큰이 사라지고 다시 로그인해야 합니다. 로그인 왕복 동안의 state/verifier만 sessionStorage에 잠시 넣고 처리 후 삭제합니다. 액세스 토큰을 localStorage에 쓰지 않습니다.

로그아웃 버튼은 메모리의 토큰을 지우고 Keycloak 로그아웃으로 이동합니다. 이미 발급된 JWT가 모든 API에서 즉시 무효화되는 것을 의미하지 않습니다. 공개 키로 검증하는 방식은 만료까지 유효할 수 있습니다. 이번 실습의 기본 수명은 5분이며, 즉시 폐기·사용자 비활성화 반영 정책은 별도 설계 항목입니다.

사용자 요청에 따라 `verify.py`가 발급한 실제 실습 토큰은 Git 밖 데스크탑 `finadmin-local-secrets.md`에 기록합니다. 해당 파일과 실행용 `.env`는 소유자만 읽고 쓸 수 있지만 평문입니다. 공개 MD와 Git에는 넣지 않습니다.

## 직접 보는 순서

1. alice로 로그인 → FinAdmin 내 정보 200 → 관리자 요약 403.
2. 로그아웃 후 admin으로 로그인 → 관리자 요약 200.
3. 토큰 없이 요청 버튼 → 401.
4. FinAccess 내 정보의 `sub`와 FinAdmin 내 정보의 `subject`가 같은지 비교. 둘 다 검증된 JWT의 `sub`를 보여줍니다.

한 브라우저 앱에서 두 API의 인증·인가를 확인하는 데모입니다. 여러 프런트 앱 사이의 SSO 시연은 구현 범위에 넣지 않았습니다.

[Keycloak OIDC 가이드](https://www.keycloak.org/securing-apps/oidc-layers), [OAuth PKCE 표준](https://www.rfc-editor.org/rfc/rfc7636)
