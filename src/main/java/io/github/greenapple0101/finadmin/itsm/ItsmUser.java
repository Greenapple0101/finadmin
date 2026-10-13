package io.github.greenapple0101.finadmin.itsm;

import jakarta.persistence.*;
import java.util.UUID;

// 비밀번호는 저장하지 않습니다. Keycloak에서 확인한 신원과 ITSM 회사 소속만 연결합니다.
@Entity
@Table(name = "itsm_users")
public class ItsmUser {
    @Id private UUID id;
    // 여러 직원이 한 회사에 속합니다. LAZY는 회사 정보가 필요할 때 읽는다는 뜻입니다.
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "company_id", nullable = false)
    private ItsmCompany company;
    @Column(name = "display_name", nullable = false, length = 100)
    private String displayName;
    @Column(name = "identity_issuer", nullable = false, length = 512)
    private String identityIssuer;
    @Column(name = "identity_subject", nullable = false, length = 255)
    private String identitySubject;

    protected ItsmUser() {}
    public UUID getId() { return id; }
    public ItsmCompany getCompany() { return company; }
    public String getDisplayName() { return displayName; }
}
