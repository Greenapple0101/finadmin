# 06. 관리자 역할이 있어야 데이터를 보내기

05번에서는 토큰을 믿을 수 있는지 확인했습니다. 이번 단계는 **인증된 사용자가 관리자 API를 사용해도 되는지** 확인하는 과정입니다.

유효한 토큰이 있어도 일반 사용자는 `/api/admin/summary`를 사용할 수 없습니다. Keycloak의 FinAdmin용 `admin` 역할이 토큰에 있고, FinAdmin이 그 역할을 인정해야 관리자 응답이 나옵니다.

## 1. 인증과 인가를 나누어 보기

| 단계 | 확인하는 질문 | FinAdmin에서 실패할 때 |
| --- | --- | --- |
| 인증 | 이 토큰을 믿고 사용자를 식별할 수 있는가? | 401 |
| 인가 | 확인된 사용자에게 이 API를 사용할 권한이 있는가? | 403 |

예를 들어 일반 사용자 `alice`와 관리자 `admin`은 모두 정상 토큰을 받을 수 있습니다. 두 사용자 모두 `/api/me`로 자신의 정보를 확인할 수 있지만, 관리자 요약 API는 `admin`만 사용할 수 있습니다.

이는 **현재 FinAdmin의 규칙**입니다. Gateway 플러그인의 실패 상태 코드까지 무조건 같은 것은 아닙니다. 이번 API7 Enterprise의 audience 불일치 응답은 403이고 FinAdmin의 audience 불일치는 401입니다. [API7 Gateway 정책](14-gateway-rbac-policy.md)에서 어느 지점이 거절했는지 함께 확인합니다.

## 2. Keycloak과 백엔드가 맡는 일을 구분한다

Keycloak의 역할 설정은 `infra/keycloak/finlab-realm.json`에 있습니다. `finadmin-api` Client에 `user`와 `admin` 역할을 정의합니다.

| 실습 사용자 | FinAdmin 역할 | 관리자 요약 API |
| --- | --- | --- |
| `alice` | `user` | 거절 |
| `bob` | `user` | 거절 |
| `outsider` | `user` | 거절 |
| `admin` | `admin` | 허용 |

FinAccess에는 별도의 역할이 있습니다. 예를 들어 `bob`이 FinAccess의 `approver`여도 FinAdmin의 관리자가 되는 것은 아닙니다.

