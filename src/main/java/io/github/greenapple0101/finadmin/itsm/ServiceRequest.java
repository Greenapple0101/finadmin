package io.github.greenapple0101.finadmin.itsm;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

// 서비스 이용 요청 한 건입니다. 요청 → 승인 → 완료 순서와 각 단계의 처리 기록을 보관합니다.
// 계정이나 서버를 실제로 발급하는 기능은 없습니다. 담당자가 수행한 처리 결과를 기록합니다.
@Entity
@Table(name = "service_requests")
public class ServiceRequest {
    public enum Status { REQUESTED, APPROVED, COMPLETED }

    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;
    // 회사·요청자 ID는 서버가 정하고, 만든 뒤 수정하는 setter는 제공하지 않습니다.
    @Column(name = "company_id", nullable = false, updatable = false) private UUID companyId;
    @Column(name = "requester_id", nullable = false, updatable = false) private UUID requesterId;
    @Column(name = "service_name", nullable = false, length = 100) private String serviceName;
    @Column(nullable = false, length = 1000) private String reason;
    // EnumType.STRING은 상태를 숫자 순번이 아니라 REQUESTED 같은 이름으로 저장합니다.
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 20) private Status status;
    @Column(name = "created_at", nullable = false, updatable = false) private Instant createdAt;
    @Column(name = "approver_id") private UUID approverId;
    @Column(name = "approved_at") private Instant approvedAt;
    @Column(name = "completed_by") private UUID completedBy;
    @Column(name = "completed_at") private Instant completedAt;
    @Column(name = "completion_note", length = 1000) private String completionNote;

    protected ServiceRequest() {}
    public ServiceRequest(UUID companyId, UUID requesterId, String serviceName, String reason) {
        this.companyId = companyId;
        this.requesterId = requesterId;
        this.serviceName = requiredText(serviceName, 100, "서비스명");
        this.reason = requiredText(reason, 1000, "요청 사유");
        this.status = Status.REQUESTED;
        this.createdAt = Instant.now();
    }

    // 회사·역할·자기 승인 검사는 Service가 먼저 합니다. 이 객체는 상태 순서를 지킵니다.
    public void approve(UUID actorId) {
        requireStatus(Status.REQUESTED);
        this.approverId = actorId;
        this.approvedAt = Instant.now();
        this.status = Status.APPROVED;
    }

    public void complete(UUID actorId, String note) {
        requireStatus(Status.APPROVED);
        // 빈 결과로 완료 처리되지 않도록 값을 먼저 검사하고, 통과한 뒤 상태를 바꿉니다.
        this.completionNote = requiredText(note, 1000, "처리 결과");
        this.completedBy = actorId;
        this.completedAt = Instant.now();
        this.status = Status.COMPLETED;
    }

    private void requireStatus(Status expected) {
        if (status != expected) throw new IllegalStateException("현재 상태에서는 처리할 수 없습니다. 새로 조회하세요.");
    }
    private static String requiredText(String value, int max, String label) {
        if (value == null || value.isBlank() || value.length() > max)
            throw new IllegalArgumentException(label + "은(는) 비어 있을 수 없고 " + max + "자 이하여야 합니다.");
        return value.strip();
    }
    public UUID getId() { return id; }
    public UUID getCompanyId() { return companyId; }
    public UUID getRequesterId() { return requesterId; }
    public String getServiceName() { return serviceName; }
    public String getReason() { return reason; }
    public Status getStatus() { return status; }
    public Instant getCreatedAt() { return createdAt; }
    public UUID getApproverId() { return approverId; }
    public Instant getApprovedAt() { return approvedAt; }
    public UUID getCompletedBy() { return completedBy; }
    public Instant getCompletedAt() { return completedAt; }
    public String getCompletionNote() { return completionNote; }
}
