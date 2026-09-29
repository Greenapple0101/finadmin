# 01. 두 번째 백엔드를 만드는 순서

> 이 문서는 인증을 붙이기 전 첫 단계의 기록입니다. 현재 JWT·권한 검사는 [05. JWT 검증](05-jwt-validation.md), 실행 방법은 [README](../README.md)를 확인하세요.

FinAdmin은 FinAccess와 별도로 실행하는 작은 Spring Boot 백엔드입니다. 지금은 관리자 화면에서 사용할 수 있는 **가짜 요약 데이터**를 JSON으로 돌려주는 것까지 만듭니다. 실제 회사 정보나 이체 내역은 읽지 않습니다.

처음부터 폴더와 파일을 모두 외우려고 하지 않아도 됩니다. 아래 순서대로 “이 파일이 왜 필요해졌는지”를 따라가 보세요.

## 먼저, 서버가 두 개라는 말부터 이해하기

FinAccess 안에 `company`, `account`, `transfer`라는 폴더가 여러 개 있어도, 그 폴더 하나하나가 서버인 것은 아닙니다. 관련 코드를 나누어 담은 공간일 뿐입니다.

이번에는 FinAccess와 다른 프로그램인 FinAdmin을 만들고, 따로 실행합니다.

| 말 | 쉬운 뜻 | 이번 프로젝트의 예 |
| --- | --- | --- |
| 프로젝트 | 한 앱을 만들기 위한 코드와 설정의 묶음 | `finaccess`, `finadmin` |
| 패키지 | Java 코드를 주소에 따라 나누는 방법 | `io.github.greenapple0101.finadmin.hello` |
| 프로세스 | 실제로 실행 중인 프로그램 | 실행 중인 FinAccess와 실행 중인 FinAdmin |
| 포트 | 같은 컴퓨터에서 요청을 어느 프로그램으로 보낼지 구분하는 번호 | FinAccess 기본 8080, FinAdmin 기본 8081 |

FinAdmin을 실행해도 FinAccess가 자동으로 켜지지는 않습니다. FinAccess를 꺼도 FinAdmin의 샘플 API는 동작합니다. 현재 FinAdmin은 FinAccess나 DB에 연결하지 않기 때문입니다.

## 1. 먼저 앱을 만들 도구를 준비한다: build.gradle

첫 번째로 필요한 것은 “어떤 Java 버전으로, 어떤 라이브러리를 사용해서 앱을 만들지” 정하는 설정입니다.

`build.gradle`에 Java 21과 Spring Boot 4.1.1을 지정합니다. Gradle은 이 설정을 읽어서 필요한 라이브러리를 준비하고, 코드를 빌드하고, 테스트를 실행합니다. 여기서 **빌드**는 소스 코드를 실행 가능한 형태로 만드는 작업입니다.

이번에는 HTTP 요청을 받고 JSON 응답을 보내는 기능만 필요하므로 웹 기능과 테스트 도구를 사용합니다. DB를 쓰지 않아서 JPA, PostgreSQL, Flyway는 추가하지 않습니다.

`gradlew`, `gradlew.bat`, `gradle/wrapper`는 프로젝트에서 정한 Gradle을 실행하는 장치입니다. 이번 버전은 9.7.1입니다. 컴퓨터마다 별도로 설치한 Gradle 버전이 달라도 이 프로젝트의 실행 명령은 `./gradlew`로 통일할 수 있습니다. 최초 실행에는 Gradle과 라이브러리를 내려받기 위한 인터넷 연결이 필요할 수 있습니다.

## 2. 앱을 켜는 시작점을 만든다: FinadminApplication.java

파일 위치는 `src/main/java/io/github/greenapple0101/finadmin/FinadminApplication.java`입니다.

이 파일의 역할은 HTTP 요청을 처리하는 것이 아니라 **Spring Boot 앱을 시작하는 것**입니다.

실행 순서는 다음과 같습니다.

1. Java가 `main` 메서드를 실행합니다.
2. `SpringApplication.run(...)`이 Spring을 시작합니다.
3. Spring이 설정을 읽고 필요한 객체와 웹 서버를 준비합니다.
4. 웹 서버가 요청이 오기를 기다립니다.

`@SpringBootApplication`은 Spring Boot 앱의 설정 기준이 되는 클래스라는 표시입니다. Spring은 이 클래스가 있는 패키지 아래에서 `@RestController` 같은 표시가 붙은 클래스를 찾아 준비합니다.

그래서 `hello`와 `admin` 폴더를 `finadmin` 아래에 둡니다. 폴더 깊이를 늘리려는 목적이 아니라, 이 앱의 코드임을 주소로 구분하기 위한 것입니다.

