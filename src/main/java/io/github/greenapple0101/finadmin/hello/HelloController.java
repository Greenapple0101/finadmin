// [이 파일이 하는 일] GET /api/hello 요청에 이 앱의 인사말을 보냅니다.
// 요청이 들어옴 → hello 실행 → HelloResponse 생성 → JSON 응답 순서입니다.
// FinAccess의 인사말과 구분해서 어느 앱에 요청했는지 확인할 수 있습니다.
// DB 조회나 계산이 없으므로 지금은 Service나 Repository를 따로 만들지 않습니다.

package io.github.greenapple0101.finadmin.hello;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

// Spring에게 웹 요청을 받고, 반환한 값을 응답 본문으로 보내는 클래스라고 알려줍니다.
// Java 객체를 JSON 글자 형식으로 바꾸는 일은 Spring이 연결한 Jackson 라이브러리가 맡습니다.
@RestController
public class HelloController {

    // GET은 정보를 달라는 요청 방식입니다. /api/hello로 GET 요청이 오면 이 메서드를 실행합니다.
    @GetMapping("/api/hello")
    public HelloResponse hello() {
        // new는 응답 객체를 만들고, return은 그 객체를 호출한 쪽으로 돌려줍니다.
        // 뒤이어 Spring이 응답을 보냅니다. 여기서 화면의 HTML을 만드는 것은 아닙니다.
        return new HelloResponse("Hello, FinAdmin!");
    }

    // record는 전달할 데이터의 모양을 짧게 적는 Java 문법입니다.
    // String message는 message라는 이름으로 글자값 하나를 담겠다는 뜻입니다.
    // JSON으로 바뀌면 {"message":"Hello, FinAdmin!"}이 됩니다. DB 테이블은 만들어지지 않습니다.
    public record HelloResponse(String message) {
    }
}
