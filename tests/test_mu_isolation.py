"""MU QA: multi-account isolation (AC1, AC2, AC7, AC8, AC9) and the SQL isolation scan (design B-3).

Real routing code (server.dispatch_full) on a temporary data directory; no mocks of auth or storage.
"""
import ast
import json
import re
import unittest

from game import storage
from game.storage import Database, ProgressRepo, Store
from tests.mu_support import (ROOT, Server, post_action, post_new_game, read_progress, revision_of, state_of)

FORBIDDEN_LEAK_KEYS = ('state', 'view', 'sync', 'revision', 'events')


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')

    # ---------------------------------------------------------------- AC1
    def test_ac1_unauthenticated_progress_endpoints_are_401_without_data(self):
        post_new_game(self.a, name='甲机密名')
        payloads = [
            ('GET', '/api/state', None),
            ('POST', '/api/new-game', {'request_id': 'r1', 'expected_revision': 0, 'name': 'x', 'mode': 'free'}),
            ('POST', '/api/action', {'request_id': 'r2', 'expected_revision': 1, 'action': 'explore', 'params': {}}),
            ('POST', '/api/password', {'old_password': 'x' * 8, 'new_password': 'y' * 9}),
        ]
        for method, path, payload in payloads:
            with self.subTest(path=path):
                status, body = self.server.raw_request(method, path, payload)
                self.assertEqual(status, 401, body)
                self.assertFalse(body['ok'])
                for key in FORBIDDEN_LEAK_KEYS:
                    self.assertNotIn(key, body)
                self.assertNotIn('甲机密名', json.dumps(body, ensure_ascii=False))
                self.assertNotIn('alice_a', json.dumps(body))

    def test_ac1_health_and_session_endpoints_return_no_user_data(self):
        post_new_game(self.a, name='甲机密名')
        for path in ('/api/health', '/api/session'):
            status, body = self.server.raw_request('GET', path)
            self.assertEqual(status, 200)
            text = json.dumps(body, ensure_ascii=False)
            self.assertNotIn('甲机密名', text)
            self.assertNotIn('alice_a', text)
            for key in FORBIDDEN_LEAK_KEYS:
                self.assertNotIn(key, body)

    def test_unauthenticated_write_does_not_create_progress(self):
        self.server.raw_request('POST', '/api/new-game', {'request_id': 'x1', 'expected_revision': 0, 'name': 'n', 'mode': 'free'})
        conn = self.server.app.db.connect()
        try:
            self.assertEqual(conn.execute('SELECT count(*) FROM requests WHERE request_id=?', ('x1',)).fetchone()[0], 0)
        finally:
            conn.close()

    # ---------------------------------------------------------------- AC7
    def test_ac7_accounts_progress_is_independent(self):
        status, body = post_new_game(self.a, name='AAA甲')
        self.assertEqual(status, 200, body)
        status, body = post_new_game(self.b, name='BBB乙')
        self.assertEqual(status, 200, body)
        b_before = state_of(self.b)[1]
        for _ in range(3):
            self.assertEqual(post_action(self.a, 'explore')[0], 200)
        self.assertEqual(state_of(self.b)[1], b_before)
        a_state = state_of(self.a)[1]
        self.assertEqual(a_state['revision'], 4)
        self.assertEqual(b_before['revision'], 1)
        self.assertEqual(a_state['state']['actions_taken'], 3)
        self.assertEqual(b_before['state']['actions_taken'], 0)
        self.assertNotIn('BBB乙', json.dumps(a_state, ensure_ascii=False))
        self.assertNotIn('AAA甲', json.dumps(b_before, ensure_ascii=False))
        # B then acts differently; A is unaffected.
        a_after = state_of(self.a)[1]
        self.assertEqual(post_action(self.b, 'explore')[0], 200)
        self.assertEqual(state_of(self.a)[1], a_after)
        self.assertEqual(state_of(self.b)[1]['revision'], 2)

    def test_ac7_database_rows_belong_to_the_acting_account(self):
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')
        for _ in range(2):
            post_action(self.a, 'explore')
        post_action(self.b, 'explore')
        path = self.server.app.db.path
        ra, rb = read_progress(path, self.a.user_id), read_progress(path, self.b.user_id)
        self.assertEqual((ra[0], ra[2]), (3, 3))   # new-game + 2 actions
        self.assertEqual((rb[0], rb[2]), (2, 2))
        self.assertEqual(ra[1]['name'], 'AAA甲')
        self.assertEqual(rb[1]['name'], 'BBB乙')
        conn = self.server.app.db.connect()
        try:
            owners = {r[0] for r in conn.execute('SELECT user_id FROM requests')}
            self.assertEqual(owners, {self.a.user_id, self.b.user_id})
            self.assertEqual(conn.execute('SELECT count(*) FROM current').fetchone()[0], 2)  # rows are created lazily, only for a and b
        finally:
            conn.close()

    def test_new_accounts_start_empty(self):
        status, body = state_of(self.a)
        self.assertEqual(status, 200)
        self.assertIsNone(body['state'])
        self.assertEqual(body['revision'], 0)

    # ---------------------------------------------------------------- AC8
    def test_ac8_same_request_id_is_independent_per_account(self):
        self.assertEqual(post_new_game(self.a, name='AAA甲', request_id='shared-1')[0], 200)
        self.assertEqual(post_new_game(self.b, name='BBB乙', request_id='shared-1')[0], 200)
        sa, ba = post_action(self.a, 'explore', request_id='shared-2')
        sb, bb = post_action(self.b, 'gather', request_id='shared-2')
        self.assertEqual((sa, sb), (200, 200), (ba, bb))
        self.assertFalse(ba['duplicate'])
        self.assertFalse(bb['duplicate'])
        self.assertEqual((ba['revision'], bb['revision']), (2, 2))
        self.assertEqual(state_of(self.a)[1]['state']['actions_taken'], 1)
        self.assertEqual(state_of(self.b)[1]['state']['actions_taken'], 1)
        # A's replay is a duplicate for A only and does not touch B.
        b_state = state_of(self.b)[1]
        status, replay = post_action(self.a, 'explore', request_id='shared-2', revision=1)
        self.assertEqual(status, 200)
        self.assertTrue(replay['duplicate'])
        self.assertEqual(state_of(self.b)[1], b_state)

    def test_ac8_request_id_reuse_with_different_payload_is_only_an_error_inside_one_account(self):
        post_new_game(self.a, name='AAA甲', request_id='k1')
        post_new_game(self.b, name='BBB乙', request_id='other')
        status, body = post_action(self.a, 'explore', request_id='k1', revision=1)
        self.assertEqual((status, body['error']['code']), (409, 'REQUEST_ID_REUSED'))
        # B may use A's request_id for an unrelated action; no signal that A used it.
        status, body = post_action(self.b, 'explore', request_id='k1')
        self.assertEqual(status, 200, body)
        self.assertFalse(body['duplicate'])

    # ---------------------------------------------------------------- AC9
    def test_ac9_identity_fields_in_body_are_rejected(self):
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')
        before_a, before_b = state_of(self.a)[1], state_of(self.b)[1]
        for field in ('user_id', 'username', 'account', 'account_id', 'uid', 'owner'):
            for value in (self.b.user_id, 'bob_b'):
                with self.subTest(field=field, value=value):
                    s1, b1 = post_action(self.a, 'explore', **{field: value})
                    s2, b2 = post_new_game(self.a, name='x', **{field: value})
                    for status, body in ((s1, b1), (s2, b2)):
                        self.assertEqual(status, 400, body)
                        self.assertEqual(body['error']['code'], 'BAD_REQUEST')
        self.assertEqual(state_of(self.a)[1], before_a)
        self.assertEqual(state_of(self.b)[1], before_b)

    def test_ac9_auth_endpoints_reject_unknown_fields(self):
        anon = self.server.raw_request
        cases = [
            ('/api/login', {'username': 'alice_a', 'password': 'tester-pass-1', 'user_id': 2}),
            ('/api/register', {'username': 'newcomer1', 'password': 'tester-pass-1', 'user_id': 2}),
            ('/api/logout', {'user_id': 2}),
        ]
        for path, payload in cases:
            with self.subTest(path=path):
                status, body = anon('POST', path, payload, headers={'Cookie': self.server.cookie_header(self.a.cookie)})
                self.assertEqual(status, 400, body)
        status, body = self.a.request('POST', '/api/password', {'old_password': 'tester-pass-1', 'new_password': 'another-pass-2', 'user_id': 2})
        self.assertEqual(status, 400, body)
        self.assertIsNone(self.server.app.auth.find_account('newcomer1'))

    def test_ac9_query_string_and_headers_cannot_select_another_account(self):
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')
        for target in ('/api/state?user_id=%d' % self.b.user_id, '/api/state?username=bob_b', '/api/state?account=bob_b'):
            status, body = self.a.request('GET', target)
            self.assertEqual(status, 200)
            self.assertEqual(body['state']['name'], 'AAA甲')
            self.assertEqual(body['account']['username'], 'alice_a')
        status, body = self.a.request('GET', '/api/state', headers={'X-User-Id': str(self.b.user_id), 'X-Username': 'bob_b'})
        self.assertEqual(body['state']['name'], 'AAA甲')

    def test_ac9_no_route_addresses_another_account(self):
        for path in ('/api/users/%d/state' % self.b.user_id, '/api/user/%d' % self.b.user_id, '/api/legacy',
                     '/api/accounts', '/api/admin', '/api/users'):
            status, body = self.a.request('GET', path)
            self.assertEqual(status, 404, (path, body))

    def test_ac9_store_requires_a_valid_user_id(self):
        db = self.server.app.db
        for bad in ('1', 1.0, True, None, 0, -3, 2 ** 63):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Store(db, bad)
        with self.assertRaises(ValueError):
            Store(db, 987654).snapshot()   # no such account: foreign key refuses to create progress

    def test_progress_repo_refuses_statements_without_a_matching_user_id(self):
        db = self.server.app.db.connect()
        try:
            uid = self.a.user_id
            bad_calls = [
                ('SELECT * FROM current', (), uid),
                ('SELECT * FROM requests WHERE request_id=?', ('x',), uid),
                ('SELECT revision FROM current WHERE user_id=?', (self.b.user_id,), uid),   # parameter is another account
                ('SELECT revision FROM current WHERE user_id=?', (str(uid),), uid),           # wrong type
                ('SELECT revision FROM current WHERE user_id=?', (True,), 1),                 # bool is not int id
                ('SELECT revision FROM current WHERE user_id=?', (), uid),                    # unbound
            ]
            for sql, params, user_id in bad_calls:
                with self.subTest(sql=sql, params=params), self.assertRaises(AssertionError):
                    ProgressRepo._exec(db, sql, params, user_id)
            with self.assertRaises(AssertionError):
                ProgressRepo._exec(db, 'SELECT revision FROM current WHERE user_id=?', (uid,), str(uid))
            ProgressRepo._exec(db, 'SELECT revision FROM current WHERE user_id=?', (uid,), uid)   # the good case runs
        finally:
            db.close()


