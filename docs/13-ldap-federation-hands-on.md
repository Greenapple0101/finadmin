# OpenLDAP → Keycloak → JWT → 두 Spring 앱 실습 보고서

> 과거 구성 기록입니다. 2026-10-06부터 FinLab Gateway는 API7 Enterprise(18090) 하나입니다. 현재 설정·실행 방법은 [Enterprise 보고서](15-api7-enterprise-integration.md)를 참고하세요. 아래 과거 실행 결과와 이미지는 당시 상태로 보존합니다.

작성일: 2026-10-01 · 대상: 처음 LDAP와 User Federation을 배우는 사람

이 문서는 개념 제안서가 아니라 실제 FinLab에 추가한 설정과 실행 결과를 설명합니다. 기존 내부 사용자 `alice / bob / admin / outsider`는 유지하고, LDAP 사용자 `ldap-alice / ldap-bob / ldap-admin / ldap-outsider`를 추가했습니다. Windows Active Directory는 설치하지 않았습니다.

## 1. 이번에 달라진 부분부터 보기

예전에는 Keycloak이 자기 DB에 저장된 비밀번호로 로그인 여부를 판단했습니다. 이제 `ldap-`로 시작하는 네 직원은 OpenLDAP에 저장된 비밀번호로 확인합니다. **토큰을 발급하는 곳은 여전히 Keycloak**입니다.

```text
로그인할 때
브라우저 → Keycloak 로그인 화면
             ├─ alice 등 기존 사용자 → Keycloak 내부 비밀번호 확인
             └─ ldap-alice 등 외부 직원 → OpenLDAP에서 비밀번호 확인
                                          + 직원의 그룹 조회
             ↓
        그룹에 연결된 Client Role → Keycloak이 서명한 JWT 발급
             ↓ Authorization Code + PKCE로 토큰을 받은 브라우저

API를 사용할 때
브라우저 → Bearer JWT → APISIX → FinAccess 또는 FinAdmin
                         검사       JWT 재검사 + 자기 앱의 접근 규칙
```

API를 호출할 때마다 Spring이 LDAP에 비밀번호를 물어보지는 않습니다. LDAP 연동은 로그인과 사용자·그룹 조회에 관계합니다. APISIX와 Spring은 기존처럼 Keycloak의 공개 키로 JWT를 검사합니다.

그래서 이번 변경에는 **Spring 보안 코드나 APISIX 라우트 변경이 필요하지 않았습니다.** 대신 새 직원의 JWT 신원을 FinAccess 업무 DB의 사용자와 연결했습니다.

## 2. 이름이 비슷한 개념을 먼저 구분하기

| 용어 | 쉬운 설명 | 이번 프로젝트에서 |
| --- | --- | --- |
| LDAP | 직원 명부를 찾고 확인할 때 사용하는 통신 규칙 | Keycloak과 명부 서버 사이의 프로토콜 |
| OpenLDAP | LDAP 규칙으로 동작하는 실제 서버 프로그램 | Compose의 `ldap` 컨테이너 |
| Active Directory, AD | Microsoft의 기업 디렉터리·도메인 관리 제품 | 이번에 설치하지 않음. OpenLDAP과 같은 제품이 아님 |
| User Federation | 외부 명부를 Keycloak 사용자와 연결하는 기능 | `finlab-openldap` Provider |
| Bind | LDAP 서버에 자신이 누구인지 인증하는 절차 | 조회 계정 Bind와 직원 비밀번호 확인 Bind |
| Group | 사람들이 소속되는 묶음 | developers, approvers, admins |
| Client Role | 특정 앱에서 할 수 있는 일의 이름 | `finadmin-api`의 admin |
| Mapper | 서로 다른 시스템의 항목을 연결하는 설정 | LDAP 그룹을 Keycloak 그룹으로 가져옴 |
| Provisioning | 앱이 사람을 업무 사용자로 사용할 수 있게 준비하기 | `iss + sub`를 `app_users`에 등록하는 실습 스크립트 |

