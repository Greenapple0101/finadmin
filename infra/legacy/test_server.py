"""실제 HTTP 통신으로 레거시 서버의 경계를 확인합니다. 외부 서비스는 필요 없습니다."""

import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from server import LegacyHandler


class LegacyServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 포트 0은 운영체제가 비어 있는 포트를 골라 달라는 뜻입니다.
        # 테스트가 평소 실행 중인 FinLab의 포트를 빼앗지 않게 합니다.
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LegacyHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.identity = {
            "X-Finlab-Subject": "demo-subject",
            "X-Finlab-Issuer": "http://keycloak.example/realms/demo",
        }

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method="GET", path="/api/reports", headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            return response.status, dict(response.getheaders()), json.loads(body) if body else None
        finally:
            connection.close()

    def test_missing_or_blank_identity_is_rejected(self):
        cases = [
            {},
            {"X-Finlab-Subject": "demo-subject"},
            {"X-Finlab-Issuer": self.identity["X-Finlab-Issuer"]},
            {**self.identity, "X-Finlab-Subject": "   "},
            {**self.identity, "X-Finlab-Issuer": "   "},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                status, _, body = self.request(headers=headers)
                self.assertEqual(status, 401)
                self.assertEqual(body["error"], "trusted_identity_required")

    def test_bearer_token_alone_does_not_authenticate_this_legacy_server(self):
        status, _, body = self.request(headers={"Authorization": "Bearer intentionally-not-a-jwt"})
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "trusted_identity_required")

    def test_duplicate_identity_is_rejected(self):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        try:
            connection.putrequest("GET", "/api/reports")
            connection.putheader("X-Finlab-Subject", "first-user")
            connection.putheader("X-Finlab-Subject", "second-user")
            connection.putheader("X-Finlab-Issuer", self.identity["X-Finlab-Issuer"])
            connection.endheaders()
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 401)
        finally:
            connection.close()

    def test_report_returns_sample_data_and_supplied_identity_without_token(self):
        status, headers, body = self.request(headers={**self.identity, "Authorization": "Bearer not-reflected"})
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Finlab-Backend"], "legacy")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(body["sampleData"])
        self.assertEqual(body["backend"], "legacy")
        self.assertEqual(body["subject"], "demo-subject")
        self.assertEqual(body["issuer"], self.identity["X-Finlab-Issuer"])
        self.assertEqual(body["reports"][0]["id"], "sample-monthly")
        self.assertNotIn("not-reflected", json.dumps(body))

    def test_admin_sample_intentionally_depends_on_gateway_role_check(self):
        # 서버 자체가 관리자 권한을 검사한다고 오해하지 않게 경계를 드러내는 테스트입니다.
        # 역할 헤더 없이도 200이므로 Gateway 우회 차단은 반드시 통합 검증해야 합니다.
        status, _, body = self.request(path="/api/admin/summary", headers=self.identity)
        self.assertEqual(status, 200)
        self.assertTrue(body["sampleData"])
        self.assertEqual(body["summary"]["reportCount"], 1)

    def test_mutating_and_other_known_methods_are_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD", "TRACE", "CONNECT"):
            with self.subTest(method=method):
                status, headers, body = self.request(method=method, headers=self.identity)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET")
                if method == "HEAD":
                    self.assertIsNone(body)
                else:
                    self.assertEqual(body["error"], "method_not_allowed")

    def test_unknown_path_returns_no_business_data(self):
        status, _, body = self.request(path="/api/unknown", headers=self.identity)
        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not_found", "backend": "legacy"})

    def test_health_check_contains_no_identity_or_business_data(self):
        status, _, body = self.request(path="/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "UP", "backend": "legacy"})


if __name__ == "__main__":
    unittest.main()