**`main`은 요청을 받을 때마다 실행되지 않습니다.** 앱을 시작할 때 실행되고, 그다음 요청들은 각각에 연결된 Controller 메서드가 처리합니다.

## 3. 요청을 받을 주소와 번호를 정한다: application.properties

파일 위치는 `src/main/resources/application.properties`입니다. Java 코드가 아니라 Spring이 읽는 설정 파일입니다.

FinAdmin의 기본 실행 주소는 `http://127.0.0.1:8081`입니다.

- `127.0.0.1`은 이 컴퓨터 자신을 가리킵니다. 기본 상태에서는 같은 컴퓨터에서 접근하는 로컬 학습용 서버로 실행합니다.
- `8081`은 FinAdmin이 요청을 받을 포트 번호입니다. FinAccess의 기본 포트인 8080과 겹치지 않게 정했습니다.
- `spring.application.name`은 이 앱을 식별할 이름입니다. 이 이름을 바꾼다고 Java 패키지나 API 주소가 자동으로 바뀌지는 않습니다.

`SERVER_ADDRESS`와 `SERVER_PORT` 환경 변수로 주소와 포트를 바꿀 수 있습니다. `${SERVER_PORT:8081}`에서 `:` 뒤의 값은 외부에서 값을 주지 않았을 때 사용할 기본값입니다.

나중에 컨테이너나 Gateway와 연결할 때는 그 환경에서 접근할 수 있도록 주소 설정도 함께 살펴봐야 합니다. 지금은 로컬에서 앱 자체가 동작하는 것부터 확인합니다.

## 4. 가장 작은 요청부터 받아 본다: HelloController.java

파일 위치는 `src/main/java/io/github/greenapple0101/finadmin/hello/HelloController.java`입니다.

우선 복잡한 업무 없이 “요청을 받고 응답할 수 있는지” 확인합니다.

```text
GET /api/hello 요청
  → HelloController의 hello 메서드 실행
  → 인사말을 담은 응답 객체 생성
  → JSON 응답
```

응답은 다음과 같습니다.

```json
{"message":"Hello, FinAdmin!"}
```

여기서 중요한 표시는 두 개입니다.

| 표시 | 의미 |
| --- | --- |
| `@RestController` | 이 클래스를 웹 요청을 처리하는 객체로 준비하고, 메서드가 반환한 값을 응답 본문으로 보내라는 뜻입니다. |
| `@GetMapping("/api/hello")` | 요청 방식이 GET이고 주소가 `/api/hello`일 때 아래 메서드를 실행하라는 뜻입니다. |

GET은 서버에 정보를 달라고 요청하는 HTTP 방식입니다. 어노테이션은 `@`로 시작하는 표시이며, Spring 같은 도구가 코드를 어떻게 다룰지 알려 줍니다.

메서드는 Java 응답 객체를 돌려줍니다. Spring이 연결한 JSON 변환 도구가 이를 JSON으로 바꿔서 보냅니다. 따라서 우리가 JSON 문자열을 손으로 조립할 필요는 없습니다.

## 5. 관리자용 샘플 응답을 만든다: AdminSummaryController.java

파일 위치는 `src/main/java/io/github/greenapple0101/finadmin/admin/AdminSummaryController.java`입니다.

두 번째 API는 `GET /api/admin/summary`입니다. 다음과 같은 고정된 데이터를 반환합니다.

```json
{
  "application": "finadmin",
  "sampleData": true,
  "pendingTransferCount": 3,
  "completedTransferCount": 7
}
```

| 항목 | 의미 |
| --- | --- |
| `application` | 이 응답을 만든 앱의 이름입니다. |
| `sampleData` | 실제 업무 데이터를 조회한 응답이 아니라는 표시입니다. |
| `pendingTransferCount` | 대기 중인 이체 건수를 흉내 낸 숫자입니다. 항상 3입니다. |
| `completedTransferCount` | 완료된 이체 건수를 흉내 낸 숫자입니다. 항상 7입니다. |

**3건과 7건은 코드에 직접 적어 놓은 샘플 값입니다.** FinAccess에서 이체를 실행해도 이 숫자는 바뀌지 않습니다. DB 조회나 FinAccess API 호출이 없기 때문입니다.

Controller 안의 `AdminSummary`는 응답 데이터의 모양을 정의한 `record`입니다. `record`는 전달할 값들을 간단하게 묶는 Java 문법입니다. 여기서는 앱 이름, 샘플 여부, 두 종류의 건수를 담습니다.

`record`를 선언했다고 DB 테이블이 만들어지는 것은 아닙니다. 이번 `record`는 JSON 응답을 만들기 위한 Java 데이터 묶음입니다. Controller 안에 둔 이유는 지금 이 응답을 사용하는 곳이 그 Controller뿐이기 때문입니다.