**그룹과 역할은 다릅니다.** `admins` 그룹에 들어갔다고 저절로 모든 앱의 관리자가 되는 것은 아닙니다. 그 그룹에 어떤 Client Role을 붙일지 별도로 결정했습니다.

## 3. 실제 직원 명부는 이렇게 생겼습니다

```text
dc=finlab,dc=com
├── ou=users
│   ├── uid=ldap-alice
│   ├── uid=ldap-bob
│   ├── uid=ldap-admin
│   └── uid=ldap-outsider
├── ou=groups
│   ├── cn=developers → ldap-alice, ldap-outsider
│   ├── cn=approvers  → ldap-bob
│   └── cn=admins     → ldap-admin
└── ou=services
    └── cn=keycloak  → 직원·그룹을 읽는 전용 서비스 계정
```

DN은 명부 안에서 항목 하나를 정확히 찾는 전체 주소입니다. 예를 들어 `uid=ldap-alice,ou=users,dc=finlab,dc=com`은 “FinLab 명부의 users 구역에 있는 ldap-alice”입니다. 폴더 경로와 비슷하지만 문법과 의미가 다른 LDAP 이름입니다.

- `dc`: 도메인 이름을 구성하는 조각입니다. `dc=finlab,dc=com`을 썼다고 실제 인터넷 도메인을 구매하거나 연결한 것은 아닙니다.
- `ou`: 용도별 구역입니다. 여기서는 직원, 그룹, 서비스 계정을 나눴습니다.
- `uid`: 직원 로그인 ID입니다.
- `cn`: 사람이나 그룹의 이름입니다.
- `entryUUID`: OpenLDAP이 항목에 부여하는 식별자입니다. 이름이 아니라 이 값으로 같은 항목을 추적합니다.
- `objectClass`: 항목에 어떤 정보를 적을 수 있는지 정하는 종류입니다. 직원은 `inetOrgPerson`, 그룹은 `groupOfNames`입니다.
- `member`: 그룹에 소속된 항목의 DN을 적는 칸입니다.

`groupOfNames`는 구성원이 최소 한 명 필요합니다. 실습 중 마지막 직원을 빼도 그룹이 유지되도록 서비스 계정 DN을 각 그룹에 함께 넣었습니다. 이 계정은 `ou=users` 밖에 있고 `inetOrgPerson`도 아니어서 직원으로 가져오지 않습니다. 앱 로그인용 계정이 아닙니다.

## 4. 프로그램을 만든 순서와 읽을 파일

처음부터 Keycloak 콘솔의 수십 개 칸을 채우는 것으로 시작하지 않았습니다. 연결할 대상을 먼저 만든 뒤 안쪽에서 바깥쪽으로 검증했습니다.

| 순서 | 만든 것 | 직접 읽을 파일 | 이유 |
| --- | --- | --- | --- |
| 1 | 직원 명부 서버 | [LDAP Dockerfile](../infra/ldap/Dockerfile) | 연결할 실제 LDAP 서버가 먼저 필요 |
| 2 | 명부 구조와 읽기 권한 | [slapd.conf](../infra/ldap/slapd.conf) | 누구의 데이터를 누가 읽는지 결정 |
| 3 | 최초 직원·그룹 생성 | [directory.py](../infra/ldap/directory.py) | 빈 명부에 실습 자료를 한 번 생성 |
| 4 | 실행·저장 공간·비밀번호 | [compose.yaml](../compose.yaml), [init-local.py](../scripts/init-local.py) | 재시작 후에도 자료가 남도록 구성 |
| 5 | Keycloak 연결값 | [ldap-federation.json](../infra/keycloak/ldap-federation.json) | 콘솔에 입력할 설정을 재현 가능하게 기록 |
| 6 | 설정 적용과 회사 연결 | [setup-ldap.py](../scripts/setup-ldap.py) | Provider → Group Mapper → 역할 → 업무 사용자 연결 |
| 7 | 실제 검증 | [verify-ldap.py](../scripts/verify-ldap.py) | 로그인 성공이 실제 API 권한으로 이어지는지 확인 |

