-- API7의 OIDC가 검증한 결과만 사용합니다. 여기서 JWT를 다시 디코딩하지 않습니다.
-- 경로·메서드는 Route가, 허용 역할 비교는 기본 acl 플러그인이 담당합니다.
return function(conf, ctx)
  local claims = ctx.external_user
  local function reject(code, message)
    ngx.header["X-Finlab-Rejected-By"] = "gateway-policy"
    if code == 401 then ngx.header["WWW-Authenticate"] = 'Bearer error="invalid_token"' end
    return code, {message = message, rejectedBy = "gateway-policy"}
  end
  -- 설치 버전에서 엄격한 시간·신원 검사를 보완합니다. 권한을 허용하는 코드는 아닙니다.
  if type(claims) ~= "table" or type(claims.exp) ~= "number" or claims.exp <= ngx.time()
    or type(claims.sub) ~= "string" or claims.sub == ""
    or (claims.nbf ~= nil and (type(claims.nbf) ~= "number" or claims.nbf > ngx.time())) then
    return reject(401, "Token identity or time is invalid")
  end
  local app = type(claims.resource_access) == "table" and claims.resource_access["__AUDIENCE__"]
  local roles
  if type(app) == "table" then roles = app.roles end
  -- ACL이 올바른 역할만 골라 허용하지 않도록, 섞인 배열은 전체 거절합니다.
  if roles ~= nil then
    if type(roles) ~= "table" then return reject(403, "Malformed application roles") end
    for k, role in pairs(roles) do
      if type(k) ~= "number" or k < 1 or k > #roles or type(role) ~= "string" or role:match("^%s*$") then
        return reject(403, "Malformed application roles")
      end
    end
  end
  -- 외부가 붙인 사용자 정보는 지웁니다. Spring은 원래 Bearer JWT를 검증합니다.
  for _, name in ipairs({"X-Finlab-Subject", "X-Finlab-Issuer", "X-Finlab-Roles",
      "X-Userinfo", "X-ID-Token", "X-Access-Token", "X-Refresh-Token", "X-Raw-ID-Token"}) do
    ngx.req.clear_header(name)
  end
end
