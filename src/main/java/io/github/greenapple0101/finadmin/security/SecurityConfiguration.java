// [이 파일이 하는 일] Controller보다 먼저 실행되는 인증·인가 검사 규칙을 정합니다.
// 요청 → 토큰 검증 → 역할 확인 → 허용된 요청만 Controller 실행 순서입니다.
// Gateway가 먼저 검사했더라도 FinAdmin은 여기서 다시 검사합니다.
// X-User, X-Role 같은 요청 헤더를 믿지 않고 검증된 Bearer 토큰만 사용합니다.

package io.github.greenapple0101.finadmin.security;

import jakarta.servlet.DispatcherType;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationConverter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.StaticHeadersWriter;

import java.util.List;
import java.time.Instant;

// @Configuration은 'Spring이 사용할 설정을 모아 둔 클래스'라는 표시입니다.
@Configuration
public class SecurityConfiguration {

    // @Bean은 반환한 객체를 Spring이 보관하고 필요한 곳에 연결하도록 합니다.
    // HttpSecurity는 검사 규칙을 적는 도구이고, build()는 완성된 검사 흐름을 만듭니다.
    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        JwtAuthenticationConverter authenticationConverter = new JwtAuthenticationConverter();
        authenticationConverter.setJwtGrantedAuthoritiesConverter(new KeycloakRoleConverter());

        http
                // 이 응답이 FinAdmin까지 도착한 요청의 결과인지 구분하는 고정 이름표입니다.
                // 401·403에도 붙습니다. 요청 헤더를 복사하지 않으며, 인증 수단으로 쓰지 않습니다.
                .headers(headers -> headers.addHeaderWriter(new StaticHeadersWriter("X-Finlab-Backend", "finadmin")))
                // 이 API는 쿠키로 로그인하지 않고 매 요청의 Authorization 헤더로 인증합니다.
                // 브라우저가 자동 전송하는 로그인 쿠키를 쓰지 않으므로 여기서는 CSRF 검사를 끕니다.
                // 나중에 쿠키 로그인 기능을 넣는다면 이 선택도 다시 검토해야 합니다.
                .csrf(csrf -> csrf.disable())
                // 이전 요청의 로그인 상태를 세션에 저장하지 않습니다. 요청마다 토큰을 확인합니다.
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(authorize -> authorize
                        // 정상 처리 중 생긴 오류를 Spring의 오류 처리기로 넘길 수 있게 합니다.
                        // 외부에서 /error 주소로 처음 들어오는 요청을 공개한다는 뜻은 아닙니다.
                        .dispatcherTypeMatchers(DispatcherType.ERROR).permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/hello").permitAll()
                        // 이 앱의 역할이 없는 토큰은 로그인 자체가 유효해도 내 정보 API를 사용할 수 없습니다.
                        // 관리자는 user 역할이 없어도 접근할 수 있게 '둘 중 하나'를 확인합니다.
                        .requestMatchers(HttpMethod.GET, "/api/me").hasAnyRole("user", "admin")
                        // hasRole("admin")은 ROLE_admin이라는 권한이 있는지 확인합니다.
                        // 주소뿐 아니라 HTTP 메서드도 정합니다. 같은 주소의 POST까지 열지는 않습니다.
                        .requestMatchers(HttpMethod.GET, "/api/admin/summary").hasRole("admin")
                        // 새 API는 여기와 Gateway에 허용 규칙을 추가해야 사용할 수 있습니다.
                        .anyRequest().denyAll())
                // oauth2ResourceServer는 토큰을 발급하는 기능이 아니라 받은 토큰을 검사하는 기능입니다.
                .oauth2ResourceServer(resourceServer -> resourceServer
                        .jwt(jwt -> jwt.jwtAuthenticationConverter(authenticationConverter)));

        return http.build();
    }

    // @Value는 application.properties의 값을 가져옵니다. 비밀번호를 여기에 적지 않습니다.
    @Bean
    public JwtDecoder jwtDecoder(
            @Value("${spring.security.oauth2.resourceserver.jwt.issuer-uri}") String issuer,
            @Value("${spring.security.oauth2.resourceserver.jwt.jwk-set-uri}") String jwkSetUri,
            @Value("${finadmin.security.audience}") String audience
    ) {
        // NimbusJwtDecoder는 공개 키로 서명을 확인합니다. JWT 글자를 읽기만 하는 것이 아닙니다.
        // 기본 허용 서명 방식은 RS256입니다. JWKS 주소를 직접 주므로 앱 시작 때 Keycloak이 없어도 됩니다.
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();

        // 기본 검사에는 만료(exp), 사용 시작 시간(nbf), 발급자(iss) 등이 포함됩니다.
        // 서버 사이의 작은 시간 오차를 허용하므로 만료 즉시 1초 단위로 거절되는 것은 아닙니다.
        var issuerAndTimeValidator = JwtValidators.createDefaultWithIssuer(issuer);
        var audienceValidator = new JwtClaimValidator<List<String>>("aud",
                audiences -> audiences != null && audiences.contains(audience));
        // sub는 로그인 사용자의 식별자입니다. /api/me가 누구인지 답하려면 반드시 필요합니다.
        var subjectValidator = new JwtClaimValidator<String>("sub",
                subject -> subject != null && !subject.isBlank());
        // 만료 시간이 아예 없는 토큰도 받지 않습니다. 만료 시각이 지났는지는 위의 시간 검사가 맡습니다.
        var expirationValidator = new JwtClaimValidator<Instant>("exp", expiration -> expiration != null);

        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
                issuerAndTimeValidator, audienceValidator, subjectValidator, expirationValidator));
        return decoder;
    }
}
