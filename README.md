# FinAdmin

[FinAccess](https://github.com/Greenapple0101/finaccess)와 별도로 실행하는 Spring Boot 관리자 API 학습용 앱입니다.
첫 단계에서는 앱의 시작점과 관리자용 샘플 응답을 준비합니다.

**처음 읽는다면 [두 번째 백엔드를 만든 순서](docs/01-first-application.md)부터 보세요.**
소스와 테스트 주석은 파일의 역할 → 실행 순서 → 각 문법의 의미를 쉬운 말로 설명합니다.

## 현재 범위

- Java 21, Spring Boot 4.1.1, Gradle Wrapper 9.7.1
- 기본 접속 주소: `http://127.0.0.1:8081`
- DB, Docker, FinAccess 없이 실행할 수 있습니다.
- 아직 로그인과 JWT 검증, 역할 검사가 없습니다. 내 컴퓨터에서 실행하는 실습용 앱입니다.

| API | 현재 하는 일 |
| --- | --- |
| `GET /api/hello` | FinAdmin 인사말로 실행 여부를 확인합니다. |
| `GET /api/admin/summary` | 관리자 화면용 고정 샘플 데이터를 반환합니다. |

`/admin`이라는 주소만으로 권한이 제한되지는 않습니다. 현재는 두 API 모두 토큰 없이 호출할 수 있습니다.
기본 주소 `127.0.0.1`은 내 컴퓨터에서만 접속받도록 하는 설정이며, 인증·인가 기능을 대신하지 않습니다.

## 실행

Java 21을 설치한 뒤 이 저장소 폴더의 터미널에서 실행합니다. Gradle은 별도로 설치하지 않아도 됩니다.
처음 실행할 때는 Gradle과 라이브러리를 내려받기 위한 인터넷 연결이 필요합니다.

```bash
./gradlew bootRun
```

위 터미널은 서버를 실행한 상태로 두고, 다른 터미널에서 호출합니다.

```bash
curl -i http://127.0.0.1:8081/api/hello
```

HTTP 200과 아래 JSON이 반환됩니다.

```json
{"message":"Hello, FinAdmin!"}
```

관리자용 샘플 API도 같은 방법으로 호출합니다.

```bash
curl -i http://127.0.0.1:8081/api/admin/summary
```

HTTP 200과 아래 JSON이 반환됩니다.

```json
{
  "application": "finadmin",
  "sampleData": true,
  "pendingTransferCount": 3,
  "completedTransferCount": 7
}
```

3건과 7건은 코드에 적어 둔 예시입니다. FinAccess의 실제 데이터를 조회하지 않습니다.
`sampleData: true`로 이 응답이 샘플임을 표시합니다.

종료하려면 실행 중인 터미널에서 `Ctrl+C`를 누릅니다.
8081번 포트를 다른 앱이 사용 중이면 `./gradlew bootRun --args='--server.port=8082'`로 바꾸고 호출 주소도 바꿉니다.
환경 변수 `SERVER_PORT`로도 포트를 바꿀 수 있습니다. `SERVER_ADDRESS`는 요청을 받을 네트워크 주소를 바꿉니다.

## 테스트와 실행 파일

```bash
./gradlew test bootJar
java -jar build/libs/finadmin-0.0.1-SNAPSHOT.jar
```

첫 줄은 HTTP 응답 테스트를 실행하고 실행 가능한 JAR을 만듭니다. 두 번째 줄은 그 파일로 앱을 켭니다.
`bootRun`과 JAR 실행은 같은 앱을 켜는 두 가지 방법입니다. 같은 포트에서 동시에 실행하지 않습니다.

## FinAccess와의 관계와 다음 단계

FinAccess는 회사·계좌·이체 기능을 담당하고, FinAdmin은 관리자 API를 연습하는 별도 앱입니다.
서로 다른 프로젝트이며 각각 따로 시작하고 종료합니다. 지금은 두 앱 사이에 API 호출이나 DB 공유가 없습니다.

| 앱 | 기본 포트 | 실행 의존성 |
| --- | --- | --- |
| FinAccess | 8080 | 기존 PostgreSQL 설정 필요 |
| FinAdmin | 8081 | Java 21, DB 불필요 |

이후 Keycloak과 Apache APISIX를 연결할 때는 다음 흐름을 구현할 예정입니다.

1. Keycloak에서 발급한 액세스 토큰을 API 요청에 포함합니다.
2. Apache APISIX에서 토큰을 검증하고 대상 백엔드까지 전달합니다.
3. FinAccess와 FinAdmin이 각각 토큰을 다시 검증하는 Resource Server가 됩니다.
4. FinAdmin은 관리자 역할이 있는 요청에만 관리자 데이터를 반환합니다.

위 인증 흐름은 아직 구현하지 않았습니다. 이번 단계에는 프런트 화면, Keycloak, APISIX 설치와 연동을 포함하지 않습니다.
SSO 시연, Istio, 대규모 부하 테스트도 현재 범위에 포함하지 않습니다.
