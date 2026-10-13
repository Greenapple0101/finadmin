package io.github.greenapple0101.finadmin.itsm;

import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import tools.jackson.databind.ObjectMapper;
import java.util.*;
import java.util.concurrent.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

// 별도 PostgreSQL에 Flyway를 실제 적용하고 HTTP → 서비스 → DB를 확인합니다.
// jwt()는 서명 검사를 생략한 업무 시험용 신원입니다. 실제 서명 검사는 AdminSummaryControllerTest와 실제 연동 검사에서 합니다.
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers
class ServiceRequestApiTest {
    @Container static final PostgreSQLContainer db = new PostgreSQLContainer("postgres:17.11-bookworm");
    @DynamicPropertySource static void database(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", db::getJdbcUrl);
        registry.add("spring.datasource.username", db::getUsername);
        registry.add("spring.datasource.password", db::getPassword);
    }
    private static final String ISSUER = "http://localhost:18080/realms/finlab";
    private static final String API = "/api/itsm/requests";
    @Autowired MockMvc mvc;
    @Autowired JdbcTemplate jdbc;
    @Autowired ObjectMapper json;
    UUID companyA, companyB;
    Map<String, UUID> people;

    @BeforeEach void seed() {
        // 개발용 DB에는 접근하지 않습니다. 각 시험은 자신만의 회사와 직원을 사용합니다.
        jdbc.update("DELETE FROM service_requests");
        jdbc.update("DELETE FROM itsm_users");
        jdbc.update("DELETE FROM itsm_companies");
        companyA = UUID.randomUUID(); companyB = UUID.randomUUID(); people = new HashMap<>();
        jdbc.update("INSERT INTO itsm_companies VALUES (?, ?), (?, ?)", companyA, "A", companyB, "B");
        for (String person : List.of("alice", "bob", "admin", "peer", "outsider", "other-admin")) {
            UUID id = UUID.randomUUID(); people.put(person, id);
            UUID company = person.equals("outsider") || person.equals("other-admin") ? companyB : companyA;
            jdbc.update("INSERT INTO itsm_users VALUES (?, ?, ?, ?, ?)", id, company, person, ISSUER, person);
        }
    }
    RequestPostProcessor login(String user, String role) {
        return jwt().jwt(token -> token.issuer(ISSUER).subject(user))
                .authorities(new SimpleGrantedAuthority("ROLE_" + role));
    }
    UUID create(String user, String role) throws Exception {
        String body = mvc.perform(post(API).with(login(user, role)).contentType(MediaType.APPLICATION_JSON)
                .content("{\"serviceName\":\"테스트 환경 이용\",\"reason\":\"개발 검증에 필요합니다.\"}"))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.status").value("REQUESTED"))
                .andReturn().getResponse().getContentAsString();
        return UUID.fromString(json.readTree(body).get("id").asText());
    }
    @Test void fullFlowPersistsHistoryAndCountsRealCompanyData() throws Exception {
        UUID id = create("alice", "user");
        mvc.perform(post(API + "/" + id + "/approve").with(login("bob", "approver")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.approverId").value(people.get("bob").toString()));
        mvc.perform(post(API + "/" + id + "/complete").with(login("admin", "admin"))
                .contentType(MediaType.APPLICATION_JSON).content("{\"note\":\"이용 안내를 완료했습니다.\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("COMPLETED"))
                .andExpect(jsonPath("$.completedBy").value(people.get("admin").toString()));
        mvc.perform(get(API + "/" + id).with(login("alice", "user")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.approvedAt").isNotEmpty())
                .andExpect(jsonPath("$.completedAt").isNotEmpty());
        mvc.perform(get("/api/itsm/summary").with(login("admin", "admin")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.sampleData").value(false))
                .andExpect(jsonPath("$.completed").value(1));
        mvc.perform(get("/api/itsm/summary").with(login("other-admin", "admin")))
                .andExpect(status().isOk()).andExpect(jsonPath("$.completed").value(0));
        assertThat(jdbc.queryForObject("SELECT completion_note FROM service_requests WHERE id=?", String.class, id))
                .isEqualTo("이용 안내를 완료했습니다.");
    }
    @Test void tokenAndBusinessProvisioningAreBothRequired() throws Exception {
        mvc.perform(get(API)).andExpect(status().isUnauthorized());
        mvc.perform(get(API).with(login("unknown", "admin"))).andExpect(status().isForbidden());
    }
    @Test void requestBodyCannotChooseCompanyRequesterOrState() throws Exception {
        mvc.perform(post(API).with(login("alice", "user")).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("serviceName", "업무 도구", "reason", "실습",
                        "companyId", companyB, "requesterId", people.get("admin"), "status", "COMPLETED"))))
                .andExpect(status().isCreated()).andExpect(jsonPath("$.companyId").value(companyA.toString()))
                .andExpect(jsonPath("$.requesterId").value(people.get("alice").toString()))
                .andExpect(jsonPath("$.status").value("REQUESTED"));
    }
    @Test void rolesAreEnforcedBeforeWork() throws Exception {
        UUID id = create("alice", "user");
        mvc.perform(post(API + "/" + id + "/approve").with(login("alice", "user"))).andExpect(status().isForbidden());
        mvc.perform(post(API + "/" + id + "/complete").with(login("bob", "approver"))
                .contentType(MediaType.APPLICATION_JSON).content("{\"note\":\"완료\"}"))
                .andExpect(status().isForbidden());
        mvc.perform(get("/api/itsm/summary").with(login("alice", "user"))).andExpect(status().isForbidden());
    }
    @ParameterizedTest @ValueSource(strings = {"approver", "admin"})
    void evenPrivilegedRequesterCannotApproveOwnRequest(String role) throws Exception {
        UUID id = create("bob", role);
        mvc.perform(post(API + "/" + id + "/approve").with(login("bob", role))).andExpect(status().isForbidden());
        assertThat(jdbc.queryForObject("SELECT status FROM service_requests WHERE id=?", String.class, id)).isEqualTo("REQUESTED");
    }
    @Test void otherCompanyIsDeniedEvenForAdmin() throws Exception {
        UUID id = create("alice", "user");
        for (String role : List.of("user", "approver", "admin")) {
            mvc.perform(get(API + "/" + id).with(login("outsider", role))).andExpect(status().isForbidden());
            mvc.perform(get(API).with(login("outsider", role))).andExpect(status().isOk())
                    .andExpect(jsonPath("$.items").isEmpty());
        }
        mvc.perform(post(API + "/" + id + "/approve").with(login("other-admin", "admin"))).andExpect(status().isForbidden());
        mvc.perform(post(API + "/" + id + "/complete").with(login("other-admin", "admin"))
                .contentType(MediaType.APPLICATION_JSON).content("{\"note\":\"완료\"}"))
                .andExpect(status().isForbidden());
    }
    @Test void ordinaryUserSeesOwnRequestsButReviewerSeesCompanyQueue() throws Exception {
        UUID own = create("alice", "user"); UUID peer = create("peer", "user"); create("outsider", "user");
        mvc.perform(get(API).with(login("alice", "user"))).andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].id").value(own.toString()));
        mvc.perform(get(API + "/" + peer).with(login("alice", "user"))).andExpect(status().isForbidden());
        mvc.perform(get(API).with(login("bob", "approver"))).andExpect(jsonPath("$.items.length()").value(2));
    }
    @Test void invalidInputMissingRequestAndInvalidPaginationHaveClearErrors() throws Exception {
        for (String name : List.of(" ", "x".repeat(101))) {
            mvc.perform(post(API).with(login("alice", "user")).contentType(MediaType.APPLICATION_JSON)
                    .content(json.writeValueAsString(Map.of("serviceName", name, "reason", "필요"))))
                    .andExpect(status().isBadRequest());
        }
        mvc.perform(get(API + "/" + UUID.randomUUID()).with(login("alice", "user"))).andExpect(status().isNotFound());
        mvc.perform(get(API + "?page=-1").with(login("alice", "user"))).andExpect(status().isBadRequest());
    }
    @Test void skippedOrRepeatedTransitionsConflictAndInvalidCompletionRollsBack() throws Exception {
        UUID id = create("alice", "user"); String complete = API + "/" + id + "/complete";
        mvc.perform(post(complete).with(login("admin", "admin")).contentType(MediaType.APPLICATION_JSON)
                .content("{\"note\":\"완료\"}")).andExpect(status().isConflict());
        mvc.perform(post(API + "/" + id + "/approve").with(login("bob", "approver"))).andExpect(status().isOk());
        mvc.perform(post(API + "/" + id + "/approve").with(login("admin", "admin"))).andExpect(status().isConflict());
        mvc.perform(post(complete).with(login("admin", "admin")).contentType(MediaType.APPLICATION_JSON)
                .content("{\"note\":\" \"}")).andExpect(status().isBadRequest());
        assertThat(jdbc.queryForObject("SELECT status FROM service_requests WHERE id=?", String.class, id)).isEqualTo("APPROVED");
        mvc.perform(post(complete).with(login("admin", "admin")).contentType(MediaType.APPLICATION_JSON)
                .content("{\"note\":\"완료\"}")).andExpect(status().isOk());
        mvc.perform(post(complete).with(login("admin", "admin")).contentType(MediaType.APPLICATION_JSON)
                .content("{\"note\":\"다시 완료\"}")).andExpect(status().isConflict());
    }
    @Test void listHasBoundedPagesWithoutLosingRequests() throws Exception {
        for (int n = 0; n < 21; n++) create("alice", "user");
        mvc.perform(get(API).with(login("alice", "user"))).andExpect(jsonPath("$.items.length()").value(20))
                .andExpect(jsonPath("$.hasNext").value(true));
        mvc.perform(get(API + "?page=1").with(login("alice", "user"))).andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.hasNext").value(false));
    }
    @Test void simultaneousApprovalOnlyRecordsOneApprover() throws Exception {
        UUID id = create("alice", "user"); CountDownLatch start = new CountDownLatch(1);
        try (ExecutorService pool = Executors.newFixedThreadPool(2)) {
            List<Future<Integer>> jobs = new ArrayList<>();
            for (String user : List.of("bob", "admin")) jobs.add(pool.submit(() -> {
                start.await();
                return mvc.perform(post(API + "/" + id + "/approve").with(login(user, "approver")))
                        .andReturn().getResponse().getStatus();
            }));
            start.countDown();
            assertThat(List.of(jobs.get(0).get(20, TimeUnit.SECONDS), jobs.get(1).get(20, TimeUnit.SECONDS)))
                    .containsExactlyInAnyOrder(200, 409);
        }
    }
}
