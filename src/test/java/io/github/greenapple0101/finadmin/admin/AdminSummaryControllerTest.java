// [이 파일이 하는 일] 실제로 서명한 JWT를 요청에 넣어 FinAdmin의 인증·인가를 확인합니다.
// 가짜로 "로그인 성공"을 주입하지 않고 서명 → 공개 키 조회 → JWT 검증 → 역할 검사까지 실행합니다.
// 외부 Keycloak 없이도 검사할 수 있게 테스트 전용 공개 키 서버를 잠깐 띄웁니다.
// 개인 키는 테스트 중 메모리에만 만들고, 공개 키만 서버로 내보냅니다. 실제 사용자의 토큰은 쓰지 않습니다.

package io.github.greenapple0101.finadmin.admin;

import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// 전체 앱의 설정을 준비합니다. MockMvc는 실제 API 포트를 열지 않고 HTTP 처리 흐름을 실행합니다.
@SpringBootTest
@AutoConfigureMockMvc
class AdminSummaryControllerTest {

    private static final String ISSUER = "http://localhost:18080/realms/finlab";
    private static final RSAKey TRUSTED_KEY = createKey();
    private static final RSAKey UNTRUSTED_KEY = createKey();
    private static final HttpServer PUBLIC_KEY_SERVER = startPublicKeyServer();

    @Autowired
    private MockMvc mockMvc;

    // 테스트에서만 공개 키 주소를 작은 로컬 서버로 바꿉니다. 실제 JwtDecoder는 그대로 사용합니다.
    @DynamicPropertySource
    static void configurePublicKeys(DynamicPropertyRegistry registry) {
        registry.add("spring.security.oauth2.resourceserver.jwt.issuer-uri", () -> ISSUER);
        registry.add("spring.security.oauth2.resourceserver.jwt.jwk-set-uri",
                () -> "http://127.0.0.1:" + PUBLIC_KEY_SERVER.getAddress().getPort() + "/jwks");
        registry.add("finadmin.security.audience", () -> "finadmin-api");
    }

    @AfterAll
    static void closePublicKeyServer() {
        PUBLIC_KEY_SERVER.stop(0);
    }

