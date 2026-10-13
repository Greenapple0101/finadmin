package io.github.greenapple0101.finadmin.itsm;

import org.springframework.http.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.UUID;

// HTTP 입구입니다. Spring Security가 JWT·앱 역할을 검사한 뒤 이 메서드들이 실행됩니다.
// 요청 본문에는 회사 ID나 수행자를 받지 않습니다. 매번 검증된 로그인 신원을 DB와 연결합니다.
@RestController
@RequestMapping("/api/itsm")
public class ServiceRequestController {
    private final CurrentItsmUser currentUser;
    private final ServiceRequestService service;
    public ServiceRequestController(CurrentItsmUser currentUser, ServiceRequestService service) {
        this.currentUser = currentUser; this.service = service;
    }
    @GetMapping("/me")
    public CurrentItsmUser.Actor me(JwtAuthenticationToken auth) { return currentUser.resolve(auth); }
    @PostMapping("/requests")
    public ResponseEntity<ServiceRequestService.Details> create(@RequestBody CreateRequest input, JwtAuthenticationToken auth) {
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(currentUser.resolve(auth), input.serviceName(), input.reason()));
    }
    @GetMapping("/requests")
    public ServiceRequestService.RequestPage list(@RequestParam(defaultValue = "0") int page, JwtAuthenticationToken auth) {
        return service.list(currentUser.resolve(auth), page);
    }
    @GetMapping("/requests/{id}")
    public ServiceRequestService.Details get(@PathVariable UUID id, JwtAuthenticationToken auth) {
        return service.get(currentUser.resolve(auth), id);
    }
    @PostMapping("/requests/{id}/approve")
    public ServiceRequestService.Details approve(@PathVariable UUID id, JwtAuthenticationToken auth) {
        return service.approve(currentUser.resolve(auth), id);
    }
    @PostMapping("/requests/{id}/complete")
    public ServiceRequestService.Details complete(@PathVariable UUID id, @RequestBody Completion input, JwtAuthenticationToken auth) {
        return service.complete(currentUser.resolve(auth), id, input.note());
    }
    @GetMapping("/summary")
    public ServiceRequestService.Summary summary(JwtAuthenticationToken auth) { return service.summary(currentUser.resolve(auth)); }

    // 상태 충돌은 409, 잘못된 입력은 400, 소속·자기 승인 위반은 403으로 설명합니다.
    @ExceptionHandler(IllegalArgumentException.class)
    public ProblemDetail invalid(IllegalArgumentException e) { return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage()); }
    @ExceptionHandler(IllegalStateException.class)
    public ProblemDetail conflict(IllegalStateException e) { return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage()); }
    @ExceptionHandler(ResponseStatusException.class)
    public ProblemDetail denied(ResponseStatusException e) { return ProblemDetail.forStatusAndDetail(e.getStatusCode(), e.getReason()); }
    public record CreateRequest(String serviceName, String reason) {}
    public record Completion(String note) {}
}
