# API 명세와 권한 정책

[문서 목차](../README.md) · 기준: 2026-10-15

## 공통 규칙

API 요청은 `Authorization: Bearer <access_token>`을 사용합니다. 실제 토큰을 Git·공유 문서에 붙이지 않습니다. audience는 두 앱 공통 `oauth-api`이며, `resource_access.oauth-api.roles`의 **USER·ADMIN을 대소문자 그대로** 검사합니다. ADMIN이 USER를 자동 포함하지 않습니다.

| 구분 | 주소 |
|---|---|
| 정상 사용자 API 진입 | `http://localhost:18090/oauth-access` |
| 정상 관리자 API 진입 | `http://localhost:18090/oauth-admin` |
| FinAccess 직접 비교 | `http://localhost:18100` |
| FinAdmin 직접 비교 | `http://localhost:18101` |

API7은 `/oauth-access` 또는 `/oauth-admin`을 제거해 Spring으로 전달합니다. 역할 없이 JSON을 반환하는 공개 업무 API는 없습니다. FinAccess의 화면 파일 GET은 로그인 전에도 받을 수 있습니다.

## 엔드포인트

| 메서드 | Spring 경로 | 역할 | 성공·오류 | 응답·목적 |
|---|---|---|---|---|
| GET | `/api/user/me` | USER | 200 | application, message, subject, roles |
| GET | `/api/admin/me` | ADMIN | 200 | application, subject, message |
| GET | `/api/admin/greeting?name=Demo` | ADMIN | 200 | message: 인사 문장 |
| GET | `/api/admin/greeting` | ADMIN | 400 | name 누락·공백 또는 Java 문자열 길이 40 초과 |
| GET | `/api/admin/demo-error` | ADMIN | 500 | 의도적인 서버 예외를 처리한 message, source |
| GET | `/api/admin/missing` | ADMIN | 404 | 인증·역할 검사 후 매핑된 Controller가 없음 |

모든 API는 조회·응답 시연용이며 DB에 저장하지 않습니다. POST 생성·201 응답·금융·ITSM API는 현재 명세에 없습니다.

정상 USER 응답 예시입니다. subject는 설명용 값이며 실제 토큰은 아닙니다.

```json
{
  "application": "FinAccess",
  "message": "USER 권한으로 FinAccess API에 접근했습니다.",
  "subject": "example-subject",
  "roles": ["USER"]
}
```

## Gateway와 Spring의 역할 분담

| 외부 경로·메서드 | API7 검사 | Spring 검사 |
|---|---|---|
| GET `/oauth-access/api/user/me` | JWT + USER | GET `/api/user/me` JWT + USER |
| OPTIONS `/oauth-access/api/user/me` | CORS 사전 요청 처리, 백엔드 전달 없음 | 실행하지 않음 |
| GET `/oauth-admin/api/admin/*` | JWT + ADMIN | GET `/api/admin/**` JWT + ADMIN, 그 뒤 Controller 존재 확인 |
| 그 밖의 `/oauth-access`·하위 경로 | JWT·USER 검사 후 fallback 403 | 전달하지 않음 |
| 그 밖의 `/oauth-admin`·하위 경로 | JWT·ADMIN 검사 후 fallback 403 | 전달하지 않음 |

fallback은 **유효한 토큰이어도 허용하지 않은 경로·메서드면 거절**하도록 만든 Route입니다. 먼저 JWT가 잘못됐다면 401로 끝날 수 있습니다. 기존 Gateway Group의 다른 접두어까지 이 네 Route가 모두 막는 것은 아닙니다.

## 상태 코드 해석

| 코드 | 이 실습의 원인 | 예시 |
|---|---|---|
| 200 | 토큰·역할·입력 조건 통과 | USER me / ADMIN me·greeting |
| 400 | Controller에 도착했지만 입력이 잘못됨 | ADMIN greeting의 빈 name |
| 401 | 인증할 유효 토큰 없음 | 토큰 없음, 서명 변조, 만료 |
| 403 | 유효한 토큰에 필요한 역할 없음, 또는 경로·메서드 거절 | USER→ADMIN API, ADMIN→USER API, 허용하지 않은 POST |
| 404 | 유효한 ADMIN 요청에 해당 핸들러 없음 | GET `/oauth-admin/api/admin/missing` |
| 500 | FinAdmin의 시연 예외 | `/demo-error`; Gateway 장애가 아님 |

`/oauth-access/unknown`은 USER fallback에서 403인 반면 `/oauth-admin/api/admin/missing`은 정상 ADMIN Route를 거쳐 Spring에서 404입니다. 서로 다른 정책이므로 “없는 경로는 항상 404”라고 설명하지 않습니다. 502·503·504 upstream 장애는 이번 최소 구성에서 재검증하지 않았습니다.

보안 필터·Gateway 기본 오류와 Controller가 작성한 오류는 응답 본문 형식이 다를 수 있습니다. 모든 오류가 하나의 JSON 형식을 갖는다고 보장하지 않습니다.

## curl로 확인

`finadmin/oauth-lab`에서 [Device 로그인](../../oauth-lab/RUNBOOK.md)을 먼저 합니다. 헤더 파일에 저장한 토큰은 약 60초의 짧은 수명입니다.

```sh
# ADMIN으로 발급했을 때 차례로 200, 400, 500
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/me
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/greeting
curl -i -H @.local/curl-header http://localhost:18090/oauth-admin/api/admin/demo-error

# USER로 다시 발급했을 때 두 경로 모두 200
curl -i -H @.local/curl-header http://localhost:18090/oauth-access/api/user/me
curl -i -H @.local/curl-header http://localhost:18100/api/user/me
```

`X-OAuth-Gateway: api7-enterprise`는 경유 응답, `X-Finlab-Backend`는 Spring 필터에 도달했음을 나타내는 실습용 표식입니다. Backend 헤더가 있다고 Controller가 성공한 것은 아닙니다. 헤더는 서버 신원을 암호학적으로 증명하는 인증 수단도 아닙니다.

근거: [AdminController](../../oauth-lab/src/main/java/io/github/greenapple0101/finadmin/oauth/AdminController.java), [SecurityConfig](../../oauth-lab/src/main/java/io/github/greenapple0101/finadmin/oauth/SecurityConfig.java), [FinAccess 코드](https://github.com/Greenapple0101/finaccess/tree/main/oauth-lab/src/main), [Gateway 역할 설정](05-api7-authorization.md).
