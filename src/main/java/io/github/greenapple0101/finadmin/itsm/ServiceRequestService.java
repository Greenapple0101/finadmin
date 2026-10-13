package io.github.greenapple0101.finadmin.itsm;

import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import static io.github.greenapple0101.finadmin.itsm.ServiceRequest.Status.*;

// 역할은 "무엇을 할 수 있나", 회사·요청자는 "어느 데이터에 할 수 있나"를 정합니다.
// Gateway는 역할을 먼저 검사하지만, 아래 업무 DB 규칙은 이 앱이 직접 검사합니다.
@Service
public class ServiceRequestService {
    private final ServiceRequestRepository requests;
    public ServiceRequestService(ServiceRequestRepository requests) { this.requests = requests; }

    @Transactional
    public Details create(CurrentItsmUser.Actor actor, String serviceName, String reason) {
        ServiceRequest request = new ServiceRequest(actor.companyId(), actor.userId(), serviceName, reason);
        return details(requests.save(request));
    }

    @Transactional(readOnly = true)
    public RequestPage list(CurrentItsmUser.Actor actor, int page) {
        if (page < 0 || page > 10000) throw new IllegalArgumentException("페이지는 0~10000 사이여야 합니다.");
        var paging = PageRequest.of(page, 20, Sort.by(Sort.Direction.DESC, "createdAt", "id"));
        var found = actor.reviewer() || actor.operator()
                ? requests.findByCompanyId(actor.companyId(), paging)
                : requests.findByCompanyIdAndRequesterId(actor.companyId(), actor.userId(), paging);
        return new RequestPage(found.map(this::details).getContent(), page, found.hasNext());
    }

    @Transactional(readOnly = true)
    public Details get(CurrentItsmUser.Actor actor, UUID id) {
        ServiceRequest request = requests.findById(id).orElseThrow(this::notFound);
        checkCompany(actor, request);
        if (!actor.reviewer() && !actor.operator() && !actor.userId().equals(request.getRequesterId()))
            throw forbidden("일반 직원은 본인이 등록한 요청만 조회할 수 있습니다.");
        return details(request);
    }

    @Transactional
    public Details approve(CurrentItsmUser.Actor actor, UUID id) {
        if (!actor.reviewer()) throw forbidden("승인자 역할이 필요합니다.");
        ServiceRequest request = requests.findLockedById(id).orElseThrow(this::notFound);
        checkCompany(actor, request);
        if (actor.userId().equals(request.getRequesterId())) throw forbidden("자신의 요청은 승인할 수 없습니다.");
        request.approve(actor.userId());
        // JPA 변경 감지가 상태·승인자·시각을 트랜잭션 끝에서 함께 저장합니다.
        return details(request);
    }

    @Transactional
    public Details complete(CurrentItsmUser.Actor actor, UUID id, String note) {
        if (!actor.operator()) throw forbidden("처리 담당자(admin) 역할이 필요합니다.");
        ServiceRequest request = requests.findLockedById(id).orElseThrow(this::notFound);
        checkCompany(actor, request);
        request.complete(actor.userId(), note);
        return details(request);
    }

    @Transactional(readOnly = true)
    public Summary summary(CurrentItsmUser.Actor actor) {
        if (!actor.operator()) throw forbidden("처리 담당자(admin) 역할이 필요합니다.");
        return new Summary(actor.companyId(), false,
                requests.countByCompanyIdAndStatus(actor.companyId(), REQUESTED),
                requests.countByCompanyIdAndStatus(actor.companyId(), APPROVED),
                requests.countByCompanyIdAndStatus(actor.companyId(), COMPLETED));
    }

    private void checkCompany(CurrentItsmUser.Actor actor, ServiceRequest request) {
        // ITSM의 admin도 자기 회사만 다룹니다. FinAccess 회사 조회의 관리자 예외와 별개입니다.
        if (!actor.companyId().equals(request.getCompanyId())) throw forbidden("다른 회사의 요청에는 접근할 수 없습니다.");
    }
    private ResponseStatusException forbidden(String message) { return new ResponseStatusException(HttpStatus.FORBIDDEN, message); }
    private ResponseStatusException notFound() { return new ResponseStatusException(HttpStatus.NOT_FOUND, "요청을 찾을 수 없습니다."); }
    private Details details(ServiceRequest r) {
        return new Details(r.getId(), r.getCompanyId(), r.getRequesterId(), r.getServiceName(), r.getReason(),
                r.getStatus(), r.getCreatedAt(), r.getApproverId(), r.getApprovedAt(),
                r.getCompletedBy(), r.getCompletedAt(), r.getCompletionNote());
    }

    // 엔티티를 직접 응답하지 않고 필요한 데이터만 담습니다. 비밀번호·JWT 원문은 없습니다.
    public record Details(UUID id, UUID companyId, UUID requesterId, String serviceName, String reason,
                          ServiceRequest.Status status, Instant createdAt, UUID approverId, Instant approvedAt,
                          UUID completedBy, Instant completedAt, String completionNote) {}
    public record RequestPage(List<Details> items, int page, boolean hasNext) {}
    public record Summary(UUID companyId, boolean sampleData, long requested, long approved, long completed) {}
}
