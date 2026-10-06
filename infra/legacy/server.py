"""JWT를 읽을 수 없는 기존 업무 서버를 흉내 내는, 읽기 전용 실습 서버입니다.

이 서버는 Keycloak을 모르고, JWT의 서명이나 사용자의 역할도 검사하지 않습니다.
바로 그 제약 때문에 Gateway가 먼저 인증과 역할 검사를 끝내야 합니다.

주의: 아래 헤더는 그 자체로 믿을 만한 증명서가 아닙니다. 아무나 이 서버에
직접 접속할 수 있으면 아무나 헤더를 위조할 수 있습니다. 따라서 이 서버는
Gateway와 연결된 전용 내부 네트워크에만 두고 호스트 포트를 공개하지 않습니다.
Gateway는 외부 요청에 들어 있던 신원 헤더를 지우고, 검증한 JWT의 값으로
새로 넣어 주어야 합니다. 이 신뢰 조건은 compose와 Gateway 설정이 담당합니다.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class LegacyHandler(BaseHTTPRequestHandler):
    """HTTP 요청을 받아 샘플 보고서만 돌려줍니다. 실제 금융 거래는 없습니다."""

    server_version = "FinLabLegacyDemo"
    sys_version = ""

    def _respond(self, status, payload, *, allow_get=False):
        # JSON을 문자열로 만든 뒤 UTF-8 바이트로 바꿉니다. Content-Length에는
        # 한글 글자 수가 아니라 실제로 보내는 바이트 수가 들어가야 합니다.
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Finlab-Backend", "legacy")
        if allow_get:
            self.send_header("Allow", "GET")
        self.end_headers()
        # HEAD는 본문을 받지 않는 HTTP 메서드입니다. 허용하지 않는 HEAD 요청에도
        # 405 상태와 헤더만 보내고 본문을 보내지 않아 HTTP 규칙을 지킵니다.
        if self.command != "HEAD":
            self.wfile.write(body)

    def _trusted_header(self, name):
        # 같은 이름의 헤더가 두 번 오면 어떤 값을 써야 할지 모호해집니다.
        # Gateway가 만든 값 하나만 받도록 중복·공백뿐인 값을 거절합니다.
        values = self.headers.get_all(name, [])
        if len(values) != 1:
            return None
        value = values[0].strip()
        return value if value else None

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            # 컨테이너가 살아 있는지 확인하는 경로입니다. 사용자·업무 정보는 없습니다.
            self._respond(200, {"status": "UP", "backend": "legacy"})
            return

        if path not in ("/api/reports", "/api/admin/summary"):
            self._respond(404, {"error": "not_found", "backend": "legacy"})
            return

        subject = self._trusted_header("X-Finlab-Subject")
        issuer = self._trusted_header("X-Finlab-Issuer")
        if subject is None or issuer is None:
            self._respond(401, {
                "error": "trusted_identity_required",
                "message": "Gateway가 전달한 신원 정보가 필요합니다.",
                "backend": "legacy",
            })
            return

        # 헤더 존재 확인은 JWT 검증이 아닙니다. 이 값이 진짜 사용자의 것인지는
        # Gateway와 네트워크 통제가 보장해야 합니다. 역할 검사도 여기에는 없습니다.
        # /api/admin/summary의 관리자 제한은 Gateway에서 먼저 수행합니다.
        response = {
            "backend": "legacy",
            "sampleData": True,
            "subject": subject,
            "issuer": issuer,
        }
        if path == "/api/reports":
            response["reports"] = [
                {"id": "sample-monthly", "title": "월간 업무 보고서 예시", "status": "READY"},
            ]
        else:
            response["summary"] = {"reportCount": 1, "pendingJobCount": 0}
        self._respond(200, response)

    def _method_not_allowed(self):
        # 실습 서버는 조회만 합니다. 저장·수정·삭제 요청은 처리하지 않습니다.
        self.close_connection = True
        self._respond(405, {"error": "method_not_allowed", "backend": "legacy"}, allow_get=True)

    do_POST = _method_not_allowed
    do_PUT = _method_not_allowed
    do_PATCH = _method_not_allowed
    do_DELETE = _method_not_allowed
    do_OPTIONS = _method_not_allowed
    do_HEAD = _method_not_allowed
    do_TRACE = _method_not_allowed
    do_CONNECT = _method_not_allowed

    def log_message(self, format, *args):
        # 기본 HTTP 로그는 요청 문자열을 출력합니다. 실수로 URL에 토큰을 넣어도
        # 남지 않도록 이 모의 서버의 요청 로그를 끕니다. 접근 추적은 Gateway에서 합니다.
        pass


def main():
    # 0.0.0.0은 컨테이너 내부에서 요청을 받겠다는 뜻입니다. 외부 공개 여부는
    # Docker의 ports/네트워크 설정이 정하므로, 레거시 서비스에는 ports를 추가하지 않습니다.
    port = int(os.environ.get("LEGACY_PORT", "8082"))
    server = ThreadingHTTPServer(("0.0.0.0", port), LegacyHandler)
    print(f"FinLab legacy sample server listening on {port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
