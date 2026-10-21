"""One-shot operator commands. They run to completion and never start the server.

Passwords are read interactively (getpass), never from argv. The `app` argument is
duck-typed: it needs db, auth, clock (server.App provides them). --migrate-multiuser runs
without an App because the old file layout cannot be opened as a Database.
"""
import getpass
import sqlite3
from pathlib import Path
from typing import Callable, List, Optional

from . import legacy
from .auth import AuthError
from .storage import LayoutError

COMMAND_ARGS = ('create_user', 'reset_password', 'migrate_multiuser', 'claim_legacy', 'legacy_status', 'backup')


def selected_command(args) -> Optional[str]:
    """Return the requested one-shot command name, or None to start the service."""
    chosen: List[str] = [name for name in COMMAND_ARGS if getattr(args, name, None)]
    if len(chosen) > 1:
        raise ValueError('运维命令不能同时使用：' + '、'.join('--' + n.replace('_', '-') for n in chosen))
    return chosen[0] if chosen else None


def _ask_password(prompt: Callable[[str], str]) -> str:
    first = prompt('请输入密码：')
    if first != prompt('请再次输入密码：'):
        raise AuthError('INVALID_PASSWORD', '两次输入的密码不一致。', 400)
    return first


def create_user(app, username: str, prompt: Callable[[str], str] = getpass.getpass) -> int:
    """Create an account interactively (for --no-register deployments)."""
    app.auth.normalize_username(username)
    app.auth.create_account(username, _ask_password(prompt))
    print('账号已创建：%s' % app.auth.normalize_username(username)[0])
    return 0


def reset_password(app, username: str, prompt: Callable[[str], str] = getpass.getpass) -> int:
    """Set a new password; all sessions of the account are revoked."""
    if app.auth.find_account(username) is None:
        print('账号不存在：%s' % username)
        return 1
    app.auth.set_password(username, _ask_password(prompt))
    print('密码已重置，该账号的全部登录会话已失效。')
    return 0


def legacy_status(app) -> int:
    """Print the state of the unclaimed old data area (read only)."""
    record = legacy.status(app.db)
    if record is None:
        print('待认领区：无（未登记旧版数据）')
        return 0
    print('待认领区状态：%s' % record.status)
    print('  迁移前备份：%s' % record.backup_file)
    print('  数据版本：%d  进度序号：%d  请求账本：%d 条' % (record.source_schema, record.revision, record.ledger_count))
    print('  校验和：%s' % record.sha256)
    if record.claimed_by:
        print('  认领账号：%s' % (record.claimed_by_name or '（账号已不存在）'))
    return 0


def migrate_multiuser(data_dir, confirm_v1: bool = False) -> int:
    """Back up and move the old data/game.db into the unclaimed area (service must be stopped).

    Takes the data directory instead of an App: the old file layout cannot be opened as a Database.
    """
    try:
        record = legacy.migrate_multiuser(Path(data_dir), confirm_v1=confirm_v1)
    except (legacy.LegacyError, LayoutError, OSError, sqlite3.Error) as exc:
        print('旧版数据迁移未完成，原数据未改动：%s' % exc)
        return 1
    print('旧版数据已迁入待认领区（状态：%s）；迁移前备份：%s' % (record.status, record.backup_file))
    print('下一步：该用户先注册或由 --create-user 创建账号，再运行 --claim-legacy 用户名。')
    return 0


def claim_legacy(app, username: str, force: bool = False) -> int:
    """Attach the unclaimed old data to an existing account."""
    try:
        record = legacy.claim(app.db, username, force=force, clock=app.clock)
    except (legacy.LegacyError, LayoutError, OSError, sqlite3.Error, ValueError) as exc:
        print('认领未完成，原数据未改动：%s' % exc)
        return 1
    print('旧版数据已归属账号：%s（进度序号：%d）' % (record.claimed_by_name or username, record.revision))
    return 0


def backup(app) -> int:
    """Online backup of the single database to data/backups/game.<UTC>.bak.db (service may keep running)."""
    try:
        dest = app.db.backup()
    except (LayoutError, OSError, sqlite3.Error) as exc:
        print('备份未完成：%s' % exc)
        return 1
    print('已备份到：%s' % dest)
    return 0


def run(args, app, prompt: Callable[[str], str] = getpass.getpass) -> int:
    """Dispatch the selected one-shot command and return a process exit code.

    app may be None only for migrate_multiuser (which takes args.data_dir).
    """
    name = selected_command(args)
    try:
        if name == 'migrate_multiuser':
            return migrate_multiuser(args.data_dir, bool(getattr(args, 'migrate_data', False)))
        if name == 'create_user':
            return create_user(app, args.create_user, prompt)
        if name == 'reset_password':
            return reset_password(app, args.reset_password, prompt)
        if name == 'claim_legacy':
            return claim_legacy(app, args.claim_legacy, bool(getattr(args, 'force', False)))
        if name == 'legacy_status':
            return legacy_status(app)
        if name == 'backup':
            return backup(app)
    except AuthError as exc:
        print(exc.message)
        return 1
    raise ValueError('没有指定运维命令')
