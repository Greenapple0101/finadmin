# FinAdmin · OAuth2 ADMIN API

현재 작업 브랜치는 **oauth-focus**입니다. 화면 없이 curl로 호출하는 관리자 API입니다. API7과 Spring이 JWT·ADMIN 역할을 각각 검사합니다.

**[현재 구성·코드: oauth-lab](oauth-lab/README.md)**

- USER와 ADMIN 두 역할, Keycloak OAuth2, 로컬 LDAP 연동
- FinAccess :18100 / FinAdmin :18101 / Keycloak :18180
- API7 Enterprise만 Docker 사용, 관리 UI :7443 / USER·ADMIN API 진입 :18090
- 업무 DB·JPA·금융 이체·ITSM·자동화 테스트를 새 실습에 포함하지 않음

[실행·시연 가이드](https://github.com/Greenapple0101/finadmin/blob/oauth-focus/oauth-lab/RUNBOOK.md) · [이번 검증 결과](https://github.com/Greenapple0101/finadmin/blob/oauth-focus/oauth-lab/RESULTS-2026-10-15.md)

과거 금융·ITSM 구현과 설명은 [main 브랜치](https://github.com/Greenapple0101/finadmin/tree/main)에 보관합니다. 이 브랜치에 남아 있는 루트의 과거 src·scripts·docs 대신 **oauth-lab 폴더만 실행**합니다.
