"""MU QA: migration drill, claiming, CLI contract and real-HTTP end-to-end (AC20, AC21, AC14, D6, MU_PRD section 5).

Old single-user files are built in temporary directories (never data/). The real released v1.1 sample from
tests/fixtures is used for the content-upgrade path; a free-profile schema2 file is used for the CLI path
(the fixture timestamps lie in 2027, so a claim must run on an injected clock).
"""
import ast
import hashlib
import http.cookiejar
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import server as server_module
from game import admin, legacy
from game.storage import Database, LegacyLayoutError, encode
from tests.mu_support import ROOT, Server, TestClock, post_action, post_new_game, state_of, test_settings
from tests.support import open_db

FIXTURE = ROOT / 'tests' / 'fixtures' / 'r4_v1_1_released_save.json'
FIXTURE_NOW = 1_800_000_000 + 28800
BANNED = ('存档', '读档', '载入', '检查点', '保存位置', '单机', '单人', '本地')
OLD_DDL = ('CREATE TABLE current (id INTEGER PRIMARY KEY CHECK(id=1), schema_version INTEGER NOT NULL, revision INTEGER NOT NULL, '
           'state TEXT NOT NULL, slot TEXT NOT NULL); CREATE TABLE requests (request_id TEXT PRIMARY KEY, payload TEXT NOT NULL);')


def write_old_db(path, row, ledger):
    with open_db(path) as db:
        db.executescript(OLD_DDL)
        db.execute('INSERT INTO current VALUES(1,?,?,?,?)', row)
        db.executemany('INSERT INTO requests VALUES(?,?)', ledger)


def read_old_db(path):
    with open_db(path) as db:
        return (db.execute('SELECT schema_version,revision,state,slot FROM current').fetchone(),
                db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall())


def fixture_rows():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    cur = data['current']
    row = (cur['schema_version'], cur['revision'], encode(cur['state']), encode(cur['slot']))
    return row, [(r['request_id'], r['payload']) for r in data['requests']], cur['state']


def free_profile_rows(name='旧日道友'):
    """A real schema2 free-profile game (built by the current rules), laid out as an old single-user file."""
    server = Server().start()
    try:
        client = server.as_user('builder_x')
        client.write('/api/new-game', name=name, mode='free')
        for _ in range(3):
            client.action('explore')
        client.action('gather')
        snap = client.snapshot()
        ledger = []
        conn = server.app.db.connect()
        try:
            ledger = conn.execute('SELECT request_id,payload FROM requests WHERE user_id=? ORDER BY request_id', (client.user_id,)).fetchall()
        finally:
            conn.close()
        return (2, snap['revision'], encode(snap['state']), 'null'), ledger, snap['state']
    finally:
        server.close()


def server_over(testcase, data_dir, clock=None):
    """Start the production routing harness on an existing (migrated) data directory.

    The default account `tester` registers first, so every test also proves the first registrant inherits nothing."""
    server = Server(clock=clock)
    server.temp.cleanup()                 # drop the harness' own empty directory
    server.data = Path(data_dir)
    server.start()
    testcase.addCleanup(server.stop)
    return server


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            result = server_module.main(list(argv))
            code = result if isinstance(result, int) else 0
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return code, out.getvalue() + err.getvalue()


def no_banned(testcase, text):
    for word in BANNED:
        testcase.assertNotIn(word, text)


class MigrationBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='guixu-mu-mig-')
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.path = self.data / 'game.db'

    def digest(self):
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def files(self):
        return sorted(p.name for p in self.data.iterdir())

    def backups(self):
        return sorted(self.data.glob('*.bak.db'))

    def app(self, clock=None):
        return server_module.App(self.data, settings=test_settings(), clock=clock)


