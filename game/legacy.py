"""Pre-multiuser data: verified import into the unclaimed area, and explicit claiming.

Never automatic: old progress is only ever attached to an account by an operator
running claim(). No HTTP path reads legacy_progress/legacy_requests.

Public interface (used by game/admin.py and server.py):
    legacy_format_present(data_dir) -> bool
    migrate_multiuser(data_dir, confirm_v1=False) -> LegacyRecord
    status(db) -> LegacyRecord | None
    claim(db, account, force=False, clock=None) -> LegacyRecord   # account: user id (int) or username (str)
    upgrade_progress(state, slot, now, source_schema=2) -> (state, slot, bumped)
    backup_verified(src, dst_dir, prefix) -> Path                  # old-format files only
"""
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from . import cadence
from . import config as C
from . import growth
from . import rules
from .auth import _key_of
from .storage import (Database, LayoutError, ProgressConflict, ProgressRepo, create_layout, encode,
                      fsync_file, open_connection, unique_path, utc_stamp)

UNCLAIMED = 'unclaimed'
CLAIMED = 'claimed'
MAX_INT64 = 2 ** 63 - 1


class LegacyError(ValueError):
    """Operator-facing failure; the original data was left untouched."""


@dataclass(frozen=True)
class LegacyRecord:
    """The single legacy_progress row (state/slot text is deliberately not exposed)."""
    status: str = UNCLAIMED
    source_schema: int = 0
    revision: int = 0
    ledger_count: int = 0
    sha256: str = ''
    backup_file: str = ''
    claimed_by: int = 0
    claimed_by_name: str = ''
    claimed_at: int = 0
    created_at: int = 0


# ---------------------------------------------------------------- old-format helpers
def _open_ro(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)


def _rows(db):
    return (db.execute('SELECT schema_version,revision,state,slot FROM current ORDER BY id').fetchall(),
            db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall())


def _digest(schema, revision, state, slot, ledger):
    """sha256 over the canonical dump of one old database (raw state/slot text, sorted ledger)."""
    dump = encode([schema, revision, state, slot, [list(r) for r in sorted(ledger)]])
    return hashlib.sha256(dump.encode('utf-8')).hexdigest()


def backup_verified(src, dst_dir, prefix):
    """Copy an old-format database with the backup API, verify row by row, fsync.

    Returns the backup path; on any failure the partial file is removed.
    """
    src, dst_dir = Path(src), Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    target_path = unique_path(dst_dir, prefix, utc_stamp(), '.bak.db')
    source = target = None
    try:
        source = _open_ro(src)
        target = sqlite3.connect(str(target_path))
        source.backup(target)
        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise LegacyError('备份完整性检查失败')
        if _rows(source) != _rows(target):
            raise LegacyError('备份与原件内容不一致')
        target.close()
        target = None
        fsync_file(target_path)
        return target_path
    except Exception:
        if target is not None:
            target.close()
            target = None
        target_path.unlink(missing_ok=True)
        raise
    finally:
        if source is not None:
            source.close()
        if target is not None:
            target.close()


def legacy_format_present(data_dir):
    """True when data/game.db is an unmigrated pre-multiuser file (startup guard)."""
    path = Path(data_dir) / 'game.db'
    try:
        if not path.is_file() or path.stat().st_size == 0:
            return False
        db = _open_ro(path)
        try:
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return db.execute('PRAGMA user_version').fetchone()[0] == 0 and tables == {'current', 'requests'}
        finally:
            db.close()
    except (sqlite3.DatabaseError, OSError):
        return False


def _is_new_layout(path):
    """True when path already carries the multi-account layout (any version)."""
    try:
        db = _open_ro(path)
        try:
            return db.execute('PRAGMA application_id').fetchone()[0] == 0x47584D55
        finally:
            db.close()
    except sqlite3.DatabaseError:
        return False


def _read_source(path, confirm_v1):
    """Validate the old database read-only and return (schema, revision, state, slot, ledger)."""
    if path.stat().st_size == 0:
        raise LegacyError('旧版数据文件为空')
    for suffix in ('-journal', '-wal', '-shm'):
        if path.with_name(path.name + suffix).exists():
            raise LegacyError('旧版数据疑似未正常结束，请先用旧版正常启动并退出一次')
    try:
        db = _open_ro(path)
    except sqlite3.DatabaseError as exc:
        raise LegacyError('旧版数据无法打开：%s' % exc) from None
    try:
        try:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise LegacyError('旧版数据完整性检查失败')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables != {'current', 'requests'}:
                raise LegacyError('旧版数据表结构不受支持')
            db.execute('BEGIN')
            rows = db.execute('SELECT schema_version,revision,state,slot FROM current').fetchall()
            ledger = db.execute('SELECT request_id,payload FROM requests ORDER BY request_id').fetchall()
        except sqlite3.DatabaseError as exc:
            raise LegacyError('旧版数据无法读取：%s' % exc) from None
    finally:
        db.close()
    if len(rows) != 1 or rows[0][0] not in (1, 2) or type(rows[0][1]) is not int or not 0 <= rows[0][1] <= MAX_INT64:
        raise LegacyError('旧版数据版本或记录无效')
    schema, revision, state, slot = rows[0]
    if not isinstance(state, str) or not isinstance(slot, str):
        raise LegacyError('旧版进度内容无效')
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in ledger):
        raise LegacyError('旧版数据请求账本无效')
    if schema == 1 and not confirm_v1:
        raise LegacyError('这是第1版数据。请同时使用 --migrate-save（别名 --migrate-data）确认先备份再迁移；原件未更改。')
    return schema, revision, state, slot, ledger


