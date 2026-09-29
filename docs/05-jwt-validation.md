# 05. FinAdmin이 받은 JWT를 직접 검증하기

이번 단계의 목표는 **FinAdmin이 요청에 담긴 액세스 토큰을 스스로 확인한 뒤 API를 실행하도록 만드는 것**입니다. APISIX에서 이미 검사했더라도 FinAdmin의 검사는 그대로 실행됩니다.

01번 문서는 인증을 붙이기 전의 첫 앱을 설명합니다. 현재는 이 문서와 06번 문서의 보안 규칙까지 적용되어 있으므로 관리자 API를 토큰 없이 호출하면 거절됩니다.

## 먼저 요청 하나를 따라가 보기

```text
GET /api/me
Authorization: Bearer 액세스_토큰
  → Spring Security가 토큰을 꺼냄
  → JwtDecoder가 서명·발급자·시간·대상·사용자 식별자를 검사
  → 검증된 토큰의 역할을 Spring 권한으로 바꿈
  → 이 주소에 접근해도 되는지 확인
  → CurrentUserController.me() 실행
  → 확인된 사용자 정보만 JSON으로 응답
```

여기서 **Controller 앞에서 검사한다**는 점이 중요합니다. `me()` 안에서 문자열을 잘라 JWT를 분석하거나, 호출자에게 비밀번호를 다시 물어보는 방식이 아닙니다. 토큰이 인정되지 않으면 보호된 Controller 메서드를 실행하기 전에 401로 응답합니다.

`Bearer`는 뒤에 액세스 토큰이 있다는 HTTP 인증 방식 표시입니다. FinAdmin에는 API 호출용 액세스 토큰을 보내며, 프런트의 로그인 결과 확인용 ID Token을 대신 보내지 않습니다.

## 1. 이번에 필요한 파일은 무엇인가

Java 파일의 공통 위치는 `src/main/java/io/github/greenapple0101/finadmin/`입니다.

| 파일 | 맡는 일 |
| --- | --- |
| `build.gradle` | OAuth2 Resource Server 라이브러리를 준비합니다. |
| `src/main/resources/application.properties` | 신뢰할 발급자, 공개 키 주소, 토큰의 대상을 정합니다. |
| `security/SecurityConfiguration.java` | Controller 앞의 검사 흐름과 실제 JWT 검증기를 만듭니다. |
| `security/KeycloakRoleConverter.java` | 검증된 토큰의 FinAdmin 역할을 Spring 권한으로 바꿉니다. 06번에서 자세히 설명합니다. |
| `security/CurrentUserController.java` | 검증에 성공한 사용자 정보를 `/api/me`로 보여줍니다. |

`spring-boot-starter-oauth2-resource-server`는 받은 토큰을 확인하는 도구 묶음입니다. 이 의존성을 추가했다고 FinAdmin이 로그인 서버가 되는 것은 아닙니다. 로그인과 토큰 발급은 Keycloak이 맡고 FinAdmin은 보호할 API를 제공합니다.

## 2. SecurityFilterChain: 요청을 Controller로 보낼지 정한다

`SecurityConfiguration`의 `securityFilterChain()` 메서드부터 읽습니다. **Filter**는 HTTP 요청을 Controller에 넘기기 전에 처리할 수 있는 장치이고, **Chain**은 이러한 장치들을 이어 놓았다는 뜻입니다.

`@Configuration`은 Spring 설정을 모은 클래스라는 표시입니다. `@Bean`이 붙은 메서드는 만들어 반환한 객체를 Spring이 관리하게 합니다. 매 API 요청마다 우리가 직접 `new SecurityFilterChain(...)`을 호출하는 구조가 아닙니다.

핵심 연결은 다음 코드입니다.

```java
.oauth2ResourceServer(resourceServer -> resourceServer
        .jwt(jwt -> jwt.jwtAuthenticationConverter(authenticationConverter)))
```