[ldap_support.py](../scripts/ldap_support.py)는 Keycloak 관리 요청과 공통 주소를 모아둔 보조 파일입니다. [check-ldap-directory.py](../scripts/check-ldap-directory.py)는 컨테이너 내부에서 LDAP 비밀번호와 읽기 권한을 검사합니다.

LDAP 서버는 Debian trixie의 공식 `slapd` 패키지로 만들었고 이번 실행에서 **OpenLDAP 2.6.10**을 확인했습니다. 배포판 이름은 지정하지만 apt 패키지 저장소 전체를 동결한 빌드는 아닙니다. 이후 재빌드 시 Debian 보안 수정 버전이 달라질 수 있습니다.

## 5. LDAP 서버는 어디에 있나

Compose 프로젝트는 기존과 같은 `finlab`이고 서비스가 하나 늘어 총 8개입니다. `ldap` 서비스는 Docker 내부의 `ldap:389`에서 접근합니다. 호스트 포트는 열지 않았습니다.

| 저장할 내용 | 실제 저장 장소 | Docker 볼륨 |
| --- | --- | --- |
| LDAP 직원·비밀번호 해시·그룹 소속 | OpenLDAP의 MDB 데이터 | `finlab_ldap_data` |
| Keycloak 사용자 연결·그룹 역할·Client·세션 등 | Keycloak PostgreSQL | `finlab_keycloak_data` |
| 회사·업무 사용자·계좌·이체 | FinAccess PostgreSQL | `finlab_app_data` |

OpenLDAP 데이터를 PostgreSQL에 넣은 것이 아닙니다. 서로 다른 세 저장 공간입니다. Docker Desktop에서는 이 볼륨이 Docker의 Linux 환경 안에 있습니다.

`slapd.conf`는 사람이 읽는 설정 원본이고 시작할 때 `slaptest`로 `cn=config` 디렉터리를 만듭니다. 실행 중 설정과 임시 비밀 파일은 컨테이너의 `/run`에 있습니다. 실제 명부만 볼륨에 남깁니다.

최초 실행은 직원을 생성하고 `.finlab-initialized` 표시를 남깁니다. 재시작하면 직원·그룹·비밀번호를 다시 만들지 않습니다. 표시 없이 DB만 발견하면 덮어쓰지 않고 멈춥니다.

## 6. Keycloak에서 Provider 설정 읽기

