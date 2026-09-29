# FinLab 인증·인가 아키텍처

![FinLab 인증·인가 아키텍처](images/finlab-architecture.png)

2026-09-29의 `compose.yaml`, APISIX 경로 설정, 프런트 로그인 코드, 두 Spring 앱의 보안 설정을 기준으로 만든 그림입니다.

## 1. 로그인해서 토큰을 받습니다

브라우저에서 로그인하면 Keycloak의 로그인 화면으로 이동합니다. 로그인이 끝나면 브라우저가 Authorization Code + PKCE 절차로 액세스 토큰을 받습니다. Keycloak은 사용자와 역할 정보를 자신의 PostgreSQL에 저장합니다.

파란 선은 로그인과 토큰 발급 과정입니다. 실제 비밀번호나 토큰 값은 그림에 포함하지 않았습니다.

## 2. 토큰을 붙여 Gateway에 요청합니다

브라우저는 `Authorization: Bearer <액세스 토큰>` 헤더를 붙여 APISIX에 요청합니다. APISIX는 서명, 발급자, 유효 시간, 대상 API를 검사합니다. 통과하면 같은 토큰을 목적지 백엔드로 전달합니다.

| 브라우저가 요청한 경로 | APISIX가 전달하는 곳 | 전달할 때의 경로 |
| --- | --- | --- |
| `/access/api/me` | FinAccess | `/api/me` |
| `/admin/api/me` | FinAdmin | `/api/me` |
| `/admin/api/admin/summary` | FinAdmin | `/api/admin/summary` |

초록색 선은 API 요청입니다. FinAccess를 거쳐 FinAdmin으로 가는 것이 아니라, 요청한 경로에 따라 둘 중 하나로 갑니다.

## 3. 해당 백엔드가 다시 검사합니다

FinAccess와 FinAdmin은 서로 별도로 실행하는 Spring Resource Server입니다. 각 앱이 JWT를 검증하고, 자기 앱에서 필요한 역할과 업무 규칙을 확인합니다.

- **FinAccess:** 회사·계좌·이체 기능을 담당합니다. 역할뿐 아니라 로그인한 사용자의 소속 회사와 이체 규칙도 확인합니다. 업무 데이터는 별도의 PostgreSQL에 저장합니다.
- **FinAdmin:** 관리자 API를 담당합니다. 관리자 요약에는 `finadmin-api` Client의 `admin` 역할이 필요합니다. 현재 통계는 샘플 데이터이며, FinAccess나 DB에서 조회하지 않습니다.

검증하는 프로그램은 APISIX·FinAccess·FinAdmin, 총 세 개입니다. 하지만 **요청 한 건이 거치는 검증은 APISIX + 선택된 백엔드, 두 단계**입니다.

## 4. 보라색 점선은 공개 키를 가져오는 길입니다

APISIX와 두 백엔드는 Keycloak의 JWKS 주소에서 서명 확인용 공개 키를 가져와 캐시합니다. 공개 키는 토큰에 있는 서명이 Keycloak에서 만들어졌는지 확인하는 데 씁니다.

이 선은 업무 요청을 Keycloak으로 전달한다는 뜻이 아닙니다. 각 서버가 공개 키로 JWT를 검증하므로 모든 업무 요청마다 Keycloak에 유효성을 물어보는 구조가 아닙니다. 키 캐시가 없거나 새 서명 키가 필요할 때 공개 키 조회가 발생할 수 있습니다.

## 5. Nginx는 화면 파일을 제공합니다

APISIX는 `/access/*`, `/admin/*`를 API로 보내고, 나머지 경로는 Nginx로 보냅니다. Nginx는 HTML·JavaScript·CSS 파일을 제공합니다. 로그인과 API 호출 코드는 이 파일을 받은 브라우저에서 실행됩니다.

## 실제 접속 주소

| 대상 | 내 컴퓨터에서 접속하는 주소 | 컨테이너 안의 포트 |
| --- | --- | --- |
| APISIX와 앱 화면 | `http://localhost:18090` | 9080 |
| Keycloak | `http://localhost:18080` | 8080 |
| FinAccess 직접 검증 | `http://localhost:18082` | 8080 |
| FinAdmin 직접 검증 | `http://localhost:18083` | 8081 |

그림의 주 경로는 APISIX를 거칩니다. 백엔드 직접 호출 포트는 백엔드만으로도 잘못된 토큰을 거절하는지 확인하기 위한 실습용입니다. 호스트 포트는 `127.0.0.1`에만 연결하며, 이 구성은 로컬 HTTP 실습 환경입니다.

이미지는 내장 imagegen 도구로 생성한 뒤 실제 설정과 비교해 연결 관계를 확인했습니다.
