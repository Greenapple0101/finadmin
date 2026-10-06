#!/usr/bin/env python3
"""격리 검사 전용: 공개 키를 제공하고, Gateway가 허용한 요청의 도착 여부만 기록합니다.

실제 Keycloak·업무 앱을 대신하는 시험용 서버입니다. 인증 기능을 흉내 내어 통과시키지
않습니다. JWT 검사는 실제 APISIX가 합니다. 이 서버에는 개인 키나 토큰을 저장하지 않습니다.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock

DIRECTORY = Path('/fixture')
RECEIVED = []
LOCK = Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # 기본 HTTP 로그 대신 아래의 제한된 항목만 메모리에 기록합니다.
        pass

    def handle_request(self):
        if self.path == '/discovery':
            value = json.loads((DIRECTORY / 'discovery.json').read_text())
        elif self.path == '/jwks':
            value = json.loads((DIRECTORY / 'jwks.json').read_text())
        elif self.path == '/fixture-stats':
            with LOCK:
                value = list(RECEIVED)
        else:
            length = int(self.headers.get('Content-Length', '0'))
            if length:
                self.rfile.read(length)
            # 토큰 원문을 내보내지 않고, 전달 여부와 필요한 신원 항목만 확인합니다.
            value = {
                'case': self.headers.get('X-Fixture-Case'),
                'method': self.command,
                'path': self.path,
                'authorizationPresent': 'Authorization' in self.headers,
                'subject': self.headers.get('X-Finlab-Subject'),
                'issuer': self.headers.get('X-Finlab-Issuer'),
                'roleHeaderPresent': 'X-Finlab-Roles' in self.headers,
                'extraIdentityHeaderPresent': any(name in self.headers for name in (
                    'X-Userinfo', 'X-ID-Token', 'X-Access-Token', 'X-Refresh-Token', 'X-Raw-ID-Token')),
            }
            with LOCK:
                RECEIVED.append(value)
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Fixture-Upstream', 'reached')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = handle_request


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
