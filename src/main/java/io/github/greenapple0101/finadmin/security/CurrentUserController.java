// [이 파일이 하는 일] FinAdmin이 토큰으로 확인한 사용자 정보를 화면에 보여줍니다.
// 보안 설정에서 JWT 검증 성공 → 검증된 사용자 정보를 받음 → 필요한 값만 JSON으로 응답합니다.
// 화면에서 두 백엔드가 같은 사용자를 알아봤는지 비교할 수 있습니다. 토큰 원문은 반환하지 않습니다.

package io.github.greenapple0101.finadmin.security;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class CurrentUserController {

    @GetMapping("/api/me")
    public CurrentUser me(@AuthenticationPrincipal Jwt jwt, Authentication authentication) {
        // @AuthenticationPrincipal은 요청자가 직접 적은 JSON이 아니라 검증을 통과한 신원을 받습니다.
        // Authentication에는 그 신원과 Spring이 인정한 권한이 함께 들어 있습니다.
        List<String> roles = authentication.getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .filter(authority -> authority.startsWith("ROLE_"))
                .map(authority -> authority.substring("ROLE_".length()))
                .distinct()
                .sorted()
                .toList();

        return new CurrentUser("finadmin", jwt.getSubject(), jwt.getIssuer().toString(), roles);
    }

    // subject는 Keycloak 사용자 ID입니다. 이름이 바뀌어도 사용자를 구분할 때 쓸 수 있습니다.
    // 서로 다른 발급자의 사용자를 혼동하지 않도록 issuer도 함께 표시합니다.
    public record CurrentUser(String application, String subject, String issuer, List<String> roles) {
    }
}
