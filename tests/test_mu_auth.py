"""MU QA: authentication, sessions, rate limits and request guards (AC2-AC6, A1-A8, N1, N2).

Uses the production routing/auth code on temporary databases. Cheap scrypt (n=2**4) is used except in the
tests that deliberately check or time the default parameters.
"""
import hashlib
import io
import json
import logging
import sqlite3
import time
import unittest
from contextlib import redirect_stdout

import server as server_module
from game import admin
from game.settings import Settings
from tests.mu_support import Server, TestClock, post_action, post_new_game, state_of, test_settings

PASSWORD = 'tester-pass-1'


def real_session_settings(**overrides):
    """Production session lifetimes (7 days idle, 30 days absolute) with cheap hashing."""
    values = dict(session_idle_seconds=604800, session_absolute_seconds=2592000)
    values.update(overrides)
    return test_settings(**values)


class AuthTestCase(unittest.TestCase):
    settings = None

    def setUp(self):
        self.clock = TestClock()
        self.server = Server(clock=self.clock, settings=self.settings).start()
        self.addCleanup(self.server.close)

    def post(self, path, payload, headers=None, ip='127.0.0.1'):
        return self.server.send('POST', path, payload, headers, ip=ip)

    def login(self, username, password=PASSWORD, ip='127.0.0.1'):
        return self.post('/api/login', {'username': username, 'password': password}, ip=ip)

    def db_dump(self):
        conn = self.server.app.db.connect()
        try:
            return {t: conn.execute('SELECT * FROM %s' % t).fetchall() for t in ('accounts', 'sessions', 'login_attempts')}
        finally:
            conn.close()


class PasswordStorageTests(AuthTestCase):
    def test_ac3_password_and_token_are_not_stored_in_plaintext(self):
        status, body, headers = self.post('/api/register', {'username': 'alice_a', 'password': 'Sup3r-secret-pw'})
        self.assertEqual(status, 200)
        token = headers['Set-Cookie'][0].split(';')[0].split('=', 1)[1]
        self.post('/api/register', {'username': 'bob_b', 'password': 'Sup3r-secret-pw'})
        # force WAL content to be inspected as well as the main file
        raw = b''
        for suffix in ('', '-wal'):
            path = str(self.server.app.db.path) + suffix
            try:
                with open(path, 'rb') as stream:
                    raw += stream.read()
            except FileNotFoundError:
                pass
        self.assertNotIn(b'Sup3r-secret-pw', raw)
        self.assertNotIn(token.encode(), raw)
        self.assertNotIn(token, json.dumps(body))

    def test_ac3_salts_differ_and_hashes_differ_for_identical_passwords(self):
        self.post('/api/register', {'username': 'alice_a', 'password': 'same-password-1'})
        self.post('/api/register', {'username': 'bob_b', 'password': 'same-password-1'})
        rows = [r for r in self.db_dump()['accounts'] if r[1] in ('alice_a', 'bob_b')]
        self.assertEqual(len(rows), 2)
        salts, hashes = {bytes(r[5]) for r in rows}, {bytes(r[6]) for r in rows}
        self.assertEqual((len(salts), len(hashes)), (2, 2))
        for r in rows:
            self.assertEqual(r[3], 'scrypt')
            self.assertEqual((len(r[5]), len(r[6])), (16, 32))
            self.assertNotEqual(bytes(r[6]), b'same-password-1')

    def test_sessions_store_only_sha256_of_the_token(self):
        _, _, headers = self.post('/api/register', {'username': 'alice_a', 'password': PASSWORD})
        token = headers['Set-Cookie'][0].split(';')[0].split('=', 1)[1]
        self.assertGreaterEqual(len(token), 32)                      # >= 128 bits of url-safe randomness
        hashes = [r[1] for r in self.db_dump()['sessions']]
        self.assertIn(hashlib.sha256(token.encode()).hexdigest(), hashes)
        self.assertNotIn(token, hashes)
        # tokens are random per login
        _, _, again = self.login('alice_a')
        self.assertNotEqual(again['Set-Cookie'][0].split(';')[0], headers['Set-Cookie'][0].split(';')[0])

    def test_default_scrypt_parameters_are_recorded_with_each_hash(self):
        settings = Settings()
        self.assertEqual((settings.kdf_n, settings.kdf_r, settings.kdf_p), (2 ** 15, 8, 1))
        self.assertEqual(self.db_dump()['accounts'][0][4], 'n=16,r=8,p=1')     # test settings stored with the row

    def test_login_rehashes_when_parameters_are_raised(self):
        self.post('/api/register', {'username': 'alice_a', 'password': PASSWORD})
        stronger = server_module.App(self.server.data, settings=test_settings(kdf_n=2 ** 5), clock=self.clock)
        who, _ = stronger.auth.login('alice_a', PASSWORD, '127.0.0.1')
        self.assertEqual(who.username, 'alice_a')
        row = [r for r in self.db_dump()['accounts'] if r[1] == 'alice_a'][0]
        self.assertEqual(row[4], 'n=32,r=8,p=1')
        stronger.auth.login('alice_a', PASSWORD, '127.0.0.1')           # still verifies after the upgrade


