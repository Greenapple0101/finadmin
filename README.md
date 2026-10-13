# FinAdmin · IT 서비스 요청·승인·처리 앱

현재 유일한 FinLab Gateway는 **API7 Enterprise의 기본 OIDC·ACL·Route 기반 인증·인가**입니다. [기본 기능으로 권한 검사를 옮긴 내용](docs/17-api7-native-authorization.md)을 참고하세요. [연동·검증 보고서](docs/15-api7-enterprise-integration.md)와 [API 역할 정책표](docs/14-gateway-rbac-policy.md)를 먼저 보세요. 관리 UI는 `https://localhost:7443`, 사용자 앱은 `http://localhost:18090`입니다.

[FinAccess](https://github.com/Greenapple0101/finaccess) 금융 앱과 별도로 실행하는 **ITSM 서비스 요청 앱**입니다. 직원이 IT 서비스를 요청하면 다른 승인자가 승인하고, 처리 담당자가 작업 결과를 기록합니다. 전체 시스템의 RBAC를 총괄하는 서버가 아닙니다.

처음에는 [ITSM 구현·학습·화면 시연 가이드](docs/18-itsm-service-requests.md)를 읽으세요. 이 저장소에는 두 백엔드를 함께 실습하기 위한 **OpenLDAP, Keycloak, API7 Enterprise 설정, 로그인 화면, 실행·검증 스크립트**도 있습니다.

Keycloak에서 발급받은 액세스 토큰을 API7 Enterprise가 검사하고 전달합니다. FinAccess와 FinAdmin도 각각 토큰을 다시 검증하고, 자기 앱의 역할과 업무 규칙에 따라 응답합니다.

사용자 로그인은 **Keycloak**이 처리합니다. Nginx는 로그인 버튼과 API 호출 화면의 정적 파일만 제공하며, 인증 서버나 Gateway 관리 UI가 아닙니다. 기존 OSS APISIX 컨테이너와 설정은 제거했습니다.

**2026-10-13 구성:** FinAccess 금융 앱 + FinAdmin ITSM 앱, 독립 백엔드 두 개와 각각의 업무 DB.

```text
브라우저 ── 로그인(Code + PKCE) ── Keycloak ── OpenLDAP
브라우저 ── Bearer 토큰 ── API7 Enterprise :18090
                            ├── FinAccess: JWT + 역할 + 회사·이체 규칙
                            ├── FinAdmin: JWT + 역할 + 회사·서비스 요청 규칙 → ITSM DB
                            └── Nginx: 사용자 화면 파일
API7 실제 관리 UI: https://localhost:7443
```

**실습 화면: [http://localhost:18090/](http://localhost:18090/)** · **Keycloak 관리: [http://localhost:18080/admin/](http://localhost:18080/admin/)**

## 현재 구현한 내용

- Java 21 · Spring Boot 4.1.1 · Gradle Wrapper 9.7.1
- Keycloak 26.7.4 · API7 Enterprise 3.10.2 · PostgreSQL 17.11
- OpenLDAP 2.6.10 · 조회 전용 User Federation · LDAP 그룹 → Keycloak 그룹 → Client Role
- 프런트의 Authorization Code + PKCE 로그인과 Bearer API 호출
- API7 Enterprise의 OIDC 검증·기본 ACL 역할 검사·경로/메서드 제한·Authorization 헤더 전달
- 두 Spring Resource Server의 독립적인 JWT 서명·발급자·시간·대상 검증
- FinAdmin의 서비스 요청·승인·완료, 회사·본인 요청 범위 제한, 자기 승인 금지
- ITSM 전용 PostgreSQL과 Flyway, 요청자·승인자·완료자·시각·결과 저장
- 내부 계정과 LDAP 직원의 ITSM 역할, 회사별 실제 현황 집계
- FinAccess의 토큰 신원 연결, 회사 접근 제한, 요청·승인·반려·모의 이체 처리

FinAdmin은 `finadmin-api` Client Role을 사용합니다. 금융 앱의 같은 이름 역할과 별개입니다.

| 역할 | 할 수 있는 업무 | 데이터 범위 |
| --- | --- | --- |
| user | 요청 등록·조회 | 본인의 요청 |
| approver | 요청 등록·조회·승인 | 자기 회사, 본인 요청 승인 불가 |
| admin | 요청 등록·조회·승인·완료·현황 조회 | 자기 회사, 본인 요청 승인 불가 |

Gateway는 `/admin/api/itsm/*`를 FinAdmin의 `/api/itsm/*`로 전달합니다. Gateway와 Spring이 역할을 각각 확인하고, 회사·요청자·상태는 ITSM DB를 조회해 판단합니다. [전체 API별 정책](docs/14-gateway-rbac-policy.md).

기존 `/api/me`, `/api/hello`, `/api/admin/summary`는 학습·진단용으로 유지합니다. `/api/admin/summary`의 3·7은 `sampleData: true`인 과거 샘플이며, 새 `/api/itsm/summary`는 `sampleData: false`인 자기 회사의 실제 요청 집계입니다. 직접 `/api/hello`만 공개하고 Gateway 경유 hello는 인증·역할을 요구합니다.

## 실행하기

Java 21, Python 3, 실행 중인 Docker와 Docker Compose가 필요합니다. 라이선스가 활성화된 API7 Enterprise Control Plane과 `.local/api7`의 전용 그룹·Gateway 등록 정보가 먼저 준비되어 있어야 합니다. [API7 준비와 실행](docs/15-api7-enterprise-integration.md)을 참고하세요. 처음에는 Gradle 의존성과 컨테이너 이미지를 내려받습니다. 두 저장소를 같은 부모 폴더 아래에 둡니다.

```text
같은 부모 폴더/
├── finaccess/
└── finadmin/
```

아직 저장소가 없다면 새 부모 폴더에서 각각 복제합니다. 이미 있다면 다시 복제하지 않아도 됩니다.

```bash
git clone https://github.com/Greenapple0101/finaccess.git
git clone https://github.com/Greenapple0101/finadmin.git
cd finadmin
./scripts/start.sh
```

`start.sh`는 아래 작업을 순서대로 합니다.

1. 무작위 실습 비밀번호를 `.env`와 데스크탑의 로컬 인증 문서에 준비합니다.
2. 옆 폴더의 FinAccess와 현재 FinAdmin을 각각 실행 JAR로 빌드합니다.
3. `finlab` 앱 컨테이너들을 실행하고 `finlab-api7`의 Enterprise Gateway를 18090에 연결합니다.
4. 기존 Keycloak 내부 계정으로 로그인하고 API와 모의 이체를 검증합니다.
5. LDAP Provider·그룹 역할과 각 앱의 직원·회사 연결을 준비합니다. FinAdmin의 `approver` 역할도 연결합니다.
6. LDAP 로그인·모의 이체·그룹 제거/복원, API7 ACL·두 백엔드 재검증, ITSM 요청·승인·완료를 검증합니다.

이 스크립트의 빌드 단계는 `bootJar`입니다. 전체 Java 테스트는 아래의 별도 명령으로 실행합니다. 자동 검증에는 실제 토큰의 만료와 Spring 시간 오차 허용 범위를 기다리는 과정이 있어 서버 준비 후에도 1분 이상 걸릴 수 있습니다.

| 접속 대상 | 주소 | 용도 |
| --- | --- | --- |
| API7 관리 콘솔 | [localhost:7443](https://localhost:7443/) | 실제 제품의 서비스·Route·ACL 설정 |
| 앱 화면·API7 Enterprise | [localhost:18090](http://localhost:18090/) | 로그인과 Gateway를 통한 API 호출 |
| Keycloak | [localhost:18080/admin/](http://localhost:18080/admin/) | Realm·Client·사용자·역할 확인 |
| FinAccess 직접 호출 | `http://localhost:18082` | 백엔드의 독립적인 검증 확인 |
| FinAdmin 직접 호출 | `http://localhost:18083` | 백엔드의 독립적인 검증 확인 |

FinLab 앱의 공개 포트는 내 컴퓨터의 `127.0.0.1`에만 연결합니다. DB와 LDAP는 호스트 포트를 열지 않습니다. LDAP는 컨테이너 내부 `ldap:389`로 연결합니다. Keycloak DB, FinAccess DB, ITSM DB는 각각의 DB·볼륨을 사용합니다. API7 제품의 자체 관리 DB도 별개입니다.

## 화면에서 보는 순서

1. [사용자 앱](http://localhost:18090/)에서 **alice**로 Keycloak 로그인 → 서비스명·목적 입력 → **요청 등록**.
2. 로그아웃하고 Keycloak의 **Logout** 확인 → **bob**으로 로그인 → 해당 요청의 **상세 보기 → 요청 승인**.
3. 같은 방식으로 **admin** 로그인 → 승인된 요청 선택 → 처리 결과 입력 → **처리 완료로 기록**.
4. 회사 현황과 상세 화면의 승인·완료 이력이 저장되었는지 확인합니다.
5. 아래 접힌 **금융 앱 연결과 인증·권한 검사 확인**에서 FinAccess 연결과 과거 샘플의 401·403·200도 비교할 수 있습니다.

비밀번호는 데스크탑의 `finadmin-local-secrets.md`에 있습니다. `admin`은 ITSM 처리 담당자이고, `bootstrap-admin`은 Keycloak 관리 콘솔 전용입니다. LDAP 계정은 **ldap-alice → ldap-bob → ldap-admin** 순서로 동일한 흐름을 사용합니다. `outsider`, `ldap-outsider`는 B회사 요청 직원입니다.

새로고침하면 메모리의 토큰이 사라지며 다시 로그인해야 합니다. 자동 토큰 갱신은 없습니다. 처리 완료는 **수행한 작업의 기록**이며 계정·서버 자동 발급 기능은 아닙니다.

## 비밀번호·토큰·검증 데이터 위치

| 파일 | 내용 | Git에 포함 |
| --- | --- | --- |
| `.env.example` | 필요한 환경 변수 이름만 제공 | 포함 |
| `.env` | 로컬 실행에 쓰는 실제 비밀번호 | 제외 |
| 데스크탑 `finadmin-local-secrets.md` | 실제 계정 비밀번호·검증용 액세스 토큰·만료 시각 | 저장소 밖 |
| `.local/verification.json` | 토큰 없는 검증 상태 코드·잔액 결과 | 제외 |
| `.local/ldap-verification.json` | LDAP·그룹 역할·JWT·이체 검증 결과 | 제외 |
| `.local/itsm-verification.json` | 이번 실행의 ITSM 상태 코드·권한·이력 검사 | 제외 |
| `docs/verification/itsm-2026-10-13.json` | 비밀값을 포함하지 않는 확정 검증 기록 | 포함 |

비밀값 파일은 소유자만 읽고 쓰도록 만들지만 평문입니다. 공개 MD 문서에는 실제 비밀번호와 토큰을 넣지 않습니다. 기존 `.env` 비밀번호는 초기화 스크립트가 보존하며, `.env` 값을 바꿔도 이미 생성한 Keycloak 계정의 비밀번호가 자동으로 변경되지는 않습니다.

전체 검증을 다시 실행하려면 다음 명령을 사용합니다.

```bash
python3 scripts/verify.py
python3 scripts/verify-ldap.py
python3 scripts/verify-itsm.py --restart
```

이 명령은 읽기만 하는 상태 확인이 아닙니다. 저장소가 관리하는 `finlab-*` 공개 Client와 필요한 기본 Client Scope 연결을 맞추고, 전용 실습 DB에 회사·사용자 연결을 준비한 뒤 새 계좌와 모의 이체 데이터를 추가합니다. 기존 데이터를 삭제하지 않습니다. 사용자 로그인은 Code + PKCE이며, 설정 동기화에만 관리용 `admin-cli` 토큰을 일시 사용합니다. 세부 동작은 [전체 검증 설명](docs/08-end-to-end-verification.md)에 있습니다.

`verify-ldap.py`도 새 계좌·모의 이체를 만들고, LDAP 관리자 직원을 그룹에서 잠시 제외했다가 복원합니다. LDAP 설정을 처음 적용하거나 원본 설정으로 맞출 때는 `python3 scripts/setup-ldap.py`를 먼저 실행합니다. [재현과 복구 방법](docs/13-ldap-federation-hands-on.md#13-명령으로-재현하기)을 확인하세요.

## 테스트와 확인한 결과

**2026-10-13 ITSM 확장:** FinAdmin Java 테스트 **51개 통과**, 실제 PKCE·API7·Spring·PostgreSQL·LDAP 계정 검증 **77개 통과**. 백엔드 재시작 후 이력 유지도 포함합니다. HTTP 상태와 신원·범위·로그·저장 내용 검사를 합친 77건이며, Java 테스트와 합산하지 않습니다. [실행 기록](docs/verification/itsm-2026-10-13.json).

ITSM 검증은 요청 4건을 추가합니다. 3건은 완료하고 B회사 1건은 접수 상태로 남깁니다. 기존 데이터는 지우지 않습니다. 이번에 FinAccess 전체 Java 테스트나 과거 135건을 다시 실행한 것으로 표시하지 않습니다.


Java 테스트 기록은 2026-09-29, 실제 서버 검증은 LDAP 추가 후 2026-10-01 기준입니다. 아래 표는 당시의 과거 기록입니다. 오늘 이 수의 Java 테스트를 다시 실행한 것은 아닙니다. 현재 API7 구성의 검사 결과는 아래 별도 기록을 기준으로 봅니다.

| 검증 | 결과 |
| --- | --- |
| FinAdmin Java 테스트 | 19개 통과 |
| FinAccess Java 테스트 | 149개 통과 |
| 실제 Keycloak·APISIX·두 백엔드 HTTP 검증 | 46개 통과 |
| LDAP 추가 검증(인증·ACL·그룹·신원·HTTP·잔액) | 93개 통과 |
| LDAP 재시작 및 설정 재실행 | Provider·Mapper·그룹·사용자 ID 유지 |
| 모의 이체 후 실제 DB 잔액 | 출금 10,000 → 9,000원, 입금 0 → 1,000원 |

FinAdmin 테스트는 임시 JWKS 서버와 실제 RSA 서명 토큰으로 JWT 검증 실패도 확인합니다. 전체 HTTP 검증은 실행 중인 Keycloak이 발급한 토큰을 사용합니다. 실제 만료 토큰과 미래 `nbf` 토큰, 다른 API 대상 토큰, 역할 부족, 회사 불일치, 사용자 ID 위조, 자기 승인, 중복 실행까지 구분해 확인합니다.

```bash
# finadmin 폴더에서
./gradlew test bootJar

# finaccess 폴더에서
./gradlew test bootJar
```

FinAccess의 DB 통합 테스트는 Docker를 사용합니다. 검증 범위와 401·403의 차이는 [08번 문서](docs/08-end-to-end-verification.md)에 정리했습니다.

## 중지와 재시작

```bash
docker compose -f compose.api7.yaml stop
docker compose stop

# 다시 시작
docker compose up -d
docker compose -f compose.api7.yaml up -d
```

일반 중지는 `stop`으로 충분합니다. `down`은 컨테이너와 네트워크를 제거하며, **`down -v`는 DB 볼륨까지 삭제**하므로 일상적인 종료에 사용하지 않습니다. 코드 변경 후에는 `./scripts/start.sh`로 빌드·이미지 생성·검증을 다시 진행합니다.

FinAdmin을 `./gradlew bootRun`으로 별도 실행할 때는 접속 가능한 PostgreSQL의 `ITSM_DB_URL`, `ITSM_DB_USERNAME`, `ITSM_DB_PASSWORD`를 설정해야 합니다. Compose의 ITSM DB는 호스트 포트를 공개하지 않으므로 기본 localhost:5432만으로 연결되지 않습니다. 권장 실습 실행은 위 Compose 흐름입니다. bootRun 기본 직접 주소는 `http://127.0.0.1:8081`입니다.

## 문서 읽는 순서

현재 ITSM 업무와 코드 읽기 순서는 [18번 가이드](docs/18-itsm-service-requests.md)부터 시작합니다. 아래 01~13번은 금융 인증 실습의 학습 과정이며 작성 날짜를 구분해서 읽습니다.

주석과 문서는 파일의 역할 → 요청이 흐르는 순서 → 설정과 문법의 의미를 쉬운 말로 설명합니다.

**Keycloak 콘솔을 열어 놓고 공부할 때는 [핸즈온 보고서](docs/11-keycloak-hands-on-report.md)부터 읽습니다.** 메뉴 위치 → 현재 값 → 설정 이유 → JWT 변화 → API 응답까지 연결합니다. [설정값 목록](docs/12-keycloak-settings-reference.md)에는 실제 서버에서 조회한 값과 보고서 작성 중 새로 통과한 읽기 전용 API 확인 32건을 모았습니다.

1. [처음 FinAdmin 앱을 만든 순서](docs/01-first-application.md) — **인증을 넣기 전의 과거 단계**입니다. 현재 접근 규칙은 05·06번을 기준으로 읽습니다.
2. [Keycloak 실행 환경](docs/02-keycloak-setup.md)
3. [Realm·Client·사용자·역할](docs/03-keycloak-realm-client-role.md)
4. [로그인과 액세스 토큰](docs/04-access-token.md)
5. [Spring의 JWT 검증](docs/05-jwt-validation.md)
6. [관리자 권한 제한](docs/06-admin-authorization.md)
7. [API7 Enterprise의 검증·인가](docs/17-api7-native-authorization.md) — 이전 APISIX 구성은 과거 기록입니다.
8. [현재 API7 검증 결과와 재현 방법](docs/15-api7-enterprise-integration.md) — [과거 HTTP 검증](docs/08-end-to-end-verification.md)은 날짜를 구분합니다.
9. [현재 회사 공유용 구성·검증 보고서](docs/15-api7-enterprise-integration.md) — [이전 공유 기록](docs/09-internal-sharing.md)
10. [아키텍처 그림을 읽는 순서](docs/10-architecture.md)
11. [Keycloak 설정을 직접 따라 읽는 핸즈온 보고서](docs/11-keycloak-hands-on-report.md)
12. [Keycloak 현재 설정값 목록과 확인 기록](docs/12-keycloak-settings-reference.md)
13. [OpenLDAP User Federation 설정과 실습 보고서](docs/13-ldap-federation-hands-on.md) — 외부 직원 → 그룹 → JWT → 실제 이체, 권한 회수의 한계까지

## 실습 범위

실제 인증·인가 흐름을 실행하는 로컬 학습 환경입니다. Keycloak은 HTTP와 `start-dev`로 실행하고, 백엔드 직접 호출 포트는 독립적인 검증을 확인하기 위해 로컬에 열었습니다. 운영 HTTPS·네트워크 격리·비밀값 관리·모니터링·백업·가용성 구성은 별도 작업입니다.

LDAP도 Docker 내부의 평문 LDAP 실습이며 StartTLS/LDAPS와 실제 Windows AD는 미적용입니다. 새 로그인에서 그룹 변경이 역할에 반영되는지 확인했고, 기존 JWT는 만료 전까지 관리자 접근이 유지된다는 점도 검증했습니다.

기존 관리자 요약만 샘플이고 ITSM 현황은 실제 업무 DB 집계입니다. 사용자·회사 연결은 초기 설정 스크립트로 준비하며 운영자 온보딩 UI, 가입·자동 프로비저닝 API는 없습니다. ITSM은 서비스 요청 3단계의 최소 구현이며 반려·취소·SLA·CMDB·장애/변경 관리·알림은 미구현입니다. 공개 키로 검증하는 기존 JWT에 역할 변경이나 로그아웃이 즉시 반영된다고 보장하지 않습니다. 여러 프런트 사이의 SSO 시연, Istio, 대규모 부하 시험, 고가용성 검증은 포함하지 않았습니다.

실제 제품 화면을 따라 읽으려면 [API7 콘솔 캡처 강의자료](docs/16-api7-console-walkthrough.md)를 참고하세요.

18090 단일 Enterprise 환경의 [현재 두 백엔드 구성의 135개 검사 기록](docs/verification/api7-two-backends-2026-10-06.json)이 모두 통과했습니다. 이전 포트의 과거 검사와 합산하지 않습니다.

확장 가능성: 필요하면 레거시 백엔드도 연결할 수 있으며, 현재 구현·아키텍처에는 포함하지 않습니다.
