# Gateway와 백엔드의 역할 정책

2026-10-06 구현 기준. 주 시연 환경은 API7 Enterprise 3.10.2의 `http://localhost:18091`입니다. 기존 Apache APISIX 18090은 비교 환경입니다.

## 검사 순서

1. `serverless-pre-function`: 잘못된 토큰 자료형을 거절합니다. 아직 서명을 믿지 않으며, 이 검사만으로 접근을 허용하지 않습니다.
2. `openid-connect`: Keycloak JWKS로 서명과 발급자·대상을 검증합니다.
3. `serverless-post-function`: exp·nbf·sub를 확인하고 경로·메서드에 필요한 앱 역할을 검사합니다. 다른 앱의 admin이나 Keycloak 관리자 권한은 대신 사용할 수 없습니다.
4. 허용된 요청만 백엔드에 전달합니다. Spring은 같은 JWT를 다시 검증하고 역할·회사·이체 규칙을 검사합니다.

`infra/gateway/policies.json`이 Gateway 정책 원본입니다. `rbac.lua`는 역할 확인, `token-shape.lua`는 거절 전용 자료형 검사입니다. 두 함수는 OIDC와 함께 적용해야 합니다. 서명 없는 JWT 해석을 인증으로 사용하는 구성은 아닙니다.

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
| GET | `/legacy/api/reports` | `finlegacy-api` | reader 또는 admin |
| GET | `/legacy/api/admin/summary` | `finlegacy-api` | admin |

Spring의 직접 `GET /api/hello`는 업무 정보가 없는 공개 진단 예외입니다. Gateway 경유 hello는 앱 역할을 요구합니다. 프런트 정적 파일은 로그인 전에도 필요하므로 공개합니다.

## 책임 분리

| 구성 요소 | 담당 |
|---|---|
| Keycloak | 사용자 로그인, 토큰 발급, Client Role 포함 |
| OpenLDAP | 외부 직원 비밀번호와 그룹 원본 |
| API7 Enterprise | JWT 검증, 경로·메서드별 RBAC, 라우팅, 레거시 신원 헤더 생성 |
| FinAccess | JWT·역할 재검증, iss+sub와 업무 사용자 연결, 회사·이체 규칙 |
| FinAdmin | JWT·역할 재검증, 관리자 API 제한 |
| 레거시 | 샘플 보고서 응답. JWT를 검증하지 않음 |

## 레거시를 안전하게 연결하는 조건

`finlegacy-api`는 별도의 audience이며 reader/admin 역할을 사용합니다. 일반 보고서는 둘 중 하나, 관리자 요약은 admin이 필요합니다. Gateway는 외부 `X-Finlab-Subject`, `X-Finlab-Issuer`, 역할 및 토큰 관련 헤더를 지우고, 검증한 JWT의 sub·iss로 신원 헤더를 만듭니다. Bearer 원문은 레거시에 전달하지 않습니다.

레거시는 호스트 포트를 공개하지 않고 internal 네트워크에만 연결합니다. 이 네트워크 구성원은 레거시와 두 비교용 Gateway뿐입니다. 다른 앱 컨테이너의 실제 IP 직접 호출도 거절됨을 확인했습니다. Docker 관리자/root의 접근까지 막는 보장은 아닙니다. 운영에서는 Gateway와 레거시 간 mTLS·방화벽 정책이 필요합니다.

회사 소속은 LDAP 그룹에서 자동 결정되지 않습니다. FinAccess 업무 DB의 `iss + sub` 연결에서 판단합니다. 그룹을 제거해 새 토큰의 역할이 사라져도 기존 미만료 JWT는 발급 당시 역할을 유지합니다.

## 정책을 바꿀 때

`policies.json` 수정 → Spring Security의 대응 규칙 수정 → `python3 scripts/render-gateway.py` → `python3 scripts/setup-api7.py --apply` → 보안 테스트와 실제 요청 검사 순서입니다. API7 콘솔에서 직접 바꾼 관리 대상 설정은 setup 스크립트를 재실행하면 코드의 정책으로 돌아갑니다.

역할에 숫자·공백 같은 잘못된 값이 섞이면 Gateway와 Spring 모두 역할 목록 전체를 거절합니다. 경로의 중복 /·인코딩·점 구간을 이용한 다른 표기도 Gateway에서 기본 거절하도록 원래 URI를 검사합니다.