class SessionTamperTests(unittest.TestCase):
    """Cookie handling as an isolation boundary: forged, foreign, revoked and malformed tokens."""

    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')

    def get_state(self, cookie_header):
        return self.server.raw_request('GET', '/api/state', headers={'Cookie': cookie_header} if cookie_header is not None else {})

    def test_each_cookie_reads_only_its_own_account(self):
        self.assertEqual(state_of(self.a)[1]['state']['name'], 'AAA甲')
        self.assertEqual(state_of(self.b)[1]['state']['name'], 'BBB乙')
        self.assertNotEqual(self.a.cookie, self.b.cookie)

    def test_tampered_tokens_are_rejected(self):
        name = self.server.settings.cookie_name
        token = self.a.cookie
        flipped = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        candidates = {
            'flipped last char': flipped,
            'truncated': token[:-4],
            'extended': token + 'x',
            'empty': '',
            'garbage': '!!!not-a-token!!!',
            'oversize': 'a' * 300,
            'sql-ish': "' OR '1'='1",
        }
        for label, value in candidates.items():
            with self.subTest(label):
                status, body = self.get_state('%s=%s' % (name, value))
                self.assertEqual(status, 401, body)
                self.assertNotIn('state', body)

    def test_wrong_cookie_name_and_malformed_headers(self):
        for header in ('other_cookie=%s' % self.a.cookie, 'guixu_session', '=;;', '\x00', 'guixu_session=' + self.a.cookie + 'junk"'):
            with self.subTest(header=header):
                status, body = self.get_state(header)
                self.assertEqual(status, 401, body)

    def test_two_session_cookies_do_not_merge_accounts(self):
        name = self.server.settings.cookie_name
        header = '%s=%s; %s=%s' % (name, self.a.cookie, name, self.b.cookie)
        status, body = self.get_state(header)
        self.assertEqual(status, 200)
        self.assertIn(body['account']['username'], ('alice_a', 'bob_b'))
        self.assertEqual(body['state']['name'], 'AAA甲' if body['account']['username'] == 'alice_a' else 'BBB乙')

    def test_logout_invalidates_the_old_cookie(self):
        old = self.server.cookie_header(self.a.cookie)
        status, body = self.a.request('POST', '/api/logout', {})
        self.assertEqual(status, 200)
        self.assertEqual(self.get_state(old)[0], 401)
        self.assertEqual(self.server.raw_request('POST', '/api/action', {'request_id': 'z', 'expected_revision': 1, 'action': 'explore', 'params': {}},
                                                 headers={'Cookie': old})[0], 401)
        # Logging out one account leaves the other signed in.
        self.assertEqual(state_of(self.b)[0], 200)
        # Logout twice is harmless.
        self.assertEqual(self.server.raw_request('POST', '/api/logout', {}, headers={'Cookie': old})[0], 200)

    def test_password_change_revokes_other_sessions_but_keeps_current(self):
        first_cookie = self.a.cookie
        second = self.server.login('alice_a')            # a second device (updates the shared Client object)
        self.assertNotEqual(second.cookie, first_cookie)
        self.assertEqual(self.get_state(self.server.cookie_header(first_cookie))[0], 200)
        self.assertEqual(state_of(second)[0], 200)
        status, body = second.request('POST', '/api/password', {'old_password': 'tester-pass-1', 'new_password': 'new-password-9'})
        self.assertEqual(status, 200, body)
        self.assertEqual(state_of(second)[0], 200)                        # the changing session survives
        status, _ = self.get_state(self.server.cookie_header(first_cookie))
        self.assertEqual(status, 401)                                      # the other session is gone
        self.assertEqual(self.server.send('POST', '/api/login', {'username': 'alice_a', 'password': 'tester-pass-1'})[0], 401)
        self.assertEqual(self.server.send('POST', '/api/login', {'username': 'alice_a', 'password': 'new-password-9'})[0], 200)
        self.assertEqual(state_of(self.b)[0], 200)                         # unrelated account untouched

    def test_session_does_not_cross_accounts_after_relogin(self):
        self.a.request('POST', '/api/logout', {})
        again = self.server.login('alice_a')
        self.assertEqual(state_of(again)[1]['state']['name'], 'AAA甲')
        self.assertEqual(state_of(again)[1]['account']['username'], 'alice_a')