class DefaultKdfTests(unittest.TestCase):
    def test_default_scrypt_cost_is_in_the_planned_range(self):
        from game.auth import PasswordHasher
        hasher = PasswordHasher(Settings())
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            params, salt, digest = hasher.hash('a-reasonable-passphrase')
            samples.append(time.perf_counter() - started)
        self.assertEqual(params, 'n=32768,r=8,p=1')
        self.assertTrue(hasher.verify('a-reasonable-passphrase', salt, digest, params))
        self.assertFalse(hasher.verify('a-reasonable-passphrasE', salt, digest, params))
        # N3 asks for roughly 0.1-0.3 s; keep a wide guard so slow CI machines do not flap.
        self.assertGreater(min(samples), 0.005)
        self.assertLess(min(samples), 3.0)


class CookieAttributeTests(unittest.TestCase):
    def cookie(self, settings):
        server = Server(settings=settings).start()
        self.addCleanup(server.close)
        _, _, headers = server.send('POST', '/api/register', {'username': 'alice_a', 'password': PASSWORD})
        return server, headers['Set-Cookie'][0]

    def test_plain_http_cookie_attributes(self):
        _, cookie = self.cookie(test_settings())
        parts = [p.strip() for p in cookie.split(';')]
        self.assertTrue(parts[0].startswith('guixu_session='))
        for attribute in ('HttpOnly', 'SameSite=Lax', 'Path=/'):
            self.assertIn(attribute, parts)
        self.assertTrue(any(p.startswith('Max-Age=') and int(p[8:]) > 0 for p in parts))
        self.assertNotIn('Secure', parts)
        self.assertFalse(any(p.lower().startswith('domain') for p in parts))

    def test_secure_mode_uses_host_prefix_secure_and_no_domain(self):
        server, cookie = self.cookie(test_settings(secure_cookies=True))
        parts = [p.strip() for p in cookie.split(';')]
        self.assertTrue(parts[0].startswith('__Host-guixu_session='))
        for attribute in ('Secure', 'HttpOnly', 'SameSite=Lax', 'Path=/'):
            self.assertIn(attribute, parts)
        self.assertFalse(any(p.lower().startswith('domain') for p in parts))
        # the plain cookie name is not honoured in secure mode
        token = parts[0].split('=', 1)[1]
        status, _, _ = server.send('GET', '/api/state', headers={'Cookie': 'guixu_session=' + token})
        self.assertEqual(status, 401)
        status, _, _ = server.send('GET', '/api/state', headers={'Cookie': '__Host-guixu_session=' + token})
        self.assertEqual(status, 200)

    def test_logout_clears_the_cookie(self):
        server, cookie = self.cookie(test_settings())
        token = cookie.split(';')[0].split('=', 1)[1]
        status, body, headers = server.send('POST', '/api/logout', {}, headers={'Cookie': 'guixu_session=' + token})
        self.assertEqual(status, 200)
        self.assertIn('Max-Age=0', headers['Set-Cookie'][0])
        self.assertTrue(headers['Set-Cookie'][0].startswith('guixu_session=;'))


