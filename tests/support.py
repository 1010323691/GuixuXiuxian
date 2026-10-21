"""White-box harness for the multi-account service.

Each test owns a temporary data directory holding one data/game.db. Requests run through
server.dispatch_full, the same routing/auth/validation code the HTTP Handler uses, without
sockets or subprocesses. `live=True` additionally serves the App over real HTTP on a background
thread for the Playwright browser suites.

Main fixtures
* `test_settings(**overrides)`  Settings with a cheap scrypt cost and very long sessions.
* `fast_store(data, clock, user_id)`  user-scoped Store with fsync off and snapshot memoisation.
* `Server`  App + default account `tester` (cookie attached automatically). Public helpers:
  `request/raw_request/send/snapshot/write/action`, `register(name)`, `login(name)`, `as_user(name)`,
  `restart()`, `fail_commit(when)`, `sql_log`, `user_id`, `store`, `app`, `clock`, `data`.
* `TestClock` / `pass_time`  frozen server clock that tests advance explicitly.
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
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
QI_SECONDS = 5  # 与 game.config.QI_SECONDS 保持一致；测试不得依赖隐式默认
DEFAULT_USER = 'tester'
DEFAULT_PASSWORD = 'tester-pass-1'
TEN_YEARS = 10 * 365 * 86400
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


def test_settings(**overrides):
    """Settings for tests: scrypt n=2**4 (fast), sessions outlive any simulated clock jump, no registration cap."""
    from game.settings import Settings
    values = dict(kdf_n=2 ** 4, session_idle_seconds=TEN_YEARS, session_absolute_seconds=TEN_YEARS,
                  register_per_ip_hour=10 ** 6)
    values.update(overrides)
    return Settings(**values)


test_settings.__test__ = False  # not a test case for unittest/pytest collection


def _fast_database_class():
    from game.storage import Database

    class FastDatabase(Database):
        """Database whose connections skip fsync; layout, transactions and SQL are the production ones."""

        def connect(self):
            db = super().connect()
            db.execute('PRAGMA synchronous=OFF')
            return db

    return FastDatabase


def ensure_account_row(db, user_id):
    """Insert a placeholder account so `current.user_id` satisfies its foreign key (idempotent)."""
    conn = db.connect()
    try:
        conn.execute('INSERT OR IGNORE INTO accounts(id,username,username_key,pw_algo,pw_params,pw_salt,pw_hash,'
                     'created_at,pw_changed_at) VALUES(?,?,?,?,?,?,?,?,?)',
                     (user_id, 'user%d' % user_id, 'user%d' % user_id, 'scrypt', 'n=16,r=8,p=1',
                      b'\x00' * 16, b'\x00' * 32, 0, 0))
    finally:
        conn.close()


def _fast_store_class():
    from game.storage import Store

    class FastStore(Store):
        """Store with a per-instance memo of projected snapshots (game rules and validation untouched).

        * _snapshot results are memoised (JSON-normalised, pickled) keyed by every input it reads (revision,
          exact state/slot bytes, server clock second); events/duplicate are filled per call. The world view
          dry-runs every projected action, so planners that re-read unchanged state dominated runtime.
          Any write or direct database edit changes the key; JSON matches what HTTP returned.
        """
        CACHE_SIZE = 64

        def __init__(self, *args, **kwargs):
            self._snapshot_cache = {}
            super().__init__(*args, **kwargs)

        def snapshot(self):
            """Read the raw row once; an unchanged row at the same clock second reuses the result."""
            row, _ = self._fetch()
            key = ('snapshot', tuple(row), self._now())
            cached = self._snapshot_cache.pop(key, None)
            if cached is None:
                cached = pickle.dumps(self._snapshot(*self._decode(row)), protocol=pickle.HIGHEST_PROTOCOL)
            self._remember(key, cached)
            return pickle.loads(cached)

        def _remember(self, key, cached):
            self._snapshot_cache[key] = cached
            while len(self._snapshot_cache) > self.CACHE_SIZE:
                self._snapshot_cache.pop(next(iter(self._snapshot_cache)))

        def _snapshot(self, revision, state, slot, events=None, duplicate=False, battle_report=None):
            # The key keeps dict order: views list dicts (e.g. inventory) in iteration order, and a
            # write's in-memory state is ordered differently from the same state decoded from SQLite.
            key = (revision, json.dumps([state, slot], ensure_ascii=False, separators=(',', ':')), self._now())
            cached = self._snapshot_cache.pop(key, None)
            if cached is None:
                result = json.loads(json.dumps(super()._snapshot(revision, state, slot),
                                               ensure_ascii=False, allow_nan=False))
                cached = pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL)
            self._remember(key, cached)
            result = pickle.loads(cached)
            result['duplicate'] = duplicate
            result['events'] = json.loads(json.dumps(events or [], ensure_ascii=False))
            if battle_report is not None:
                result['battle_report'] = json.loads(json.dumps(battle_report, ensure_ascii=False))
            return result

    return FastStore


def fast_database(data, clock=None):
    """FastDatabase over the temp directory `data` (one game.db)."""
    return _fast_database_class()(data, clock=clock)


def fast_store(data, clock=None, user_id=1, **kwargs):
    """Production Store for `user_id`, tuned for in-process tests.

    `data` is a data directory or an existing Database. A placeholder account row is created so the
    progress row's foreign key holds. Extra keyword arguments go to Store (none are needed today).
    """
    db = data if hasattr(data, 'connect') else fast_database(data, clock)
    ensure_account_row(db, user_id)
    return _fast_store_class()(db, user_id, clock=clock if clock is not None else getattr(db, 'clock', None), **kwargs)


class TestClock:
    """Server-side clock for white-box suites: frozen until a test calls advance()."""
    __test__ = False

    def __init__(self, start=None):
        self.value = int(time.time() if start is None else start)
        self.lock = threading.Lock()

    def __call__(self):
        with self.lock:
            return self.value

    def advance(self, seconds):
        with self.lock:
            self.value += seconds
            return self.value


def pass_time(snapshot, action, seconds):
    """让序章吐纳自然运转 `seconds` 秒。

    Store 型装具直接拨快服务端时钟（随后第一次写入会结算）；纯规则型装具没有时钟，
    则用同一个 rules.settle_qi 就地推进状态。"""
    from game import rules
    for fn in (snapshot, action):
        clock = getattr(getattr(fn, '__self__', None), 'clock', None)
        if hasattr(clock, 'advance'):
            clock.advance(seconds)
            return
    state = snapshot()['state']
    if state.get('qi_at') is None:
        state['qi_at'] = 0
    state.update(rules.settle_qi(state, state['qi_at'] + seconds))


class _FaultyConnection:
    """Connection proxy used by Server.fail_commit: raises around COMMIT, delegates everything else."""

    def __init__(self, real, when, budget):
        self._real = real
        self._when = when
        self._budget = budget

    def __getattr__(self, name):
        return getattr(self._real, name)

    def execute(self, sql, *args):
        if sql.strip().upper() == 'COMMIT' and self._budget['left'] != 0:
            if self._budget['left'] > 0:
                self._budget['left'] -= 1
            if self._when == 'before':
                raise sqlite3.OperationalError('disk I/O error (injected before COMMIT)')
            self._real.execute(sql, *args)
            raise sqlite3.OperationalError('disk I/O error (injected after COMMIT)')
        return self._real.execute(sql, *args)


class Client:
    """One signed-in account of a Server: its cookie plus request/snapshot/write/action helpers."""

    def __init__(self, server, username, password, cookie, user_id):
        self.server = server
        self.username = username
        self.password = password
        self.cookie = cookie
        self.user_id = user_id

    @property
    def clock(self):
        return self.server.clock

    @property
    def store(self):
        """In-process Store of this account (None while the server is stopped)."""
        return self.server.store_of(self.user_id)

    def request(self, method, path, payload=None, headers=None, raw=None):
        merged = dict(headers or {})
        if self.cookie and 'Cookie' not in merged:
            merged['Cookie'] = self.server.cookie_header(self.cookie)
        return self.server.raw_request(method, path, payload, merged, raw)

    def _direct(self):
        """In-process Store for the convenience helpers; live servers keep the real HTTP path."""
        if self.server.httpd or self.server.app is None:
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


class Server:
    HOST = '127.0.0.1'
    PORT = 8000

    def __init__(self, clock=None, live=False, settings=None, fast=True, trace_sql=False):
        self.temp = tempfile.TemporaryDirectory(prefix='guixu-qa-')
        self.data = Path(self.temp.name)
        self.clock = clock if clock is not None else TestClock()
        self.live = live
        self.settings = settings if settings is not None else test_settings()
        self.fast = fast
        self.trace_sql = trace_sql
        self.sql_log = []
        self.app = None
        self.httpd = None
        self.worker = None
        self.known = {}  # username -> Client, kept across restart()
        self.default = None
        self.url = f'http://{self.HOST}:{self.PORT}'

    # ------------------------------------------------------------ lifecycle
    def _make_app(self):
        from server import App
        if not self.fast:
            return App(self.data, settings=self.settings, clock=self.clock)
        store_class = _fast_store_class()

        class FastApp(App):
            """App on a no-fsync Database with memoising Stores; routing and auth are production code."""

            def __init__(inner, data_dir, settings=None, clock=None):
                from game.auth import AuthService
                inner.data_dir = Path(data_dir)
                inner.settings = settings
                inner._clock = clock if clock is not None else time.time
                inner.db = fast_database(inner.data_dir, inner.clock)
                inner.auth = AuthService(inner.db, inner.settings, inner.clock)
                inner._stores = {}

            def store_for(inner, user_id):
                # One memoising Store per account for the app's lifetime (stateless apart from the memo).
                if user_id not in inner._stores:
                    inner._stores[user_id] = store_class(inner.db, user_id, clock=inner.clock)
                return inner._stores[user_id]

        return FastApp(self.data, settings=self.settings, clock=self.clock)

    def start(self):
        """Open the database like a fresh server start; repeated start/stop models a restart.

        Registers (first start) or logs in (later starts) the default account `tester`.
        """
        self.app = self._make_app()
        if self.trace_sql:
            self._install_trace()
        if self.live:
            from server import GameServer
            self.httpd = GameServer((self.HOST, 0), self.app)
            self.url = f'http://{self.HOST}:{self.httpd.server_port}'
            self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.worker.start()
        status, body = self.request_anonymous('GET', '/api/health')
        if status != 200 or not body['ok']:
            raise RuntimeError(f'server health failed: {status} {body}')
        self.default = self.sign_in(DEFAULT_USER, DEFAULT_PASSWORD)
        return self

    def request_anonymous(self, method, path, payload=None, headers=None, raw=None):
        status, body, _ = self.send(method, path, payload, headers, raw)
        return status, body

    def _install_trace(self):
        db = self.app.db
        original = db.connect
        log = self.sql_log

        def traced():
            conn = original()
            conn.set_trace_callback(log.append)
            return conn

        db.connect = traced

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.worker.join(timeout=5)
            self.httpd = None
        self.app = None
        # Connections are per call and closed, but finalize stragglers so Windows releases the file.
        gc.collect()

    def restart(self):
        """Close and reopen the App on the same data directory; accounts persist, sessions are renewed."""
        known = list(self.known.values())
        self.stop()
        self.app = None
        self.start()
        for client in known:
            if client is not self.default:
                self.login(client.username, client.password)
        return self

    def close(self):
        self.stop()
        self.temp.cleanup()

    # ------------------------------------------------------------ accounts
    def cookie_header(self, token):
        return f'{self.settings.cookie_name}={token}'

    def _adopt(self, username, password, headers):
        name = self.settings.cookie_name
        token = None
        for header in headers.get('Set-Cookie', []):
            first = header.split(';', 1)[0]
            if first.startswith(name + '='):
                token = first[len(name) + 1:]
        assert token, headers
        user_id = self.app.auth.find_account(username)
        client = self.known.get(username)
        if client is None:
            client = self.known[username] = Client(self, username, password, token, user_id)
        else:
            client.password, client.cookie, client.user_id = password, token, user_id
        return client

    def register(self, username, password=DEFAULT_PASSWORD, ip='127.0.0.1'):
        """POST /api/register; returns a Client holding the new session cookie. Raises on any refusal."""
        status, body, headers = self.send('POST', '/api/register', {'username': username, 'password': password}, ip=ip)
        assert status == 200, (username, status, body)
        return self._adopt(username, password, headers)

    def login(self, username, password=DEFAULT_PASSWORD, ip='127.0.0.1'):
        """POST /api/login; returns a Client holding the new session cookie. Raises on any refusal."""
        status, body, headers = self.send('POST', '/api/login', {'username': username, 'password': password}, ip=ip)
        assert status == 200, (username, status, body)
        return self._adopt(username, password, headers)

    def sign_in(self, username, password=DEFAULT_PASSWORD):
        """Register the account if it is new, otherwise log in."""
        status, body, headers = self.send('POST', '/api/register', {'username': username, 'password': password})
        if status == 409 and body['error']['code'] == 'USERNAME_TAKEN':
            return self.login(username, password)
        assert status == 200, (username, status, body)
        return self._adopt(username, password, headers)

    def as_user(self, username, password=DEFAULT_PASSWORD):
        """Client for another (auto-created) account; the default account is `tester`."""
        client = self.known.get(username)
        return client if client is not None else self.sign_in(username, password)

    @property
    def user_id(self):
        return self.default.user_id

    def store_of(self, user_id):
        return self.app.store_for(user_id) if self.app is not None else None

    @property
    def store(self):
        """In-process Store of the default account."""
        return self.default.store

    # ------------------------------------------------------------ requests
    def send(self, method, path, payload=None, headers=None, raw=None, ip='127.0.0.1'):
        """Low level request without any implicit cookie: (status, parsed body, {header: [values]})."""
        data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
        merged = {'Content-Type': 'application/json', 'X-Game-Client': 'guixu-web', **(headers or {})}
        if self.httpd:
            request = urllib.request.Request(self.url + path, data=data, method=method, headers=merged)
            try:
                response = urllib.request.urlopen(request, timeout=12)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, json.loads(response.read()), {'Set-Cookie': response.headers.get_all('Set-Cookie') or []}
        if self.app is None:
            raise ConnectionRefusedError('server is stopped')
        from server import dispatch_full
        if data is not None:
            merged.setdefault('Content-Length', str(len(data)))
        merged.setdefault('Host', f'{self.HOST}:{self.PORT}')
        status, body, _, out = dispatch_full(self.app, method, path, merged, data or b'', (self.HOST, self.PORT), ip)
        return status, json.loads(body), {name: [value] for name, value in out.items()}

    def raw_request(self, method, path, payload=None, headers=None, raw=None):
        """Request exactly as given (no implicit cookie): (status, body)."""
        return self.request_anonymous(method, path, payload, headers, raw)

    def request(self, method, path, payload=None, headers=None, raw=None):
        """Request as the default account (its cookie is attached unless headers carry one)."""
        return self.default.request(method, path, payload, headers, raw)

    def snapshot(self):
        return self.default.snapshot()

    def write(self, endpoint, **fields):
        return self.default.write(endpoint, **fields)

    def action(self, action, **params):
        return self.default.action(action, **params)

    # ------------------------------------------------------------ fault injection
    @contextmanager
    def fail_commit(self, when='before', times=-1):
        """Make COMMIT of write transactions fail (disk error) while the block runs.

        when='before': the error is raised instead of committing (rolled back);
        when='after': the transaction commits, then the error is raised (lost acknowledgement).
        times: number of failures (-1 = every commit). Works on the temporary database only.
        """
        assert when in ('before', 'after'), when
        db = self.app.db
        budget = {'left': times}
        previous = db.__dict__.get('connect')
        original = db.connect
        db.connect = lambda: _FaultyConnection(original(), when, budget)
        try:
            yield
        finally:
            if previous is not None:
                db.connect = previous
            else:
                del db.connect



def battle_round(state, action, context=None):
    """White-box access to the internal single-round resolver (no public click action exists any more).

    Mirrors world.apply_action's per-opportunity bookkeeping; returns (new_state, events, trace).
    """
    from game import world, journey, activities
    from game.clone import clone
    result = clone(state)
    w = result['world']
    events, trace = [], []
    world._round(w, action, events, trace)
    world._clamp(w)
    w['tick'] += 1
    result['actions_taken'] += 1
    world._ai(w, events)
    if 'r3' in w:
        activities.observe(state['world'], w, action, {}, context)
        journey.observe(state['world'], w, action, {})
    w['journal'] = (w['journal'] + events)[-100:]
    world.validate(result)
    return result, events, trace


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
        pass_time(snapshot, action, threshold * QI_SECONDS)
        action('breakthrough')
    if snapshot()['state']['region'] != 'ruins':
        action('travel', region='ruins')
    action('challenge', enemy='shadow')
    win_battle(snapshot, action)
    assert snapshot()['state']['completed'], snapshot()


def win_battle(snapshot, action):
    """序章自动斗法：一次提交打完整场；败退则静养后重试，直到战斗结束。"""
    for _ in range(8):
        if snapshot()['state']['battle'] is None:
            return
        action('auto_battle')
        state = snapshot()['state']
        if state['battle'] is None and not state['victories']:
            action('rest')
    assert snapshot()['state']['battle'] is None, 'auto battle did not finish'


def baseline_route(snapshot, action):
    """无升级/道具/注入状态的序章最短路线；战斗全部由自动斗法完成。"""
    for threshold, region, enemy in [(32, 'forest', 'ape'), (64, 'ruins', 'sentinel'), (96, None, 'shadow')]:
        pass_time(snapshot, action, threshold * QI_SECONDS)
        action('breakthrough')
        if region:
            action('travel', region=region)
        action('challenge', enemy=enemy)
        for _ in range(6):
            if snapshot()['state']['battle'] is None:
                break
            action('auto_battle')
            if snapshot()['state']['battle'] is None and enemy not in snapshot()['state']['victories']:
                action('rest')
                action('challenge', enemy=enemy)
        assert enemy in snapshot()['state']['victories'], snapshot()['state']
    state = snapshot()['state']
    assert state['completed'] and state['battle'] is None, state
