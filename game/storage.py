"""Single-file SQLite storage: one data/game.db, rows scoped by user_id, WAL journal.

Layers (this module is the only place that may run SQL against the progress
tables `current` and `requests`):

* Database      - connection factory, layout creation/detection, backup.
* ProgressRepo  - every statement on `current`/`requests`; each one carries a
                  user_id predicate that is verified at run time.
* Store         - user-scoped facade (user_id bound at construction, never a
                  method argument) with the short-transaction write protocol:
                  read and compute outside the transaction, then commit with an
                  optimistic revision check (CAS) inside BEGIN IMMEDIATE.

Correctness never depends on process-local locks: the CAS, the (user_id,
request_id) primary key and BEGIN IMMEDIATE all live inside SQLite.
"""
import enum
import json
import os
import random
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import cadence
from . import config as C
from . import growth
from . import rules

DB_LAYOUT_VERSION = 1
APPLICATION_ID = 0x47584D55  # "GXMU"
BUSY_TIMEOUT_MS = 5000
WRITE_RETRIES = 2
MAX_INT64 = 2 ** 63 - 1
TABLES = ('meta', 'accounts', 'sessions', 'login_attempts', 'current', 'requests', 'legacy_progress', 'legacy_requests')

DDL = '''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE accounts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL,
  username_key TEXT NOT NULL UNIQUE,
  pw_algo TEXT NOT NULL,
  pw_params TEXT NOT NULL,
  pw_salt BLOB NOT NULL,
  pw_hash BLOB NOT NULL,
  created_at INTEGER NOT NULL,
  pw_changed_at INTEGER NOT NULL);
CREATE TABLE sessions(
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  last_seen_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  absolute_expires_at INTEGER NOT NULL);
CREATE INDEX sessions_account ON sessions(account_id);
CREATE TABLE login_attempts(
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  fails INTEGER NOT NULL,
  last_fail_at INTEGER NOT NULL,
  locked_until INTEGER NOT NULL,
  PRIMARY KEY(scope, key));
CREATE TABLE current(
  user_id INTEGER PRIMARY KEY REFERENCES accounts(id),
  schema_version INTEGER NOT NULL,
  revision INTEGER NOT NULL,
  state TEXT NOT NULL,
  slot TEXT NOT NULL,
  updated_at INTEGER NOT NULL);
CREATE TABLE requests(
  user_id INTEGER NOT NULL REFERENCES accounts(id),
  request_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  PRIMARY KEY(user_id, request_id)) WITHOUT ROWID;
CREATE TABLE legacy_progress(
  id INTEGER PRIMARY KEY CHECK(id = 1),
  status TEXT NOT NULL CHECK(status IN ('unclaimed','claimed')),
  source_schema INTEGER NOT NULL,
  revision INTEGER NOT NULL,
  state TEXT NOT NULL,
  slot TEXT NOT NULL,
  ledger_count INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  backup_file TEXT NOT NULL,
  claimed_by INTEGER REFERENCES accounts(id),
  claimed_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL);
CREATE TABLE legacy_requests(
  request_id TEXT PRIMARY KEY,
  payload TEXT NOT NULL);
'''

# Layout upgrades: {target_version: callable(connection)}; each runs in BEGIN IMMEDIATE after a backup.
MIGRATIONS = {}


class LayoutError(ValueError):
    """The database file cannot be used; the original file was left untouched."""


class LegacyLayoutError(LayoutError):
    """The file is a pre-multiuser database that must go through --migrate-multiuser."""


class ProgressConflict(ValueError):
    """Target account already holds progress and force was not given."""


class CommitOutcome(enum.Enum):
    COMMITTED = 'committed'
    DUPLICATE = 'duplicate'
    STALE = 'stale'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def utc_stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def unique_path(folder, prefix, stamp, suffix):
    """First free name `<prefix><stamp>[-n]<suffix>` in folder; never overwrites."""
    candidate = Path(folder) / ('%s%s%s' % (prefix, stamp, suffix))
    n = 1
    while candidate.exists():
        candidate = Path(folder) / ('%s%s-%d%s' % (prefix, stamp, n, suffix))
        n += 1
    return candidate


