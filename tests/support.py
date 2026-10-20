"""White-box harness: each test owns an in-process Store and temporary save directory.

Requests run through server.dispatch, the same routing/validation code the HTTP
Handler uses, without sockets or subprocesses. `live=True` additionally serves the
Store over real HTTP on a background thread for the Playwright browser suites.
"""
from contextlib import contextmanager
import gc
import json
import logging
import pickle
from pathlib import Path
import sqlite3
import tempfile
import threading
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
# The routing layer logs injected storage failures with full tracebacks; tests assert the responses instead.
logging.disable(logging.CRITICAL)


@contextmanager
def open_db(path):
    """Like `with sqlite3.connect(path)` (commit/rollback) but also closes, so Windows releases the file."""
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def fast_store(data, clock=None):
    """Production Store tuned for in-process tests; game rules and validation are untouched.

    * fsync-per-commit is disabled: durability is not observable in-process.
    * _snapshot results are memoised (JSON-normalised, pickled) keyed by every input it reads (revision, exact
      state/slot bytes, server clock second); events/duplicate are filled per call. The world view dry-runs
      every projected action, so planners that re-read unchanged state dominated runtime.
      Any write or direct database edit changes the key; JSON matches what HTTP returned.
    """
    from game.storage import Store

    class FastStore(Store):
        CACHE_SIZE = 64

        def __init__(self, *args, **kwargs):
            self._snapshot_cache = {}
            super().__init__(*args, **kwargs)

        def connect(self):
            db = super().connect()
            db.execute('PRAGMA synchronous=OFF')
            return db

        def snapshot(self):
            """Read the raw row once; an unchanged row at the same clock second reuses the result.

            Uncached reads run the production _read (JSON parse + full validation) on that row.
            """
            db = self.connect()
            try:
                row = db.execute('SELECT schema_version,revision,state,slot FROM current WHERE id=1').fetchone()
            finally:
                db.close()
            key = ('snapshot', row, self._now())
            cached = self._snapshot_cache.pop(key, None)
            if cached is None:
                cached = pickle.dumps(self._snapshot(*self._read(_FixedRow(row))), protocol=pickle.HIGHEST_PROTOCOL)
            self._remember(key, cached)
            return pickle.loads(cached)

        def _remember(self, key, cached):
            self._snapshot_cache[key] = cached
            while len(self._snapshot_cache) > self.CACHE_SIZE:
                self._snapshot_cache.pop(next(iter(self._snapshot_cache)))

        def _snapshot(self, revision, state, slot, events=None, duplicate=False):
            # events/duplicate only fill their own two fields of the result, so the projected
            # body is shared between a write's response and later reads of the same save.
            # The key keeps dict order: views list dicts (e.g. inventory) in iteration order, and a
            # write's in-memory state is ordered differently from the same state decoded from SQLite.
            key = (revision, json.dumps([state, slot], ensure_ascii=False, separators=(',', ':')), self._now())
            cached = self._snapshot_cache.pop(key, None)
            if cached is None:
                # Normalise through JSON once (exactly what HTTP clients saw), then keep a pickle:
                # each hit returns a fresh independent copy without re-parsing JSON.
                result = json.loads(json.dumps(super()._snapshot(revision, state, slot),
                                               ensure_ascii=False, allow_nan=False))
                cached = pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL)
            self._remember(key, cached)
            result = pickle.loads(cached)
            result['duplicate'] = duplicate
            result['events'] = json.loads(json.dumps(events or [], ensure_ascii=False))
            return result

    return FastStore(data, clock=clock)


class _FixedRow:
    """Stand-in connection that answers Store._read's single SELECT with an already-fetched row."""
    def __init__(self, row):
        self.row = row

    def execute(self, sql, *args):
        return self

    def fetchone(self):
        return self.row


