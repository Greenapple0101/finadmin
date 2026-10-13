package io.github.greenapple0101.finadmin.itsm;

import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import java.util.UUID;

@Service
public class CurrentItsmUser {
    private final ItsmUserRepository users;
    public CurrentItsmUser(ItsmUserRepository users) { this.users = users; }

    // JWT 검증을 통과했다고 모든 업무 앱의 직원이 되는 것은 아닙니다.
    // ITSM에 등록된 신원만 회사·요청 데이터와 연결합니다. 헤더나 입력 본문의 회사 ID는 읽지 않습니다.
    @Transactional(readOnly = true)
    public Actor resolve(JwtAuthenticationToken authentication) {
        var jwt = authentication.getToken();
        ItsmUser user = users.findByIdentityIssuerAndIdentitySubject(jwt.getIssuer().toString(), jwt.getSubject())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "ITSM 직원으로 등록되지 않았습니다."));
        boolean admin = hasRole(authentication, "admin");
        return new Actor(user.getId(), user.getCompany().getId(), user.getCompany().getName(),
                user.getDisplayName(), admin || hasRole(authentication, "approver"), admin);
    }

    private boolean hasRole(JwtAuthenticationToken authentication, String role) {
        return authentication.getAuthorities().stream()
                .anyMatch(authority -> authority.getAuthority().equals("ROLE_" + role));
    }

    // record는 관련 값을 묶은 것입니다. 별도 서버가 아닙니다.
    // reviewer는 승인 가능 여부, operator는 완료 처리 가능 여부입니다. 서버가 JWT로 계산합니다.
    public record Actor(UUID userId, UUID companyId, String companyName, String displayName,
                        boolean reviewer, boolean operator) {}
}