def fsync_file(path):
    with Path(path).open('r+b') as stream:  # Windows rejects fsync on read-only handles
        os.fsync(stream.fileno())


def open_connection(path):
    """Autocommit connection (explicit BEGIN) with the mandatory pragmas applied."""
    db = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
    try:
        db.execute('PRAGMA busy_timeout=%d' % BUSY_TIMEOUT_MS)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA foreign_keys=ON')
    except Exception:
        db.close()
        raise
    return db


def create_layout(path, now=None):
    """Create a brand-new, fully laid-out database file at path (must not exist)."""
    path = Path(path)
    if path.exists():
        raise LayoutError('目标数据库文件已存在')
    stamp = int(time.time() if now is None else now)
    db = sqlite3.connect(str(path), isolation_level=None)
    try:
        if db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
            raise LayoutError('当前存储位置不支持 WAL 日志模式，拒绝建库')
        db.execute('PRAGMA application_id=%d' % APPLICATION_ID)
        db.executescript('BEGIN;' + DDL + 'COMMIT;')
        db.execute('BEGIN')
        db.executemany('INSERT INTO meta(key,value) VALUES(?,?)',
                       [('layout_version', str(DB_LAYOUT_VERSION)), ('created_at', str(stamp)),
                        ('progress_schema', str(C.SCHEMA_VERSION))])
        db.execute('COMMIT')
        db.execute('PRAGMA user_version=%d' % DB_LAYOUT_VERSION)
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        db.close()
    fsync_file(path)


def _remove_with_sidecars(path):
    for suffix in ('', '-wal', '-shm', '-journal'):
        Path(str(path) + suffix).unlink(missing_ok=True)