“이 앱은 Bearer JWT를 받아 검사하는 Resource Server이고, 성공하면 지정한 변환기로 사용자의 권한을 읽겠다”는 설정입니다. 람다식의 `->`는 왼쪽으로 받은 설정 도구를 오른쪽에서 다룬다는 뜻으로 읽으면 됩니다.

**`JwtDecoder`가 먼저 토큰을 검증하고, 검증된 정보에 대해서만 역할 변환이 진행됩니다.** 역할 변환기에 `admin`이라는 글자가 보인다고 서명 검사를 건너뛰지는 않습니다.

## 3. JwtDecoder: 읽을 수 있는 토큰과 믿을 수 있는 토큰을 구분한다

같은 파일의 `jwtDecoder()` 메서드에서 다음 검증기를 만듭니다.

```java
NimbusJwtDecoder decoder = NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();
```

JWT의 가운데 부분을 풀면 내용을 읽을 수 있습니다. 하지만 내용을 읽을 수 있다는 사실은 진짜 발급된 토큰이라는 증거가 아닙니다. `NimbusJwtDecoder`는 **신뢰하는 공개 키로 서명이 맞는지 확인**합니다. 현재 설정의 기본 허용 서명 방식은 RS256입니다.

Keycloak은 자신이 가진 개인 키로 서명하고, 백엔드에는 검증용 공개 키를 제공합니다. FinAdmin이 사용자 비밀번호나 Keycloak의 개인 키를 알아야 하는 것은 아닙니다. 공개 키 여러 개를 JSON으로 제공하는 목록을 **JWKS**라고 합니다.

서명을 확인한 다음에는 아래 조건도 검사합니다. 토큰 안의 이름 붙은 값들을 **claim(클레임)**이라고 부릅니다.

| 검사할 값 | 쉬운 뜻 | 현재 코드의 규칙 |
| --- | --- | --- |
| 서명 | 믿는 발급자가 서명했고 내용이 바뀌지 않았는가 | 설정한 JWKS 공개 키로 확인합니다. |
| `iss` | 누가 발급했는가 | 설정한 issuer와 일치해야 합니다. |
| `exp` | 언제 만료되는가 | 값이 반드시 있고, 시간 검사를 통과해야 합니다. |
| `nbf` | 언제부터 사용해도 되는가 | 값이 있다면 사용 가능 시각인지 검사합니다. 생략 자체는 허용합니다. |
| `aud` | 어느 API를 위한 토큰인가 | 목록에 `JWT_AUDIENCE` 값, 기본 `finadmin-api`가 있어야 합니다. |
| `sub` | 누구를 가리키는 토큰인가 | 비어 있지 않은 사용자 식별자가 있어야 합니다. |

`JwtValidators.createDefaultWithIssuer(issuer)`에 기본 시간·발급자 검사가 들어 있습니다. 여기에 `aud`, `sub`, `exp` 존재 검사를 추가하고 `DelegatingOAuth2TokenValidator`로 함께 실행하게 합니다. 이름이 길지만 **여러 검사 조건을 하나로 묶는 도구**라고 이해하면 됩니다.

`aud`에 FinAccess와 FinAdmin이 모두 들어 있는 것은 허용합니다. FinAccess만 들어 있는 토큰은 FinAdmin에서 401로 거절합니다. 발급자와 대상 검사는 서로 다른 조건이므로, 같은 Keycloak에서 발급했다고 모든 API에서 사용할 수 있는 것은 아닙니다. [Spring JWT 검증과 audience 설정 문서](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html)

## 4. issuer와 공개 키 주소가 다른 이유

`application.properties`의 환경 변수는 다음과 같습니다.

