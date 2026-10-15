package io.github.greenapple0101.finadmin.oauth;

import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

// 각 URL은 HTTP 응답을 비교하기 위한 작은 실습입니다. 실제 금융·ITSM 업무는 포함하지 않습니다.
// 역할 검사는 SecurityConfig에서 먼저 끝납니다. 이 코드는 통과한 요청만 처리합니다.
@RestController
public class AdminController {
    @GetMapping("/api/admin/me")
    public Map<String, Object> me(@AuthenticationPrincipal Jwt jwt) {
        // sub는 검증된 토큰의 사용자 번호입니다. 요청자가 보내는 사용자 ID 헤더를 믿지 않습니다.
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("application", "FinAdmin");
        body.put("subject", jwt.getSubject());
        body.put("department", jwt.getClaimAsString("department"));
        body.put("message", "ADMIN 권한으로 접근했습니다.");
        return body;
    }

    @GetMapping("/api/admin/greeting")
    public ResponseEntity<Map<String, String>> greeting(@RequestParam(defaultValue = "") String name) {
        // 이름을 빼면 입력 오류 400, 이름을 넣으면 정상 200입니다. DB 저장은 하지 않습니다.
        if (name.isBlank() || name.length() > 40) {
            return ResponseEntity.badRequest().body(Map.of("message", "name은 1~40자로 입력하세요."));
        }
        return ResponseEntity.ok(Map.of("message", name + "님, 안녕하세요."));
    }

    @GetMapping("/api/admin/demo-error")
    public void demoError() {
        // 500 응답을 재현하는 로컬 발표 전용 API입니다. 운영 기능으로 사용하지 않습니다.
        throw new DemoException();
    }

    @org.springframework.web.bind.annotation.ExceptionHandler(DemoException.class)
    public ResponseEntity<Map<String, String>> handleDemoError() {
        // 예상한 시연 예외만 처리합니다. 내부 예외 내용이나 비밀번호는 응답에 넣지 않습니다.
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(Map.of("message", "시연용 서버 오류입니다.", "source", "FinAdmin"));
    }

    private static class DemoException extends RuntimeException { }
}
