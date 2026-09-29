# FinAdmin

[FinAccess](https://github.com/Greenapple0101/finaccess)와 별도로 실행하는 Spring Boot 관리자 API 학습용 앱입니다.
첫 단계에서는 앱의 시작점과 HTTP 요청·응답을 준비합니다.

## 현재 범위

- Java 21, Spring Boot 4.1.1, Gradle Wrapper 9.7.1
- 기본 접속 주소: `http://127.0.0.1:8081`
- DB, Docker, FinAccess 없이 실행할 수 있습니다.
- 아직 로그인과 JWT 검증, 역할 검사가 없습니다. 내 컴퓨터에서 실행하는 실습용 앱입니다.

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

종료하려면 실행 중인 터미널에서 `Ctrl+C`를 누릅니다.
8081번 포트를 다른 앱이 사용 중이면 `./gradlew bootRun --args='--server.port=8082'`로 바꾸고 호출 주소도 바꿉니다.

## 테스트와 실행 파일

```bash
./gradlew test bootJar
java -jar build/libs/finadmin-0.0.1-SNAPSHOT.jar
```

첫 줄은 HTTP 응답 테스트를 실행하고 실행 가능한 JAR을 만듭니다. 두 번째 줄은 그 파일로 앱을 켭니다.
`bootRun`과 JAR 실행은 같은 앱을 켜는 두 가지 방법입니다. 같은 포트에서 동시에 실행하지 않습니다.