[관리 콘솔](http://localhost:18080/admin/)에 `bootstrap-admin`으로 로그인하고 Realm을 **finlab**으로 바꿉니다. 왼쪽 **User federation → finlab-openldap**을 엽니다.

콘솔 버전에 따라 칸의 배치는 달라도 아래 저장 값은 [JSON 원본](../infra/keycloak/ldap-federation.json)과 대응됩니다.

| 설정 | 실제 값 | 왜 이렇게 했나 |
| --- | --- | --- |
| Enabled / Priority | true / 0 | 이 외부 사용자 저장소를 사용 |
| Vendor | Other | OpenLDAP이며 AD 전용 설정을 쓰지 않음 |
| Connection URL | `ldap://ldap:389` | Keycloak 컨테이너에서 보는 명부 주소 |
| Authentication type | simple | DN과 비밀번호로 Bind |
| Bind DN | `cn=keycloak,ou=services,dc=finlab,dc=com` | 직원 검색용 읽기 전용 계정 |
| Bind credential | 로컬 `.env`의 `LDAP_BIND_PASSWORD` | Git에는 실제 값을 기록하지 않음 |
| Users DN | `ou=users,dc=finlab,dc=com` | 서비스 계정·그룹이 아닌 직원 구역만 검색 |
| Username LDAP attribute | uid | `ldap-alice`를 로그인 ID로 사용 |
| RDN LDAP attribute | uid | 직원 DN의 맨 앞 이름을 uid로 사용 |
| UUID LDAP attribute | entryUUID | LDAP 항목의 고유 식별자 |
| User object classes | inetOrgPerson | 직원 객체만 가져옴 |
| Search scope | 2 / Subtree | Users DN 아래 하위 구역까지 검색 |
| Edit mode | READ_ONLY | Keycloak이 직원 명부를 수정하지 않음 |
| Import users | true | 사용자 프로필과 외부 저장소 연결을 Keycloak DB에도 저장 |
| Sync registrations | false | Keycloak 신규 가입으로 LDAP 직원을 만들지 않음 |
| Cache policy | NO_CACHE | 실습에서 그룹 변화가 새 로그인에 보이도록 사용자 캐시를 사용하지 않음 |
| Full / Changed sync period | -1 / -1 | 자동 주기 동기화는 끄고 준비 스크립트에서 전체 동기화 |
| Pagination / Batch size | true / 100 | 여러 사용자를 나누어 읽는 기능 사용 |
| Connection / Read timeout | 5000 / 5000 ms | 명부 응답이 없을 때 무한히 기다리지 않음 |
| Connection pooling | false | 이 작은 실습에서는 연결 풀을 사용하지 않음 |
| StartTLS | false | Docker 내부 LDAP 구간도 암호화하지 않은 로컬 실습 |
| Trust email | false | 명부에 주소가 있다고 이메일 확인을 했다고 간주하지 않음 |

**Test connection**은 연결 가능한지, **Test authentication**은 조회용 Bind 계정이 맞는지 확인하는 버튼입니다. 이 둘이 성공했다고 직원 비밀번호와 앱 권한까지 검증된 것은 아닙니다. 직원 로그인을 별도로 해야 합니다.

Import users를 켜도 LDAP 비밀번호를 Keycloak DB로 복사하지 않습니다. 이번 검사에서는 네 직원 모두 Keycloak DB의 저장된 `password` Credential이 0개임을 확인했습니다. Credentials API에는 외부에서 지원하는 인증 수단으로 `password`가 보일 수 있어서, 그 표시만으로 비밀번호가 복사됐다고 판단하면 안 됩니다. [Keycloak 공식 LDAP 저장 모드 설명](https://www.keycloak.org/docs/latest/server_admin/index.html#_ldap)

## 7. 조회용 Bind와 직원 로그인 Bind는 다릅니다

`cn=keycloak`은 명부 담당 창구라고 생각하면 됩니다. 직원의 DN과 속성·그룹을 찾을 수 있지만 명부 내용을 바꾸거나 비밀번호 해시를 읽을 수 없습니다.

직원이 로그인하면 Keycloak은 찾은 **직원 자신의 DN + 입력된 비밀번호**로 LDAP에 확인합니다. 조회 계정 비밀번호를 모든 직원의 비밀번호 대신 쓰는 것이 아닙니다.

`slapd.conf`의 ACL은 다음 결과를 만들도록 했습니다.

| 시도 | 검사 결과 |
| --- | --- |
| 각 직원의 올바른 비밀번호로 Bind | 성공 |
| 틀린 직원 비밀번호로 Bind | LDAP 오류 49 |
| 조회 계정으로 직원 4명 검색 | 성공 |
| 조회 계정으로 userPassword 조회 | 비밀번호 속성 반환 안 됨 |
| 조회 계정으로 직원 메모 수정 | LDAP 오류 50, 권한 없음 |
| 로그인하지 않고 직원 목록 검색 | 직원 목록 반환 안 됨 |

ACL의 `auth`는 “비밀번호가 맞는지 검사할 수 있다”는 권한입니다. `read`처럼 내용을 돌려주는 권한과 다릅니다. [OpenLDAP 접근 제어 설명](https://www.openldap.org/doc/admin26/access-control.html)

## 8. Group Mapper는 역할을 바로 만들지 않습니다

**User federation → finlab-openldap → Mappers → finlab-ldap-groups**를 엽니다.

| 설정 | 실제 값 | 읽는 방법 |
| --- | --- | --- |
| Mapper type | group-ldap-mapper | 외부 그룹과 Keycloak 그룹 연결 |
| LDAP Groups DN | `ou=groups,dc=finlab,dc=com` | 그룹이 들어 있는 구역 |
| Groups Path | `/ldap` | Keycloak에서 그룹을 넣을 부모 경로 |
| Group Name LDAP Attribute | cn | LDAP의 cn을 그룹 이름으로 사용 |
| Group Object Classes | groupOfNames | 이 종류의 그룹만 가져옴 |
| Membership LDAP Attribute | member | 구성원 이름이 들어 있는 속성 |
| Membership Attribute Type | DN | member의 값이 전체 직원 DN임 |
| Mode | READ_ONLY | LDAP에서 그룹 소속을 읽음 |
| User Groups Retrieve Strategy | LOAD_GROUPS_BY_MEMBER_ATTRIBUTE | 해당 직원 DN을 member로 가진 그룹을 검색 |
| Preserve Group Inheritance | false | 중첩 그룹 대신 평평한 세 그룹으로 실습 |
| Drop non-existing groups during sync | false | 외부에서 사라진 그룹을 자동으로 삭제하지 않음 |

Mapper를 만들기 전에 Keycloak에 `/ldap` 부모 그룹을 먼저 만들어야 합니다. 설정 스크립트가 이 순서를 지킵니다.

`READ_ONLY` 그룹 Mapper는 LDAP 소속과 Keycloak DB의 로컬 소속을 합칠 수 있습니다. 따라서 “Keycloak에서 실수로 부여한 별도 권한까지 LDAP에서 자동으로 없애준다”는 뜻이 아닙니다. 이번 직원에게는 직접 Client Role을 부여하지 않았고, 관리 그룹에 별도로 가입시키지도 않았습니다. 테스트에서 직접 부여한 Client Role이 없는지 확인합니다. [Keycloak 26.7.4 Group Mapper 구현](https://github.com/keycloak/keycloak/blob/26.7.4/federation/ldap/src/main/java/org/keycloak/storage/ldap/mappers/membership/group/GroupLDAPStorageMapperFactory.java)

## 9. 그룹에서 Client Role로 넘어가기

왼쪽 **Groups → ldap → admins → Role mapping**을 봅니다. 그룹 소속과 앱 권한을 잇는 설정이 여기에 있습니다. 상속 역할 표시 필터에 따라 화면에 보이는 목록이 달라질 수 있습니다.

| LDAP / Keycloak 그룹 | 직원 | FinAccess 역할 | FinAdmin 역할 | 회사 |
| --- | --- | --- | --- | --- |
| developers / `/ldap/developers` | ldap-alice | user | user | A |
| developers / `/ldap/developers` | ldap-outsider | user | user | B |
| approvers / `/ldap/approvers` | ldap-bob | approver | user | A |
| admins / `/ldap/admins` | ldap-admin | user, approver, admin | admin | A |

회사 열은 LDAP 그룹에서 자동으로 정한 값이 아닙니다. 실습 스크립트가 FinAccess DB에 연결한 값입니다. 같은 developers 소속인 alice와 outsider도 서로 다른 회사에 연결됩니다.

왼쪽 **Users → ldap-admin**에서 외부 저장소 연결과 Groups를 확인합니다. 사용자에게 직접 admin을 붙이는 대신 그룹에서 역할을 물려받도록 했습니다.

```text
OpenLDAP admins.member에 ldap-admin의 DN이 있음
  → Keycloak /ldap/admins 소속으로 조회됨
  → 그 그룹의 finadmin-api:admin 역할을 물려받음
  → 기존 Client Role Protocol Mapper가 JWT에 역할을 넣음
  → Spring이 ROLE_admin으로 변환
  → hasRole("admin") 검사 통과
```

LDAP의 **Group Mapper**와 JWT의 **Protocol Mapper**는 단계가 다릅니다. 앞의 것은 명부를 Keycloak 모델로 옮기고, 뒤의 것은 Keycloak 역할을 토큰의 JSON 속성으로 넣습니다.

아래는 실제 토큰 문자열이 아닌 구조 예시입니다.

```json
{
  "iss": "http://localhost:18080/realms/finlab",
  "sub": "Keycloak에 연결된 해당 직원의 사용자 ID",
  "aud": ["finaccess-api", "finadmin-api"],
  "resource_access": {
    "finaccess-api": {"roles": ["user", "approver", "admin"]},
    "finadmin-api": {"roles": ["admin"]}
  }
}
```

LDAP `uid`, LDAP `entryUUID`, Keycloak 사용자 ID/JWT `sub`, FinAccess `app_users.id`는 서로 다른 식별자입니다. 우연히 같을 것이라고 가정하지 않습니다.

## 10. 로그인 성공과 금융 업무 권한은 별개입니다

FinAccess는 JWT가 유효하다고 바로 아무 회사의 이체나 허용하지 않습니다.

1. Spring이 JWT 서명·issuer·시간·audience 등을 검사합니다.
2. 해당 API에 필요한 Client Role이 있는지 검사합니다.
3. `CurrentAppUser`가 검증된 `iss + sub`로 `app_users`를 찾습니다.
4. 그 사용자의 회사와 출금 계좌의 회사를 비교합니다.
5. 자기 승인 금지, 거래 상태, 잔액 같은 업무 규칙을 검사합니다.

[setup-ldap.py](../scripts/setup-ldap.py)의 `link_business_users`가 3번의 연결을 미리 준비합니다. 다른 회사에 연결된 기록이 있으면 자동으로 회사 소속을 바꾸지 않고 멈춥니다.

실제 검증은 `ldap-alice`가 1,000원 이체 요청 → `ldap-bob` 승인 → 실행 순서입니다. 요청자·승인자·실행자의 ID와 잔액 9,000원/1,000원을 DB까지 확인했습니다. B회사 `ldap-outsider`가 A회사 출금 계좌로 요청하면 403입니다.

이 연결 코드는 **로컬 실습용 온보딩**입니다. 인사 시스템 연동, 가입 승인, 퇴사자 업무 계정 비활성화 API까지 만든 것은 아닙니다.

## 11. 그룹에서 빼면 언제 접근이 막히나

관리자 그룹에서 직원을 빼는 실험에서는 다음을 실제로 확인했습니다.

| 시점 | 사용하는 토큰 | Gateway 경유 | FinAdmin 직접 호출 |
| --- | --- | --- | --- |
| admins 소속일 때 | 정상 관리자 토큰 | 200 | 200 |
| LDAP admins에서 제거 후 다시 로그인 | admin이 없는 새 토큰 | 403 | 403 |
| 제거 후에도 이전 토큰을 그대로 사용 | 아직 만료되지 않은 기존 관리자 토큰 | 200 | 200 |
| admins에 다시 넣고 다시 로그인 | 복원된 admin이 있는 새 토큰 | 200 | 200 |

이 실험은 `NO_CACHE`와 `READ_ONLY` 그룹 조회 조건에서 **새 로그인**을 비교한 것입니다. 주기 동기화나 사용자 캐시를 지우지 않고 확인했습니다. 이미 열려 있는 세션의 모든 동작, 모든 Refresh Token 정책, 실제 AD 비활성화 동작까지 검증한 것은 아닙니다.

JWT에는 발급 당시 역할이 서명되어 들어 있습니다. LDAP의 그룹을 바꿔도 이미 받은 JWT 내용이 수정되지는 않습니다. 기본 유효 시간은 5분이고 Spring은 시간 검사에 기본 시계 오차 60초를 허용합니다. 모든 경로가 퇴사 시점에 즉시 막힌다고 설명하면 안 됩니다.

즉시 차단이 필요하면 토큰 수명 외에 세션·재발급 통제와 API 측 폐기·온라인 확인 정책 등을 함께 설계해야 합니다. 이번 범위는 기존 토큰이 계속 유효하다는 사실을 재현한 단계입니다.

## 12. 직접 화면에서 따라 하는 순서

1. [앱 화면](http://localhost:18090/)에서 로그인 버튼을 누릅니다.
2. 데스크탑 `finadmin-local-secrets.md`의 **ldap-alice** 비밀번호로 로그인합니다.
3. 두 앱의 **내 정보**는 200, **관리자 요약**은 403인지 봅니다.
4. 로그아웃한 뒤 **ldap-admin**으로 로그인합니다. 같은 관리자 요약이 200입니다.
5. Keycloak **User federation**에서 `finlab-openldap`의 URL, Users DN, READ_ONLY를 확인합니다.
6. Provider의 **Mappers**에서 `finlab-ldap-groups`와 `/ldap` 경로를 확인합니다.
7. **Groups → ldap → admins**의 Role mapping을 확인합니다.
8. **Users → ldap-admin**의 외부 저장소 연결, Groups, 상속 역할을 비교합니다.

회사 발표에서는 “직원 명부는 OpenLDAP, 토큰 발급은 Keycloak, JWT 검증은 Gateway와 각 백엔드, 회사·이체 규칙은 FinAccess”라고 나누어 설명하면 됩니다.

## 13. 명령으로 재현하기

명령은 모두 **finadmin 저장소 폴더**에서 실행합니다. 터미널 위치가 다르면 먼저 그 폴더로 이동합니다. 비밀번호는 명령에 직접 적지 않습니다.

처음부터 전체 환경을 준비하려면:

```bash
./scripts/start.sh
```

실행 중인 기존 FinLab에 LDAP 설정만 준비할 때는:

```bash
python3 scripts/init-local.py
docker compose up -d --build --wait ldap
python3 scripts/setup-ldap.py
python3 scripts/verify-ldap.py
```

설정 적용은 반복할 수 있습니다. 같은 이름의 Provider·Mapper를 갱신하고 누락된 그룹 역할·업무 사용자 연결만 추가합니다. LDAP 직원이나 기존 내부 계정은 삭제하지 않습니다. 다만 관리 대상 Provider 설정은 JSON에 맞추므로 콘솔에서 변경한 그 설정은 재실행하면 원본 값으로 돌아갑니다. 별도로 추가한 그룹 역할은 자동 제거하지 않으며 역할 검증이 차이를 알려줍니다.

`verify-ldap.py`는 읽기 전용 검사가 아닙니다. 로그인을 수행하고 새 계좌·모의 이체를 추가하며, 짧은 시간 동안 `ldap-admin`을 admins에서 뺐다가 복원합니다. 토큰은 데스크탑 비밀 문서에만 기록합니다.

직접 그룹 변화 실험을 하려면:

```bash
# LDAP admins에서 앱 관리자 직원 한 명을 뺍니다.
docker compose exec ldap python3 /opt/finlab/directory.py membership delete admins admin

# 앱에서 로그아웃 → ldap-admin으로 새 로그인 → 관리자 요약 403 확인

# 실험 후 반드시 원래 소속으로 돌립니다.
docker compose exec ldap python3 /opt/finlab/directory.py membership add admins admin

# 다시 로그인 → 관리자 요약 200 확인
```

위 명령의 마지막 `admin`은 스크립트에서 `ldap-admin` 직원을 가리키는 짧은 이름입니다. Keycloak 관리 계정 `bootstrap-admin`을 변경하는 명령이 아닙니다. 이미 빠진 사람을 또 빼거나 이미 있는 사람을 다시 넣으면 LDAP 오류가 납니다.

자동 검사는 `finally`로 복구합니다. 컴퓨터 강제 종료 등으로 복구하지 못했다면 마지막 add 명령으로 복구합니다. `setup-ldap.py` 재실행은 LDAP 원본 소속을 덮어쓰지 않으므로 복구를 대신하지 않습니다.

## 14. 실제 확인한 결과와 위치

2026-10-01에 LDAP 추가 검증 **93개**가 통과했습니다. 이 숫자는 HTTP 응답뿐 아니라 LDAP 인증·ACL, 저장된 비밀번호 유무, 그룹·역할·신원·잔액 검사를 합친 수입니다. 원래 내부 계정의 HTTP 검증 46개와는 별도로 집계합니다.

| 검증 내용 | 확인 결과 |
| --- | --- |
| LDAP 네 직원 비밀번호·조회 권한 제한 | 통과 |
| 외부 저장소 연결과 Keycloak 내 비밀번호 미복사 | 네 직원 모두 통과 |
| 개인 직접 역할 없이 그룹에서 역할 상속 | 두 API 역할 모두 통과 |
| Gateway와 직접 호출에서 일반 사용자/관리자 구분 | 403 / 200 |
| LDAP 직원의 회사 격리·이체 승인·실행 | 통과, 잔액 9,000원 / 1,000원 |
| 그룹 제거·복원에 따른 새 토큰 권한 | 403 → 200 |
| 그룹 제거 전 기존 토큰 | 만료 전 200 유지 |
| 기존 내부 admin 로그인 | 유지 |

세부 결과는 Git에서 제외된 `.local/ldap-verification.json`에 있고 비밀번호·토큰 원문은 없습니다. 기존 46개 검사는 `.local/verification.json`입니다. 재시작·설정 재실행으로 Provider·Mapper·그룹·사용자 ID가 유지되는지 확인한 기록은 `.local/ldap-restart-verification.json`입니다.

## 15. 헷갈릴 때 확인할 지점

| 현상 | 먼저 확인할 것 |
| --- | --- |
| Keycloak Test connection 실패 | `docker compose ps ldap`, Connection URL이 localhost가 아닌 `ldap://ldap:389`인지 |
| Test authentication 실패 | Bind DN, `.env`의 LDAP_BIND_PASSWORD와 최초 명부 비밀번호 일치 여부 |
| 직원이 Users에 안 보임 | Users DN, objectClass, 전체 사용자 동기화 결과 |
| 로그인은 되는데 관리자 요약 403 | LDAP admins.member → Keycloak 그룹 → Client Role → 새 토큰 순서 |
| 콘솔에서 역할을 바꿨는데 화면은 그대로 | 로그아웃 후 새 로그인. 기존 JWT는 자동 수정되지 않음 |
| FinAccess 내 정보는 되는데 회사/이체 API 403 | `iss + sub` 업무 사용자 연결과 회사 소속 |
| `.env` 비밀번호를 바꿨는데 로그인 실패 | 이미 저장된 직원·Bind 비밀번호는 재시작으로 바뀌지 않음 |
| 재시작 후 초기화 표시 없는 DB 오류 | 이전 초기화 실패 여부 확인. `down -v`로 기존 자료를 무조건 지우지 않기 |

LDAP 관리 root DN의 비밀번호는 실행 설정으로 생성하므로 재시작 때 `LDAP_ADMIN_PASSWORD`를 읽습니다. 직원과 조회 계정의 비밀번호는 최초 LDAP 데이터에 저장되므로 `.env`만 바꿔서는 갱신되지 않습니다.

## 16. 구현 범위와 다음 학습 주제

이번에 구현한 것은 OpenLDAP 사용자·그룹 Federation입니다. Windows AD, 중첩 그룹, AD 잠금/퇴사 정책, 다중 LDAP 서버, 자동 인사 프로비저닝은 별도입니다.

LDAP 구간은 호스트 포트를 열지 않은 Docker 내부 통신이지만 **TLS로 암호화하지 않았습니다.** 실제 기업망 연동에서는 StartTLS/LDAPS와 인증서 검증, 계정 수명 주기, 비밀정보 보관, 접근 정책을 다뤄야 합니다. `NO_CACHE`는 변화를 쉽게 관찰하는 설정이지 대규모 환경의 성능 권장값이 아닙니다.

지금 먼저 설명할 수 있어야 할 문장은 이것입니다.

> 직원의 비밀번호와 그룹 소속은 OpenLDAP에 두고 Keycloak User Federation으로 연동했습니다. LDAP 그룹을 Keycloak 그룹으로 읽어 Client Role을 부여했으며, 발급된 JWT를 APISIX와 두 Spring Resource Server에서 검증했습니다. 실제 이체와 회사별 접근 제한을 확인했고, 그룹 변경이 새 토큰에는 반영되지만 기존 JWT를 즉시 무효화하지 않는다는 점도 검증했습니다.

학습 순서는 **명부의 DN → Bind → User Federation → Group Mapper → 그룹의 Client Role → JWT → Spring의 역할 검사 → 회사 규칙**으로 잡으면 됩니다.