**Keycloak은 역할을 사용자에게 부여하고 토큰에 전달합니다. 백엔드는 그 역할을 읽고 요청을 허용하거나 거절합니다.** Keycloak 설정만으로 우리 Controller가 보호되거나 업무 DB 데이터가 자동으로 걸러지는 것은 아닙니다. [Keycloak 역할 관리 문서](https://www.keycloak.org/docs/latest/server_admin/)

여기서 `finadmin-api`의 `admin` 역할은 **우리 앱의 관리자**입니다. Keycloak 관리 콘솔에 접속해 Realm이나 사용자를 수정하는 관리자 권한과 다릅니다. 앱 관리자가 Keycloak 운영 권한까지 가질 필요는 없습니다.

## 3. 토큰의 어느 역할을 읽는가

아래 JSON은 역할 위치를 이해하기 위한 **토큰 내용 일부의 예시**입니다. 실제 토큰이나 완전한 토큰 검증 입력이 아닙니다.

```json
{
  "resource_access": {
    "finaccess-api": {
      "roles": ["admin"]
    },
    "finadmin-api": {
      "roles": ["user"]
    }
  }
}
```

이 사람은 FinAccess에서는 관리자지만 FinAdmin에서는 일반 사용자입니다. 토큰 전체에서 `admin`이라는 글자를 검색해서 허용하면 잘못된 앱의 권한까지 가져오게 됩니다.

FinAdmin은 정확히 **`resource_access.finadmin-api.roles`만** 읽습니다. `realm_access.roles`의 `admin`, 다른 Client의 `admin`, 요청 본문에 사용자가 직접 쓴 역할은 관리자 권한으로 사용하지 않습니다.

읽는 파일은 `src/main/java/io/github/greenapple0101/finadmin/security/KeycloakRoleConverter.java`입니다.

## 4. KeycloakRoleConverter를 줄 단위로 읽는 방법

이 클래스는 `Converter<Jwt, Collection<GrantedAuthority>>`를 구현합니다. 긴 선언은 “JWT 하나를 받아 Spring 권한 목록으로 바꾸는 도구”라고 읽으면 됩니다.

`convert()` 안에서는 다음 순서대로 내려갑니다.

1. JWT에서 `resource_access` 값을 꺼냅니다.
2. 이름으로 값을 찾는 `Map` 모양인지 확인합니다.
3. 그 안의 `finadmin-api` 값만 꺼냅니다.
4. 그 안의 `roles`가 목록인지 확인합니다.
5. 모든 항목이 비어 있지 않은 문자열인지 확인합니다. 하나라도 잘못됐으면 권한 목록 전체를 비웁니다.
6. 검사를 통과한 역할값에 `ROLE_`를 붙여 Spring 권한을 만듭니다.

예를 들면 다음처럼 바뀝니다.

```text
Keycloak의 finadmin-api 역할 admin
  → KeycloakRoleConverter
  → Spring 권한 ROLE_admin
```

`Map`은 이름과 값을 짝지어 보관하는 자료구조입니다. `Collection`은 여러 값을 모아 놓은 자료구조입니다. `instanceof`는 지금 꺼낸 값이 예상한 자료형인지 검사합니다.

중간 값이 없거나 모양이 이상하면 `List.of()`로 빈 권한 목록을 반환합니다. 잘못된 역할 정보 때문에 관리자로 인정하거나 500 오류를 내는 대신, 관리자 권한을 부여하지 않습니다.

역할이 없다고 토큰 자체가 항상 잘못된 것은 아닙니다. 하지만 현재 `GET /api/me`도 `user` 또는 `admin` 역할이 필요합니다. 유효한 토큰에 이 앱의 역할이 없다면 내 정보와 관리자 API 모두 403입니다.

## 5. SecurityConfiguration에서 역할과 URL을 연결한다

파일은 `src/main/java/io/github/greenapple0101/finadmin/security/SecurityConfiguration.java`입니다.

먼저 역할 변환기를 Spring의 인증 정보 변환기에 연결합니다.

```java
JwtAuthenticationConverter authenticationConverter = new JwtAuthenticationConverter();
authenticationConverter.setJwtGrantedAuthoritiesConverter(new KeycloakRoleConverter());
```

`JwtAuthenticationConverter`는 검증된 JWT를 Spring이 다루는 로그인 정보로 바꾸는 도구입니다. 그중 권한을 어떻게 읽을지 우리가 만든 `KeycloakRoleConverter`로 정합니다. Keycloak의 중첩된 Client 역할이 우리가 원하는 규칙으로 저절로 연결된다고 가정하지 않습니다.

그다음 관리자 주소에 필요한 권한을 적습니다.

```java
.requestMatchers(HttpMethod.GET, "/api/me").hasAnyRole("user", "admin")
.requestMatchers(HttpMethod.GET, "/api/admin/summary").hasRole("admin")
.anyRequest().denyAll()
```

`HttpMethod.GET`과 정확한 경로를 함께 지정하므로 다른 메서드나 주소까지 자동 허용하지 않습니다. `denyAll()`은 명시하지 않은 요청을 거절합니다. `hasRole("admin")`은 기본적으로 `ROLE_admin`이라는 Spring 권한을 찾습니다. 그래서 앞에서 `ROLE_`를 붙였습니다. 역할 이름의 대소문자는 구분하며, 여기서는 소문자 `admin`을 사용합니다. [Spring HTTP 요청 인가 문서](https://docs.spring.io/spring-security/reference/servlet/authorization/authorize-http-requests.html)

이 검사는 Controller 실행 전에 일어납니다. 현재는 `AdminSummaryController` 안에 `if (관리자)` 코드를 쓰거나 `@PreAuthorize`를 추가하지 않아도 URL 접근 규칙이 적용됩니다.

## 6. 요청 헤더에 admin이라고 쓰면 어떻게 되는가

누구나 HTTP 요청에 다음 글자를 붙일 수 있습니다.

```http
X-User: admin
X-Role: admin
```

따라서 FinAdmin은 이 헤더를 신원이나 권한의 근거로 사용하지 않습니다. Gateway가 보냈다는 이름표만 보고 관리자로 인정하지도 않습니다. **서명과 조건 검사를 통과한 토큰에 들어 있는 FinAdmin 역할**을 사용합니다.

사용자 식별도 같습니다. `/api/me`는 요청자의 본문이나 `X-User`가 아니라 `@AuthenticationPrincipal`로 받은 검증된 JWT의 `sub`를 보여줍니다. `Authentication`의 권한 목록에서는 `ROLE_`로 시작하는 앱 역할만 골라 표시합니다.

## 7. 관리자 역할은 실제로 검사하지만 데이터는 샘플이다

`src/main/java/io/github/greenapple0101/finadmin/admin/AdminSummaryController.java`가 반환하는 데이터는 다음과 같습니다.

```json
{
  "application": "finadmin",
  "sampleData": true,
  "pendingTransferCount": 3,
  "completedTransferCount": 7
}
```

관리자 역할 검사는 실제 Spring Security 설정으로 동작합니다. 반면 `3`과 `7`은 고정된 예시입니다. FinAccess의 DB나 API에서 가져온 실제 통계가 아니며, FinAccess에서 이체해도 숫자가 바뀌지 않습니다.

이번 앱의 목적은 독립적인 두 번째 백엔드에서도 토큰 검증과 권한에 따른 응답 제한이 동작함을 보여주는 것입니다. 실제 통계가 필요해지면 관리자 접근을 확인한 뒤 데이터를 읽는 업무 코드를 별도로 구현해야 합니다.

## 8. 어떤 결과를 확인해야 하는가

아래 표는 **FinAdmin을 직접 호출했을 때**의 결과입니다. Docker Compose 실행 시 직접 호출 주소는 `http://localhost:18083`, Mac에서 기본 `bootRun`으로 실행하면 `http://127.0.0.1:8081`입니다.

| 상황 | 경로 | 결과 |
| --- | --- | --- |
| 토큰 없음 | `/api/hello` | 200, 인사말 |
| 토큰 없음 | `/api/me` | 401 |
| 토큰이 변조되거나 충분히 오래 전에 만료됨 | `/api/admin/summary` | 401 |
| FinAccess만 대상인 토큰 | `/api/admin/summary` | 401 |
| 정상적인 FinAdmin 대상 일반 사용자 토큰 | `/api/me` | 200, 자기 신원 |
| 정상적인 FinAdmin 대상 일반 사용자 토큰 | `/api/admin/summary` | 403 |
| 다른 Client에만 admin 역할이 있는 토큰 | `/api/admin/summary` | 403 |
| 정상적인 FinAdmin 대상이며 FinAdmin admin 역할이 있는 토큰 | `/api/admin/summary` | 200, 관리자 샘플 데이터 |

비밀값 없이 확인할 수 있는 예시는 다음과 같습니다.

```bash
curl -i http://localhost:18083/api/hello
curl -i http://localhost:18083/api/admin/summary
```

첫 요청은 200, 두 번째 요청은 401이 나와야 합니다. 토큰이 있는 상황은 실습 프런트에서 일반 사용자와 관리자로 각각 로그인해 비교합니다. 실제 토큰이나 비밀번호를 이 문서에 붙이지 않습니다.

## 9. 자동 테스트는 역할 구분까지 검사한다

`src/test/java/io/github/greenapple0101/finadmin/admin/AdminSummaryControllerTest.java`에는 다음 사례가 있습니다.

- 일반 사용자는 관리자 API에서 403을 받습니다.
- 다른 Client에만 있는 admin이나 Realm admin으로는 접근할 수 없습니다.
- 역할이 목록이어야 하는데 문자열 하나로 잘못 들어오면 접근을 거절합니다.
- `X-User`, `X-Role`만 보내는 요청은 인증되지 않습니다.
- 올바른 관리자는 샘플 JSON을 받고 세션 쿠키는 발급되지 않습니다.
- `/api/me`는 서명된 토큰의 subject와 FinAdmin 역할만 응답합니다.

여기서 사용하는 토큰은 테스트용 키로 실제 서명합니다. `jwt()` 같은 테스트 도구로 이미 인증되었다고 처리하는 방식으로 서명 검증을 생략하지 않습니다. 테스트 전체 실행 방법과 토큰 검증 실패 사례는 [05번 문서](05-jwt-validation.md)에 있습니다.

## 10. 현재 방식의 범위를 이해하기

JWT를 공개 키로 검사하는 방식에서는 Keycloak의 역할을 바꿔도 이미 발급된 토큰의 내용이 자동으로 바뀌지 않습니다. 현재 FinAdmin은 매 요청마다 Keycloak에 사용자 세션이나 최신 역할을 조회하지 않으므로, 즉시 권한 회수가 구현됐다고 설명하면 안 됩니다. 실습에서 역할을 바꿨다면 새 토큰을 받아 비교합니다.

이번 구성은 로컬에서 인증·인가 경계를 재현하는 실습입니다. 실제 금융 운영 서비스의 배포 보안이나 권한 관리 절차가 모두 완성되었다는 뜻은 아닙니다. 이번에 설명할 수 있어야 하는 핵심은 **Keycloak의 역할이 토큰에 들어오고, 각 백엔드가 자신의 역할만 읽어 API 접근을 결정한다는 것**입니다.
