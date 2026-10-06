-- [입력] render-gateway.py가 아래 자리표시에 이 경로의 권한표를 넣습니다.
-- 이 함수는 rewrite의 마지막(-2000)에 실행됩니다. 먼저 실행되는 openid-connect(2599)가
-- 서명/발급자/audience를 검증합니다. load_jwt는 단순 해석이므로 이 함수만 쓰면 안 됩니다.
-- API7으로 옮겨도 반드시 OIDC와 이 함수를 함께 붙이고 실행 순서를 실제 검증해야 합니다.
return function(conf, ctx)
  local core = require("apisix.core")
  local policy = core.json.decode([==[__POLICY_JSON__]==])
  local function reject(status, reason)
    ngx.header["X-Finlab-Rejected-By"] = "gateway-policy"
    if status == 401 then
      ngx.header["WWW-Authenticate"] = 'Bearer error="invalid_token"'
    end
    return status, {message = reason, rejectedBy = "gateway-policy"}
  end

  -- OIDC를 통과한 뒤 다시 읽는 헤더입니다. X-Userinfo 같은 외부 입력은 믿지 않습니다.
  local header = core.request.header(ctx, "Authorization")
  local token = type(header) == "string" and header:match("^Bearer%s+(.+)$")
  local parsed = token and require("resty.jwt"):load_jwt(token)
  local claims = parsed and parsed.valid and parsed.payload
  if type(claims) ~= "table" or type(claims.exp) ~= "number"
    or claims.exp <= ngx.time() or type(claims.sub) ~= "string" or claims.sub == "" then
    return reject(401, "Token identity or expiry is invalid")
  end
  if claims.nbf ~= nil and (type(claims.nbf) ~= "number" or claims.nbf > ngx.time()) then
    return reject(401, "Token is not yet valid")
  end

  -- APISIX의 request_uri는 이미 정규화되어 있습니다. real_request_uri에서 원래 표기를 검사합니다.
  -- proxy-rewrite가 뒤로 전달할 주소를 바꿔도, 이 권한표는 /access 같은 원래 접두사를 사용합니다.
  -- %-인코딩, ;, 중복 / 같은 별도 표기는 표에 없으므로 허용되지 않습니다.
  local path = ctx.var.real_request_uri:match("^[^?]*")
  local required
  for _, rule in ipairs(policy.rules) do
    if ngx.req.get_method() == rule.method and path:match(rule.pattern) then
      required = rule.roles
      break
    end
  end
  if not required then return reject(403, "No policy for this method and path") end

  -- 다른 API의 admin이나 Keycloak 관리 권한은 이 API의 권한이 아닙니다.
  local resources = claims.resource_access
  local app = type(resources) == "table" and resources[policy.audience]
  local roles = type(app) == "table" and app.roles
  if type(roles) ~= "table" then return reject(403, "Required application role missing") end
  -- JSON 객체나 섞인 배열을 역할 목록으로 받아들이지 않습니다.
  for k, role in pairs(roles) do
    if type(k) ~= "number" or k < 1 or k > #roles or type(role) ~= "string" or role:match("^%s*$") then
      return reject(403, "Malformed application roles")
    end
  end
  local allowed = false
  for _, role in ipairs(roles) do
    if type(role) ~= "string" then return reject(403, "Malformed application roles") end
    for _, wanted in ipairs(required) do
      if role == wanted then allowed = true end
    end
  end
  if not allowed then return reject(403, "Required application role missing") end

  -- 사용자가 붙인 신원 헤더를 지웁니다. Spring은 원래 JWT로 다시 판단합니다.
  for _, name in ipairs({"X-Finlab-Subject", "X-Finlab-Issuer", "X-Finlab-Roles",
      "X-Userinfo", "X-ID-Token", "X-Access-Token", "X-Refresh-Token", "X-Raw-ID-Token"}) do
    ngx.req.clear_header(name)
  end
  if policy.legacy then
    -- 레거시는 JWT를 이해하지 못하므로 필요한 신원만 새 헤더로 전달합니다.
    -- 헤더를 신뢰할 수 있는 이유는 별도 내부 네트워크에 Gateway와 레거시만 연결하기 때문입니다.
    -- 로컬 Docker 관리자까지 막는 보장은 아닙니다. 운영에서는 mTLS/방화벽으로 신뢰 경계를 강화합니다.
    if claims.sub:find("[%c]") or type(claims.iss) ~= "string" or claims.iss:find("[%c]") then
      return reject(401, "Identity cannot be forwarded")
    end
    core.request.set_header(ctx, "X-Finlab-Subject", claims.sub)
    core.request.set_header(ctx, "X-Finlab-Issuer", claims.iss)
    -- 역할은 Gateway에서 이미 확인했습니다. 레거시에 불필요한 권한/토큰 전체는 보내지 않습니다.
    ngx.req.clear_header("Authorization")
  end
end
