# Keycloak · Apache APISIX · Spring Resource Server 인증·인가 검증

작성일: 2026-09-29
저장소: [FinAccess](https://github.com/Greenapple0101/finaccess), [FinAdmin](https://github.com/Greenapple0101/finadmin)

## 진행 목적

Keycloak 로그인 연동을 실제 API 사용 흐름까지 확장하여, Gateway와 여러 백엔드가 JWT를 독립적으로 검증하고 역할·업무 데이터 범위에 따라 접근을 제한하는 구성을 구현했습니다.

기존 금융 업무 실습 앱인 FinAccess를 첫 번째 Resource Server로 사용하고, 관리자 API를 제공하는 FinAdmin을 별도 프로세스로 구성했습니다. 프런트에서 받은 액세스 토큰이 Apache APISIX를 거쳐 각 앱까지 전달되는 흐름과 실패 사례를 확인했습니다.

## 요구사항과 구현 결과

| 요구사항 | 구현 및 확인한 결과 |
| --- | --- |
| 여러 백엔드를 대상으로 인증 체계 확인 | FinAccess와 FinAdmin을 독립적인 Spring 앱·컨테이너로 실행 |
| APISIX Gateway에서 JWT 검사 | Bearer 토큰의 서명·발급자·대상·시간 조건 검사 |
| Gateway 이후에도 백엔드에서 검증 | 두 앱을 각각 OAuth2 Resource Server로 구성하고 직접 호출 실패도 확인 |
| Keycloak 역할에 따라 관리자 데이터 제한 | Client별 역할을 토큰에 넣고 FinAdmin admin만 관리자 API 허용 |
| 발급된 토큰을 실제 업무에 사용 | FinAccess에서 검증된 iss + sub를 업무 사용자에 연결하여 요청·승인·실행 처리 |
| 정상 로그인 외 실패 사례 확인 | 토큰 누락·변조·만료·미래 사용 시각·대상 불일치·역할 부족·회사 불일치 검사 |

## 구성

![FinLab 인증·인가 아키텍처](images/finlab-architecture.png)

[그림을 읽는 순서](10-architecture.md)

```text
프런트 ── Authorization Code + PKCE ── Keycloak
프런트 ── 액세스 토큰 ── Apache APISIX
                           ├── FinAccess: JWT → 앱 역할 → 회사·계좌·이체 규칙
                           └── FinAdmin: JWT → 앱 관리자 역할 → 관리자 샘플 응답
```

| 구성 요소 | 역할 |
| --- | --- |
| Keycloak 26.7.4 | 사용자 로그인, 앱별 역할, 토큰 발급 |
| Apache APISIX 3.18.0 | standalone 파일 설정으로 API 라우팅·JWT 검증·토큰 전달 |
| FinAccess | 회사·계좌·이체 API와 업무 데이터 접근 제한 |
| FinAdmin | 독립적인 JWT 검증과 관리자 API 역할 제한 |
| 간단한 웹 화면 | 실제 로그인 및 사용자별 API 응답 비교 |
| PostgreSQL 17.11 | Keycloak 설정과 FinAccess 실습 데이터 저장 |

두 백엔드는 Java 21·Spring Boot 4.1.1을 사용합니다. 한 프런트에서 두 API를 호출하는 구조이며 여러 프런트 사이의 SSO 시연을 구현 범위로 삼지 않았습니다.

## 주요 구현 내용

### 1. 사용자 로그인과 토큰 전달

프런트에서 Authorization Code + PKCE로 로그인합니다. 로그인 응답의 state·발급자와 코드 교환을 확인하고, API 호출에는 액세스 토큰을 Authorization 헤더에 붙입니다.

APISIX는 토큰을 검증한 뒤 같은 Bearer 토큰을 목적지 백엔드로 전달합니다. 백엔드는 Gateway가 보냈다는 이유만으로 신원을 인정하지 않고 자체 검증을 수행합니다. 호출자가 작성한 사용자·역할 헤더를 신뢰하지 않습니다.

### 2. JWT 검증 조건

각 Spring 앱은 서명, issuer, 만료 및 사용 가능 시각, 대상 audience를 검사하고 사용자 식별자와 만료 시간이 있는지 확인합니다. 공개 발급자 주소와 Docker 내부 공개 키 주소를 구분해 설정했습니다.

실제 연동 과정에서 Keycloak의 기본 `basic` Client Scope가 사용자 식별자 `sub`를 넣는다는 점을 확인했습니다. 역할과 audience만 설정한 상태를 완성된 토큰 연결로 간주하지 않고, 백엔드가 요구하는 신원 정보까지 전달하도록 맞췄습니다.

### 3. 앱별 역할과 데이터 접근

FinAdmin은 `resource_access.finadmin-api.roles`만 읽어 관리자 권한을 판단합니다. FinAccess의 관리자 역할이나 Keycloak 자체 운영 관리자 권한과 혼동하지 않도록 분리했습니다.

FinAccess는 역할 검사에 더해 회사 소속을 확인합니다. 같은 user 역할이어도 다른 회사 데이터나 출금 계좌에는 접근할 수 없도록 했습니다. 관리자 역할이 있어도 자기 승인 금지 같은 업무 규칙은 적용됩니다.

### 4. 요청자·처리자 신원 연결

FinAccess의 요청자·승인자·실행자는 본문에서 받은 ID 대신 검증된 토큰의 `iss + sub`로 업무 DB 사용자를 찾아 결정합니다. 기존 방식의 `requesterId` 또는 `actorId`를 본문에 넣으면 400으로 거절합니다.

검증 결과에서도 이체 요청자, 승인자, 실행자가 해당 로그인 사용자의 업무 ID로 기록되는지 확인했습니다. 실습 사용자 등록 및 업무 DB 연결은 검증 스크립트가 준비하며, 일반 사용자 프로비저닝 API는 아직 없습니다.

## 검증 결과

| 구분 | 결과 |
| --- | --- |
| FinAccess Java 테스트 | 149개 통과 |
| FinAdmin Java 테스트 | 19개 통과 |
| 실제 서버 간 HTTP 결과 검사 | 46개 통과 |
| 모의 이체 DB 확인 | 1,000원 이체 후 출금 9,000원·입금 1,000원 |
| 실제 브라우저 | alice의 내 정보 200·관리자 요약 403, 로그아웃 후 admin의 관리자 요약 200 |

대표 결과는 다음과 같습니다.

| 상황 | 확인 결과 |
| --- | --- |
| 토큰 없음·변조·실제 만료·미래 nbf | 두 앱의 Gateway·직접 호출 경로에서 401 |
| 다른 API만 대상인 토큰 | APISIX 403, Spring 직접 호출 401 |
| 일반 사용자의 관리자 조회 | 403 |
| 관리자 사용자의 관리자 조회 | 200 |
| 다른 회사 데이터 접근 | 403 |
| 요청자·승인자 ID를 본문에 추가 | 400 |
| 자기 승인 | 403 |
| 완료된 이체 재실행 | 409 |

시간 검증은 토큰 글자를 수정한 위조 토큰으로 대체하지 않았습니다. Keycloak이 실제 서명한 짧은 수명 토큰의 만료를 기다리고, Spring의 60초 시계 오차 허용 범위도 지난 뒤 거절되는지 확인했습니다. 미래 nbf도 실제 서명된 테스트 토큰을 사용했습니다.

Gateway 경로 응답 헤더만으로 백엔드 도달을 판단하지 않고, APISIX 로그의 upstream 상태와 백엔드 직접 호출을 함께 확인했습니다. Java 보안 테스트에서는 테스트용 RSA 서명·JWKS를 사용해 실제 디코더의 실패 경로도 검증했습니다.

## 시연 순서

1. 앱 화면에서 alice로 Keycloak 로그인합니다.
2. 두 앱의 내 정보 API로 동일한 사용자 신원을 확인합니다. FinAccess의 `sub`와 FinAdmin의 `subject`가 같은 사용자 식별자입니다.
3. 일반 사용자의 관리자 요약 403을 확인합니다.
4. 로그아웃 후 admin으로 로그인하여 같은 API의 200을 확인합니다.
5. 토큰 없는 요청의 401을 확인합니다.
6. 자동 검증 결과에서 잘못된 토큰·회사 불일치·처리자 위조·모의 이체 잔액을 확인합니다.

로컬 진입점은 `http://localhost:18090/`, Keycloak 관리 화면은 `http://localhost:18080/admin/`입니다. 비밀번호는 Git에서 제외한 실행용 `.env`와 데스크탑 인증 문서에, 발급한 실습 토큰은 데스크탑 인증 문서에 보관합니다. 공유 문서에는 실제 비밀값을 포함하지 않습니다.

## 구현 범위와 남은 고려사항

- 현재는 로컬 HTTP 및 Keycloak 개발 실행 모드입니다. 운영 TLS·네트워크 격리·비밀정보 관리·관측·백업 구성은 별도입니다.
- 백엔드 직접 호출 포트는 독립 검증 확인을 위해 로컬에 열었습니다. 운영 공개 경로 설계와 구분합니다.
- FinAdmin 관리자 통계는 고정 샘플이며 실제 FinAccess 집계 기능이 아닙니다.
- 실제 금융망 이체가 아니라 로컬 실습 DB에서 처리하는 모의 내부 이체입니다.
- 이미 발급된 JWT의 역할 변경·로그아웃을 즉시 반영하는 폐기 정책은 별도로 설계해야 합니다.
- SSO 시연, Istio, 대규모 부하 시험, 고가용성·장애 복구 검증은 이번 범위에 포함하지 않았습니다.

## 관련 자료

- [실행과 전체 구성](../README.md)
- [Keycloak 실행 환경](02-keycloak-setup.md)
- [Realm·Client·사용자·역할](03-keycloak-realm-client-role.md)
- [로그인과 액세스 토큰](04-access-token.md)
- [Spring JWT 검증](05-jwt-validation.md)
- [관리자 권한 제한](06-admin-authorization.md)
- [APISIX 검증과 전달](07-apisix-gateway.md)
- [상세 검증 결과와 재현 방법](08-end-to-end-verification.md)

### 회의에서 설명할 내용

> Keycloak에서 발급한 액세스 토큰을 APISIX Gateway와 독립적인 Spring 백엔드 두 개에서 각각 검증하는 구성을 만들었습니다. 앱별 역할에 따른 관리자 API 제한과 회사별 데이터 접근을 적용했고, 토큰의 사용자 신원을 실제 이체 요청·승인·실행 처리자와 연결했습니다. 실제 로그인과 46개 HTTP 결과 검사, DB 잔액 확인까지 완료했으며 현재는 로컬 인증·인가 기능 검증 범위입니다.
