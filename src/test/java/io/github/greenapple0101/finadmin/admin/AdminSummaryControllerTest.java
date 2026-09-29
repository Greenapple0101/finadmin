// [이 파일이 하는 일] 관리자 샘플 API의 주소와 JSON 응답이 약속대로 연결되는지 확인합니다.
// MockMvc로 GET 요청 → 200 확인 → JSON 형식과 값 확인 순서입니다.
// 아직 권한 검사 기능이 없으므로 '관리자만 접근한다'는 보안을 검증하는 테스트는 아닙니다.
// 이후 JWT를 연결할 때 일반 사용자 거절·관리자 허용 같은 검사를 추가합니다.

package io.github.greenapple0101.finadmin.admin;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// 이 Controller와 웹 요청 처리에 필요한 Spring 설정만 준비합니다. 실제 포트는 열지 않습니다.
@WebMvcTest(AdminSummaryController.class)
class AdminSummaryControllerTest {

    // Spring이 준비한 MockMvc를 받아 사용합니다. HTTP 요청 처리 과정을 시험하는 도구입니다.
    @Autowired
    private MockMvc mockMvc;

    // JUnit이 @Test를 보고 실행합니다. 오류가 생기면 throws Exception을 통해 테스트에 알립니다.
    @Test
    void returnsClearlyMarkedSampleSummaryAsJson() throws Exception {
        mockMvc.perform(get("/api/admin/summary"))
                // 200: 요청 정상 처리. JSON: 응답 데이터 형식.
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                // sampleData 표시까지 검사해서 고정 예시를 실제 통계로 오해하지 않게 합니다.
                // 세 개의 큰따옴표는 여러 줄 글자를 적는 Java 문법입니다.
                .andExpect(content().json("""
                        {
                          "application": "finadmin",
                          "sampleData": true,
                          "pendingTransferCount": 3,
                          "completedTransferCount": 7
                        }
                        """));
    }
}