# ---------------------------------------------------------------- content upgrade
def _needs_content_upgrade(state):
    return growth.is_longline(state) and (
        growth.curve_version(state) != 2 or any(key not in state['world']['r3'] for key in ('cadence', 'journey')))


def _validate_full(state):
    rules.validate_state(state)
    growth.validate(state, check_balance=True)
    cadence.validate(state, check_clock=True)


def upgrade_progress(state, slot, now, source_schema=2):
    """Offline upgrade of decoded progress: v1 -> v2 world, then R4 content. Pure; no database.

    Returns (state, slot, bumped); bumped is True when content was rewritten, in which
    case the caller raises the revision by one (same rule the online path used to apply).
    """
    from . import journey
    from . import world
    if source_schema == 1:
        rules.validate_legacy_state(state)
        rules.validate_legacy_state(slot)

        def lift(old):
            if old is None:
                return None
            original = json.loads(encode(old))
            upgraded = world.migrate_v1(old)
            if not isinstance(upgraded, dict) or set(upgraded) != set(original) | {'world'} or any(
                    upgraded[key] != value for key, value in original.items()):
                raise ValueError('迁移改变了原有角色字段，拒绝提交')
            return upgraded

        state, slot = lift(state), lift(slot)
    elif source_schema != 2:
        raise ValueError('进度数据版本不受支持')
    _validate_full(state)
    _validate_full(slot)
    bumped = any(_needs_content_upgrade(s) for s in (state, slot))
    if not bumped:
        return state, slot, False

    def upgrade(old):
        if not _needs_content_upgrade(old):
            return old
        result = growth.upgrade_legacy(old, now)
        result = cadence.migrate_legacy(result, now)
        journey.migrate(result['world'])
        _validate_full(result)
        return result

    return upgrade(state), upgrade(slot), True


def _trial_upgrade(schema, state_text, slot_text, now):
    try:
        upgrade_progress(json.loads(state_text), json.loads(slot_text), now, schema)
    except (ValueError, KeyError, TypeError) as exc:
        raise LegacyError('旧版进度无法通过升级校验，原数据未改动：%s' % exc) from None


# ---------------------------------------------------------------- migrate
def _record_from_row(row):
    return LegacyRecord(status=row[0], source_schema=row[1], revision=row[2], ledger_count=row[3], sha256=row[4],
                        backup_file=row[5], claimed_by=row[6] or 0, claimed_at=row[7], created_at=row[8],
                        claimed_by_name=row[9] or '')


_SELECT_RECORD = ('SELECT l.status,l.source_schema,l.revision,l.ledger_count,l.sha256,l.backup_file,l.claimed_by,'
                  'l.claimed_at,l.created_at,a.username FROM legacy_progress l LEFT JOIN accounts a ON a.id=l.claimed_by WHERE l.id=1')


def status(db):
    """Current LegacyRecord from the unclaimed area, or None when nothing was migrated."""
    with db.read() as conn:
        row = conn.execute(_SELECT_RECORD).fetchone()
    return _record_from_row(row) if row else None


def _fill_new_database(tmp, schema, revision, state, slot, ledger, backup_name, now):
    """Create the new layout at tmp and write the unclaimed area in one transaction; verify."""
    create_layout(tmp, now)
    sha = _digest(schema, revision, state, slot, ledger)
    conn = open_connection(tmp)
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO legacy_progress(id,status,source_schema,revision,state,slot,ledger_count,sha256,'
                     'backup_file,claimed_by,claimed_at,created_at) VALUES(1,?,?,?,?,?,?,?,?,NULL,0,?)',
                     (UNCLAIMED, schema, revision, state, slot, len(ledger), sha, backup_name, now))
        conn.executemany('INSERT INTO legacy_requests(request_id,payload) VALUES(?,?)', ledger)
        conn.execute('COMMIT')
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise LegacyError('新库完整性检查失败')
        row = conn.execute('SELECT source_schema,revision,state,slot,ledger_count,sha256 FROM legacy_progress WHERE id=1').fetchone()
        stored = conn.execute('SELECT request_id,payload FROM legacy_requests ORDER BY request_id').fetchall()
        if len(stored) != row[4] or row[4] != len(ledger) or _digest(row[0], row[1], row[2], row[3], stored) != row[5] or row[5] != sha:
            raise LegacyError('新库内容与原件校验和不一致')
        conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    finally:
        conn.close()
    fsync_file(tmp)
    return sha