    @Test
    void missingTokenIsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/admin/summary"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void invalidTokenTextIsUnauthorized() throws Exception {
        mockMvc.perform(get("/api/admin/summary")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void tokenSignedWithAnotherPrivateKeyIsUnauthorized() throws Exception {
        // kid(키 이름)가 같아도 개인 키가 다르면 서명 검사가 실패해야 합니다.
        String token = sign(claims("admin"), UNTRUSTED_KEY);
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void expiredTokenIsUnauthorized() throws Exception {
        // 기본 시간 오차 허용 범위보다 충분히 오래 전에 만료된 토큰을 만듭니다.
        Instant now = Instant.now();
        JWTClaimsSet.Builder expiredClaims = claims("admin")
                .issueTime(Date.from(now.minusSeconds(600)))
                .notBeforeTime(Date.from(now.minusSeconds(600)))
                .expirationTime(Date.from(now.minusSeconds(300)));
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(expiredClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void tokenNotYetUsableIsUnauthorized() throws Exception {
        Instant now = Instant.now();
        JWTClaimsSet.Builder futureClaims = claims("admin")
                .notBeforeTime(Date.from(now.plusSeconds(300)))
                .expirationTime(Date.from(now.plusSeconds(600)));
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(futureClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void wrongIssuerIsUnauthorized() throws Exception {
        JWTClaimsSet.Builder wrongIssuerClaims = claims("admin").issuer("https://another-issuer.example/realm");
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(wrongIssuerClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void tokenForFinaccessOnlyIsUnauthorized() throws Exception {
        JWTClaimsSet.Builder otherApiClaims = claims("admin").audience("finaccess-api");
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(otherApiClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void missingAudienceIsUnauthorized() throws Exception {
        JWTClaimsSet.Builder noAudienceClaims = claims("admin").claim("aud", null);
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(noAudienceClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void missingSubjectIsUnauthorized() throws Exception {
        JWTClaimsSet.Builder noSubjectClaims = claims("admin").subject(null);
        mockMvc.perform(get("/api/me").header(HttpHeaders.AUTHORIZATION, bearer(noSubjectClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void tokenWithoutExpirationIsUnauthorized() throws Exception {
        JWTClaimsSet.Builder noExpirationClaims = claims("admin").expirationTime(null);
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(noExpirationClaims)))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void ordinaryUserCannotReadAdminData() throws Exception {
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(claims("user"))))
                .andExpect(status().isForbidden());
    }

    @Test
    void adminRoleForAnotherClientDoesNotGrantFinadminAccess() throws Exception {
        JWTClaimsSet.Builder otherClientAdmin = claims("user").claim("resource_access", Map.of(
                "finadmin-api", Map.of("roles", List.of("user")),
                "finaccess-api", Map.of("roles", List.of("admin"))));
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(otherClientAdmin)))
                .andExpect(status().isForbidden());
    }

    @Test
    void realmAdminRoleDoesNotGrantFinadminAccess() throws Exception {
        JWTClaimsSet.Builder realmAdmin = claims("user")
                .claim("realm_access", Map.of("roles", List.of("admin")));
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(realmAdmin)))
                .andExpect(status().isForbidden());
    }

    @Test
    void malformedRolesDoNotGrantAdminAccessOrCauseServerError() throws Exception {
        JWTClaimsSet.Builder malformedRoles = claims("user")
                .claim("resource_access", Map.of("finadmin-api", Map.of("roles", "admin")));
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(malformedRoles)))
                .andExpect(status().isForbidden());
    }

    @Test
    void forwardedUserAndRoleHeadersCannotReplaceToken() throws Exception {
        mockMvc.perform(get("/api/admin/summary")
                        .header("X-User", "admin")
                        .header("X-Role", "admin"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void adminReceivesClearlyMarkedSampleSummaryAsJsonWithoutSessionCookie() throws Exception {
        mockMvc.perform(get("/api/admin/summary").header(HttpHeaders.AUTHORIZATION, bearer(claims("admin"))))
                .andExpect(status().isOk())
                .andExpect(header().doesNotExist(HttpHeaders.SET_COOKIE))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(content().json("""
                        {
                          "application": "finadmin",
                          "sampleData": true,
                          "pendingTransferCount": 3,
                          "completedTransferCount": 7
                        }
                        """));
    }

    @Test
    void currentUserComesFromVerifiedTokenAndContainsOnlyFinadminRoles() throws Exception {
        JWTClaimsSet.Builder userClaims = claims("user")
                .subject("keycloak-user-42")
                .claim("resource_access", Map.of(
                        "finadmin-api", Map.of("roles", List.of("user")),
                        "finaccess-api", Map.of("roles", List.of("admin"))));
        mockMvc.perform(get("/api/me")
                        .header(HttpHeaders.AUTHORIZATION, bearer(userClaims))
                        .header("X-User", "another-user"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.application").value("finadmin"))
                .andExpect(jsonPath("$.subject").value("keycloak-user-42"))
                .andExpect(jsonPath("$.issuer").value(ISSUER))
                .andExpect(jsonPath("$.roles[0]").value("user"))
                .andExpect(jsonPath("$.roles.length()").value(1))
                .andExpect(jsonPath("$.token").doesNotExist())
                .andExpect(jsonPath("$.access_token").doesNotExist());
    }

    @Test
    void currentUserRequiresToken() throws Exception {
        mockMvc.perform(get("/api/me"))
                .andExpect(status().isUnauthorized());
    }

    // 여기서부터는 여러 테스트가 함께 사용하는 준비 도구입니다.
    // claimsはJWTの中身です。通常はKeycloakが作りますが、ここでは失敗例も作るため自分で組み立てます。
    private JWTClaimsSet.Builder claims(String role) {
        Instant now = Instant.now();
        return new JWTClaimsSet.Builder()
                .issuer(ISSUER)
                .subject("test-user")
                .audience("finadmin-api")
                .issueTime(Date.from(now.minusSeconds(10)))
                .notBeforeTime(Date.from(now.minusSeconds(10)))
                .expirationTime(Date.from(now.plusSeconds(300)))
                .claim("resource_access", Map.of("finadmin-api", Map.of("roles", List.of(role))));
    }

    private String bearer(JWTClaimsSet.Builder claims) throws Exception {
        return "Bearer " + sign(claims, TRUSTED_KEY);
    }

    private String sign(JWTClaimsSet.Builder claims, RSAKey signingKey) throws Exception {
        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.RS256)
                .type(JOSEObjectType.JWT)
                .keyID("finadmin-test-key")
                .build();
        SignedJWT jwt = new SignedJWT(header, claims.build());
        jwt.sign(new RSASSASigner(signingKey));
        return jwt.serialize();
    }

    private static RSAKey createKey() {
        try {
            return new RSAKeyGenerator(2048).keyID("finadmin-test-key").generate();
        } catch (Exception exception) {
            throw new IllegalStateException("테스트용 RSA 키를 만들지 못했습니다", exception);
        }
    }

    private static HttpServer startPublicKeyServer() {
        try {
            // 0번 포트는 운영체제에게 비어 있는 포트를 골라 달라는 뜻입니다.
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            server.createContext("/jwks", exchange -> {
                byte[] response = new JWKSet(TRUSTED_KEY.toPublicJWK()).toString()
                        .getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json");
                exchange.sendResponseHeaders(200, response.length);
                try (var body = exchange.getResponseBody()) {
                    body.write(response);
                }
            });
            server.start();
            return server;
        } catch (Exception exception) {
            throw new IllegalStateException("테스트용 공개 키 서버를 시작하지 못했습니다", exception);
        }
    }
}
