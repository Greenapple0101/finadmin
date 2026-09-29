// [이 파일이 하는 일] 관리자 화면을 흉내 내는 요약 데이터를 JSON으로 보냅니다.
// GET /api/admin/summary 요청 → summary 실행 → AdminSummary 생성 → JSON 응답 순서입니다.
// 현재는 고정된 샘플 값만 사용합니다. FinAccess나 DB에서 실제 건수를 읽는 기능은 없습니다.
// 따라서 FinAccess에서 이체를 실행해도 아래 숫자는 바뀌지 않습니다.
//
// [인증·인가를 공부할 때 기억할 점]
// 주소에 admin이라는 글자가 들어 있어도 관리자만 접근할 수 있게 되는 것은 아닙니다.
// 지금은 이 앱에 접속할 수 있는 누구나 응답을 받을 수 있습니다.
// 이후에는 Keycloak의 토큰을 검증하고 관리자 역할까지 확인한 뒤 응답하도록 만들 예정입니다.

package io.github.greenapple0101.finadmin.admin;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

// Spring이 이 클래스의 객체를 준비하고, 웹 요청에 대한 반환값을 응답 본문으로 보내게 합니다.
// 반환하는 record는 Spring이 연결한 JSON 변환 도구를 거쳐 이름과 값으로 표현됩니다.
@RestController
public class AdminSummaryController {

    // 이 주소로 GET 요청이 오면 실행합니다. GET은 정보를 달라는 HTTP 요청 방식입니다.
    // 이 표시에는 로그인 확인이나 권한 검사 기능이 없습니다.
    @GetMapping("/api/admin/summary")
    public AdminSummary summary() {
        // new는 아래 record 모양에 맞는 데이터 묶음을 하나 만듭니다.
        // 괄호 안 값은 record의 선언 순서인 앱 이름, 샘플 여부, 대기 건수, 완료 건수에 대응합니다.
        // true는 '맞다'라는 뜻입니다. 실제 통계로 오해하지 않도록 sampleData를 true로 보냅니다.
        // 3과 7은 실습을 위해 정한 숫자입니다. 합계 계산이나 외부 호출은 하지 않습니다.
        return new AdminSummary("finadmin", true, 3, 7);
    }

    // record는 응답으로 전달할 값들을 하나로 묶는 Java 문법입니다. DB 테이블을 만들지 않습니다.
    // String은 글자값, boolean은 true/false, int는 정수입니다.
    // application: 응답을 만든 앱 / sampleData: 샘플 데이터인지 여부.
    // pendingTransferCount: 대기 이체 건수 예시 / completedTransferCount: 완료 이체 건수 예시.
    // 이 응답을 쓰는 곳이 여기뿐이라 Controller 안에 둡니다. 중첩된 별도 서버라는 뜻은 아닙니다.
    public record AdminSummary(
            String application,
            boolean sampleData,
            int pendingTransferCount,
            int completedTransferCount
    ) {
    }
}