class SessionLifetimeTests(AuthTestCase):
    settings = real_session_settings()

    def setUp(self):
        super().setUp()
        self.a = self.server.as_user('alice_a')

    def probe(self):
        return self.server.send('GET', '/api/state', headers={'Cookie': self.server.cookie_header(self.a.cookie)})

    def test_a4_idle_session_expires_after_7_days_with_session_expired(self):
        self.assertEqual(self.probe()[0], 200)
        self.clock.advance(7 * 86400 - 60)
        self.assertEqual(self.probe()[0], 200)                   # sliding renewal: touched at day 6.99
        self.clock.advance(7 * 86400 - 60)
        self.assertEqual(self.probe()[0], 200)                   # still alive because it was renewed
        self.clock.advance(7 * 86400 + 5)                         # idle past 7 days
        status, body, headers = self.probe()
        self.assertEqual((status, body['error']['code']), (401, 'SESSION_EXPIRED'))
        self.assertIn('Max-Age=0', headers['Set-Cookie'][0])

    def test_a4_absolute_limit_of_30_days_cannot_be_extended_by_activity(self):
        day = 86400
        for _ in range(4):
            self.clock.advance(6 * day)
            self.assertEqual(self.probe()[0], 200)
        self.clock.advance(6 * day)                                # day 30 reached
        status, body, _ = self.probe()
        self.assertEqual((status, body['error']['code']), (401, 'SESSION_EXPIRED'))

    def test_ac4_expires_at_in_the_past_returns_401_session_expired(self):
        conn = self.server.app.db.connect()
        try:
            conn.execute('UPDATE sessions SET expires_at=?', (self.clock() - 1,))
        finally:
            conn.close()
        status, body, _ = self.probe()
        self.assertEqual((status, body['error']['code']), (401, 'SESSION_EXPIRED'))
        self.assertNotIn('state', body)
        # writes with an expired session are rejected as well and change nothing
        status, body, _ = self.server.send('POST', '/api/new-game', {'request_id': 'e1', 'expected_revision': 0, 'name': 'x', 'mode': 'free'},
                                           headers={'Cookie': self.server.cookie_header(self.a.cookie)})
        self.assertEqual((status, body['error']['code']), (401, 'SESSION_EXPIRED'))

    def test_session_row_deadlines_match_settings(self):
        rows = self.db_dump()['sessions']
        row = [r for r in rows if r[2] == self.a.user_id][0]
        created, idle, absolute = row[3], row[5], row[6]
        self.assertEqual(idle - created, 604800)
        self.assertEqual(absolute - created, 2592000)

    def test_session_cap_per_account_drops_the_oldest(self):
        cookies = [self.a.cookie]
        for _ in range(11):
            self.clock.advance(1)
            cookies.append(self.server.login('alice_a').cookie)
        alive = [self.server.send('GET', '/api/state', headers={'Cookie': self.server.cookie_header(c)})[0] == 200 for c in cookies]
        self.assertEqual(sum(alive), 10)
        self.assertFalse(alive[0])
        self.assertTrue(alive[-1])