class Database:
    """Owns data/game.db: creation, layout checks, connections, transactions, backups."""
    DB_LAYOUT_VERSION = DB_LAYOUT_VERSION

    def __init__(self, data_dir, clock=None):
        self.clock = clock if clock is not None else time.time
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'game.db'
        self._local = threading.local()
        if not self.path.exists():
            self._create()
        self._check_layout()

    # ------------------------------------------------------------------ layout
    def _create(self):
        """Build in a private temp name, then publish without overwriting a concurrent winner."""
        tmp = self.root / ('game.db.%d.%s.new' % (os.getpid(), secrets.token_hex(4)))
        try:
            create_layout(tmp, self.clock())
            try:
                os.link(tmp, self.path)
            except FileExistsError:
                pass
            except OSError:
                if not self.path.exists():
                    os.replace(tmp, self.path)
        finally:
            _remove_with_sidecars(tmp)

    def _check_layout(self):
        if self.path.stat().st_size == 0:
            raise LayoutError('进度数据库为空，拒绝覆盖；请保留原件并恢复备份。')
        try:
            db = open_connection(self.path)
        except sqlite3.DatabaseError as exc:
            raise LayoutError('进度数据库无法打开，已保留原件：%s' % exc) from None
        try:
            try:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                app_id = db.execute('PRAGMA application_id').fetchone()[0]
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            except sqlite3.DatabaseError as exc:
                raise LayoutError('进度数据库无法读取，已保留原件：%s' % exc) from None
            if version == 0 and 'meta' not in tables and tables == {'current', 'requests'}:
                raise LegacyLayoutError('检测到旧版数据文件 %s。请先停服，再运行 python server.py --migrate-multiuser'
                                        '（第1版数据需追加 --migrate-save）；原数据未改动。' % self.path)
            if version > DB_LAYOUT_VERSION:
                raise LayoutError('数据库布局版本 %d 高于当前程序支持的 %d，已保留原件' % (version, DB_LAYOUT_VERSION))
            if version < 1 or app_id != APPLICATION_ID or not set(TABLES) <= tables:
                raise LayoutError('进度数据库布局不受支持，已保留原件')
            try:
                if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise LayoutError('进度数据库完整性检查失败，已保留原件')
            except sqlite3.DatabaseError as exc:
                raise LayoutError('进度数据库完整性检查失败，已保留原件：%s' % exc) from None
            row = db.execute("SELECT value FROM meta WHERE key='layout_version'").fetchone()
            if row is None or row[0] != str(version):
                raise LayoutError('进度数据库布局记录不一致，已保留原件')
            mode = db.execute('PRAGMA journal_mode').fetchone()[0].lower()
            if mode != 'wal':
                mode = db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower()
            if mode != 'wal':
                raise LayoutError('当前存储位置不支持 WAL 日志模式（网络盘或只读介质？），拒绝启动')
        finally:
            db.close()
        if version < DB_LAYOUT_VERSION:
            self._run_migrations(version)

    def _run_migrations(self, from_version):
        """Apply MIGRATIONS[from_version+1 ..] in order, each after a verified backup."""
        for target in range(from_version + 1, DB_LAYOUT_VERSION + 1):
            step = MIGRATIONS.get(target)
            if step is None:
                raise LayoutError('缺少布局升级步骤 %d，已保留原件' % target)
            self.backup(unique_path(self.root, 'game.pre-layout%d.' % target, utc_stamp(), '.bak.db'))
            with self.tx() as db:
                step(db)
                db.execute('PRAGMA user_version=%d' % target)
                db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('layout_version',?)", (str(target),))

    # ------------------------------------------------------------- connections
    def connect(self):
        """New autocommit connection (callers close it). WAL/FULL/FK/busy_timeout applied."""
        return open_connection(self.path)

    @contextmanager
    def read(self):
        """Deferred read transaction: a consistent WAL snapshot, no write lock."""
        db = self.connect()
        try:
            db.execute('BEGIN')
            try:
                yield db
            finally:
                if db.in_transaction:
                    db.execute('ROLLBACK')
        finally:
            db.close()

    @contextmanager
    def tx(self):
        """BEGIN IMMEDIATE ... COMMIT; any exception rolls back and propagates."""
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            self._local.active = True
            try:
                yield db
                db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
        finally:
            self._local.active = False
            db.close()

    def write_tx_active(self):
        """True while the current thread holds a write transaction (used by tests)."""
        return bool(getattr(self._local, 'active', False))

    def ping(self):
        """Cheap liveness probe: layout metadata only, never user rows."""
        db = self.connect()
        try:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            row = db.execute("SELECT value FROM meta WHERE key='layout_version'").fetchone()
        finally:
            db.close()
        return {'schema_version': C.SCHEMA_VERSION, 'layout_version': int(row[0]) if row else version}

    # ------------------------------------------------------------------ backup
    def backup(self, dest=None):
        """Online backup (sqlite3 backup API; writers are not blocked). Returns the new file path."""
        if dest is None:
            dest = unique_path(self.root / 'backups', 'game.', utc_stamp(), '.bak.db')
        dest = Path(dest)
        if dest.exists():
            raise LayoutError('备份目标已存在，拒绝覆盖')
        dest.parent.mkdir(parents=True, exist_ok=True)
        source = self.connect()
        target = None
        try:
            before = self._counts(source)
            target = sqlite3.connect(str(dest))
            source.backup(target)
            after = self._counts(source)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise LayoutError('备份完整性检查失败')
            copied = self._counts(target)
            for name in TABLES:
                low, high = sorted((before[name], after[name]))
                if not low <= copied[name] <= high:
                    raise LayoutError('备份与原库行数不一致：' + name)
            target.close()
            target = None
            fsync_file(dest)
            return dest
        except Exception:
            if target is not None:
                target.close()
                target = None
            _remove_with_sidecars(dest)
            raise
        finally:
            if target is not None:
                target.close()
            source.close()

    @staticmethod
    def _counts(db):
        return {name: db.execute('SELECT count(*) FROM ' + name).fetchone()[0] for name in TABLES}


# SQL guard: every statement on current/requests must bind user_id at a known placeholder.
_PREDICATE = re.compile(r'\buser_id\s*=\s*\?')
_FIRST_COLUMN = re.compile(r'\(\s*user_id\s*,')


