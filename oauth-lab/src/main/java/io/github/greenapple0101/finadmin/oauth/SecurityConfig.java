package io.github.greenapple0101.finadmin.oauth;

import jakarta.servlet.DispatcherType;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Map;
import java.util.List;
import java.time.Duration;
import java.time.Instant;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtIssuerValidator;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.StaticHeadersWriter;

// 요청이 Controller에 도착하기 전에 실행할 검사 순서를 정합니다.
@Configuration
public class SecurityConfig {
    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(this::readRoles);

        http
            // 로그인 쿠키로 API를 허용하지 않고, 요청마다 Bearer 토큰을 받습니다.
            // 이런 API에서는 CSRF용 쿠키/폼 토큰 대신 JWT 검증으로 요청자를 확인합니다.
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .headers(headers -> headers.addHeaderWriter(new StaticHeadersWriter("X-Finlab-Backend", "finadmin")))
            .authorizeHttpRequests(authorize -> authorize
                // 오류를 JSON으로 만드는 내부 처리까지 다시 막지 않도록 합니다.
                .dispatcherTypeMatchers(DispatcherType.ERROR, DispatcherType.FORWARD).permitAll()
                // Gateway를 거쳤어도 여기서 다시 JWT와 ADMIN 역할을 검사합니다.
                .requestMatchers(HttpMethod.GET, "/api/admin/**").hasRole("ADMIN")
                .anyRequest().denyAll())
            // application.properties의 발급자·대상·공개 키 설정으로 JWT를 먼저 검증합니다.
            // 서명이 틀리면 401로 끝납니다. 아래의 역할 변환도 진행하지 않습니다.
            .oauth2ResourceServer(resource -> resource.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)));
        return http.build();
    }

    // 두 서버 모두 자기 힘으로 서명·발급자·대상·시간을 확인합니다.
    // 같은 Mac에서 시연하므로 시계 오차 허용은 0초입니다. 운영에서는 서버 시간 동기화와 함께 정합니다.
    @Bean
    JwtDecoder jwtDecoder(
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuer,
            @Value("${spring.security.oauth2.resourceserver.jwt.jwk-set-uri}") String jwks) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withJwkSetUri(jwks).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
            new JwtTimestampValidator(Duration.ZERO),
            new JwtIssuerValidator(issuer),
            new JwtClaimValidator<List<String>>("aud", value -> value != null && value.contains("oauth-api")),
            new JwtClaimValidator<Instant>("exp", value -> value != null),
            new JwtClaimValidator<String>("sub", value -> value != null && !value.isBlank())));
        return decoder;
    }

    // 이 메서드에는 검증을 마친 JWT만 들어옵니다. 단순히 디코딩한 내용을 믿는 것이 아닙니다.
    // Keycloak의 resource_access → oauth-api → roles 배열을 Spring 권한으로 바꿉니다.
    private Collection<GrantedAuthority> readRoles(Jwt jwt) {
        Collection<GrantedAuthority> authorities = new ArrayList<>();
        Object resources = jwt.getClaim("resource_access");
        if (!(resources instanceof Map<?, ?> resourceMap)) return authorities;
        Object api = resourceMap.get("oauth-api");
        if (!(api instanceof Map<?, ?> apiMap)) return authorities;
        Object roles = apiMap.get("roles");
        if (!(roles instanceof Collection<?> roleList)) return authorities;

        for (Object role : roleList) {
            // 업무 역할은 정확히 USER와 ADMIN 두 개만 사용합니다.
            if ("USER".equals(role) || "ADMIN".equals(role)) {
                // hasRole("USER")가 실제로 찾는 이름은 ROLE_USER입니다.
                authorities.add(new SimpleGrantedAuthority("ROLE_" + role));
            }
        }
        // 역할이 없으면 빈 목록입니다. hasRole 검사를 통과하지 못해 403이 됩니다.
        return authorities;
    }
}
