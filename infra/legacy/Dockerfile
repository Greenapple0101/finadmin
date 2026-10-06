# Python 표준 라이브러리만 사용하므로 별도 패키지 설치가 필요하지 않습니다.
FROM python:3.13-slim
WORKDIR /app
COPY --chown=65532:65532 server.py /app/server.py
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEGACY_PORT=8082
# EXPOSE는 문서 역할이며 호스트에 포트를 공개하지 않습니다.
EXPOSE 8082
HEALTHCHECK --interval=10s --timeout=3s --start-period=3s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['LEGACY_PORT'] + '/healthz', timeout=2).close()"
CMD ["python", "/app/server.py"]