class TimeSettlementTests(unittest.TestCase):
    """AC11 / D4: time driven qi settlement is per account; one account being idle or acting never changes another."""

    def setUp(self):
        from tests.mu_support import TestClock
        self.clock = TestClock()
        self.server = Server(clock=self.clock).start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')
        post_new_game(self.a, name='甲')
        post_new_game(self.b, name='乙')
        self.path = self.server.app.db.path

    def raw(self, client):
        return read_progress(self.path, client.user_id)[1]

    def test_ac11_offline_account_is_untouched_by_another_accounts_settlement(self):
        a_before = self.raw(self.a)
        self.clock.advance(100)                        # 20 qi worth of time for everyone
        self.assertEqual(post_action(self.b, 'explore')[0], 200)
        self.assertEqual(self.raw(self.a), a_before)   # A did not act: its stored row is byte-for-byte the same state
        self.assertEqual(self.raw(self.b)['cultivation'], 20)
        view = state_of(self.a)[1]['view']['qi']       # A's own read already projects its own elapsed time
        self.assertEqual(view['value'], 20)
        self.assertEqual(self.raw(self.a), a_before)   # and reading does not write
        self.clock.advance(50)
        self.assertEqual(post_action(self.a, 'explore')[0], 200)
        self.assertEqual(self.raw(self.a)['cultivation'], 30)     # A settles on A's own clock marks
        self.assertEqual(self.raw(self.b)['cultivation'], 20)     # B stays at what B's own last write settled

    def test_qi_never_exceeds_the_cap_and_does_not_accumulate_offline(self):
        self.clock.advance(10 * 86400)
        post_action(self.a, 'explore')
        state = self.raw(self.a)
        self.assertEqual(state['cultivation'], 32)     # realm bottleneck, not days of offline hoarding


