#!/usr/bin/env bash
# 같은 부모 폴더의 finaccess와 finadmin을 빌드한 뒤, 실습 전체를 시작합니다.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/init-local.py
# 라이선스가 활성화된 실제 API7 Control Plane과 DP 등록 정보가 먼저 필요합니다.
python3 scripts/setup-api7.py
test -f .local/api7/gateway.env
test -f .local/api7/apisix.uid
docker network inspect api7-ee_api7 >/dev/null
(cd ../finaccess && ./gradlew bootJar)
./gradlew bootJar
docker compose up -d --build --wait --wait-timeout 180
python3 -c "import sys; sys.path.insert(0, 'scripts'); from verify import ISSUER, wait_ready; wait_ready(ISSUER + '/.well-known/openid-configuration')"
python3 scripts/setup-gateway-rbac.py
python3 scripts/setup-api7.py --apply --start
python3 scripts/verify.py
# 원래 내부 계정 검증을 마친 뒤, 외부 직원 명부와 그룹 역할을 연결합니다.
python3 scripts/setup-ldap.py
python3 scripts/verify-ldap.py

# Gateway·백엔드·레거시에서 같은 역할 규칙을 적용했는지 확인합니다.
python3 scripts/verify-gateway-rbac.py