또한 이번에는 계산하거나 저장하는 별도 업무가 없으므로 Service나 Repository를 만들지 않습니다. 나중에 실제 업무 처리가 생기면 그 역할에 맞게 파일을 나눌 수 있습니다.

### 주소에 admin이 있는데 관리자만 접근할 수 있나요?

아직은 아닙니다. `/api/admin/summary`는 주소 이름일 뿐입니다. 이름에 `admin`을 붙이는 것만으로 로그인 확인이나 관리자 권한 검사가 생기지 않습니다.

현재는 인증·인가 기능을 넣지 않았습니다. 로컬 실행 주소에 접근할 수 있으면 이 샘플 응답을 받을 수 있습니다. 그래서 실제 사용자 정보나 관리자용 비밀 데이터를 넣지 않습니다.

나중에는 Keycloak이 발급한 액세스 토큰을 받고, 이 앱이 토큰의 유효성과 역할을 확인한 뒤 관리자 응답을 보내도록 확장합니다. 그때 FinAccess와 FinAdmin은 각각 토큰을 검증하는 Resource Server가 됩니다. **Resource Server**는 보호할 API를 제공하고, 전달받은 액세스 토큰을 확인하는 서버라는 뜻입니다.

Apache APISIX, Keycloak, Spring Security 연결은 다음 단계입니다. 이번 단계에서는 설치하거나 연결하지 않습니다. SSO 시연이나 Istio도 현재 구현 범위에 포함하지 않습니다.

## 6. 실제로 실행해서 요청한다

터미널에서 FinAdmin 프로젝트 폴더로 이동한 뒤 실행합니다.

```bash
./gradlew bootRun
```

서버가 시작되면 실행 터미널은 계속 열린 상태로 있습니다. 요청을 기다리고 있기 때문입니다. 다른 터미널을 열어서 두 API를 확인합니다.

```bash
curl -i http://127.0.0.1:8081/api/hello
curl -i http://127.0.0.1:8081/api/admin/summary
```

`curl`은 터미널에서 HTTP 요청을 보내는 도구입니다. `-i`는 응답 데이터뿐 아니라 상태 코드와 헤더도 보여 달라는 옵션입니다. 두 요청 모두 HTTP 200과 앞에서 본 JSON 응답이 나와야 합니다. 200은 요청을 정상 처리했다는 뜻입니다.

서버를 종료할 때는 서버를 실행한 터미널에서 `Ctrl+C`를 누릅니다.

### 8081 포트를 이미 다른 앱이 사용하고 있다면

포트를 바꿔 실행할 수 있습니다.

```bash
SERVER_PORT=8082 ./gradlew bootRun
```

이 경우 요청 주소도 `http://127.0.0.1:8082`로 바꿔야 합니다. 실행 옵션으로 바꾸는 방법도 있습니다.

```bash
./gradlew bootRun --args='--server.port=8082'
```

주소 설정은 `SERVER_ADDRESS`로 바꿀 수 있지만, 이번 로컬 실습에서는 기본값인 `127.0.0.1`을 그대로 사용하면 됩니다.

## 7. 자동 검사와 실행 파일 만들기

다음 명령으로 테스트를 실행하고 실행 가능한 JAR 파일을 만듭니다.

```bash
./gradlew test bootJar
```

테스트는 요청을 처리했을 때 상태 코드와 JSON 내용이 예상대로 나오는지 자동으로 확인합니다. `bootJar`는 Java 코드와 실행에 필요한 라이브러리를 JAR 파일로 묶습니다. 생성된 파일은 `build/libs`에 있습니다.

이번 테스트에는 DB나 Docker가 필요하지 않습니다. 아직 인증·인가 기능이 없으므로, 이 테스트가 통과해도 “관리자만 접근할 수 있다”는 사실을 검증한 것은 아닙니다.

## 파일을 다시 읽을 때의 순서

1. `build.gradle`: 이 앱에 어떤 도구를 넣었는지 봅니다.
2. `FinadminApplication.java`: 앱이 어디서 시작되는지 봅니다.
3. `application.properties`: 어느 주소와 포트에서 요청을 받는지 봅니다.
4. `HelloController.java`: 요청 하나가 메서드 하나로 이어지는 모습을 봅니다.
5. `AdminSummaryController.java`: 여러 값을 묶어 JSON으로 보내는 모습을 봅니다.
6. 테스트 파일: 위 응답을 어떻게 자동 확인하는지 봅니다.

여기까지 만들면 FinAccess와 별도로 켜고 끌 수 있는 두 번째 백엔드가 준비됩니다. 다음 인증·인가 단계에서는 이 작은 앱을 대상으로 토큰 검증과 관리자 권한 검사를 하나씩 추가할 수 있습니다.
