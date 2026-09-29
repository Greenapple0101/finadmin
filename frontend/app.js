// [이 파일이 하는 일] Keycloak 로그인 → 토큰 받기 → APISIX를 통해 API 호출 순서로 동작합니다.
// 액세스 토큰은 메모리에만 둡니다. 새로고침하면 다시 로그인해야 하며 localStorage에 저장하지 않습니다.
// API 허용 여부는 화면 버튼이 아니라 APISIX와 Spring 백엔드가 결정합니다.
const issuer = "http://localhost:18080/realms/finlab";
const clientId = "finlab-web";
const redirectUri = "http://localhost:18090/";
let accessToken = null;
let expiresAt = 0;
const session = document.querySelector("#session");
const resultStatus = document.querySelector("#result-status");
const result = document.querySelector("#result");

// PKCE는 로그인 시작 때 만든 비밀값을, 받은 코드를 토큰으로 바꿀 때 다시 증명하는 방법입니다.
function base64url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function randomValue() { return base64url(crypto.getRandomValues(new Uint8Array(32))); }

async function login() {
  const verifier = randomValue();
  const state = randomValue();
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
  // 화면이 Keycloak으로 이동했다가 돌아오는 동안에만 필요한 일회용 정보를 보관합니다.
  sessionStorage.setItem("finlab-login", JSON.stringify({ verifier, state, createdAt: Date.now() }));
  const query = new URLSearchParams({ client_id: clientId, redirect_uri: redirectUri,
    response_type: "code", scope: "openid", state, code_challenge: challenge,
    code_challenge_method: "S256", prompt: "login" });
  window.location.assign(`${issuer}/protocol/openid-connect/auth?${query}`);
}

async function finishLogin() {
  const query = new URLSearchParams(location.search);
  if (!query.has("code") && !query.has("error")) return;
  // 코드가 주소창과 브라우저 방문 기록에 오래 남지 않도록 먼저 지웁니다.
  history.replaceState(null, "", "/");
  const stored = sessionStorage.getItem("finlab-login");
  sessionStorage.removeItem("finlab-login");
  const saved = stored ? JSON.parse(stored) : null;
  if (!saved || saved.state !== query.get("state") || Date.now() - saved.createdAt > 600000) {
    throw new Error("로그인 요청 정보를 확인할 수 없습니다. 다시 로그인하세요.");
  }
  if (query.has("error")) throw new Error("로그인이 취소되었거나 허용되지 않았습니다.");
  if (query.get("iss") !== issuer) throw new Error("예상한 Keycloak의 응답이 아닙니다.");
  const response = await fetch(`${issuer}/protocol/openid-connect/token`, {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "authorization_code", client_id: clientId,
      redirect_uri: redirectUri, code: query.get("code"), code_verifier: saved.verifier })
  });
  if (!response.ok) throw new Error("토큰 발급에 실패했습니다. 다시 로그인하세요.");
  const tokens = await response.json();
  accessToken = tokens.access_token;
  expiresAt = Date.now() + tokens.expires_in * 1000;
  session.textContent = "로그인했습니다. 내 정보 버튼으로 백엔드가 확인한 사용자와 역할을 볼 수 있습니다.";
}

async function callApi(path, anonymous = false) {
  const headers = {};
  if (!anonymous && accessToken) {
    if (Date.now() >= expiresAt) {
      accessToken = null;
      session.textContent = "토큰이 만료되었습니다. 다시 로그인하세요.";
    } else {
      // ID 토큰은 보내지 않습니다. API 호출용 액세스 토큰을 그대로 전달합니다.
      headers.Authorization = `Bearer ${accessToken}`;
    }
  }
  try {
    const response = await fetch(path, { headers, cache: "no-store" });
    const text = await response.text();
    resultStatus.textContent = `${path} → HTTP ${response.status} · Gateway: ${response.headers.get("X-Finlab-Gateway") || "확인 불가"}`;
    try { result.textContent = JSON.stringify(JSON.parse(text), null, 2); }
    catch { result.textContent = text || "응답 본문 없음"; }
  } catch {
    resultStatus.textContent = "서버에 연결할 수 없습니다. 실습 서버가 실행 중인지 확인하세요.";
  }
}

document.querySelector("#login").addEventListener("click", () => login().catch(() => {
  session.textContent = "로그인을 시작할 수 없습니다. localhost 주소로 접속했는지 확인하세요.";
}));
document.querySelector("#logout").addEventListener("click", () => {
  accessToken = null;
  expiresAt = 0;
  sessionStorage.removeItem("finlab-login");
  // Keycloak에서 로그아웃 확인 후 돌아옵니다. 이미 발급된 JWT 즉시 폐기와는 다른 동작입니다.
  const query = new URLSearchParams({ client_id: clientId, post_logout_redirect_uri: redirectUri });
  location.assign(`${issuer}/protocol/openid-connect/logout?${query}`);
});
document.querySelectorAll("[data-path]").forEach(button => {
  button.addEventListener("click", () => callApi(button.dataset.path));
});
document.querySelector("#anonymous").addEventListener("click", () => callApi("/admin/api/admin/summary", true));
finishLogin().catch(error => { session.textContent = error.message; });
