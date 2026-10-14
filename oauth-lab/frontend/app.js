// 브라우저가 하는 일은 세 가지입니다: 인증 코드 요청, 토큰 교환, 토큰을 붙여 API 호출.
// 비밀번호는 Keycloak만 받습니다. 브라우저용 Client에는 client_secret을 넣지 않습니다.
const issuer = 'http://localhost:18180/realms/oauth-lab';
const endpoint = issuer + '/protocol/openid-connect';
const clientId = 'oauth-browser';
const redirectUri = 'http://localhost:18100/';
const gateway = 'http://localhost:18090/oauth-lab/api';
let tokens = null;
const show = (id, message) => document.getElementById(id).textContent = message;

// PKCE에 쓰는 임의의 값을 URL에 실을 수 있는 문자열로 바꿉니다.
function base64url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
}
const random = () => base64url(crypto.getRandomValues(new Uint8Array(32)));

async function authorize() {
  const verifier = random();
  const state = random();
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
  // 화면이 Keycloak으로 이동했다 돌아오는 동안만 verifier와 state를 보관합니다.
  sessionStorage.setItem('oauth-pending', JSON.stringify({verifier, state, started: Date.now()}));
  const params = new URLSearchParams({client_id: clientId, redirect_uri: redirectUri,
    response_type: 'code', scope: 'demo.read', state,
    code_challenge: challenge, code_challenge_method: 'S256', prompt: 'login'});
  // openid scope를 요청하지 않습니다. ID Token으로 로그인 결과를 처리하지 않습니다.
  location.assign(endpoint + '/auth?' + params);
}

async function exchange(parameters) {
  const response = await fetch(endpoint + '/token', {method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({client_id: clientId, ...parameters})});
  const body = await response.json();
  if (!response.ok) throw new Error('토큰 교환 실패: ' + (body.error || response.status));
  if (body.id_token) throw new Error('예상과 달리 ID Token이 발급되었습니다. scope 설정을 확인하세요.');
  tokens = body;
  // 토큰 원문과 사용자 정보를 화면에 출력하지 않습니다. API7이 검증하는 토큰을 그대로 보냅니다.
  show('token', JSON.stringify({발급: '성공', token_type: body.token_type,
    expires_in: body.expires_in, scope: body.scope, ID_Token: '없음'}, null, 2));
}

async function callback() {
  const params = new URLSearchParams(location.search);
  if (!params.has('code') && !params.has('error')) return;
  // 인증 코드가 주소창과 브라우저 기록에 계속 남지 않도록 바로 지웁니다.
  history.replaceState({}, '', redirectUri);
  const pending = JSON.parse(sessionStorage.getItem('oauth-pending') || 'null');
  sessionStorage.removeItem('oauth-pending');
  if (!pending || params.get('state') !== pending.state || Date.now() - pending.started > 600000)
    throw new Error('내가 시작한 요청과 응답이 맞지 않거나 시간이 지났습니다. 다시 시작하세요.');
  if (params.get('iss') !== issuer) throw new Error('예상한 Keycloak의 응답이 아닙니다.');
  if (params.has('error')) throw new Error('인증 요청이 완료되지 않았습니다: ' + params.get('error'));
  await exchange({grant_type: 'authorization_code', code: params.get('code'),
    redirect_uri: redirectUri, code_verifier: pending.verifier});
}

async function callApi(path, withoutToken = false) {
  const headers = {};
  if (!withoutToken && tokens) headers.Authorization = 'Bearer ' + tokens.access_token;
  const response = await fetch(gateway + path, {headers});
  show('result', `HTTP ${response.status}\n${await response.text()}`);
}

// 예외가 생겨도 사용자에게 이유를 보여 줍니다. 자동 갱신은 하지 않아 만료 후 401도 관찰할 수 있습니다.
const safely = action => async () => { try { await action(); } catch (error) { show('result', error.message); } };
document.getElementById('authorize').onclick = safely(authorize);
document.getElementById('refresh').onclick = safely(async () => {
  if (!tokens?.refresh_token) throw new Error('먼저 토큰을 받으세요.');
  await exchange({grant_type: 'refresh_token', refresh_token: tokens.refresh_token});
});
document.getElementById('clear').onclick = () => { tokens = null; show('token', '이 페이지의 토큰을 지웠습니다.'); };
document.getElementById('read').onclick = safely(() => callApi('/read'));
document.getElementById('admin').onclick = safely(() => callApi('/admin'));
document.getElementById('anonymous').onclick = safely(() => callApi('/read', true));
safely(callback)();