class CorruptRowIsolationTests(unittest.TestCase):
    """A damaged progress row refuses to load for its owner only, and is never silently reset (D6)."""

    def test_corrupt_row_returns_503_for_owner_only_and_stays_untouched(self):
        server = Server().start()
        self.addCleanup(server.close)
        a, b = server.as_user('alice_a'), server.as_user('bob_b')
        post_new_game(a, name='甲')
        post_new_game(b, name='乙')
        conn = server.app.db.connect()
        try:
            conn.execute('UPDATE current SET state=? WHERE user_id=?', ('{broken json', a.user_id))
        finally:
            conn.close()
        status, body = state_of(a)
        self.assertEqual((status, body['error']['code']), (503, 'SAVE_FAILED'))
        self.assertEqual(body['error']['message'], '进度暂时无法读取，请稍后重试或联系管理员。')
        text = json.dumps(body, ensure_ascii=False)
        for fragment in ('Traceback', 'json', 'JSON', 'sqlite', 'broken'):
            self.assertNotIn(fragment, text)
        status, body = post_action(a, 'explore', revision=1)
        self.assertEqual(status, 503)
        self.assertEqual(state_of(b)[1]['state']['name'], '乙')
        raw = sqlite_state(server, a.user_id)
        self.assertEqual(raw, '{broken json')           # not repaired, not reset

    def test_future_progress_schema_row_is_refused_not_overwritten(self):
        server = Server().start()
        self.addCleanup(server.close)
        a = server.as_user('alice_a')
        post_new_game(a, name='甲')
        conn = server.app.db.connect()
        try:
            conn.execute('UPDATE current SET schema_version=99 WHERE user_id=?', (a.user_id,))
        finally:
            conn.close()
        self.assertEqual(state_of(a)[0], 503)
        self.assertEqual(post_new_game(a, name='覆盖', revision=1)[0], 503)
        conn = server.app.db.connect()
        try:
            self.assertEqual(conn.execute('SELECT schema_version FROM current WHERE user_id=?', (a.user_id,)).fetchone()[0], 99)
        finally:
            conn.close()


