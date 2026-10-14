# API7 AI Gateway 기능 메모

2026-10-14 공식 문서 조사. 현재 설치는 API7 Enterprise **3.10.2**이며, 공식 문서는 **3.10.x의 더 최신 기능도 포함**합니다. 아래는 제품 기능 조사이며 이 PoC에서 LLM을 호출하거나 모든 기능을 검증했다는 뜻이 아닙니다.

AI Gateway는 앱과 모델 제공자 사이에서 요청을 받아 경로·접근·사용량을 관리합니다. 이번 API7 인증 실습을 확장한다면, Spring upstream 대신 모델 제공자 API로 전달하는 Route를 별도로 둘 수 있습니다. 기존 JWT 검증과 모델 제공자 API 키는 서로 다른 인증 정보입니다. [공식 개요](https://docs.api7.ai/api7-gateway/ai-gateway/overview).

| 기능 | 활용 예 | 관련 플러그인 |
|---|---|---|
| 모델 API 중계 | 앱에서 제공자마다 다른 연결 설정을 분산 관리하는 부담 감소 | ai-proxy |
| 여러 모델로 분산·대체 | 모델 오류·한도 초과 때 정한 대체 대상 사용 | ai-proxy-multi |
| 공통 프롬프트 | 공통 지침·템플릿을 Route에서 관리 | ai-prompt-decorator, ai-prompt-template |
| 입력 필터 | 정한 패턴이나 외부 검사 기준으로 요청 제한 | ai-prompt-guard, content moderation 계열 |
| 토큰 사용량 제한 | 호출 수와 별개로 모델 토큰 소비를 제한 | ai-rate-limiting |
| 관측 | 모델·토큰 사용량·첫 응답 시간을 기록 | AI proxy 로그·메트릭 |
| RAG·MCP 관련 기능 | 검색을 보완하거나 API를 에이전트 도구로 노출 | ai-rag, openapi-to-mcp |

위 항목은 최신 공식 개요의 기능 범위입니다. 비용 제한·필터가 모든 과금이나 유해 응답을 완벽히 막는다고 보장할 수는 없습니다. 로그에 프롬프트 원문을 남길지 별도 판단해야 합니다.

[AI Proxy Multi 공식 문서](https://docs.api7.ai/hub/ai-proxy-multi)는 가중치·우선순위·재시도·fallback과 제공자별 제약을 설명합니다. 프로토콜 변환도 모든 필드를 완벽히 바꾸는 방식이 아니라 지원 범위가 정해져 있습니다. 3.10.2에서 사용할 옵션은 해당 버전의 플러그인 schema·릴리스 노트와 라이선스를 먼저 확인해야 합니다.

현재 완료: API7의 일반 JWT·ACL·Route 기능 시연, AI 기능 문서 조사.
현재 미실행: 모델 API 키 등록, 유료 LLM 호출, AI 토큰 제한·fallback의 실제 부하 실험.

별도 제품인 AISIX AI Gateway와 API7 Enterprise의 AI 플러그인 기능을 혼동하지 않습니다. 이번 프로젝트는 API7 Enterprise를 유지합니다.