class ProgressRepo:
    """The only SQL on `current` and `requests`; each statement is scoped by user_id."""

    @staticmethod
    def _exec(db, sql, params, user_id):
        """Run sql after proving that its user_id placeholder is bound to user_id."""
        if type(user_id) is not int:
            raise AssertionError('账号编号类型无效')
        match = _PREDICATE.search(sql)
        if match:
            index = sql.count('?', 0, match.start())
        elif _FIRST_COLUMN.search(sql):
            index = 0
        else:
            raise AssertionError('进度表语句缺少账号条件')
        if index >= len(params) or type(params[index]) is not int or params[index] != user_id:
            raise AssertionError('进度表语句的账号参数与当前账号不符')
        return db.execute(sql, params)

    @staticmethod
    def ensure_row(db, user_id, now):
        """Create the user's empty progress row if missing (idempotent)."""
        ProgressRepo._exec(
            db, "INSERT OR IGNORE INTO current(user_id,schema_version,revision,state,slot,updated_at) "
                "VALUES(?,?,0,'null','null',?)", (user_id, C.SCHEMA_VERSION, now), user_id)

    @staticmethod
    def load(db, user_id):
        """(schema_version, revision, state_text, slot_text) or None."""
        return ProgressRepo._exec(
            db, 'SELECT schema_version,revision,state,slot FROM current WHERE user_id=?', (user_id,), user_id).fetchone()

    @staticmethod
    def ledger_get(db, user_id, request_id):
        """Stored canonical payload for this user's request_id, or None."""
        row = ProgressRepo._exec(
            db, 'SELECT payload FROM requests WHERE user_id=? AND request_id=?', (user_id, request_id), user_id).fetchone()
        return row[0] if row else None

    @staticmethod
    def has_progress(db, user_id):
        """True when the user already has a character, a revision, or any ledger row."""
        row = ProgressRepo.load(db, user_id)
        if row is not None and (row[1] > 0 or row[2] != 'null'):
            return True
        return ProgressRepo._exec(db, 'SELECT 1 FROM requests WHERE user_id=? LIMIT 1', (user_id,), user_id).fetchone() is not None

    @staticmethod
    def commit(db, user_id, expected_revision, schema_version, state, slot, request_id, canonical, now):
        """Inside an open BEGIN IMMEDIATE: recheck ledger, CAS the row, append the ledger.

        state/slot are already-encoded JSON text. Writes nothing for DUPLICATE/STALE.
        """
        if ProgressRepo.ledger_get(db, user_id, request_id) is not None:
            return CommitOutcome.DUPLICATE
        cursor = ProgressRepo._exec(
            db, 'UPDATE current SET revision=?,schema_version=?,state=?,slot=?,updated_at=? WHERE user_id=? AND revision=?',
            (expected_revision + 1, schema_version, state, slot, now, user_id, expected_revision), user_id)
        if cursor.rowcount != 1:
            return CommitOutcome.STALE
        ProgressRepo._exec(
            db, 'INSERT INTO requests(user_id,request_id,payload) VALUES(?,?,?)', (user_id, request_id, canonical), user_id)
        return CommitOutcome.COMMITTED

    @staticmethod
    def import_legacy(db, user_id, state, slot, revision, force, now):
        """Inside an open BEGIN IMMEDIATE: replace the user's progress with upgraded legacy data.

        state/slot are encoded JSON text. The ledger comes from legacy_requests. Without force an
        account that already has progress is refused (ProgressConflict).
        """
        ProgressRepo.ensure_row(db, user_id, now)
        if ProgressRepo.has_progress(db, user_id):
            if not force:
                raise ProgressConflict('目标账号已有进度；确认覆盖请加 --force（覆盖前会自动备份）')
            ProgressRepo._exec(db, 'DELETE FROM requests WHERE user_id=?', (user_id,), user_id)
        ProgressRepo._exec(
            db, 'UPDATE current SET schema_version=?,revision=?,state=?,slot=?,updated_at=? WHERE user_id=?',
            (C.SCHEMA_VERSION, revision, state, slot, now, user_id), user_id)
        ProgressRepo._exec(
            db, 'INSERT INTO requests(user_id,request_id,payload) SELECT ?,request_id,payload FROM legacy_requests',
            (user_id,), user_id)


def _is_busy(exc):
    text = str(exc).lower()
    return 'locked' in text or 'busy' in text


