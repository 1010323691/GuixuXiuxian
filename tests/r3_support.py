"""R3 harness with an injected server-side UTC clock.

No test-only HTTP route or client-supplied time is added to the application.
The production dispatch and Store receive a normal callable clock.
"""
import threading
import uuid

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
    def __init__(self, clock=None, live=False):
        super().__init__(clock=clock or Clock(), live=live)

    def create(self, mode=None, name='持续修炼QA'):
        # Deliberately bypass old free-mode helper: omission must test longline.
        payload = {'request_id': str(uuid.uuid4()),
                   'expected_revision': self.snapshot()['revision'], 'name': name}
        if mode is not None:
            payload['mode'] = mode
        status, body = self.request('POST', '/api/new-game', payload)
        assert status == 200, body
        return body
