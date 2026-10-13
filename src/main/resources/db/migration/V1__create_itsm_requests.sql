-- FinAdmin 전용 DB의 첫 구조입니다. 기존 금융 DB와 테이블을 공유하지 않습니다.
CREATE TABLE itsm_companies (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);
CREATE TABLE itsm_users (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES itsm_companies(id),
    display_name VARCHAR(100) NOT NULL,
    identity_issuer VARCHAR(512) NOT NULL,
    identity_subject VARCHAR(255) NOT NULL,
    CONSTRAINT uk_itsm_identity UNIQUE(identity_issuer, identity_subject)
);
CREATE INDEX idx_itsm_users_company ON itsm_users(company_id);

CREATE TABLE service_requests (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES itsm_companies(id),
    requester_id UUID NOT NULL REFERENCES itsm_users(id),
    service_name VARCHAR(100) NOT NULL CHECK(char_length(trim(service_name)) > 0),
    reason VARCHAR(1000) NOT NULL CHECK(char_length(trim(reason)) > 0),
    status VARCHAR(20) NOT NULL CHECK(status IN ('REQUESTED', 'APPROVED', 'COMPLETED')),
    created_at TIMESTAMPTZ NOT NULL,
    approver_id UUID REFERENCES itsm_users(id),
    approved_at TIMESTAMPTZ,
    completed_by UUID REFERENCES itsm_users(id),
    completed_at TIMESTAMPTZ,
    completion_note VARCHAR(1000),
    -- 상태 이름뿐 아니라 그 상태에 필요한 처리자·시각도 함께 저장해야 합니다.
    CONSTRAINT ck_service_request_history CHECK (
        (status = 'REQUESTED' AND approver_id IS NULL AND approved_at IS NULL
            AND completed_by IS NULL AND completed_at IS NULL AND completion_note IS NULL)
        OR (status = 'APPROVED' AND approver_id IS NOT NULL AND approved_at IS NOT NULL
            AND completed_by IS NULL AND completed_at IS NULL AND completion_note IS NULL)
        OR (status = 'COMPLETED' AND approver_id IS NOT NULL AND approved_at IS NOT NULL
            AND completed_by IS NOT NULL AND completed_at IS NOT NULL
            AND completion_note IS NOT NULL AND char_length(trim(completion_note)) > 0)
    ),
    CONSTRAINT ck_service_request_self_approval CHECK(requester_id <> approver_id)
);
CREATE INDEX idx_service_requests_company ON service_requests(company_id, created_at DESC, id DESC);
CREATE INDEX idx_service_requests_requester ON service_requests(company_id, requester_id, created_at DESC, id DESC);