class LoginRateLimitTests(AuthTestCase):
    settings = real_session_settings()

    def setUp(self):
        super().setUp()
        self.server.register('alice_a', PASSWORD)
        self.server.register('bob_b', PASSWORD)

    def test_ac5_five_failures_then_429_even_with_the_right_password(self):
        for attempt in range(5):
            status, body, _ = self.login('alice_a', 'wrong-password')
            self.assertEqual((status, body['error']['code']), (401, 'LOGIN_FAILED'), attempt)
        status, body, headers = self.login('alice_a', PASSWORD)
        self.assertEqual((status, body['error']['code']), (429, 'RATE_LIMITED'))
        self.assertEqual(int(headers['Retry-After'][0]), body['error']['retry_after'])
        self.assertTrue(0 < body['error']['retry_after'] <= 300)
        self.assertNotIn('Set-Cookie', headers)
        # another account from the same address is not locked by alice's failures
        self.assertEqual(self.login('bob_b')[0], 200)

    def test_ac5_lock_expires_after_five_minutes(self):
        for _ in range(5):
            self.login('alice_a', 'wrong-password')
        self.clock.advance(299)
        self.assertEqual(self.login('alice_a')[0], 429)
        self.clock.advance(2)
        self.assertEqual(self.login('alice_a')[0], 200)

    def test_ac5_unknown_user_and_wrong_password_are_indistinguishable(self):
        s1, b1, h1 = self.login('alice_a', 'wrong-password')
        s2, b2, h2 = self.login('nobody_here', 'wrong-password')
        self.assertEqual((s1, b1), (s2, b2))
        self.assertEqual(sorted(h1), sorted(h2))
        # the lockout also triggers for names that do not exist (no enumeration through 429)
        for _ in range(4):
            self.login('nobody_here', 'wrong-password')
        self.assertEqual(self.login('nobody_here', 'wrong-password')[0], 429)
        self.assertEqual(self.login('ghost_user', 'x')[0], 401)

    def test_success_clears_the_counter(self):
        for _ in range(4):
            self.login('alice_a', 'wrong-password')
        self.assertEqual(self.login('alice_a')[0], 200)
        for _ in range(4):
            self.login('alice_a', 'wrong-password')
        self.assertEqual(self.login('alice_a')[0], 200)

    def test_malformed_credentials_are_login_failures_not_server_errors(self):
        for payload in ({'username': None, 'password': PASSWORD}, {'username': 123, 'password': PASSWORD},
                        {'username': 'alice_a', 'password': None}, {'username': 'alice_a', 'password': ['x']},
                        {'username': 'alice_a', 'password': 'x' * 5000}, {'username': 'a' * 5000, 'password': 'x'}):
            status, body, _ = self.post('/api/login', payload)
            self.assertIn(status, (401, 429, 400), (payload, body))
            self.assertNotEqual(status, 500)

    def test_password_change_attempts_are_rate_limited_too(self):
        a = self.server.known['alice_a']
        for _ in range(5):
            status, body = a.request('POST', '/api/password', {'old_password': 'nope-nope-1', 'new_password': 'another-pass-2'})
            self.assertEqual((status, body['error']['code']), (400, 'OLD_PASSWORD_INCORRECT'))
        status, body = a.request('POST', '/api/password', {'old_password': PASSWORD, 'new_password': 'another-pass-2'})
        self.assertEqual((status, body['error']['code']), (429, 'RATE_LIMITED'))