class Store:
    """Per-user facade over Database. Cheap to construct; touches no file until used."""

    def __init__(self, db, user_id, clock=None):
        if type(user_id) is not int or not 0 < user_id < 2 ** 63:
            raise ValueError('账号编号无效')
        self.db = db
        self.user_id = user_id
        self.clock = clock if clock is not None else (getattr(db, 'clock', None) or time.time)

    # ------------------------------------------------------------------ reading
    def _decode(self, row):
        """Parse and fully validate a `current` row -> (revision, state, slot)."""
        if not row or row[0] != C.SCHEMA_VERSION or not rules.valid_int(row[1], 0, MAX_INT64):
            raise ValueError('进度数据版本或元信息不受支持')
        state, slot = json.loads(row[2]), json.loads(row[3])
        rules.validate_state(state)
        rules.validate_state(slot)
        growth.validate(state, check_balance=True)
        growth.validate(slot, check_balance=True)
        cadence.validate(state, check_clock=True)
        cadence.validate(slot, check_clock=True)
        return row[1], state, slot

    def _read(self, db):
        return self._decode(ProgressRepo.load(db, self.user_id))

    def _fetch(self, request_id=None):
        """One consistent read: (row, ledger_payload). Creates the empty row on first use."""
        for _ in range(2):
            with self.db.read() as conn:
                row = ProgressRepo.load(conn, self.user_id)
                old = None if row is None or request_id is None else ProgressRepo.ledger_get(conn, self.user_id, request_id)
            if row is not None:
                return row, old
            try:
                with self.db.tx() as conn:
                    ProgressRepo.ensure_row(conn, self.user_id, self._now())
            except sqlite3.IntegrityError:
                raise ValueError('账号不存在，无法读取进度') from None
        raise ValueError('进度数据暂时无法读取')

    def _now(self):
        value = self.clock()
        if type(value) not in (int, float) or value < 0:
            raise ValueError('服务端时钟无效')
        try:
            return int(value)
        except (ValueError, OverflowError):
            raise ValueError('服务端时钟无效') from None

    @staticmethod
    def _context(state, now):
        raw_now = now
        if growth.is_longline(state):
            account = state['world']['r3'].get('growth') or {}
            now = max(now, account.get('last_settled') or now)
        return {'now': now, 'day': datetime.fromtimestamp(now, timezone.utc).date().isoformat(), 'raw_now': raw_now}

    def _snapshot(self, revision, state, slot, events=None, duplicate=False, battle_report=None):
        summary = None if state is None else '%s · %s · 第%d行' % (state['name'], C.REALMS[state['realm']], state['actions_taken'])
        now = self._now()
        projected, growth_view = growth.preview(state, now)
        projected = cadence.sync(projected, self._context(projected, now)['now'])
        view = rules.project(projected, context=self._context(projected, now))
        longline = growth.is_longline(state)
        view['profile'] = {'mode': 'longline' if longline else 'free'}
        if growth_view is not None:
            view['growth'] = growth_view
        result = dict(ok=True, duplicate=duplicate, revision=revision, state=state, view=view,
                      sync={'persisted': True, 'revision': revision, 'saved_at': now, 'summary': summary},
                      events=events or [])
        # The HTTP layer may add fields (e.g. account); this describes the committed server progress only.
        # The auto-battle replay is returned with this response only and is never stored.
        if battle_report is not None:
            result['battle_report'] = battle_report
        return result

    def snapshot(self):
        """Current progress of this user as an API payload (read only)."""
        row, _ = self._fetch()
        return self._snapshot(*self._decode(row))

    # ------------------------------------------------------------------ writing
    @staticmethod
    def _stale(revision):
        exc = rules.GameError('STALE_STATE', '进度已在其他页面更新，请刷新后重试。', 409)
        exc.revision = revision
        return exc

    def _compute(self, endpoint, payload, state, slot, now):
        """Pure rules step (no database access) -> (state, slot, events, context)."""
        state = growth.sync(state, now)
        state = cadence.sync(state, self._context(state, now)['now'])
        context = self._context(state, now)
        events = []
        if endpoint == 'new-game':
            mode = payload.get('mode', 'longline')
            if not isinstance(mode, str) or mode not in {'free', 'longline'}:
                raise rules.GameError('BAD_REQUEST', '游戏模式须为free或longline。', 400)
            state = rules.settle_qi(cadence.sync(growth.sync(rules.new_game(payload['name'], mode=mode), now), now), now)
            slot = None
            events = ['初入青岚村，修行自此开始。']
        elif endpoint == 'action':
            before = state
            state, events = rules.apply_action(state, payload['action'], payload['params'], context=context)
            state = growth.finish(before, state, now)
            state = cadence.sync(state, self._context(state, now)['now'])
        else:
            raise rules.GameError('BAD_REQUEST', '未知操作。', 400)
        rules.validate_state(state)
        rules.validate_state(slot)
        growth.validate(state, check_balance=True)
        growth.validate(slot, check_balance=True)
        cadence.validate(state, check_clock=True)
        cadence.validate(slot, check_clock=True)
        return state, slot, events, context

    def _resolve(self, request_id, canonical):
        """Re-read after a lost race and answer as the ledger/revision now dictate."""
        row, old = self._fetch(request_id)
        current, state, slot = self._decode(row)
        if old is not None:
            return self._replay(old, canonical, current, state, slot)
        raise self._stale(current)

    def _replay(self, old, canonical, current, state, slot):
        if old != canonical:
            raise rules.GameError('REQUEST_ID_REUSED', '请求编号已用于其他操作。', 409)
        return self._snapshot(current, state, slot, duplicate=True)

    def _write_once(self, endpoint, payload, request_id, revision, canonical):
        row, old = self._fetch(request_id)
        current, state, slot = self._decode(row)
        if old is not None:
            return self._replay(old, canonical, current, state, slot)
        if revision != current:
            raise self._stale(current)
        if current >= MAX_INT64:
            raise ValueError('进度数据版本号已到上限，拒绝覆盖')
        now = self._now()  # taken after the read so settlement timestamps follow revisions
        state, slot, events, context = self._compute(endpoint, payload, state, slot, now)
        result = self._snapshot(current + 1, state, slot, events,
                                battle_report=context.get('battle_report') if endpoint == 'action' else None)
        encoded_state, encoded_slot = encode(state), encode(slot)
        try:
            with self.db.tx() as conn:
                outcome = ProgressRepo.commit(conn, self.user_id, current, C.SCHEMA_VERSION,
                                              encoded_state, encoded_slot, request_id, canonical, now)
        except sqlite3.IntegrityError:
            return self._resolve(request_id, canonical)
        if outcome is CommitOutcome.COMMITTED:
            return result
        return self._resolve(request_id, canonical)

    def write(self, endpoint, payload):
        """Apply new-game/action. Returns only after COMMIT; same request_id is idempotent."""
        if endpoint not in ('new-game', 'action'):
            raise rules.GameError('BAD_REQUEST', '未知操作。', 400)
        request_id = payload.get('request_id')
        revision = payload.get('expected_revision')
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128 or any(not 32 <= ord(c) <= 126 for c in request_id):
            raise rules.GameError('BAD_REQUEST', '请求编号须为1至128个可打印ASCII字符。', 400)
        if not rules.valid_int(revision, 0, MAX_INT64):
            raise rules.GameError('BAD_REQUEST', '进度版本须为非负整数。', 400)
        extra = {'name'} if endpoint == 'new-game' else {'action', 'params'}
        fields = set(payload)
        if endpoint == 'new-game':
            fields.discard('mode')
        if fields != {'request_id', 'expected_revision'} | extra:
            raise rules.GameError('BAD_REQUEST', '请求字段不完整或包含未知字段。', 400)
        canonical = encode({'endpoint': endpoint, 'payload': payload})
        for attempt in range(WRITE_RETRIES + 1):
            try:
                return self._write_once(endpoint, payload, request_id, revision, canonical)
            except sqlite3.OperationalError as exc:
                # busy_timeout already waited; retry the whole read-compute-commit a bounded number of times.
                if not _is_busy(exc) or attempt >= WRITE_RETRIES:
                    raise
                time.sleep(random.uniform(0.02, 0.08))
