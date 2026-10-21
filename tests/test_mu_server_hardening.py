"""PR自检回归：慢连接不得无限占线程；认领与注册共用同一用户名规范化。"""
import socket
import time
import unittest
from unittest.mock import patch

import server
from game import legacy
from tests.mu_support import started_server


class SlowConnectionTests(unittest.TestCase):
    def test_handler_has_a_bounded_socket_timeout(self):
        self.assertIsNotNone(server.Handler.timeout)
        self.assertTrue(0 < server.Handler.timeout <= 60)

    def test_half_sent_body_connection_is_closed_by_the_server(self):
        with patch.object(server.Handler, 'timeout', 1):
            srv = started_server(live=True)
            try:
                host, port = srv.httpd.server_address[:2]
                sock = socket.create_connection((host, port), timeout=6)
                try:
                    sock.sendall(('POST /api/login HTTP/1.1\r\nHost: %s:%d\r\nX-Game-Client: guixu-web\r\n'
                                  'Content-Type: application/json\r\nContent-Length: 200\r\n\r\n{"user' % (host, port)).encode())
                    started = time.time()
                    try:
                        data = sock.recv(4096)
                    except (ConnectionError, socket.timeout) as exc:
                        data = exc
                    elapsed = time.time() - started
                finally:
                    sock.close()
                self.assertLess(elapsed, 5, '服务端应在套接字超时后释放连接')
                self.assertNotIsInstance(data, socket.timeout)
            finally:
                srv.stop()


class UsernameKeyTests(unittest.TestCase):
    def test_claim_lookup_uses_the_registration_key(self):
        srv = started_server()
        try:
            account_id = srv.app.auth.create_account('ＡliceＢob9', 'long-enough-pass')
            for spelled in ('aliceBOB9', ' ＡLICEbob9 ', 'ALICEBOB9'):
                self.assertEqual(legacy._resolve_account(srv.app.db, spelled), account_id, spelled)
            with self.assertRaises(legacy.LegacyError):
                legacy._resolve_account(srv.app.db, '')
        finally:
            srv.stop()


if __name__ == '__main__':
    unittest.main()