class RegistrationTests(AuthTestCase):
    settings = test_settings(register_per_ip_hour=3)

    def register(self, username, password=PASSWORD, ip='127.0.0.1'):
        return self.post('/api/register', {'username': username, 'password': password}, ip=ip)

    def test_ac2_register_then_login_and_case_insensitive_duplicate(self):
        self.assertEqual(self.register('Alice_A')[0], 200)
        self.assertEqual(self.login('Alice_A')[0], 200)
        self.assertEqual(self.login('alice_a')[0], 200)               # case-insensitive login
        for variant in ('alice_a', 'ALICE_A', 'Alice_a'):
            status, body, _ = self.register(variant)
            self.assertEqual((status, body['error']['code']), (409, 'USERNAME_TAKEN'), variant)
        count = sum(1 for r in self.db_dump()['accounts'] if r[2].startswith('alice_a'))
        self.assertEqual(count, 1)

    def test_nfkc_lookalikes_collide_with_existing_names(self):
        self.assertEqual(self.register('alice_a')[0], 200)
        status, body, _ = self.register('ａｌｉｃｅ＿ａ')                # full-width forms normalise to alice_a
        self.assertEqual((status, body['error']['code']), (409, 'USERNAME_TAKEN'))
        status, body, _ = self.login('ａｌｉｃｅ＿ａ')                    # and log in as the same account
        self.assertEqual(status, 200)
        self.assertEqual(body['account']['username'], 'alice_a')

    def test_chinese_usernames_and_nfkc_for_cjk_compatibility_forms(self):
        self.assertEqual(self.register('归墟修行者')[0], 200)
        status, body, _ = self.register('归墟修行者')
        self.assertEqual(status, 409)

    def test_username_and_password_validation(self):
        bad_names = ['ab', 'a' * 21, 'bad name', 'bad-name', 'x!yz', '😀😀😀', '', ' ', 'a\nb', None, 12345, ['abc']]
        for name in bad_names:
            with self.subTest(name=name):
                status, body, _ = self.register(name)
                self.assertEqual((status, body['error']['code']), (400, 'INVALID_USERNAME'))
                self.assertEqual(body['error']['field'], 'username')
        for password in ('short7!', 'x' * 65, '', None, 12345678, 'abc\u0000defgh', 'new\nline-pass'):
            with self.subTest(password=password):
                status, body, _ = self.register('valid_name', password)
                self.assertEqual((status, body['error']['code']), (400, 'INVALID_PASSWORD'))
                self.assertEqual(body['error']['field'], 'password')
        self.assertEqual(self.register('valid_name', 'x' * 64)[0], 200)
        self.assertEqual(self.register('valid_nam2', 'x' * 8)[0], 200)
        status, body, _ = self.register('same_as_pw1', 'same_as_pw1')
        self.assertEqual((status, body['error']['code']), (400, 'INVALID_PASSWORD'))

    def test_registration_is_rate_limited_per_address(self):
        for index in range(3):
            self.assertEqual(self.register('player_%d' % index, ip='10.0.0.7')[0], 200)
        status, body, headers = self.register('player_9', ip='10.0.0.7')
        self.assertEqual((status, body['error']['code']), (429, 'RATE_LIMITED'))
        self.assertIn('Retry-After', headers)
        self.assertEqual(self.register('player_9', ip='10.0.0.8')[0], 200)


class ConcurrentAccountTests(unittest.TestCase):
    def test_parallel_registration_of_one_name_creates_one_account_and_no_500(self):
        import threading
        server = Server(settings=test_settings(register_per_ip_hour=10 ** 6)).start()
        self.addCleanup(server.close)
        barrier, results = threading.Barrier(8), []

        def attempt(index):
            barrier.wait(10)
            results.append(server.send('POST', '/api/register', {'username': 'racer_one', 'password': 'racer-pass-%d' % index})[:2])

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join(60) for t in threads]
        statuses = sorted(status for status, _ in results)
        self.assertEqual(statuses, [200] + [409] * 7, results)
        self.assertTrue(all(body['error']['code'] == 'USERNAME_TAKEN' for status, body in results if status == 409))
        conn = server.app.db.connect()
        try:
            self.assertEqual(conn.execute("SELECT count(*) FROM accounts WHERE username_key='racer_one'").fetchone()[0], 1)
        finally:
            conn.close()

    def test_parallel_wrong_passwords_lock_exactly_at_the_limit_without_errors(self):
        import threading
        server = Server(settings=test_settings()).start()
        self.addCleanup(server.close)
        server.register('lock_target', PASSWORD)
        barrier, results = threading.Barrier(12), []

        def attempt(_):
            barrier.wait(10)
            results.append(server.send('POST', '/api/login', {'username': 'lock_target', 'password': 'wrong-password'})[0])

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(12)]
        [t.start() for t in threads]
        [t.join(60) for t in threads]
        self.assertTrue(set(results) <= {401, 429}, results)
        self.assertGreaterEqual(results.count(401), 1)
        status, body, _ = server.send('POST', '/api/login', {'username': 'lock_target', 'password': PASSWORD})
        self.assertEqual(status, 429, 'account must be locked after a burst of parallel failures')


