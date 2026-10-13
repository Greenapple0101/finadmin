// [이 파일이 하는 일] /api/hello 요청에 FinAdmin의 인사말이 JSON으로 오는지 검사합니다.
// 준비된 MockMvc로 요청 보내기 → 상태 코드 확인 → 응답 형식과 내용 확인 순서입니다.
// 실제 포트를 열지 않고 Spring의 웹 요청 처리 과정을 시험합니다.

package io.github.greenapple0101.finadmin.hello;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import io.github.greenapple0101.finadmin.security.SecurityConfiguration;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

// static import는 get이나 status 같은 도구의 메서드를 짧은 이름으로 쓰게 합니다.
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// 전체 앱의 보안 설정도 준비해서 공개 API가 토큰 없이 호출되는지 확인합니다.
// 이 요청에는 JWT가 없으므로 Keycloak의 공개 키를 받아 올 필요도 없습니다.
@WebMvcTest(HelloController.class)
@Import(SecurityConfiguration.class)
class HelloControllerTest {

    // Spring이 준비한 테스트 도구를 넣어 줍니다. 여기서 직접 new로 만들 필요가 없습니다.
    @Autowired
    private MockMvc mockMvc;

    // @Test가 붙은 메서드는 JUnit이 테스트로 실행합니다.
    // throws Exception은 요청 처리 중 오류가 나면 테스트 실행 도구에 알릴 수 있다는 선언입니다.
    @Test
    void returnsFinadminGreetingAsJson() throws Exception {
        mockMvc.perform(get("/api/hello"))
                // 200은 요청을 정상 처리했다는 HTTP 상태 코드입니다.
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                // JSON 내용으로 비교하므로 공백이나 줄바꿈 차이는 실패 원인이 아닙니다.
                .andExpect(content().json("""
                        {"message":"Hello, FinAdmin!"}
                        """));
    }
}