class Server:
    HOST = '127.0.0.1'
    PORT = 8000

    def __init__(self, clock=None, live=False):
        self.temp = tempfile.TemporaryDirectory(prefix='guixu-qa-')
        self.data = Path(self.temp.name)
        self.clock = clock
        self.live = live
        self.store = None
        self.httpd = None
        self.worker = None
        self.url = f'http://{self.HOST}:{self.PORT}'

    def start(self):
        """Open the save like a fresh server start; repeated start/stop models a restart."""
        self.store = fast_store(self.data, self.clock)
        if self.live:
            from server import GameServer
            self.httpd = GameServer((self.HOST, 0), self.store)
            self.url = f'http://{self.HOST}:{self.httpd.server_port}'
            self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.worker.start()
        status, body = self.request('GET', '/api/health')
        if status != 200 or not body['ok']:
            raise RuntimeError(f'server health failed: {status} {body}')
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.worker.join(timeout=5)
            self.httpd = None
        self.store = None
        # Store leaves per-request sqlite3 connections to the garbage collector; finalize them so
        # Windows releases the database file before a restart or temp-dir cleanup.
        gc.collect()

    def close(self):
        self.stop()
        self.temp.cleanup()

    def request(self, method, path, payload=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        merged = {'Content-Type': 'application/json', 'X-Game-Client': 'guixu-web', **(headers or {})}
        if self.httpd:
            request = urllib.request.Request(self.url + path, data=data, method=method, headers=merged)
            try:
                response = urllib.request.urlopen(request, timeout=12)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, json.loads(response.read())
        if self.store is None:
            raise ConnectionRefusedError('server is stopped')
        from server import dispatch
        if data is not None:
            merged.setdefault('Content-Length', str(len(data)))
        merged.setdefault('Host', f'{self.HOST}:{self.PORT}')
        status, body, _ = dispatch(self.store, method, path, merged, data or b'', (self.HOST, self.PORT))
        return status, json.loads(body)

    def _direct(self):
        """In-process Store for the convenience helpers; live servers keep the real HTTP path."""
        if self.httpd or self.store is None:
            return None
        return self.store

    def snapshot(self):
        store = self._direct()
        if store is not None:
            return store.snapshot()
        status, body = self.request('GET', '/api/state')
        assert status == 200, body
        return body

    def write(self, endpoint, **fields):
        # Existing W1 suites explicitly exercise the retained free-action profile.
        # R3 tests submit raw HTTP payloads to verify the new longline default.
        if endpoint == '/api/new-game':
            fields.setdefault('mode', 'free')
        payload = {'request_id': str(uuid.uuid4()), 'expected_revision': self.snapshot()['revision'], **fields}
        store = self._direct()
        if store is not None:
            from game.rules import GameError
            try:
                return store.write(endpoint[len('/api/'):], payload)
            except GameError as exc:
                raise AssertionError((endpoint, fields, exc.status, {'code': exc.code, 'message': exc.message})) from None
        status, body = self.request('POST', endpoint, payload)
        assert status == 200, (endpoint, fields, status, body)
        return body

    def action(self, action, **params):
        return self.write('/api/action', action=action, params=params)


def route_to_ending(snapshot, action):
    """Public legal actions only; no internal rules, state injection, or save edits."""
    for _ in range(12):
        action('explore')
    action('upgrade')
    action('upgrade')
    for _ in range(6):
        action('gather')
    for _ in range(4):
        action('alchemy')
    for realm, threshold, region, enemy in [(0, 32, None, None), (1, 64, 'forest', 'ape'), (2, 96, 'ruins', 'sentinel')]:
        if enemy:
            action('travel', region=region)
            action('challenge', enemy=enemy)
            win_battle(snapshot, action)
        while snapshot()['state']['cultivation'] < threshold:
            action('cultivate')
        action('breakthrough')
    if snapshot()['state']['region'] != 'ruins':
        action('travel', region='ruins')
    action('challenge', enemy='shadow')
    win_battle(snapshot, action)
    assert snapshot()['state']['completed'], snapshot()


def win_battle(snapshot, action):
    for _ in range(80):
        snap = snapshot()
        state = snap['state']
        if state['battle'] is None:
            return
        max_hp = [60, 80, 100, 140][state['realm']]
        if state['pills'] and state['hp'] <= max_hp - 35:
            action('use_pill')
        elif state['mp'] >= 6:
            action('power_attack')
        else:
            action('defend')
    raise AssertionError('battle failed to terminate within 80 public actions')


def baseline_route(snapshot, action):
    """GDD's exact 53-action route, without upgrades, items, or injected state."""
    for count, region, enemy, sequence, hp, mp in [
        (6, 'forest', 'ape', ['power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'attack'], 46, 1),
        (8, 'ruins', 'sentinel', ['power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'defend', 'power_attack', 'attack'], 24, 2),
        (10, None, 'shadow', ['power_attack', 'power_attack', 'defend', 'power_attack', 'power_attack', 'defend', 'power_attack', 'attack', 'attack'], 36, 4),
    ]:
        for _ in range(count):
            action('cultivate')
        action('breakthrough')
        if region:
            action('travel', region=region)
        action('challenge', enemy=enemy)
        for command in sequence:
            action(command)
        state = snapshot()['state']
        assert state['battle'] is None, state
        assert (state['hp'], state['mp']) == (hp, mp), state
    state = snapshot()['state']
    assert state['completed'] and state['actions_taken'] == 53, state