class RegistrationFailureThrottleTests(AuthTestCase):
    """PRD A7: login AND registration need a failure throttle (5 consecutive failures -> 429)."""
    settings = test_settings(register_per_ip_hour=10 ** 6)

    def test_a7_repeated_failed_registrations_from_one_source_are_throttled(self):
        self.server.register('taken_name', PASSWORD)
        statuses = [self.post('/api/register', {'username': 'taken_name', 'password': 'some-pass-123'})[0] for _ in range(12)]
        self.assertIn(429, statuses, 'registration failures (USERNAME_TAKEN) are never throttled: %s' % statuses)
        self.assertEqual(statuses[:5], [409] * 5)


class RegistrationClosedTests(unittest.TestCase):
    def test_no_register_blocks_signup_but_allows_operator_created_accounts(self):
        server = Server(settings=test_settings(registration_open=False))
        self.addCleanup(server.close)
        server.app = server._make_app()                     # start() would auto-register the default account
        status, body, _ = server.send('POST', '/api/register', {'username': 'newcomer', 'password': PASSWORD})
        self.assertEqual((status, body['error']['code']), (403, 'REGISTRATION_CLOSED'))
        health = server.send('GET', '/api/health')[1]
        self.assertIs(health['registration_open'], False)
        self.assertIs(server.send('GET', '/api/session')[1]['registration_open'], False)
        answers = iter([PASSWORD, PASSWORD])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(admin.create_user(server.app, 'operator_made', lambda prompt: next(answers)), 0)
        status, body, _ = server.send('POST', '/api/login', {'username': 'operator_made', 'password': PASSWORD})
        self.assertEqual(status, 200)
        self.assertEqual(server.send('POST', '/api/register', {'username': 'newcomer', 'password': PASSWORD})[0], 403)


class ChangeAndResetPasswordTests(AuthTestCase):
    def test_ac6_old_password_stops_working_new_one_works(self):
        a = self.server.register('alice_a', PASSWORD)
        status, body = a.request('POST', '/api/password', {'old_password': PASSWORD, 'new_password': 'brand-new-pass-3'})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.login('alice_a', PASSWORD)[0], 401)
        self.assertEqual(self.login('alice_a', 'brand-new-pass-3')[0], 200)

    def test_change_password_validation(self):
        a = self.server.register('alice_a', PASSWORD)
        status, body = a.request('POST', '/api/password', {'old_password': 'wrong-wrong-1', 'new_password': 'brand-new-pass-3'})
        self.assertEqual((status, body['error']['code'], body['error']['field']), (400, 'OLD_PASSWORD_INCORRECT', 'old_password'))
        for new in ('short', 'x' * 65, 'alice_a', None, 123):
            status, body = a.request('POST', '/api/password', {'old_password': PASSWORD, 'new_password': new})
            self.assertEqual((status, body['error']['code'], body['error']['field']), (400, 'INVALID_PASSWORD', 'new_password'), new)
        self.assertEqual(self.login('alice_a', PASSWORD)[0], 200)      # nothing changed

    def test_password_endpoint_requires_a_session(self):
        self.server.register('alice_a', PASSWORD)
        status, body = self.server.raw_request('POST', '/api/password', {'old_password': PASSWORD, 'new_password': 'brand-new-pass-3'})
        self.assertEqual(status, 401)
        self.assertEqual(self.login('alice_a', PASSWORD)[0], 200)

    def test_operator_reset_revokes_every_session_and_lock(self):
        a = self.server.register('alice_a', PASSWORD)
        second = self.login('alice_a')
        for _ in range(5):
            self.login('alice_a', 'wrong-password')
        answers = iter(['reset-pass-77', 'reset-pass-77'])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(admin.reset_password(self.server.app, 'alice_a', lambda p: next(answers)), 0)
        self.assertIn('已失效', buffer.getvalue())
        self.assertEqual(state_of(a)[0], 401)
        self.assertEqual(self.login('alice_a', 'reset-pass-77')[0], 200)      # lock cleared too
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(admin.reset_password(self.server.app, 'nobody_x', lambda p: 'x'), 1)
        self.assertIn('账号不存在', buffer.getvalue())

    def test_operator_mismatched_confirmation_is_refused(self):
        answers = iter(['first-password-1', 'other-password-2'])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = admin.run(type('A', (), dict(create_user='new_one', reset_password=None, migrate_multiuser=False, claim_legacy=None,
                                                 legacy_status=False, backup=False, force=False, migrate_data=False, data_dir=''))(),
                             self.server.app, lambda p: next(answers))
        self.assertEqual(code, 1)
        self.assertIsNone(self.server.app.auth.find_account('new_one'))