class StartupGuardTests(MigrationBase):
    def test_old_layout_refuses_to_start_without_touching_the_file(self):
        row, ledger, _ = free_profile_rows()
        write_old_db(self.path, row, ledger)
        before, names = self.digest(), self.files()
        with self.assertRaises(LegacyLayoutError) as caught:
            server_module.App(self.data, settings=test_settings())
        self.assertIn('--migrate-multiuser', str(caught.exception))
        no_banned(self, str(caught.exception))
        code, text = run_main(['--data-dir', str(self.data), '--port', '0'])
        self.assertEqual(code, 1)
        self.assertIn('--migrate-multiuser', text)
        no_banned(self, text)
        self.assertEqual((self.digest(), self.files()), (before, names))

    def test_corrupt_unknown_and_empty_files_are_preserved_and_refused(self):
        cases = {
            'garbage': b'this is not a database' * 100,
            'empty': b'',
        }
        for label, content in cases.items():
            with self.subTest(label):
                self.path.write_bytes(content)
                code, text = run_main(['--data-dir', str(self.data), '--port', '0'])
                self.assertEqual(code, 1, text)
                no_banned(self, text)
                self.assertEqual(self.path.read_bytes(), content)
                code, text = run_main(['--migrate-multiuser', '--data-dir', str(self.data)])
                self.assertEqual(code, 1, text)
                self.assertEqual(self.path.read_bytes(), content)
                self.assertEqual(self.backups(), [])

    def test_future_layout_version_is_refused_with_original_bytes(self):
        Database(self.data)
        conn = sqlite3.connect(str(self.path))
        conn.execute('PRAGMA user_version=99')
        conn.commit()
        conn.close()
        before = self.digest()
        code, text = run_main(['--data-dir', str(self.data), '--port', '0'])
        self.assertEqual(code, 1)
        self.assertEqual(self.digest(), before)
        no_banned(self, text)

    def test_unsupported_progress_schema_is_not_migrated(self):
        row, ledger, _ = free_profile_rows()
        write_old_db(self.path, (7,) + row[1:], ledger)
        before = self.digest()
        code, text = run_main(['--migrate-multiuser', '--data-dir', str(self.data)])
        self.assertEqual(code, 1, text)
        self.assertIn('未改动', text)
        self.assertEqual((self.digest(), self.backups()), (before, []))


