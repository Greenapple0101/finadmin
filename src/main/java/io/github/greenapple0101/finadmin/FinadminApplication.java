// [이 파일이 하는 일] FinAdmin 앱을 켜는 시작점입니다.
// main 실행 → Spring 설정 준비 → Controller 객체 준비 → 웹 서버 시작 순서로 진행합니다.
// 앱이 켜진 뒤 들어오는 요청은 Controller가 받습니다. 요청마다 main이 다시 실행되지는 않습니다.
// FinAccess와 별도로 실행하므로 FinAccess를 꺼도 이 앱은 계속 동작할 수 있습니다.
//
// [먼저 알면 좋은 말]
// 객체: 프로그램 안에서 정보나 동작을 담아 사용하는 것입니다.
// Bean(빈): Spring이 만들고 관리하는 객체입니다. Controller도 Bean으로 준비됩니다.
// package는 관련 코드를 모아 두는 주소이지, 실행 중인 서버를 뜻하지는 않습니다.

package io.github.greenapple0101.finadmin;

// import를 적으면 라이브러리 클래스의 긴 주소를 매번 쓰지 않고 짧은 이름으로 부를 수 있습니다.
// 라이브러리를 실제로 내려받는 일은 build.gradle을 읽는 Gradle이 맡습니다.
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

// 이 클래스를 기준으로 Spring Boot의 기본 설정을 준비하라는 표시입니다.
// 현재 package 아래에서 Controller 같은 표시가 붙은 클래스를 찾습니다.
// 설치된 웹 라이브러리에 맞춰 웹 서버와 요청·응답 처리 도구도 준비합니다.
@SpringBootApplication
public class FinadminApplication {

    // main은 Java 프로그램이 실행을 시작하는 메서드(동작)입니다.
    // public: 밖에서 호출 가능 / static: 이 클래스의 객체를 먼저 만들지 않아도 호출 가능.
    // void: 돌려주는 값 없음 / String[] args: 실행할 때 전달한 글자 목록.
    public static void main(String[] args) {
        // .class는 앱 설정의 기준이 되는 클래스 정보입니다.
        // args로 --server.port=8082 같은 실행 옵션을 Spring에 전달할 수 있습니다.
        SpringApplication.run(FinadminApplication.class, args);
    }
}