| 환경 변수 | 목적 | 앱을 Mac에서 직접 실행할 때 기본값 |
| --- | --- | --- |
| `JWT_ISSUER_URI` | 토큰의 `iss`와 비교할 발급자 | `http://localhost:18080/realms/finlab` |
| `JWT_JWK_SET_URI` | 서명 확인용 공개 키를 가져올 주소 | `http://localhost:18080/realms/finlab/protocol/openid-connect/certs` |
| `JWT_AUDIENCE` | 토큰 대상에 있어야 하는 값 | `finadmin-api` |

Docker Compose로 실행할 때는 `JWT_JWK_SET_URI`가 `http://keycloak:8080/realms/finlab/protocol/openid-connect/certs`로 바뀝니다. 컨테이너 안의 `localhost`는 그 컨테이너 자신이기 때문입니다. Docker 네트워크에서는 Keycloak을 서비스 이름인 `keycloak`으로 찾습니다.

반면 `JWT_ISSUER_URI`는 계속 `http://localhost:18080/realms/finlab`입니다. **발급자 이름을 비교하는 값과 공개 키를 받으러 접속하는 주소는 목적이 다릅니다.** 공개 키 주소를 내부 주소로 바꿨다고 토큰의 `iss`를 내부 주소로 바꾸거나 검사를 끄면 안 됩니다.

공개 키 주소를 직접 지정했으므로 FinAdmin은 Keycloak에 접속하지 않고도 시작할 수 있습니다. 보호된 요청을 검증할 때는 필요한 공개 키를 받아야 합니다. 받은 키를 캐시하므로 매 요청마다 Keycloak에 “이 사용자를 믿어도 되나요?”라고 물어보는 방식도 아닙니다.

## 5. 공개 API와 기본 보호 규칙

실제 백엔드 규칙은 다음 순서로 적혀 있습니다.

```java
.requestMatchers(HttpMethod.GET, "/api/hello").permitAll()
.requestMatchers("/api/admin/**").hasRole("admin")
.anyRequest().authenticated()
```

- `GET /api/hello`는 토큰 없이 실행 여부를 확인할 수 있습니다.
- `/api/admin/` 아래 주소는 관리자 역할이 필요합니다.
- `/api/me`를 비롯한 나머지 요청은 인증이 필요합니다.

`permitAll()`은 접근에 인증을 요구하지 않는다는 뜻입니다. **잘못된 Bearer 토큰을 일부러 붙여도 무시한다는 뜻은 아닙니다.** 토큰을 보낸 요청은 인증 필터의 검사를 받을 수 있습니다.

`DispatcherType.ERROR`를 허용하는 줄은 이미 처리 중인 오류를 Spring 오류 처리기로 넘기기 위한 것입니다. 외부에서 처음 요청하는 `/error` 주소 전체를 공개하는 설정은 아닙니다.

Gateway는 별도 규칙을 가집니다. 이번 APISIX 설정은 `/admin/*` 전체를 보호하므로 Gateway를 거친 `/admin/api/hello`도 토큰이 필요합니다. 백엔드에 직접 보낸 인사 요청과 구분해야 합니다.

## 6. 세션과 CSRF 설정을 이렇게 선택한 이유

`SessionCreationPolicy.STATELESS`는 로그인 정보를 서버 세션에 저장해 다음 요청에 사용하는 방식을 쓰지 않겠다는 뜻입니다. 어제나 직전 요청에 성공했더라도, 이번 보호된 요청에는 다시 Bearer 토큰이 있어야 합니다.

CSRF는 브라우저가 자동으로 붙이는 로그인 쿠키 등을 악용해 다른 사이트에서 원치 않는 요청을 보내게 하는 공격입니다. 현재 FinAdmin API는 **인증 쿠키나 HTTP Basic 로그인을 사용하지 않고**, 호출 코드가 직접 붙인 Authorization 헤더로만 인증하므로 CSRF 검사를 끕니다.

단순히 “JWT라서”, “세션이 없어서” 항상 꺼도 된다는 뜻은 아닙니다. 나중에 인증을 쿠키로 받도록 바꾸면 다시 검토해야 합니다. Keycloak 로그인 화면 자체의 쿠키와 FinAdmin API의 인증 방식도 구분해야 합니다. [Spring CSRF 문서](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html)

