#!/usr/bin/env bash
# 같은 부모 폴더의 finaccess와 finadmin을 빌드한 뒤, 실습 전체를 시작합니다.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/init-local.py
(cd ../finaccess && ./gradlew bootJar)
./gradlew bootJar
docker compose up -d --build
python3 scripts/verify.py
