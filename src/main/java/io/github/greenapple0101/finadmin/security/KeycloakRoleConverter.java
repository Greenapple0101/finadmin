// [이 파일이 하는 일] 검증된 Keycloak 토큰에서 FinAdmin 역할만 골라 Spring 권한으로 바꿉니다.
// resource_access → finadmin-api → roles 안의 admin을 ROLE_admin으로 바꿉니다.
// 다른 앱의 admin이나 realm 전체 역할을 가져오면 의도하지 않은 관리자 권한이 생길 수 있습니다.

package io.github.greenapple0101.finadmin.security;

import org.springframework.core.convert.converter.Converter;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;

public class KeycloakRoleConverter implements Converter<Jwt, Collection<GrantedAuthority>> {

    @Override
    public Collection<GrantedAuthority> convert(Jwt jwt) {
        // Map은 '이름 → 값'으로 찾는 자료구조입니다. JWT의 JSON 객체를 이 모양으로 읽습니다.
        // 모양이 다르거나 값이 없으면 권한을 하나도 주지 않습니다. 예외로 서버가 죽게 하지 않습니다.
        Object resourceAccessClaim = jwt.getClaims().get("resource_access");
        if (!(resourceAccessClaim instanceof Map<?, ?> resourceAccess)) {
            return List.of();
        }

        Object clientAccessClaim = resourceAccess.get("finadmin-api");
        if (!(clientAccessClaim instanceof Map<?, ?> clientAccess)) {
            return List.of();
        }

        Object rolesClaim = clientAccess.get("roles");
        if (!(rolesClaim instanceof Collection<?> roles)) {
            return List.of();
        }

        List<GrantedAuthority> authorities = new ArrayList<>();
        for (Object roleValue : roles) {
            if (roleValue instanceof String role && !role.isBlank()) {
                authorities.add(new SimpleGrantedAuthority("ROLE_" + role));
            }
        }
        return authorities;
    }
}
