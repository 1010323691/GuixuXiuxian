"""MU QA: save timing and no-lost-update guarantees (AC10, AC12, AC13, AC14, design B-1, B-2, B-4, B-5).

Everything runs on temporary databases. Concurrency tests use the production Store/App (not the memoising
test Store) and several App instances over one data directory to model several server processes.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import server as server_module
from game import admin, cadence, growth, rules
from game.rules import GameError
from game.storage import Database, ProgressRepo
from tests.mu_support import (ROOT, Server, TestClock, post_action, post_new_game, read_progress, revision_of,
                              state_of, test_settings)

SAVE_FAILED_MESSAGE = '进度保存失败，请稍后重试，当前操作未生效。'


def raw_revision(db_path, user_id):
    row = read_progress(db_path, user_id)
    return row[0] if row else None


def make_payload(revision, action='explore', request_id=None):
    return {'request_id': request_id or str(uuid.uuid4()), 'expected_revision': revision, 'action': action, 'params': {}}


class SaveTimingTests(unittest.TestCase):
    """AC12: a successful response means the revision is already in the database."""

    def setUp(self):
        self.server = Server(fast=False).start()      # production Database: synchronous=FULL
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.path = self.server.app.db.path

    def test_ac12_response_matches_an_independent_reader_after_every_write(self):
        status, body = post_new_game(self.a, name='AAA甲')
        self.assertEqual(status, 200)
        for index in range(6):
            status, body = post_action(self.a, 'explore')
            self.assertEqual(status, 200, body)
            stored = read_progress(self.path, self.a.user_id)     # separate connection, no shared cache
            self.assertEqual(stored[0], body['revision'])
            self.assertEqual(stored[1], body['state'])
            self.assertEqual(stored[2], index + 2)               # new-game + actions so far
            self.assertTrue(body['sync']['persisted'])
            self.assertEqual(body['sync']['revision'], body['revision'])

    def test_new_game_response_is_also_durable(self):
        status, body = post_new_game(self.a, name='AAA甲')
        self.assertEqual(status, 200)
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['name']), (1, 'AAA甲'))

    def test_s5_progress_after_restart_equals_last_acknowledged_state(self):
        post_new_game(self.a, name='AAA甲')
        last = None
        for _ in range(4):
            last = post_action(self.a, 'explore')[1]
        self.server.restart()
        body = state_of(self.server.as_user('alice_a'))[1]
        self.assertEqual((body['revision'], body['state']), (last['revision'], last['state']))

    def test_ac14_replay_after_lost_response_is_a_duplicate_applied_once(self):
        post_new_game(self.a, name='AAA甲')
        payload = make_payload(1, request_id='lost-ack')
        first = self.a.request('POST', '/api/action', payload)[1]
        again = self.a.request('POST', '/api/action', payload)
        self.assertEqual(again[0], 200)
        self.assertTrue(again[1]['duplicate'])
        self.assertFalse(first['duplicate'])
        self.assertEqual(again[1]['revision'], 2)
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (2, 1, 2))


class PragmaTests(unittest.TestCase):
    def test_wal_full_busy_timeout_and_foreign_keys_are_in_effect(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(folder)
            conn = db.connect()
            try:
                self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
                self.assertEqual(conn.execute('PRAGMA synchronous').fetchone()[0], 2)     # FULL
                self.assertEqual(conn.execute('PRAGMA busy_timeout').fetchone()[0], 5000)
                self.assertEqual(conn.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            finally:
                conn.close()
            # persisted in the file header, so any other client also sees WAL
            plain = sqlite3.connect(str(Path(folder) / 'game.db'))
            try:
                self.assertEqual(plain.execute('PRAGMA journal_mode').fetchone()[0], 'wal')
            finally:
                plain.close()

    def test_every_write_transaction_is_begin_immediate(self):
        log = []
        with tempfile.TemporaryDirectory() as folder:
            db = Database(folder)
            real = db.connect

            def traced():
                conn = real()
                conn.set_trace_callback(log.append)
                return conn

            db.connect = traced
            with db.tx() as conn:
                conn.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('probe', '1'))
        self.assertIn('BEGIN IMMEDIATE', log)
        self.assertEqual(log.index('BEGIN IMMEDIATE') < log.index('COMMIT'), True)


class FaultInjectionTests(unittest.TestCase):
    """AC13: failures before/after COMMIT leave the account on a consistent side of the action."""

    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')
        self.path = self.server.app.db.path

    def rows(self, client):
        return read_progress(self.path, client.user_id)

    def assertSaveFailed(self, status, body):
        self.assertEqual(status, 503, body)
        self.assertEqual(body['error']['code'], 'SAVE_FAILED')
        self.assertEqual(body['error']['message'], SAVE_FAILED_MESSAGE)
        self.assertNotIn('state', body)
        self.assertNotIn('已同步', json.dumps(body, ensure_ascii=False))

    def test_failure_before_commit_rolls_back_everything_and_retry_applies_once(self):
        before = self.rows(self.a)
        payload = make_payload(1, request_id='retry-me')
        with self.server.fail_commit('before'):
            status, body = self.a.request('POST', '/api/action', payload)
        self.assertSaveFailed(status, body)
        self.assertEqual(self.rows(self.a), before)                   # revision, state and ledger unchanged
        status, body = self.a.request('POST', '/api/action', payload)  # same request_id after recovery
        self.assertEqual(status, 200, body)
        self.assertFalse(body['duplicate'])
        self.assertEqual(body['revision'], 2)
        status, body = self.a.request('POST', '/api/action', payload)
        self.assertTrue(body['duplicate'])
        stored = self.rows(self.a)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (2, 1, 2))

    def test_failure_after_commit_means_lost_ack_and_retry_is_duplicate(self):
        payload = make_payload(1, request_id='lost-ack')
        with self.server.fail_commit('after'):
            status, body = self.a.request('POST', '/api/action', payload)
        self.assertSaveFailed(status, body)            # the client cannot know; the server must stay consistent
        stored = self.rows(self.a)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (2, 1, 2))
        status, body = self.a.request('POST', '/api/action', payload)
        self.assertEqual(status, 200)
        self.assertTrue(body['duplicate'])
        self.assertEqual(self.rows(self.a)[0], 2)

    def test_new_game_failure_leaves_no_character(self):
        c = self.server.as_user('carol_c')
        with self.server.fail_commit('before'):
            status, body = post_new_game(c, name='丙', revision=0)
        self.assertSaveFailed(status, body)
        status, body = state_of(c)
        self.assertEqual((status, body['revision'], body['state']), (200, 0, None))

    def test_failure_for_one_account_does_not_touch_the_other(self):
        before_b = self.rows(self.b)
        with self.server.fail_commit('before'):
            self.a.request('POST', '/api/action', make_payload(1))
        self.assertEqual(self.rows(self.b), before_b)
        self.assertEqual(post_action(self.b, 'explore')[0], 200)

    def test_exception_after_update_inside_transaction_is_rolled_back(self):
        before = self.rows(self.a)
        real = ProgressRepo.commit

        def commit_then_crash(*args, **kwargs):
            real(*args, **kwargs)                       # UPDATE current + INSERT requests executed...
            raise sqlite3.OperationalError('disk I/O error (injected after UPDATE)')   # ...then the transaction dies

        with patch.object(ProgressRepo, 'commit', staticmethod(commit_then_crash)):
            status, body = self.a.request('POST', '/api/action', make_payload(1, request_id='crash-1'))
        self.assertSaveFailed(status, body)
        self.assertEqual(self.rows(self.a), before)
        status, body = self.a.request('POST', '/api/action', make_payload(1, request_id='crash-1'))
        self.assertEqual((status, body['duplicate'], body['revision']), (200, False, 2))

    def test_integrity_error_does_not_leak_details(self):
        with self.server.fail_commit('before'):
            _, body = self.a.request('POST', '/api/action', make_payload(1))
        text = json.dumps(body, ensure_ascii=False)
        for fragment in ('disk I/O', 'sqlite', 'Traceback', 'injected'):
            self.assertNotIn(fragment, text)


CHILD = r'''
import os, sys
sys.path.insert(0, sys.argv[1])
from server import App
from tests.support import test_settings
data, user_id, mode, revision, now, request_id = sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
app = App(data, settings=test_settings(), clock=lambda: now)
real = app.db.connect
class Proxy:
    def __init__(self, conn): self._c = conn
    def __getattr__(self, name): return getattr(self._c, name)
    def execute(self, sql, *a):
        if sql.strip().upper() == 'COMMIT':
            if mode == 'after': self._c.execute(sql, *a)
            os._exit(9)
        return self._c.execute(sql, *a)
app.db.connect = lambda: Proxy(real())
app.store_for(user_id).write('action', {'request_id': request_id, 'expected_revision': revision, 'action': 'explore', 'params': {}})
os._exit(0)
'''


class ProcessKillTests(unittest.TestCase):
    """AC13/S4 with a real process kill (os._exit) at the commit boundary."""

    def setUp(self):
        self.clock = TestClock()
        self.server = Server(clock=self.clock, fast=False).start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        post_new_game(self.a, name='AAA甲')
        self.path = self.server.app.db.path
        self.server.stop()                  # no open handles while the child works on the file

    def kill_child(self, mode, request_id):
        proc = subprocess.run([sys.executable, '-I', '-c', CHILD, str(ROOT), str(self.server.data), str(self.a.user_id), mode,
                               '1', str(self.clock()), request_id], cwd=str(ROOT), capture_output=True, timeout=60)
        self.assertEqual(proc.returncode, 9, proc.stderr.decode('utf-8', 'replace'))

    def test_kill_before_commit_leaves_state_before_the_action(self):
        self.kill_child('before', 'k-before')
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (1, 0, 1))
        self.server.start()
        reopened = self.server.as_user('alice_a')
        self.assertEqual(state_of(reopened)[1]['revision'], 1)
        status, body = post_action(reopened, 'explore', request_id='k-before', revision=1)
        self.assertEqual((status, body['duplicate'], body['revision']), (200, False, 2))

    def test_kill_right_after_commit_keeps_the_action(self):
        self.kill_child('after', 'k-after')
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (2, 1, 2))
        conn = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        finally:
            conn.close()
        self.server.start()
        reopened = self.server.as_user('alice_a')
        self.assertEqual(state_of(reopened)[1]['revision'], 2)
        status, body = post_action(reopened, 'explore', request_id='k-after', revision=1)   # the client retries its unacknowledged request
        self.assertEqual((status, body['duplicate'], body['revision']), (200, True, 2))


class ConcurrencyTests(unittest.TestCase):
    """B-1/B-2/AC10 with real threads against SQLite. Correctness must come from SQLite, not process locks."""

    def setUp(self):
        self.clock = TestClock()
        self.server = Server(clock=self.clock, fast=False).start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')
        self.path = self.server.app.db.path
        # two additional App instances on the same directory model separate server processes
        self.apps = [self.server.app] + [server_module.App(self.server.data, settings=test_settings(), clock=self.clock) for _ in range(2)]

    def run_threads(self, count, target):
        results, errors, barrier = [None] * count, [], threading.Barrier(count)

        def runner(index):
            try:
                barrier.wait(timeout=30)
                results[index] = target(index)
            except BaseException as exc:    # unexpected exceptions are test failures, collected here
                errors.append((index, repr(exc)))

        threads = [threading.Thread(target=runner, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        self.assertEqual(errors, [])
        return results

    @staticmethod
    def attempt(store, payload):
        try:
            return store.write('action', payload)
        except GameError as exc:
            return exc

    def test_b1_same_revision_race_has_exactly_one_winner(self):
        start = raw_revision(self.path, self.a.user_id)
        stores = [self.apps[i % 3].store_for(self.a.user_id) for i in range(8)]
        results = self.run_threads(8, lambda i: self.attempt(stores[i], make_payload(start)))
        winners = [r for r in results if isinstance(r, dict)]
        losers = [r for r in results if isinstance(r, GameError)]
        self.assertEqual(len(winners), 1, results)
        self.assertEqual(sorted((e.status, e.code) for e in losers), [(409, 'STALE_STATE')] * 7)
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (start + 1, 1, start + 1))

    def test_b1_retry_loops_never_lose_updates(self):
        start = raw_revision(self.path, self.a.user_id)
        wins = [0] * 6

        def worker(index):
            store = self.apps[index % 3].store_for(self.a.user_id)
            for _ in range(15):
                while True:
                    outcome = self.attempt(store, make_payload(raw_revision(self.path, self.a.user_id)))
                    if isinstance(outcome, dict):
                        wins[index] += 1
                        break
                    self.assertEqual(outcome.code, 'STALE_STATE')

        self.run_threads(6, worker)
        total = sum(wins)
        self.assertEqual(total, 90)
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (start + total, total, start + total))

    def test_ac10_two_accounts_write_concurrently_without_loss_or_cross_talk(self):
        start_a, start_b = raw_revision(self.path, self.a.user_id), raw_revision(self.path, self.b.user_id)

        def worker(index):
            client = (self.a, self.b)[index]
            store = self.apps[index].store_for(client.user_id)
            for _ in range(100):
                outcome = store.write('action', make_payload(raw_revision(self.path, client.user_id), 'explore' if index == 0 else 'gather'))
                self.assertTrue(outcome['ok'])

        self.run_threads(2, worker)
        sa, sb = read_progress(self.path, self.a.user_id), read_progress(self.path, self.b.user_id)
        self.assertEqual((sa[0], sa[1]['actions_taken'], sa[2]), (start_a + 100, 100, start_a + 100))
        self.assertEqual((sb[0], sb[1]['actions_taken'], sb[2]), (start_b + 100, 100, start_b + 100))
        self.assertEqual((sa[1]['name'], sb[1]['name']), ('AAA甲', 'BBB乙'))

    def test_b2_same_request_id_sent_16_times_applies_once(self):
        start = raw_revision(self.path, self.a.user_id)
        payload = make_payload(start, request_id='dup-16')
        stores = [self.apps[i % 3].store_for(self.a.user_id) for i in range(16)]
        results = self.run_threads(16, lambda i: self.attempt(stores[i], dict(payload)))
        self.assertTrue(all(isinstance(r, dict) for r in results), results)
        self.assertEqual(sum(1 for r in results if not r['duplicate']), 1)
        self.assertEqual({r['revision'] for r in results}, {start + 1})
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[2]), (start + 1, start + 1))

    def test_b2_same_request_id_with_different_content_has_one_winner(self):
        start = raw_revision(self.path, self.a.user_id)
        stores = [self.apps[i % 3].store_for(self.a.user_id) for i in range(8)]
        results = self.run_threads(8, lambda i: self.attempt(stores[i], make_payload(start, ('explore', 'gather')[i % 2], 'same-id')))
        winners = [r for r in results if isinstance(r, dict)]
        errors = [r for r in results if isinstance(r, GameError)]
        self.assertGreaterEqual(len(winners), 1)
        self.assertTrue(all(e.status == 409 and e.code in ('REQUEST_ID_REUSED', 'STALE_STATE') for e in errors), errors)
        self.assertTrue(all(w['duplicate'] is False or w['revision'] == start + 1 for w in winners))
        stored = read_progress(self.path, self.a.user_id)
        self.assertEqual((stored[0], stored[1]['actions_taken'], stored[2]), (start + 1, 1, start + 1))
        # winner was a single action; the loser content is reported as reuse, never silently applied
        reused = [e for e in errors if e.code == 'REQUEST_ID_REUSED']
        self.assertGreaterEqual(len(reused), 1, 'no REQUEST_ID_REUSED reported for conflicting content')

    def test_http_level_stale_conflict_is_409_with_current_revision(self):
        start = raw_revision(self.path, self.a.user_id)
        self.assertEqual(post_action(self.a, 'explore', revision=start)[0], 200)
        status, body = post_action(self.a, 'explore', revision=start)
        self.assertEqual((status, body['error']['code']), (409, 'STALE_STATE'))
        self.assertEqual(body['revision'], start + 1)
        self.assertNotIn('进度已同步', body['error']['message'])


class ShortTransactionTests(unittest.TestCase):
    """B-4: rules run outside the write transaction; the transaction holds only CAS + ledger write."""

    def setUp(self):
        self.server = Server(fast=False, trace_sql=True).start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        self.b = self.server.as_user('bob_b')
        post_new_game(self.a, name='AAA甲')
        post_new_game(self.b, name='BBB乙')

    def test_rules_never_run_inside_a_write_transaction(self):
        db = self.server.app.db
        seen = {}

        def spy(module, name):
            real = getattr(module, name)

            def wrapper(*args, **kwargs):
                seen.setdefault(name, []).append(db.write_tx_active())
                return real(*args, **kwargs)

            return patch.object(module, name, wrapper)

        with spy(rules, 'apply_action'), spy(growth, 'sync'), spy(cadence, 'sync'), spy(growth, 'validate'), \
                spy(rules, 'validate_state'):
            self.assertEqual(post_action(self.a, 'explore')[0], 200)
        for name in ('apply_action', 'sync', 'validate', 'validate_state'):
            self.assertIn(name, seen)
        for name, flags in seen.items():
            self.assertFalse(any(flags), '%s ran while a write transaction was open' % name)

    def test_commit_statement_set_is_minimal(self):
        self.server.sql_log.clear()
        self.assertEqual(post_action(self.a, 'explore')[0], 200)
        log = self.server.sql_log
        begin = max(i for i, s in enumerate(log) if s.startswith('BEGIN IMMEDIATE'))
        end = log.index('COMMIT', begin)
        inside = log[begin + 1:end]
        updates = [s for s in inside if s.lstrip().upper().startswith('UPDATE CURRENT')]
        inserts = [s for s in inside if 'INSERT INTO requests' in s]
        reads = [s for s in inside if s.lstrip().upper().startswith('SELECT')]
        self.assertEqual((len(updates), len(inserts)), (1, 1), inside)
        self.assertLessEqual(len(reads), 1, inside)
        self.assertEqual(len(inside), len(updates) + len(inserts) + len(reads), inside)
        # no heavy table scans or other tables in the write window
        self.assertFalse([s for s in inside if 'sessions' in s or 'accounts' in s])

    def test_slow_rules_of_one_account_do_not_block_another_account(self):
        real = rules.apply_action
        gate = threading.Event()

        def slow_for_a(state, action, params, context=None):
            if threading.current_thread().name == 'slow-a':
                gate.set()
                time.sleep(0.8)
            return real(state, action, params, context=context)

        outcome = {}

        def run_a():
            outcome['a'] = post_action(self.a, 'explore')

        with patch.object(rules, 'apply_action', slow_for_a):
            thread = threading.Thread(target=run_a, name='slow-a')
            thread.start()
            self.assertTrue(gate.wait(10))
            started = time.perf_counter()
            status, _ = post_action(self.b, 'gather')
            elapsed = time.perf_counter() - started
            thread.join(10)
        self.assertEqual(status, 200)
        self.assertEqual(outcome['a'][0], 200)
        self.assertLess(elapsed, 0.6, 'account B waited for account A rules computation: %.3fs' % elapsed)


class RequestValidationTests(unittest.TestCase):
    """Malformed write requests are 400 and never reach the database (no ledger row, no revision change)."""

    def setUp(self):
        self.server = Server().start()
        self.addCleanup(self.server.close)
        self.a = self.server.as_user('alice_a')
        post_new_game(self.a, name='AAA甲')
        self.path = self.server.app.db.path

    def assertRejectedUntouched(self, payload, label):
        before = read_progress(self.path, self.a.user_id)
        status, body = self.a.request('POST', '/api/action', payload)
        self.assertEqual(status, 400, (label, body))
        self.assertEqual(body['error']['code'], 'BAD_REQUEST', label)
        self.assertEqual(read_progress(self.path, self.a.user_id), before, label)

    def test_bad_request_ids(self):
        base = make_payload(1)
        for label, value in (('empty', ''), ('too long', 'a' * 129), ('non ascii', '编号一'), ('control char', 'ab'),
                             ('int', 7), ('none', None), ('list', ['a']), ('bool', True)):
            self.assertRejectedUntouched(dict(base, request_id=value), 'request_id ' + label)

    def test_bad_revisions(self):
        base = make_payload(1)
        for label, value in (('bool', True), ('negative', -1), ('float', 1.0), ('string', '1'), ('none', None), ('huge', 2 ** 63), ('list', [1])):
            self.assertRejectedUntouched(dict(base, expected_revision=value), 'revision ' + label)

    def test_missing_or_extra_fields_and_unknown_actions(self):
        base = make_payload(1)
        for key in ('request_id', 'expected_revision', 'action', 'params'):
            self.assertRejectedUntouched({k: v for k, v in base.items() if k != key}, 'missing ' + key)
        self.assertRejectedUntouched(dict(base, extra=1), 'extra field')
        before = read_progress(self.path, self.a.user_id)
        for action in ('does_not_exist', '', None, 5, 'save', 'load', 'cultivate'):
            status, body = self.a.request('POST', '/api/action', dict(base, action=action, request_id=str(uuid.uuid4())))
            self.assertIn(status, (400, 422), (action, body))
        self.assertEqual(read_progress(self.path, self.a.user_id), before)

    def test_new_game_mode_and_name_validation(self):
        before = read_progress(self.path, self.a.user_id)
        for payload in (dict(name='x', mode='hard'), dict(name='x', mode=5), dict(name='a' * 40, mode='free'),
                        dict(name=None, mode='free'), dict(name=['x'], mode='free')):
            status, body = self.a.request('POST', '/api/new-game', dict(request_id=str(uuid.uuid4()), expected_revision=1, **payload))
            self.assertIn(status, (400, 422), (payload, body))
            self.assertFalse(body['ok'])
        self.assertEqual(read_progress(self.path, self.a.user_id), before)


class BackupWalTests(unittest.TestCase):
    def test_online_backup_contains_latest_commit_while_wal_is_live(self):
        server = Server(fast=False).start()
        self.addCleanup(server.close)
        a = server.as_user('alice_a')
        post_new_game(a, name='AAA甲')
        pin = server.app.db.connect()                      # an open reader keeps the WAL file from being checkpointed away
        try:
            pin.execute('BEGIN')
            pin.execute('SELECT count(*) FROM current').fetchone()
            post_action(a, 'explore')
            self.assertTrue(Path(str(server.app.db.path) + '-wal').exists())
            dest = server.app.db.backup()
        finally:
            pin.close()
        copy = sqlite3.connect(str(dest))
        try:
            self.assertEqual(copy.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            row = copy.execute('SELECT revision,state FROM current WHERE user_id=?', (a.user_id,)).fetchone()
        finally:
            copy.close()
        self.assertEqual(row[0], 2)
        self.assertEqual(json.loads(row[1])['actions_taken'], 1)
        self.assertEqual(dest.parent.name, 'backups')

    def test_backup_never_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(folder)
            first = db.backup()
            second = db.backup()
            self.assertNotEqual(first, second)
            from game.storage import LayoutError
            with self.assertRaises(LayoutError):
                db.backup(first)

    def test_backup_cli_command_succeeds_and_prints_path(self):
        import io
        from contextlib import redirect_stdout
        server = Server().start()
        self.addCleanup(server.close)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = admin.backup(server.app)
        self.assertEqual(code, 0)
        self.assertIn('已备份到', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
