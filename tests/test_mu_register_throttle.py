"""MU QA round 2: independent review of the registration-failure throttle (PRD A7 fix).

Checks the 409 contract, that locked sources never reach scrypt, per-source isolation, window recovery and
that successful registration / login are unaffected.
"""
import unittest
from unittest import mock

from tests.mu_support import Server, TestClock, test_settings

PASSWORD = 'tester-pass-1'
LIMIT = 4          # small, explicit threshold so the tests do not depend on the production default


class ThrottleCase(unittest.TestCase):
    def setUp(self):
        self.clock = TestClock()
        self.server = Server(clock=self.clock, settings=test_settings(register_fail_max_failures=LIMIT)).start()
        self.addCleanup(self.server.close)
        self.assertEqual(self.register('taken_name')[0], 200)

    def register(self, name, ip='10.0.0.1', password='some-pass-123'):
        return self.server.send('POST', '/api/register', {'username': name, 'password': password}, ip=ip)

    def exhaust(self, ip='10.0.0.1'):
        return [self.register('taken_name', ip=ip)[0] for _ in range(LIMIT)]


class ContractTests(ThrottleCase):
    def test_taken_name_still_returns_409_with_the_original_body_until_the_limit(self):
        for _ in range(LIMIT):
            status, body, _ = self.register('taken_name')
            self.assertEqual(status, 409)
            error = body['error']
            self.assertEqual((error['code'], error['field'], error['message']), ('USERNAME_TAKEN', 'username', '该用户名已被使用。'))
        status, body, _ = self.register('taken_name')
        self.assertEqual((status, body['error']['code']), (429, 'RATE_LIMITED'))

    def test_failures_below_the_limit_do_not_block_a_successful_registration_or_login(self):
        for _ in range(LIMIT - 1):
            self.assertEqual(self.register('taken_name')[0], 409)
        self.assertEqual(self.register('fresh_user')[0], 200)
        status, _, headers = self.server.send('POST', '/api/login', {'username': 'fresh_user', 'password': 'some-pass-123'}, ip='10.0.0.1')
        self.assertEqual(status, 200)
        self.assertTrue(headers['Set-Cookie'])

    def test_validation_errors_are_not_counted_as_failures(self):
        for _ in range(LIMIT * 3):
            self.assertEqual(self.register('x', password='short')[0], 400)
        self.assertEqual(self.register('fresh_user')[0], 200)

    def test_a_locked_source_can_still_log_in(self):
        self.exhaust()
        self.assertEqual(self.register('taken_name')[0], 429)
        status, _, _ = self.server.send('POST', '/api/login', {'username': 'taken_name', 'password': 'some-pass-123'}, ip='10.0.0.1')
        self.assertEqual(status, 200)


class IsolationAndRecoveryTests(ThrottleCase):
    def test_a_locked_source_does_not_affect_another_source(self):
        self.exhaust('10.0.0.1')
        self.assertEqual(self.register('taken_name', ip='10.0.0.1')[0], 429)
        self.assertEqual(self.register('taken_name', ip='10.0.0.2')[0], 409)
        self.assertEqual(self.register('other_user', ip='10.0.0.2')[0], 200)

    def test_the_lock_expires_after_the_lockout_period(self):
        self.exhaust()
        self.assertEqual(self.register('fresh_user')[0], 429)           # even a free name is refused while locked
        self.clock.advance(self.server.app.auth.settings.lockout_seconds + 1)
        self.assertEqual(self.register('fresh_user')[0], 200)

    def test_stale_failures_outside_the_window_do_not_accumulate(self):
        for _ in range(LIMIT - 1):
            self.assertEqual(self.register('taken_name')[0], 409)
        self.clock.advance(self.server.app.auth.settings.failure_window_seconds + 1)
        for _ in range(LIMIT - 1):                                       # counter restarted: still below the limit
            self.assertEqual(self.register('taken_name')[0], 409)


class NoKdfWhenLockedTests(ThrottleCase):
    def test_locked_source_never_reaches_scrypt(self):
        self.exhaust()
        hasher = self.server.app.auth.hasher
        with mock.patch.object(hasher, 'hash', wraps=hasher.hash) as spy:
            for name in ('taken_name', 'fresh_user'):
                self.assertEqual(self.register(name)[0], 429)
            self.assertEqual(spy.call_count, 0)

    def test_unlocked_source_does_hash(self):
        hasher = self.server.app.auth.hasher
        with mock.patch.object(hasher, 'hash', wraps=hasher.hash) as spy:
            self.assertEqual(self.register('taken_name')[0], 409)
            self.assertEqual(spy.call_count, 1)


class ThresholdTests(unittest.TestCase):
    def test_production_default_threshold_and_ordering(self):
        from game.settings import Settings
        s = Settings()
        self.assertEqual(s.register_fail_max_failures, 10)
        self.assertGreaterEqual(s.register_fail_max_failures, s.login_max_failures)   # documented deviation: 10 vs PRD 5


if __name__ == '__main__':
    unittest.main()