class RequestGuardTests(unittest.TestCase):
    """Host / Origin / X-Game-Client / content-type checks, run through dispatch_full with explicit headers."""

    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.cookie = self.server.cookie_header(self.a.cookie)
        self.body = json.dumps({'request_id': 'g1', 'expected_revision': 0, 'name': '甲', 'mode': 'free'}).encode()

    def call(self, method='POST', path='/api/new-game', settings=None, **overrides):
        headers = {'Host': '127.0.0.1:8000', 'Cookie': self.cookie, 'Content-Type': 'application/json',
                   'Content-Length': str(len(self.body)), 'X-Game-Client': 'guixu-web', 'Origin': 'http://127.0.0.1:8000'}
        for key, value in overrides.items():
            name = key.replace('_', '-')
            if value is None:
                headers.pop(name, None)
            else:
                headers[name] = value
        app = self.server.app
        status, data, _, out = server_module.dispatch_full(app, method, path, headers, self.body if method == 'POST' else b'', ('127.0.0.1', 8000))
        return status, json.loads(data)

    def test_baseline_request_is_accepted(self):
        self.assertEqual(self.call()[0], 200)

    def test_missing_or_wrong_game_client_header_is_forbidden(self):
        for value in (None, '', 'other', 'GUIXU-WEB'):
            status, body = self.call(X_Game_Client=value)
            self.assertEqual((status, body['error']['code']), (403, 'FORBIDDEN_ORIGIN'), value)

    def test_foreign_origin_is_forbidden(self):
        for origin in ('http://evil.example.com', 'https://127.0.0.1:8000', 'null', 'http://127.0.0.1:9999', 'http://localhost:8000'):
            status, body = self.call(Origin=origin)
            self.assertEqual((status, body['error']['code']), (403, 'FORBIDDEN_ORIGIN'), origin)

    def test_forged_host_is_forbidden_for_get_and_post(self):
        for host in ('evil.example.com', '127.0.0.1:9999', 'evil.example.com:8000', '', 'user@127.0.0.1:8000', '127.0.0.1:8000/x'):
            for method, path in (('GET', '/api/health'), ('GET', '/api/state'), ('POST', '/api/new-game')):
                status, body = self.call(method, path, Host=host, Origin=None if host == '' else 'http://' + host)
                self.assertEqual((status, body['error']['code']), (403, 'FORBIDDEN_ORIGIN'), (host, path))

    def test_non_json_content_type_and_bad_bodies_are_400(self):
        for ctype in ('text/plain', 'application/x-www-form-urlencoded', None):
            status, body = self.call(Content_Type=ctype)
            self.assertEqual((status, body['error']['code']), (400, 'BAD_REQUEST'), ctype)
        original = self.body
        try:
            for raw in (b'{', b'[]', b'"x"', b'{"a":NaN}', b'{"a":Infinity}', b'\xff\xfe', b'x' * 20000):
                self.body = raw
                status, body = self.call(Content_Length=str(len(raw)))
                self.assertEqual((status, body['error']['code']), (400, 'BAD_REQUEST'), raw[:10])
        finally:
            self.body = original

    def test_unknown_methods_and_paths(self):
        self.assertEqual(self.call('PUT')[0], 405)
        self.assertEqual(self.call('DELETE')[0], 405)
        self.assertEqual(self.call('POST', '/api/nope')[0], 404)
        self.assertEqual(self.call('GET', '/api/nope')[0], 404)

    def test_save_and_load_are_retired(self):
        for method in ('GET', 'POST'):
            for path in ('/api/save', '/api/load'):
                status, body = self.call(method, path)
                self.assertEqual(status, 404, (method, path, body))
        status, body = self.call('POST', '/api/save')
        self.assertEqual(body['error']['code'], 'NOT_FOUND')

    def test_extra_allowed_hosts_and_secure_origins(self):
        server = Server(settings=test_settings(allowed_hosts=('game.example.com',), secure_cookies=True)).start()
        self.addCleanup(server.close)
        a = server.as_user('alice_a')
        headers = {'Host': 'game.example.com', 'Cookie': server.cookie_header(a.cookie), 'Content-Type': 'application/json',
                   'X-Game-Client': 'guixu-web', 'Origin': 'https://game.example.com'}
        payload = json.dumps({'request_id': 'h1', 'expected_revision': 0, 'name': '甲', 'mode': 'free'}).encode()
        headers['Content-Length'] = str(len(payload))
        status, data, _, _ = server_module.dispatch_full(server.app, 'POST', '/api/new-game', headers, payload, ('127.0.0.1', 8000))
        self.assertEqual(status, 200, data)
        headers['Origin'] = 'https://evil.example.com'
        self.assertEqual(server_module.dispatch_full(server.app, 'POST', '/api/new-game', headers, payload, ('127.0.0.1', 8000))[0], 403)
        headers['Host'] = 'other.example.com'
        headers['Origin'] = 'https://other.example.com'
        self.assertEqual(server_module.dispatch_full(server.app, 'GET', '/api/health', headers, b'', ('127.0.0.1', 8000))[0], 403)

    def test_proxy_header_ignored_unless_trust_proxy(self):
        headers = {'X-Forwarded-For': '9.9.9.9, 8.8.8.8'}
        self.assertEqual(server_module.client_ip_of(headers, '127.0.0.1', Settings()), '127.0.0.1')
        self.assertEqual(server_module.client_ip_of(headers, '127.0.0.1', Settings(trust_proxy=True)), '8.8.8.8')


