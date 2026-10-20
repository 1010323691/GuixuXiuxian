"""Isolated real-HTTP R3 harness with an injected server-side UTC clock.

No test-only HTTP route or client-supplied time is added to the application.
The running production Handler and Store receive a normal callable clock.
"""
from fractions import Fraction
import tempfile
import threading
import uuid
from pathlib import Path

from tests.support import Server


class Clock:
    def __init__(self, seconds=1_800_000_000):
        self.value = seconds
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def advance(self, seconds):
        with self.lock:
            self.value += seconds
            return self.value


class ClockHTTP(Server):
    def __init__(self, clock=None):
        super().__init__()
        self.clock = clock or Clock()
        self.httpd = None
        self.worker = None

    def start(self):
        from game.storage import Store
        from server import GameServer
        self.store = Store(self.data, clock=self.clock)
        self.httpd = GameServer(('127.0.0.1', 0), self.store)
        self.url = 'http://127.0.0.1:' + str(self.httpd.server_port)
        self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.worker.start()
        assert self.request('GET', '/api/health')[0] == 200
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.worker.join(timeout=5)
            self.httpd = None

    def create(self, mode=None, name='持续修炼QA'):
        # Deliberately bypass old free-mode helper: omission must test longline.
        payload = {'request_id': str(uuid.uuid4()),
                   'expected_revision': self.snapshot()['revision'], 'name': name}
        if mode is not None:
            payload['mode'] = mode
        status, body = self.request('POST', '/api/new-game', payload)
        assert status == 200, body
        return body