def migrate_multiuser(data_dir, confirm_v1=False):
    """Back up the old data/game.db, import it into a fresh multi-account database, swap atomically.

    Needs the service stopped. Safe to re-run: before the final os.replace the old file is
    untouched; afterwards the layout is new and a re-run reports the existing record.
    """
    root = Path(data_dir)
    source = root / 'game.db'
    if not source.exists():
        raise LegacyError('没有发现旧版数据文件')
    if _is_new_layout(source):
        db = Database(root)
        record = status(db)
        if record is None:
            raise LegacyError('当前已是多账号布局，没有旧版数据需要迁移')
        return record
    lock = root / '.migrate.lock'
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise LegacyError('另一个迁移正在进行，或上次迁移异常中断；确认无其他实例后删除 %s' % lock.name) from None
    os.close(descriptor)
    tmp = root / 'game.db.migrating'
    try:
        schema, revision, state, slot, ledger = _read_source(source, confirm_v1)
        now = int(time.time())
        _trial_upgrade(schema, state, slot, now)
        backup = backup_verified(source, root, 'game.pre-multiuser.')
        for suffix in ('', '-wal', '-shm', '-journal'):
            Path(str(tmp) + suffix).unlink(missing_ok=True)
        _fill_new_database(tmp, schema, revision, state, slot, ledger, backup.name, now)
        try:
            os.replace(tmp, source)
        except OSError as exc:
            raise LegacyError('无法替换数据文件，请确认服务已停止：%s' % exc) from None
        return status(Database(root))
    except BaseException:
        for suffix in ('', '-wal', '-shm', '-journal'):
            Path(str(tmp) + suffix).unlink(missing_ok=True)
        raise
    finally:
        lock.unlink(missing_ok=True)


# ---------------------------------------------------------------- claim
def _resolve_account(db, account):
    """Account id from an int id or a username (NFKC + casefold, same key as registration)."""
    with db.read() as conn:
        if type(account) is int:
            row = conn.execute('SELECT id FROM accounts WHERE id=?', (account,)).fetchone()
        elif isinstance(account, str):
            key = _key_of(account)
            row = conn.execute('SELECT id FROM accounts WHERE username_key=?', (key,)).fetchone() if key else None
        else:
            row = None
    if row is None:
        raise LegacyError('账号不存在，请先注册或创建该账号')
    return row[0]


def claim(db, account, force=False, clock=None):
    """Attach the unclaimed old progress to an existing account in ONE transaction.

    Upgrade (v1 -> v2, R4 content) runs outside the transaction on a decoded copy. With force an
    account that already has progress is overwritten after a verified online backup.
    """
    user_id = _resolve_account(db, account)
    record = status(db)
    if record is None:
        raise LegacyError('没有待认领的旧版数据')
    if record.status == CLAIMED:
        raise LegacyError('旧版数据已被账号 %s 认领' % (record.claimed_by_name or record.claimed_by))
    with db.read() as conn:
        row = conn.execute('SELECT source_schema,revision,state,slot FROM legacy_progress WHERE id=1').fetchone()
    schema, revision, state_text, slot_text = row
    now = int((clock or time.time)())
    try:
        state, slot, bumped = upgrade_progress(json.loads(state_text), json.loads(slot_text), now, schema)
    except (ValueError, KeyError, TypeError) as exc:
        raise LegacyError('旧版进度升级失败，原数据未改动：%s' % exc) from None
    if bumped:
        if revision >= MAX_INT64:
            raise LegacyError('进度数据版本号已到上限，拒绝覆盖')
        revision += 1
    with db.read() as conn:
        has_progress = ProgressRepo.has_progress(conn, user_id)
    if has_progress:
        if not force:
            raise LegacyError('目标账号已有进度；确认覆盖请加 --force（覆盖前会自动备份）')
        db.backup(unique_path(db.root, 'game.pre-claim.', utc_stamp(), '.bak.db'))
    encoded_state, encoded_slot = encode(state), encode(slot)
    try:
        with db.tx() as conn:
            current = conn.execute('SELECT status FROM legacy_progress WHERE id=1').fetchone()
            if current is None or current[0] != UNCLAIMED:
                raise LegacyError('旧版数据已被其他操作认领')
            ProgressRepo.import_legacy(conn, user_id, encoded_state, encoded_slot, revision, force, now)
            conn.execute("UPDATE legacy_progress SET status=?,claimed_by=?,claimed_at=? WHERE id=1 AND status=?",
                         (CLAIMED, user_id, now, UNCLAIMED))
    except ProgressConflict as exc:
        raise LegacyError(str(exc)) from None
    return status(db)