def sqlite_state(server, user_id):
    conn = server.app.db.connect()
    try:
        return conn.execute('SELECT state FROM current WHERE user_id=?', (user_id,)).fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------- SQL isolation scan (B-3)
SQL_TABLE_RE = re.compile(r'\b(FROM|INTO|UPDATE|JOIN)\s+(current|requests)\b', re.I)
DYNAMIC_TABLE_RE = re.compile(r'\b(FROM|INTO|UPDATE|JOIN)\s*$', re.I)
# (file, enclosing function) allowed to touch current/requests WITHOUT user_id, and why:
OLD_FORMAT_ALLOWED = {
    ('game/legacy.py', '_rows'): 'reads the pre-multiuser single-user file (no user_id column exists there)',
    ('game/legacy.py', '_read_source'): 'reads the pre-multiuser single-user file (no user_id column exists there)',
    ('game/storage.py', '_counts'): 'row counts for backup verification, dynamic table name, returns no row data',
}


def python_sources():
    files = sorted((ROOT / 'game').glob('*.py')) + [ROOT / 'server.py']
    return [(p.relative_to(ROOT).as_posix(), p) for p in files]


class _SqlCollector(ast.NodeVisitor):
    """Collect string constants (and f-string literal parts) with their enclosing class/function."""

    def __init__(self):
        self.stack = []
        self.items = []

    def _push(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _push

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.items.append((tuple(self.stack), node.lineno, node.value))


class SqlIsolationScanTests(unittest.TestCase):
    def collect(self, path):
        collector = _SqlCollector()
        collector.visit(ast.parse(path.read_text(encoding='utf-8')))
        return collector.items

    def test_progress_table_sql_lives_only_in_storage_progress_repo(self):
        violations = []
        matched_in_storage = 0
        for name, path in python_sources():
            for scope, line, text in self.collect(path):
                dynamic = DYNAMIC_TABLE_RE.search(text) is not None
                if not (SQL_TABLE_RE.search(text) or dynamic):
                    continue
                function = scope[-1] if scope else ''
                if (name, function) in OLD_FORMAT_ALLOWED:
                    continue
                if name == 'game/storage.py' and 'ProgressRepo' in scope and not dynamic:
                    matched_in_storage += 1
                    continue
                violations.append('%s:%d in %s: %r' % (name, line, '.'.join(scope), text[:80]))
        self.assertEqual(violations, [])
        self.assertGreaterEqual(matched_in_storage, 8)   # guards against the scanner silently matching nothing

    def test_every_progress_statement_in_progress_repo_has_a_user_id_predicate(self):
        path = ROOT / 'game' / 'storage.py'
        checked = 0
        for scope, line, text in self.collect(path):
            if 'ProgressRepo' not in scope or not SQL_TABLE_RE.search(text):
                continue
            checked += 1
            self.assertRegex(text, r'user_id\s*=\s*\?|\(\s*user_id\s*,|SELECT\s+\?,', 'storage.py:%d lacks user_id: %r' % (line, text))
            if re.match(r'\s*(SELECT|UPDATE|DELETE)', text, re.I) and 'INSERT INTO requests' not in text:
                self.assertRegex(text, r'user_id\s*=\s*\?', 'storage.py:%d: read/update/delete must filter by user_id: %r' % (line, text))
        self.assertGreaterEqual(checked, 8)

    def test_no_other_module_names_the_progress_tables_via_database_helpers(self):
        """auth/admin/server must reach progress only through Store/ProgressRepo."""
        for name in ('game/auth.py', 'game/admin.py', 'server.py', 'game/settings.py'):
            text = (ROOT / name).read_text(encoding='utf-8')
            self.assertIsNone(SQL_TABLE_RE.search(text), name)

    def test_runtime_trace_of_a_two_account_session_binds_user_id_everywhere(self):
        server = Server(trace_sql=True).start()
        self.addCleanup(server.close)
        a, b = server.as_user('alice_a'), server.as_user('bob_b')
        post_new_game(a, name='AAA甲', request_id='t-1')
        post_new_game(b, name='BBB乙', request_id='t-1')
        for _ in range(2):
            post_action(a, 'explore')
            post_action(b, 'gather')
        state_of(a), state_of(b)
        post_action(a, 'explore', request_id='t-dup', revision=3)
        post_action(a, 'explore', request_id='t-dup', revision=3)       # duplicate path
        post_action(a, 'explore', revision=0)                             # stale path
        touched = [sql for sql in server.sql_log if SQL_TABLE_RE.search(sql)]
        self.assertGreater(len(touched), 20)
        users_seen = set()
        for sql in touched:
            match = re.search(r'user_id\s*=\s*(\d+)', sql) or re.search(r'\(\s*user_id[^)]*\)\s*VALUES\s*\(\s*(\d+)', sql, re.I) \
                or re.search(r'SELECT\s+(\d+),request_id', sql, re.I)
            self.assertIsNotNone(match, 'statement on current/requests without a bound user_id: %r' % sql)
            users_seen.add(int(match.group(1)))
        self.assertTrue({a.user_id, b.user_id} <= users_seen)
        # tester never acted, but its empty row may be created lazily; no statement may mix two ids.
        for sql in touched:
            ids = set(re.findall(r'user_id\s*=\s*(\d+)', sql))
            self.assertLessEqual(len(ids), 1, sql)


class LayoutIsolationTests(unittest.TestCase):
    def test_requests_primary_key_is_user_scoped(self):
        server = Server().start()
        self.addCleanup(server.close)
        conn = server.app.db.connect()
        try:
            pk = [r[1] for r in sorted(conn.execute('PRAGMA table_info(requests)').fetchall(), key=lambda r: r[5]) if r[5]]
            self.assertEqual(pk, ['user_id', 'request_id'])
            pk = [r[1] for r in conn.execute('PRAGMA table_info(current)').fetchall() if r[5]]
            self.assertEqual(pk, ['user_id'])
        finally:
            conn.close()

    def test_database_class_exposes_no_user_data_without_store(self):
        self.assertFalse(hasattr(Database, 'snapshot'))
        self.assertFalse(hasattr(storage, 'Store') and hasattr(Store, 'switch_user'))


if __name__ == '__main__':
    unittest.main()
