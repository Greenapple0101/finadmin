package io.github.greenapple0101.finadmin.itsm;

import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Slice;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.Optional;
import java.util.UUID;

public interface ServiceRequestRepository extends JpaRepository<ServiceRequest, UUID> {
    // DB 조회 자체에 회사·요청자 조건을 넣습니다. 전체 데이터를 가져온 뒤 화면에서 숨기지 않습니다.
    Slice<ServiceRequest> findByCompanyId(UUID companyId, Pageable page);
    Slice<ServiceRequest> findByCompanyIdAndRequesterId(UUID companyId, UUID requesterId, Pageable page);
    long countByCompanyIdAndStatus(UUID companyId, ServiceRequest.Status status);

    // 같은 요청을 동시에 승인해도 한 번만 바뀌도록, 처리 중에는 해당 행을 잠급니다.
    // 먼저 온 트랜잭션이 끝나면 다음 요청이 바뀐 상태를 읽고 409로 멈춥니다.
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select r from ServiceRequest r where r.id = :id")
    Optional<ServiceRequest> findLockedById(@Param("id") UUID id);
}
