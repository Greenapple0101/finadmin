# Gateway와 백엔드의 역할 정책

2026-10-06 구현 기준. 주 시연 환경은 API7 Enterprise 3.10.2의 `http://localhost:18090`입니다. 기존 OSS APISIX는 제거했습니다.

## 검사 순서

API7 Enterprise는 **기본 Route + OIDC + ACL**로 처리합니다. 사용자 정의 함수가 역할 허용 여부를 비교하지 않습니다.

1. Route의 경로·메서드·원래 URI 조건으로 API를 선택합니다.
2. `serverless-pre-function`은 잘못된 토큰 자료형을 거절합니다. 이 단계만으로 인증하지 않습니다.
3. `openid-connect`는 Keycloak 공개 키로 서명·발급자·audience를 검증합니다.
4. `enterprise-identity.lua`는 검증된 `ctx.external_user`의 시간·신원·역할 자료형을 보완 검사하고 신원 헤더를 정리합니다.
5. 기본 `acl`의 `allow_labels.roles`가 해당 API의 허용 역할을 비교합니다.
6. Spring은 전달받은 JWT와 역할을 독립적으로 재검증하고 업무 규칙을 적용합니다.

API Route 12개, 미등록 경로·메서드를 막는 fallback 2개, 프런트 Route 1개입니다. fallback은 OIDC 검사 후 기본 `fault-injection.abort`로 403을 반환하며 upstream에 전달하지 않습니다.

정책 원본은 `infra/gateway/policies.json` 하나입니다. `scripts/setup-api7.py`가 실제 제품 설정으로 변환합니다. 이전 OSS 구성과 RBAC 코드는 제거하고 Enterprise 설정을 직접 만듭니다. [실제 콘솔 강의자료](16-api7-console-walkthrough.md)와 [기본 ACL 전환 설명](17-api7-native-authorization.md)을 함께 보세요.

## API별 정책

아래 역할은 해당 API Client의 역할입니다. 여러 역할은 OR 조건입니다. 표에 없는 메서드와 API 경로는 기본 거절합니다.

| 메서드 | Gateway 경로 | Client | 허용 역할 |
|---|---|---|---|
| GET | `/access/api/hello` | `finaccess-api` | user 또는 approver 또는 admin |
| GET | `/access/api/me` | `finaccess-api` | user 또는 approver 또는 admin |
| POST | `/access/api/companies` | `finaccess-api` | admin |
| GET | `/access/api/companies/{id}` | `finaccess-api` | user 또는 approver 또는 admin |
| POST | `/access/api/companies/{id}/accounts` | `finaccess-api` | admin |
| POST | `/access/api/transfers` | `finaccess-api` | user 또는 admin |
| POST | `/access/api/transfers/{id}/approve` | `finaccess-api` | approver 또는 admin |
| POST | `/access/api/transfers/{id}/reject` | `finaccess-api` | approver 또는 admin |
| POST | `/access/api/transfers/{id}/execute` | `finaccess-api` | approver 또는 admin |
| GET | `/admin/api/hello` | `finadmin-api` | user 또는 admin |
| GET | `/admin/api/me` | `finadmin-api` | user 또는 admin |
| GET | `/admin/api/admin/summary` | `finadmin-api` | admin |

Spring의 직접 `GET /api/hello`는 업무 정보가 없는 공개 진단 예외입니다. Gateway 경유 hello는 앱 역할을 요구합니다. 프런트 정적 파일은 로그인 전에도 필요하므로 공개합니다.

## 책임 분리

| 구성 요소 | 담당 |
|---|---|
| Keycloak | 사용자 로그인, 토큰 발급, Client Role 포함 |
| OpenLDAP | 외부 직원 비밀번호와 그룹 원본 |
| API7 Enterprise | JWT 검증, 경로·메서드별 RBAC, 라우팅 |
| FinAccess | JWT·역할 재검증, iss+sub와 업무 사용자 연결, 회사·이체 규칙 |
| FinAdmin | JWT·역할 재검증, 관리자 API 제한 |

## 업무 데이터와 역할의 구분

회사 소속은 LDAP 그룹에서 자동 결정되지 않습니다. FinAccess 업무 DB의 `iss + sub` 연결에서 판단합니다. 그룹을 제거해 새 토큰의 역할이 사라져도 기존 미만료 JWT는 발급 당시 역할을 유지합니다.

## 정책을 바꿀 때

`policies.json` 수정 → Spring Security의 대응 규칙 수정 → `python3 scripts/setup-api7.py --apply` → 보안 테스트와 실제 요청 검사 순서입니다. API7 콘솔에서 직접 바꾼 관리 대상 설정은 setup 스크립트를 재실행하면 코드의 정책으로 돌아갑니다.

역할에 숫자·공백 같은 잘못된 값이 섞이면 Gateway와 Spring 모두 역할 목록 전체를 거절합니다. 경로의 중복 /·인코딩·점 구간을 이용한 다른 표기도 Gateway에서 기본 거절하도록 원래 URI를 검사합니다.