class SecretsNotLoggedTests(unittest.TestCase):
    """D5/A3: passwords and tokens never reach server logs; responses carry no other account's identity."""

    def test_live_http_session_logs_contain_no_secret(self):
        server = Server(live=True).start()
        self.addCleanup(server.close)
        previous = logging.root.manager.disable
        logging.disable(logging.NOTSET)
        self.addCleanup(logging.disable, previous)
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers, root.level = [handler], logging.DEBUG       # capture only; keep the test run's output quiet

        def restore():
            root.handlers, root.level = saved_handlers, saved_level

        self.addCleanup(restore)
        secret = 'Top-Secret-Pw-42'
        client = server.register('logger_a', secret)
        token = client.cookie
        server.send('POST', '/api/login', {'username': 'logger_a', 'password': 'bad-password-1'})
        post_new_game(client, name='日志甲')
        with server.fail_commit('before'):          # exercises the logging.exception path of a failed write
            post_action(client, 'explore')
        server.send('GET', '/api/state', headers={'Cookie': 'guixu_session=' + token})
        server.send('POST', '/api/login', {'username': 'logger_a', 'password': secret})
        logged = stream.getvalue()
        self.assertGreater(len(logged), 0, 'no log lines captured; the check would be vacuous')
        for secret_text in (secret, 'bad-password-1', token):
            self.assertNotIn(secret_text, logged)


if __name__ == '__main__':
    unittest.main()
