# Keycloak 계정·역할과 토큰

[문서 목차](../README.md) · 기준: 2026-10-16 저장소 설정

## 계정과 인증

사용자 계정·비밀번호·역할은 Keycloak의 **oauth-lab** Realm에서 직접 관리합니다.
[realm.json](../../oauth-lab/keycloak/realm.json)은 다음 두 사용자를 생성합니다.

| 사용자 | oauth-api Client Role | 사용할 API |
|---|---|---|
| alice | USER | FinAccess `/api/user/me` |
| admin | ADMIN | FinAdmin `/api/admin/**` |

ADMIN은 USER를 자동으로 포함하지 않습니다. API7 제품 운영자 계정과 Keycloak master Realm의 `bootstrap-admin`은 위 앱 사용자와 별도입니다.

비밀번호는 시작 스크립트가 비공개 `.local/credentials.json`에 생성하고 환경 변수로 Realm import에 전달합니다. 공개 설정 파일에는 실제 비밀번호를 넣지 않습니다.

## Client

| Client | 역할 | 인증 흐름 |
|---|---|---|
| oauth-browser | FinAccess 브라우저 | public client, Authorization Code + PKCE S256 |
| oauth-cli | 관리자 CLI | public client, Device Authorization Grant |
| oauth-api | 두 Resource Server의 공통 대상·역할 공간 | bearer-only, USER·ADMIN client role |

| 설정 | 값 |
|---|---|
| redirect URI / browser origin | `http://localhost:18100/` / `http://localhost:18100` |
| 요청 scope | `demo.read` |
| audience | `oauth-api` |
| issuer | `http://localhost:18180/realms/oauth-lab` |
| Access Token 수명 | 60초 |
| 앱 Client의 Implicit·Direct Access Grants | 비활성화 |
| ID Token | 현재 요청에서 발급·사용하지 않음 |

`demo.read`는 scope이며 API 접근 정책은 별도의 USER·ADMIN 역할을 검사합니다. `openid` scope를 요청하지 않으므로 현재 앱은 Access Token만 사용합니다.

## JWT Mapper

| Mapper | JWT 내용 | 검사·사용 위치 |
|---|---|---|
| api-audience | `aud`에 `oauth-api` | API7·두 Spring의 대상 검사 |
| api-roles | `resource_access.oauth-api.roles` | API7 ACL·Spring `hasRole` |
| subject | `sub` | 검증된 사용자 식별자 응답 |

Keycloak이 사용자 인증 후 역할을 담은 JWT를 발급합니다. API7은 JWT를 검증하고 요청 경로에 필요한 역할을 확인합니다. Spring도 같은 토큰의 서명·발급자·대상·만료와 자신의 역할 조건을 다시 검사합니다.

## 설정 적용과 변경

처음 시작할 때 Realm을 import합니다. 기존 Realm은 import만으로 덮어쓰지 않습니다.

- `scripts/configure-auth.py`: `oauth-browser`·`oauth-cli` 설정과 토큰 Mapper를 원본에 맞춥니다. 원본에서 빠진 Mapper는 제거합니다.
- `scripts/configure-roles.py`: `alice=USER`, `admin=ADMIN` 역할을 적용합니다.

역할을 바꾼 뒤에는 새 토큰을 발급해 확인합니다. 기존 JWT는 발급 당시 역할을 유지하며, 사용자 설정 변경만으로 즉시 다시 작성되지 않습니다.

[OAuth 메모](../../oauth-lab/OAUTH-NOTES.md) · [실행·시연](../../oauth-lab/RUNBOOK.md)
