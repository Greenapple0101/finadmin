# OpenLDAP 서버(slapd)와 명령 도구를 Debian 공식 패키지로 설치합니다.
# Intel Mac과 Apple Silicon에서 같은 Dockerfile을 사용할 수 있습니다.
FROM debian:trixie-slim
RUN echo 'slapd slapd/no_configuration boolean true' | debconf-set-selections \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends slapd ldap-utils python3 \
    && rm -rf /var/lib/apt/lists/*
COPY slapd.conf /opt/finlab/slapd.conf
COPY directory.py /opt/finlab/directory.py
ENTRYPOINT ["python3", "/opt/finlab/directory.py"]
