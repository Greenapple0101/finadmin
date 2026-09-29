# 02. Keycloak을 실행하는 순서

이번 단계의 목적은 로그인과 토큰 발급을 맡을 서버를 준비하는 것입니다. Java API 두 개와 별도 프로세스입니다.

## 준비한 파일

- `compose.yaml`: Keycloak, Keycloak DB, FinAccess DB, 두 백엔드, 정적 화면, APISIX를 묶어 실행합니다.
- `infra/keycloak/finlab-realm.json`: 실습 영역, 클라이언트, 역할, 사용자를 처음 준비합니다.
- `scripts/init-local.py`: 무작위 비밀번호를 `.env`와 데스크탑 `finadmin-local-secrets.md`에 기록합니다.
- `.env.example`: 비밀값 없이 필요한 설정 이름만 공유합니다.

Docker Compose의 서비스 이름은 컨테이너 사이에서 주소로 사용됩니다. 그래서 앱에서 `keycloak`이나 `app-db`라는 이름으로 다른 컨테이너를 찾을 수 있습니다. 각 서버가 별도로 실행되지만 같은 실습 네트워크 안에서 통신합니다.

## 시작 방법

`finaccess`와 `finadmin` 저장소를 같은 부모 폴더에 둡니다. Java 21, Python 3, Docker Compose가 필요합니다. 처음에는 이미지를 내려받으므로 시간이 걸립니다.

```bash
cd /Users/baegseoyeon/Desktop/finadmin
./scripts/start.sh
```

이 명령은 비밀번호 준비 → 두 앱의 실행 JAR 만들기 → 컨테이너 시작 → 실제 로그인 및 API 검증 순서로 실행합니다. 검증은 가짜 회사·계좌·이체 데이터를 실습 DB에 추가합니다.

Keycloak만 먼저 보고 싶다면 다음 두 줄로 시작합니다.

```bash
python3 scripts/init-local.py
docker compose up -d keycloak-db keycloak
```

관리 화면은 <http://localhost:18080/admin/>입니다. 사용자 이름은 `bootstrap-admin`, 비밀번호는 데스크탑의 로컬 인증 문서에 있습니다. 이 계정은 Keycloak 관리용입니다. 앱의 `admin` 사용자와 다릅니다.

## 포트와 저장 공간

| 서버 | 내 컴퓨터 주소 | 역할 |
| --- | --- | --- |
| Keycloak | http://localhost:18080 | 로그인·토큰 발급·설정 화면 |
| APISIX 및 앱 화면 | http://localhost:18090 | 사용자 진입점 |
| FinAccess 직접 호출 | http://localhost:18082 | Gateway를 우회해도 JWT 검사가 되는지 검증 |
| FinAdmin 직접 호출 | http://localhost:18083 | 독립적인 JWT 검증·관리자 제한 확인 |

DB는 외부 포트를 열지 않았습니다. 모든 공개 실습 포트는 `127.0.0.1`에만 연결합니다. 운영 환경에서는 백엔드 직접 포트를 외부에 공개하지 않고 TLS, 비밀정보 관리, 백업·모니터링 등을 별도로 구성해야 합니다.

`finlab`이라는 별도 Compose 프로젝트와 전용 DB 볼륨을 사용합니다. 기존 FinAccess 개발 DB는 이 구성에 연결하지 않습니다. Keycloak은 개발 실행 모드(`start-dev`)와 PostgreSQL을 사용합니다. 이 구성을 운영 배포 완료로 표현하지 않습니다.

## 중지와 재시작

```bash
docker compose stop
docker compose up -d
```

앱 코드가 바뀌면 `./scripts/start.sh`로 JAR과 이미지를 다시 만듭니다. 이미 존재하는 Realm은 시작 시 JSON을 다시 읽어서 덮어쓰지 않습니다. `.env` 수정도 이미 저장된 비밀번호를 자동 변경하지 않습니다. 설정 변경은 관리 화면이나 명시적인 관리 API 작업으로 적용해야 합니다.

`docker compose down -v`는 DB 데이터까지 삭제하므로 일반적인 종료 명령으로 사용하지 않습니다.

## 참고

[Keycloak Docker 시작 문서](https://www.keycloak.org/getting-started/getting-started-docker), [Realm 가져오기](https://www.keycloak.org/server/importExport), [외부 주소와 내부 주소](https://www.keycloak.org/server/hostname)