## 7. /api/me로 백엔드가 확인한 신원 보기

`CurrentUserController.me()`의 `@AuthenticationPrincipal Jwt jwt`는 보안 검사를 통과한 사용자의 토큰 정보를 받습니다. JSON 본문이나 `X-User` 헤더에 사용자가 직접 적은 ID를 받는 것이 아닙니다.

일반 사용자에게 돌아오는 응답의 모양은 다음과 같습니다. 아래 식별자는 설명용입니다.

```json
{
  "application": "finadmin",
  "subject": "예시-사용자-ID",
  "issuer": "http://localhost:18080/realms/finlab",
  "roles": ["user"]
}
```

같은 사용자가 두 백엔드를 호출했을 때 FinAccess의 `sub`와 FinAdmin의 `subject`, 그리고 양쪽 `issuer`가 같은지 비교하면 각 앱이 어떤 신원을 확인했는지 볼 수 있습니다. `roles`는 이 앱이 인정한 역할만 표시합니다. 응답에 토큰 원문이나 비밀번호는 넣지 않습니다.

## 8. 자동 테스트는 무엇을 증명하는가

검증 파일은 `src/test/java/io/github/greenapple0101/finadmin/admin/AdminSummaryControllerTest.java`입니다. 이름에는 관리자 Controller가 들어 있지만 JWT 인증부터 관리자 인가까지 함께 확인합니다.

1. 테스트 메모리에서 RSA 개인 키·공개 키를 만듭니다.
2. 임시 HTTP 서버로 공개 키 목록만 제공합니다.
3. 테스트용 토큰을 실제 개인 키로 서명합니다.
4. MockMvc 요청의 Authorization 헤더에 그 토큰을 넣습니다.
5. 실제 `JwtDecoder`와 권한 검사 결과를 확인합니다.

**MockMvc라는 이름이 있어도 토큰 검증을 가짜 성공으로 바꾸지는 않습니다.** API HTTP 포트를 직접 열지 않고 요청 처리 흐름을 시험하는 도구입니다. 키 조회에는 실제 임시 HTTP 서버를 사용합니다. 운영 Keycloak의 사용자나 키는 사용하지 않습니다.

위조 서명, 틀린 issuer/audience, 만료, 미래 nbf, 누락된 exp/sub/aud 등을 거절하는지 확인합니다. 서명 키의 이름인 `kid`가 같아도 실제 키가 다르면 거절하는 사례도 포함합니다. 별도의 `HelloControllerTest`는 토큰 없이 공개 인사 API에 접근할 수 있는지 확인합니다.

```bash
./gradlew test bootJar
```

Spring 기본 시간 검사는 서버 간 시계 차이를 고려해 **60초의 오차 범위**를 허용합니다. 그래서 테스트에서는 5분 전에 만료되거나 5분 뒤부터 사용할 수 있는 토큰을 만듭니다. 만료 시각에서 1초 지난 토큰이 백엔드에 즉시 거절되어야 한다고 기대하면 이 설정을 잘못 이해한 것입니다. [Spring 시간 검증 설명](https://docs.spring.io/spring-security/reference/servlet/oauth2/resource-server/jwt.html#oauth2resourceserver-jwt-validation)

이 테스트는 백엔드 검증을 확인합니다. 실제 Keycloak 로그인과 APISIX 연결까지의 전체 흐름은 별도 실행 검증이 필요합니다. 현재 HTTP 주소와 직접 호출 포트는 로컬 실습용이며 운영 배포 구성이 완성되었다는 뜻은 아닙니다.

다음은 [06. 관리자 권한 제한](06-admin-authorization.md)에서 “정상 토큰인데 왜 403이 나오는가”를 읽으면 됩니다.
