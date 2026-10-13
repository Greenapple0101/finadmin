package io.github.greenapple0101.finadmin.itsm;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;
import java.util.UUID;

// 메서드 이름의 IssuerAndSubject는 두 값이 모두 같은 직원을 찾는다는 뜻입니다.
// username만 비교하지 않으므로 이름 변경이나 서로 다른 인증 서버의 동명이인을 구분합니다.
public interface ItsmUserRepository extends JpaRepository<ItsmUser, UUID> {
    Optional<ItsmUser> findByIdentityIssuerAndIdentitySubject(String issuer, String subject);
}
