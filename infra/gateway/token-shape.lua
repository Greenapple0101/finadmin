-- [거절 전용 입구 검사] 이 단계에서는 아직 서명을 믿지 않습니다.
-- exp가 숫자가 아닌 잘못된 JWT가 OIDC 내부에서 500을 일으키지 않도록 자료형만 걸러냅니다.
-- 여기서 통과해도 인증 성공이 아닙니다. 바로 뒤의 OIDC 서명/issuer/audience 검사가 필수입니다.
return function(conf, ctx)
  local core = require("apisix.core")
  local header = core.request.header(ctx, "Authorization")
  local token = type(header) == "string" and header:match("^[Bb][Ee][Aa][Rr][Ee][Rr]%s+(.+)$")
  local parsed = token and require("resty.jwt"):load_jwt(token)
  local c = parsed and parsed.valid and parsed.payload
  local valid = type(c) == "table" and type(c.exp) == "number"
    and type(c.sub) == "string" and c.sub ~= ""
    and type(c.iss) == "string" and c.iss ~= ""
  if valid and c.nbf ~= nil then valid = type(c.nbf) == "number" end
  if valid then
    if type(c.aud) == "table" then
      valid = #c.aud > 0
      for k, v in pairs(c.aud) do
        if type(k) ~= "number" or k < 1 or k > #c.aud or type(v) ~= "string" then valid = false end
      end
    else
      valid = type(c.aud) == "string" and c.aud ~= ""
    end
  end
  if not valid then
    ngx.header["WWW-Authenticate"] = 'Bearer error="invalid_token"'
    ngx.header["X-Finlab-Rejected-By"] = "gateway-token-shape"
    return 401, {message = "Token structure is invalid", rejectedBy = "gateway-token-shape"}
  end
end