class MigrationDrillTests(MigrationBase):
    def setUp(self):
        super().setUp()
        self.row, self.ledger, self.original_state = free_profile_rows()
        write_old_db(self.path, self.row, self.ledger)
        self.source_digest = self.digest()
        self.name = '旧日道友'

    def progress_rows(self):
        with open_db(self.path) as db:
            return db.execute('SELECT user_id,revision,state FROM current ORDER BY user_id').fetchall()

    def migrate(self, *extra):
        return run_main(['--migrate-multiuser', '--data-dir', str(self.data), *extra])

    def test_ac20_backup_is_row_identical_and_record_checksums_match(self):
        code, text = self.migrate()
        self.assertEqual(code, 0, text)
        no_banned(self, text)
        self.assertIn('待认领区', text)
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertEqual(read_old_db(backups[0]), (self.row, sorted(self.ledger)))
        record = legacy.status(Database(self.data))
        self.assertEqual((record.status, record.revision, record.ledger_count), (legacy.UNCLAIMED, self.row[1], len(self.ledger)))
        self.assertEqual(record.sha256, legacy._digest(self.row[0], self.row[1], self.row[2], self.row[3], self.ledger))
        self.assertFalse(legacy.legacy_format_present(self.data))
        self.assertFalse((self.data / '.migrate.lock').exists())
        self.assertFalse((self.data / 'game.db.migrating').exists())

    def test_new_accounts_never_see_unclaimed_progress_on_any_route(self):
        self.migrate()
        server = server_over(self, self.data)
        accounts = [server.default] + [server.register(name) for name in ('first_reg', 'second_reg', '第三位玩家')]
        for client in accounts:
            status, body = state_of(client)
            self.assertEqual((status, body['state'], body['revision']), (200, None, 0))
        paths = ['/api/state', '/api/session', '/api/health', '/', '/index.html', '/app.js', '/api/legacy', '/api/legacy-progress',
                 '/api/legacy_progress', '/api/unclaimed', '/api/legacy/state', '/api/claim']
        for client in accounts:
            for path in paths:
                response = server_module.dispatch_full(
                    server.app, 'GET', path, {'Host': '127.0.0.1:8000', 'Cookie': server.cookie_header(client.cookie)}, b'', ('127.0.0.1', 8000))
                text = response[1].decode('utf-8', 'replace')
                self.assertNotIn(self.name, text, path)
                if path.startswith('/api'):
                    self.assertNotIn('legacy', text.lower(), path)
        status, body = post_new_game(accounts[0], name='全新开始')
        self.assertEqual((status, body['revision']), (200, 1))
        for method, path in (('POST', '/api/claim'), ('POST', '/api/legacy'), ('POST', '/api/migrate')):
            self.assertEqual(accounts[0].request(method, path, {})[0], 404)
        self.assertEqual(legacy.status(server.app.db).status, legacy.UNCLAIMED)

    def test_no_http_route_code_path_touches_the_unclaimed_area(self):
        tree = ast.parse((ROOT / 'server.py').read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in ('dispatch_full', 'dispatch', '_serve', 'do_GET', 'do_POST'):
                names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
                self.assertFalse({'legacy', 'claim', 'migrate_multiuser'} & names, node.name)
                strings = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                self.assertFalse([s for s in strings if 'legacy_' in s], node.name)
        for module in ('game/storage.py',):
            source = (ROOT / module).read_text(encoding='utf-8')
            store_part = source[source.index('class Store'):]
            self.assertNotIn('legacy_progress', store_part)
            self.assertNotIn('legacy_requests', store_part)

    def test_claim_cli_attaches_exact_state_and_ledger_to_the_named_account_only(self):
        self.migrate()
        app = self.app()
        other = app.auth.create_account('other_player', 'other-pass-123')
        target = app.auth.create_account('Claimer', 'claimer-pass-1')
        code, text = run_main(['--legacy-status', '--data-dir', str(self.data)])
        self.assertEqual(code, 0)
        self.assertIn('unclaimed', text)
        no_banned(self, text)
        code, text = run_main(['--claim-legacy', 'claimer', '--data-dir', str(self.data)])
        self.assertEqual(code, 0, text)
        self.assertIn('Claimer', text)
        no_banned(self, text)
        with Database(self.data).read() as db:
            cur = db.execute('SELECT schema_version,revision,state,slot FROM current WHERE user_id=?', (target,)).fetchone()
            ledger = db.execute('SELECT request_id,payload FROM requests WHERE user_id=? ORDER BY request_id', (target,)).fetchall()
            others = db.execute('SELECT count(*) FROM current WHERE user_id=?', (other,)).fetchone()[0] + \
                db.execute('SELECT count(*) FROM requests WHERE user_id=?', (other,)).fetchone()[0]
        self.assertEqual((cur[1], json.loads(cur[2])), (self.row[1], json.loads(self.row[2])))
        self.assertEqual(ledger, sorted(self.ledger))
        self.assertEqual(others, 0)
        record = legacy.status(Database(self.data))
        self.assertEqual((record.status, record.claimed_by, record.claimed_by_name), (legacy.CLAIMED, target, 'Claimer'))
        code, text = run_main(['--legacy-status', '--data-dir', str(self.data)])
        self.assertIn('claimed', text)

    def test_second_claim_is_refused_and_changes_nothing(self):
        self.migrate()
        app = self.app()
        app.auth.create_account('claimer_a', 'claimer-pass-1')
        app.auth.create_account('claimer_b', 'claimer-pass-2')
        self.assertEqual(run_main(['--claim-legacy', 'claimer_a', '--data-dir', str(self.data)])[0], 0)
        before = self.progress_rows()
        for forced in ([], ['--force']):
            code, text = run_main(['--claim-legacy', 'claimer_b', '--data-dir', str(self.data), *forced])
            self.assertEqual(code, 1, text)
            self.assertIn('认领', text)
            no_banned(self, text)
        self.assertEqual(before, self.progress_rows())

    def test_claim_for_missing_account_or_without_migration_fails_cleanly(self):
        self.migrate()
        code, text = run_main(['--claim-legacy', 'no_such_account', '--data-dir', str(self.data)])
        self.assertEqual(code, 1)
        self.assertIn('账号不存在', text)
        self.assertEqual(legacy.status(Database(self.data)).status, legacy.UNCLAIMED)
        fresh = tempfile.TemporaryDirectory()
        self.addCleanup(fresh.cleanup)
        app = server_module.App(fresh.name, settings=test_settings())
        app.auth.create_account('claimer_a', 'claimer-pass-1')
        code, text = run_main(['--claim-legacy', 'claimer_a', '--data-dir', fresh.name])
        self.assertEqual(code, 1)
        self.assertIn('没有待认领', text)

    def test_claim_onto_account_with_progress_needs_force_and_backs_up_first(self):
        self.migrate()
        app = self.app()
        target = app.auth.create_account('has_progress', 'progress-pass-1')
        store = app.store_for(target)
        store.write('new-game', {'request_id': 'mine-1', 'expected_revision': 0, 'name': '现有进度', 'mode': 'free'})
        code, text = run_main(['--claim-legacy', 'has_progress', '--data-dir', str(self.data)])
        self.assertEqual(code, 1, text)
        self.assertIn('--force', text)
        self.assertEqual(store.snapshot()['state']['name'], '现有进度')
        self.assertEqual(legacy.status(app.db).status, legacy.UNCLAIMED)
        self.assertEqual(list(self.data.glob('game.pre-claim.*')), [])
        code, text = run_main(['--claim-legacy', 'has_progress', '--force', '--data-dir', str(self.data)])
        self.assertEqual(code, 0, text)
        backup = list(self.data.glob('game.pre-claim.*.bak.db'))
        self.assertEqual(len(backup), 1)
        saved = sqlite3.connect(str(backup[0]))
        try:       # the pre-claim backup still contains the overwritten progress
            self.assertEqual(json.loads(saved.execute('SELECT state FROM current WHERE user_id=?', (target,)).fetchone()[0])['name'], '现有进度')
        finally:
            saved.close()
        after = server_module.App(self.data, settings=test_settings()).store_for(target).snapshot()
        self.assertEqual(after['state']['name'], self.name)
        conn = sqlite3.connect(str(self.path))
        try:
            ids = {r[0] for r in conn.execute('SELECT request_id FROM requests WHERE user_id=?', (target,))}
        finally:
            conn.close()
        self.assertNotIn('mine-1', ids)
        self.assertEqual(ids, {r[0] for r in self.ledger})

    def test_claimed_account_continues_play_and_old_request_ids_stay_idempotent(self):
        self.migrate()
        app = self.app()
        app.auth.create_account('claimer_a', 'claimer-pass-1')
        self.assertEqual(run_main(['--claim-legacy', 'claimer_a', '--data-dir', str(self.data)])[0], 0)
        server = server_over(self, self.data)
        client = server.login('claimer_a', 'claimer-pass-1')
        body = state_of(client)[1]
        self.assertEqual(body['state']['name'], self.name)
        revision = body['revision']
        old_id, old_payload = self.ledger[0]
        replay = json.loads(old_payload)
        status, again = client.request('POST', '/api/' + replay['endpoint'], replay['payload'])
        self.assertEqual(status, 200, again)
        self.assertTrue(again['duplicate'])
        self.assertEqual(again['revision'], revision)
        status, fresh = post_action(client, 'explore')
        self.assertEqual((status, fresh['revision']), (200, revision + 1))

    def test_claim_race_between_two_accounts_has_exactly_one_winner(self):
        self.migrate()
        app = self.app()
        app.auth.create_account('racer_a', 'racer-pass-001')
        app.auth.create_account('racer_b', 'racer-pass-002')
        barrier, outcomes = threading.Barrier(2), {}

        def claim(name):
            db = Database(self.data)
            barrier.wait(10)
            try:
                legacy.claim(db, name)
                outcomes[name] = 'ok'
            except legacy.LegacyError as exc:
                outcomes[name] = 'refused'

        threads = [threading.Thread(target=claim, args=(n,)) for n in ('racer_a', 'racer_b')]
        [t.start() for t in threads]
        [t.join(30) for t in threads]
        self.assertEqual(sorted(outcomes.values()), ['ok', 'refused'])
        conn = sqlite3.connect(str(self.path))
        try:
            rows = conn.execute('SELECT user_id FROM current WHERE revision>0').fetchall()
        finally:
            conn.close()
        self.assertEqual(len(rows), 1)

    def test_ac21_failed_swap_keeps_original_then_rerun_succeeds(self):
        with patch.object(legacy.os, 'replace', side_effect=OSError('injected swap failure')):
            code, text = self.migrate()
        self.assertEqual(code, 1, text)
        self.assertIn('原数据未改动', text)
        no_banned(self, text)
        self.assertEqual(self.digest(), self.source_digest)
        self.assertFalse((self.data / 'game.db.migrating').exists())
        self.assertFalse((self.data / '.migrate.lock').exists())
        code, text = run_main(['--data-dir', str(self.data), '--port', '0'])           # service still refuses to start
        self.assertEqual(code, 1)
        self.assertIn('--migrate-multiuser', text)
        no_banned(self, text)
        code, text = self.migrate()                                                       # resume after the interruption
        self.assertEqual(code, 0, text)
        self.assertEqual(len(self.backups()), 2)                                          # one verified backup per attempt, none overwritten
        self.assertEqual(read_old_db(self.backups()[0]), read_old_db(self.backups()[1]))

    def test_ac21_failure_while_filling_new_database_leaves_original_and_no_residue(self):
        with patch.object(legacy, '_fill_new_database', side_effect=sqlite3.OperationalError('disk I/O error')):
            code, text = self.migrate()
        self.assertEqual(code, 1, text)
        self.assertEqual(self.digest(), self.source_digest)
        self.assertEqual(sorted(n for n in self.files() if n != 'game.db' and not n.endswith('.bak.db')), [])

    def test_stale_lock_blocks_until_removed(self):
        (self.data / '.migrate.lock').write_text('x')
        code, text = self.migrate()
        self.assertEqual(code, 1)
        self.assertIn('.migrate.lock', text)
        self.assertEqual(self.digest(), self.source_digest)
        (self.data / '.migrate.lock').unlink()
        self.assertEqual(self.migrate()[0], 0)

    def test_migrating_twice_is_a_noop_and_creates_no_extra_backup(self):
        self.assertEqual(self.migrate()[0], 0)
        backups = self.backups()
        snapshot = self.digest()
        code, text = self.migrate()
        self.assertEqual(code, 0, text)
        self.assertEqual(self.backups(), backups)
        self.assertEqual(self.digest(), snapshot)

    def test_cli_flag_combination_errors(self):
        for argv in (['--force'], ['--migrate-save'], ['--backup', '--legacy-status'], ['--create-user', 'x', '--backup']):
            code, text = run_main([*argv, '--data-dir', str(self.data)])
            self.assertNotEqual(code, None)
            no_banned(self, text)
        code, text = run_main(['--force', '--data-dir', str(self.data)])
        self.assertEqual(code, 2)                     # argparse usage error
        self.assertIn('--force', text)


class FixtureUpgradeTests(MigrationBase):
    """The released v1.1 sample goes through the content upgrade on claim (needs the 2027 clock the sample was made with)."""

    def test_real_released_sample_is_preserved_field_by_field(self):
        row, ledger, original = fixture_rows()
        write_old_db(self.path, row, ledger)
        before = self.digest()
        self.assertEqual(admin.migrate_multiuser(self.data), 0)
        self.assertEqual(read_old_db(self.backups()[0])[0], row)
        clock = TestClock(FIXTURE_NOW)
        app = self.app(clock)
        user_id = app.auth.create_account('v11_player', 'v11-player-pass')
        stranger = app.auth.create_account('stranger_x', 'stranger-pass-1')
        record = legacy.claim(app.db, 'v11_player', clock=clock)
        self.assertEqual((record.status, record.claimed_by), (legacy.CLAIMED, user_id))
        snap = app.store_for(user_id).snapshot()
        self.assertIn(snap['revision'], (row[1], row[1] + 1))      # +1 when the R4 content upgrade rewrote the progress
        migrated = snap['state']
        for key, value in original.items():
            if key in ('world', 'profile'):
                continue
            self.assertEqual(migrated.get(key), value, key)
        self.assertEqual(migrated['name'], original['name'])
        self.assertEqual(app.store_for(stranger).snapshot()['state'], None)
        with app.db.read() as db:
            ledger_after = db.execute('SELECT request_id,payload FROM requests WHERE user_id=? ORDER BY request_id', (user_id,)).fetchall()
        self.assertEqual(ledger_after, sorted(ledger))
        self.assertEqual(self.digest() != before, True)       # the file was replaced by the multi-account layout


# --------------------------------------------------------------------- real HTTP end-to-end
class HttpClient:
    """Minimal browser stand-in over real sockets: keeps cookies, sends the same headers the page sends."""

    def __init__(self, base):
        self.base = base
        self.cookie = None

    def call(self, method, path, payload=None, extra=None):
        headers = {'Content-Type': 'application/json', 'X-Game-Client': 'guixu-web', **(extra or {})}
        if self.cookie:
            headers['Cookie'] = self.cookie
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=20)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            for header in response.headers.get_all('Set-Cookie') or []:
                pair = header.split(';', 1)[0]
                self.cookie = None if pair.endswith('=') else pair
            try:
                body = json.loads(raw)
            except ValueError:
                body = raw
            return response.status, body, response.headers


