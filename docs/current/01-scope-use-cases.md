# 현재 범위와 유즈케이스

[문서 목차](../README.md) · 기준: 2026-10-16

**Keycloak 자체 계정으로 로그인하고, 발급된 Access Token을 API7과 Spring이 각각 검증하여 USER·ADMIN API 접근을 제한하는 OAuth2 PoC입니다.**

## 등장인물과 역할

| 주체 | 실제 예 | 하는 일 |
|---|---|---|
| 일반 사용자 | alice / USER | FinAccess에서 로그인 후 자기 토큰 정보 조회 |
| 관리자 역할 사용자 | admin / ADMIN | CLI로 토큰을 받아 FinAdmin API 호출 |
| 인증 서버 | Keycloak oauth-lab Realm | 계정·비밀번호·역할 관리, 사용자 인증, 토큰 발급 |
| API Gateway | API7 Enterprise | 경로·메서드 선택, JWT·역할 검사, 백엔드 전달 |
| Resource Server | FinAccess, FinAdmin | JWT·역할 재검증 후 API 응답 |
| 제품 설정 운영자 | API7·Keycloak 관리 콘솔 사용자 | 제품 설정 관리. 앱의 ADMIN 역할과 별도 |

FinAccess는 화면과 USER API를 제공합니다. FinAdmin은 ADMIN API를 제공하며 별도 사용자 화면은 없습니다. 두 앱 모두 금융 업무나 전체 시스템의 권한 관리 기능은 구현하지 않습니다.

## 유즈케이스

| ID | 누가·무엇을 | 성공 흐름 | 실패·비교 흐름 |
|---|---|---|---|
| UC-01 | USER의 브라우저 API 호출 | 18100 화면 → Keycloak Code+PKCE → API7 → FinAccess 200 | 토큰 없으면 401, ADMIN만 있으면 403 |
| UC-02 | ADMIN의 curl 호출 | Device Grant → Keycloak 승인 → API7 → FinAdmin 200 | USER 토큰이면 403 |
| UC-03 | 백엔드 자체 검사 | 같은 토큰으로 18100·18101 직접 호출 | 잘못된 토큰·역할을 Spring도 거절 |
| UC-04 | JWT 위조·만료 확인 | 토큰 복사본 변조와 실제 만료를 각각 시험 | 서명 변조·만료 모두 401 |
| UC-05 | HTTP 오류 구분 | ADMIN greeting 정상 입력 200 | 입력 오류 400, 시연 예외 500 |
| UC-06 | API7 정책 실습 | 제품 UI에서 Route 확인·수정 → curl → 복원 | 수정 전후 요청·응답 비교 |

## 구현 범위

- 인증: Code + PKCE, Device Grant, 수동 Refresh.
- 인가: 공통 audience `oauth-api`, 서로 독립적인 USER·ADMIN 역할, API7·Spring의 중복 검사.
- 응답: 사용자 식별자와 역할 확인, 간단한 입력 검증과 오류 시연.
- 미구현: 금융 업무·업무 DB·JPA·SCIM 운영자 생성·기존 JWT 즉시 폐기·고가용성·부하 검증·AI 모델 호출.

두 Spring·Keycloak은 JVM 프로그램이며 API7 제품과 관리 DB는 Docker에서 실행합니다. 제공된 Python 시작 도구는 macOS용입니다. 실제 재실행한 범위는 [검증 기록](06-verification.md)에 구분합니다.

[아키텍처·시퀀스](02-architecture.md) · [API 명세](03-api-spec.md) · [실행·시연](../../oauth-lab/RUNBOOK.md)
