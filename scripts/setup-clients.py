#!/usr/bin/env python3
"""프런트·검증용 Keycloak Client를 저장소 설정에 맞춥니다. 사용자와 업무 DB는 유지합니다."""
from ldap_support import read_values
from verify import prepare_clients


if __name__ == '__main__':
    prepare_clients(read_values())
    print('프런트·검증용 Client의 로그인 주소·scope·mapper 설정을 적용했습니다.')