class LiveHttpTests(unittest.TestCase):
    def setUp(self):
        self.server = Server(live=True).start()
        self.addCleanup(self.server.close)
        self.base = self.server.url

    def test_end_to_end_register_play_logout_and_switch_account(self):
        a, b = HttpClient(self.base), HttpClient(self.base)
        self.assertEqual(a.call('POST', '/api/register', {'username': 'live_alice', 'password': 'alice-password-1'})[0], 200)
        status, body, _ = a.call('GET', '/api/state')
        self.assertEqual((status, body['state'], body['account']), (200, None, {'username': 'live_alice'}))
        status, body, _ = a.call('POST', '/api/new-game', {'request_id': 'live-1', 'expected_revision': 0, 'name': '甲', 'mode': 'free'})
        self.assertEqual((status, body['revision']), (200, 1))
        status, body, _ = a.call('POST', '/api/action', {'request_id': 'live-2', 'expected_revision': 1, 'action': 'explore', 'params': {}})
        self.assertEqual((status, body['revision'], body['sync']['persisted']), (200, 2, True))
        self.assertEqual(a.call('POST', '/api/logout', {})[0], 200)
        self.assertIsNone(a.cookie)
        self.assertEqual(a.call('GET', '/api/state')[0], 401)
        # second player in the same service
        self.assertEqual(b.call('POST', '/api/register', {'username': 'live_bob', 'password': 'bobby-password-1'})[0], 200)
        status, body, _ = b.call('GET', '/api/state')
        self.assertEqual((body['state'], body['revision']), (None, 0))
        status, body, _ = b.call('POST', '/api/new-game', {'request_id': 'live-1', 'expected_revision': 0, 'name': '乙', 'mode': 'free'})
        self.assertEqual((status, body['revision'], body['duplicate']), (200, 1, False))
        self.assertEqual(a.call('POST', '/api/login', {'username': 'live_alice', 'password': 'alice-password-1'})[0], 200)
        status, body, _ = a.call('GET', '/api/state')
        self.assertEqual((body['state']['name'], body['revision'], body['state']['actions_taken']), ('甲', 2, 1))
        status, body, _ = b.call('GET', '/api/state')
        self.assertEqual((body['state']['name'], body['revision'], body['state']['actions_taken']), ('乙', 1, 0))

    def test_response_headers_and_static_assets(self):
        client = HttpClient(self.base)
        status, body, headers = client.call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'id="save-status"', body)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        status, _, headers = client.call('POST', '/api/register', {'username': 'live_alice', 'password': 'alice-password-1'})
        cookie = headers['Set-Cookie']
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Lax', cookie)
        for path in ('/app.js', '/styles.css', '/battle_replay.js'):
            self.assertEqual(client.call('GET', path)[0], 200)
        self.assertEqual(client.call('GET', '/../game.db')[0], 404)
        self.assertEqual(client.call('GET', '/game/storage.py')[0], 404)
        self.assertEqual(client.call('GET', '/data/game.db')[0], 404)

    def test_forged_host_over_real_socket_is_refused(self):
        request = urllib.request.Request(self.base + '/api/health', headers={'Host': 'evil.example.com'})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class ProcessRestartTests(unittest.TestCase):
    """A real `python server.py` process, hard-killed after an acknowledged action, then restarted."""

    def start(self, data, port, *extra):
        proc = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(port), '--data-dir', str(data), *extra],
                                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/api/health' % port, timeout=1) as response:
                    if response.status == 200:
                        return proc
            except OSError:
                time.sleep(0.2)
        proc.kill()
        self.fail('server did not become ready: %s' % proc.stdout.read().decode('utf-8', 'replace'))

    def test_hard_kill_after_acknowledged_write_loses_nothing(self):
        with tempfile.TemporaryDirectory(prefix='guixu-mu-proc-') as folder:
            port = free_port()
            proc = self.start(folder, port)
            client = HttpClient('http://127.0.0.1:%d' % port)
            self.assertEqual(client.call('POST', '/api/register', {'username': 'proc_alice', 'password': 'alice-password-1'})[0], 200)
            self.assertEqual(client.call('POST', '/api/new-game', {'request_id': 'p-1', 'expected_revision': 0, 'name': '甲', 'mode': 'longline'})[0], 200)
            last = None
            for index in range(5):
                status, last, _ = client.call('POST', '/api/action', {'request_id': 'p-a%d' % index, 'expected_revision': index + 1, 'action': 'explore', 'params': {}})
                self.assertEqual(status, 200, last)
            proc.kill()                           # TerminateProcess: no clean shutdown, no WAL checkpoint
            proc.wait(10)
            output = proc.stdout.read().decode('utf-8', 'replace')
            no_banned(self, output)
            self.assertNotIn('alice-password-1', output)
            proc2 = self.start(folder, port)
            again = HttpClient('http://127.0.0.1:%d' % port)
            self.assertEqual(again.call('GET', '/api/state')[0], 401)             # sessions are in the database, cookies live in client
            self.assertEqual(again.call('POST', '/api/login', {'username': 'proc_alice', 'password': 'alice-password-1'})[0], 200)
            status, body, _ = again.call('GET', '/api/state')
            self.assertEqual((body['revision'], body['state']), (last['revision'], last['state']))
            status, body, _ = again.call('POST', '/api/action', {'request_id': 'p-a4', 'expected_revision': 5, 'action': 'explore', 'params': {}})
            self.assertEqual((status, body['duplicate'], body['revision']), (200, True, 6))     # unacknowledged-retry semantics hold across restart
            proc2.kill()
            proc2.wait(10)
            no_banned(self, proc2.stdout.read().decode('utf-8', 'replace'))

    def test_old_cookie_survives_restart_because_sessions_are_persistent(self):
        with tempfile.TemporaryDirectory(prefix='guixu-mu-proc-') as folder:
            port = free_port()
            proc = self.start(folder, port)
            client = HttpClient('http://127.0.0.1:%d' % port)
            client.call('POST', '/api/register', {'username': 'proc_alice', 'password': 'alice-password-1'})
            cookie = client.cookie
            proc.kill()
            proc.wait(10)
            proc2 = self.start(folder, port)
            client2 = HttpClient('http://127.0.0.1:%d' % port)
            client2.cookie = cookie
            self.assertEqual(client2.call('GET', '/api/state')[0], 200)
            proc2.kill()
            proc2.wait(10)


if __name__ == '__main__':
    unittest.main()
