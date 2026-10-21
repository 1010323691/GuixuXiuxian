"""Accounts, sessions, password hashing and rate limits, stored in the shared data/game.db.

Identity comes only from a server-side session token (Cookie). Plain tokens and
passwords are never stored: sessions keep sha256(token), accounts keep scrypt.
The tables (accounts/sessions/login_attempts) are created by storage.create_layout;
this module only reads and writes them through Database.connect()/tx(). The slow
KDF always runs outside any write transaction.
"""
import hashlib
import hmac
import http.cookies
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .rules import GameError
from .settings import Settings
from .storage import Database

USERNAME_RE = re.compile(r'^[一-鿿A-Za-z0-9_]{3,20}$')
MAX_PASSWORD_PROBE = 256
DUMMY_SALT = b'\x00' * 16
DUMMY_HASH = b'\x00' * 32


class AuthError(GameError):
    """GameError with optional field name, retry delay and cookie-clearing flag."""

    def __init__(self, code: str, message: str, status: int = 400, field: Optional[str] = None,
                 retry_after: Optional[int] = None, clear_cookie: bool = False) -> None:
        super().__init__(code, message, status)
        self.field = field
        self.retry_after = retry_after
        self.clear_cookie = clear_cookie


@dataclass(frozen=True)
class Principal:
    """Authenticated caller. set_cookie is a refreshed Set-Cookie value, if any."""
    account_id: int
    username: str
    session_id: int
    token_hash: str = ''
    set_cookie: str = ''


class PasswordHasher:
    """scrypt with per-account salt; parameters are stored with each hash."""
    algo = 'scrypt'

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._gate = threading.BoundedSemaphore(max(1, settings.hash_concurrency))

    def current_params(self) -> str:
        s = self.settings
        return 'n=%d,r=%d,p=%d' % (s.kdf_n, s.kdf_r, s.kdf_p)

    @staticmethod
    def _parse(params: str) -> Tuple[int, int, int]:
        values = dict(item.split('=') for item in params.split(','))
        return int(values['n']), int(values['r']), int(values['p'])

    def _derive(self, password: str, salt: bytes, params: str) -> bytes:
        n, r, p = self._parse(params)
        with self._gate:
            return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=n, r=r, p=p, dklen=32,
                                  maxmem=256 * n * r * p + 8 * 1024 * 1024)

    def hash(self, password: str, params: Optional[str] = None) -> Tuple[str, bytes, bytes]:
        """Return (params, salt, digest) for a fresh random salt."""
        params = params or self.current_params()
        salt = os.urandom(16)
        return params, salt, self._derive(password, salt, params)

    def verify(self, password: str, salt: bytes, expected: bytes, params: str) -> bool:
        """Constant-time comparison of the derived key with the stored one."""
        return hmac.compare_digest(self._derive(password, bytes(salt), params), bytes(expected))

    def needs_rehash(self, params: str) -> bool:
        return params != self.current_params()


def _key_of(raw: object) -> str:
    """Tolerant lookup key (never raises): casefold(NFKC(strip))."""
    if not isinstance(raw, str):
        return ''
    return unicodedata.normalize('NFKC', raw).strip().casefold()[:64]


class AuthService:
    """All account/session operations on the shared Database (thread safe: one connection per call)."""

    def __init__(self, db: Database, settings: Optional[Settings] = None, clock=None) -> None:
        self.db = db
        self.settings = settings or Settings()
        self.clock = clock or getattr(db, 'clock', None) or time.time
        self.hasher = PasswordHasher(self.settings)

    # ------------------------------------------------------------ storage
    def _now(self) -> int:
        return int(self.clock())

    def _connect(self) -> sqlite3.Connection:
        return self.db.connect()

    def _tx(self):
        """BEGIN IMMEDIATE ... COMMIT context from Database; exceptions roll back and propagate."""
        return self.db.tx()

    def ping(self) -> Dict[str, object]:
        """Cheap liveness probe (layout metadata only, never user rows)."""
        info = dict(self.db.ping())
        info['registration_open'] = self.settings.registration_open
        return info

    # ------------------------------------------------------------ validation
    def normalize_username(self, raw: object) -> Tuple[str, str]:
        """Return (display, key) or raise INVALID_USERNAME."""
        if not isinstance(raw, str):
            raise AuthError('INVALID_USERNAME', '用户名需为3–20位：中文、字母、数字或下划线。', 400, 'username')
        display = unicodedata.normalize('NFKC', raw).strip()
        if not USERNAME_RE.match(display):
            raise AuthError('INVALID_USERNAME', '用户名需为3–20位：中文、字母、数字或下划线。', 400, 'username')
        return display, display.casefold()

    def validate_password(self, password: object, username_key: str = '', field: str = 'password') -> None:
        """Enforce 8-64 printable code points and not equal to the username."""
        if not isinstance(password, str) or not 8 <= len(password) <= 64:
            raise AuthError('INVALID_PASSWORD', '密码长度需为8–64个字符。', 400, field)
        try:
            password.encode('utf-8')
        except UnicodeEncodeError:
            raise AuthError('INVALID_PASSWORD', '密码包含不可用字符。', 400, field) from None
        if not password.isprintable():
            raise AuthError('INVALID_PASSWORD', '密码包含不可用字符。', 400, field)
        if username_key and password.casefold() == username_key:
            raise AuthError('INVALID_PASSWORD', '密码不能与用户名相同。', 400, field)

    # ------------------------------------------------------------ rate limits
    @staticmethod
    def _rate_error(retry: int) -> AuthError:
        retry = max(1, int(retry))
        minutes = max(1, math.ceil(retry / 60))
        return AuthError('RATE_LIMITED', '尝试次数过多，请 %d 分钟后再试。' % minutes, 429, retry_after=retry)

    def _locked_for(self, db, scope: str, key: str, now: int) -> int:
        row = db.execute('SELECT locked_until FROM login_attempts WHERE scope=? AND key=?', (scope, key)).fetchone()
        return row[0] - now if row and row[0] > now else 0

    def _check_lock(self, db, checks, now: int) -> None:
        for scope, key in checks:
            remaining = self._locked_for(db, scope, key, now)
            if remaining:
                raise self._rate_error(remaining)

    def _record_failure(self, db, scope: str, key: str, limit: int, now: int) -> None:
        row = db.execute('SELECT fails,last_fail_at FROM login_attempts WHERE scope=? AND key=?', (scope, key)).fetchone()
        fails = 0 if row is None or now - row[1] >= self.settings.failure_window_seconds else row[0]
        fails += 1
        locked = 0
        if fails >= limit:
            fails, locked = 0, now + self.settings.lockout_seconds
        elif row is not None:
            locked = db.execute('SELECT locked_until FROM login_attempts WHERE scope=? AND key=?', (scope, key)).fetchone()[0]
        db.execute('INSERT OR REPLACE INTO login_attempts(scope,key,fails,last_fail_at,locked_until) VALUES(?,?,?,?,?)',
                   (scope, key, fails, now, locked))

    def _purge(self, db, now: int) -> None:
        s = self.settings
        db.execute('DELETE FROM sessions WHERE expires_at<=? OR absolute_expires_at<=?', (now, now))
        db.execute("DELETE FROM login_attempts WHERE scope!='register_ip' AND locked_until<=? AND last_fail_at<?",
                   (now, now - s.failure_window_seconds))
        db.execute("DELETE FROM login_attempts WHERE scope='register_ip' AND last_fail_at<?",
                   (now - s.register_window_seconds,))

    def _check_register_limit(self, db, ip: str, now: int) -> None:
        row = db.execute("SELECT fails,last_fail_at FROM login_attempts WHERE scope='register_ip' AND key=?", (ip,)).fetchone()
        window = self.settings.register_window_seconds
        if row and now - row[1] < window and row[0] >= self.settings.register_per_ip_hour:
            raise self._rate_error(row[1] + window - now)

    def _count_register(self, db, ip: str, now: int) -> None:
        row = db.execute("SELECT fails,last_fail_at FROM login_attempts WHERE scope='register_ip' AND key=?", (ip,)).fetchone()
        if row is None or now - row[1] >= self.settings.register_window_seconds:
            fails, start = 1, now
        else:
            fails, start = row[0] + 1, row[1]
        db.execute("INSERT OR REPLACE INTO login_attempts(scope,key,fails,last_fail_at,locked_until) VALUES('register_ip',?,?,?,0)",
                   (ip, fails, start))

    # ------------------------------------------------------------ cookies / sessions
    def cookie_for(self, token: str, max_age: int) -> str:
        """Build a Set-Cookie value (empty token + 0 clears the cookie)."""
        parts = ['%s=%s' % (self.settings.cookie_name, token), 'Path=/', 'HttpOnly', 'SameSite=Lax', 'Max-Age=%d' % max(0, int(max_age))]
        if self.settings.secure_cookies:
            parts.append('Secure')
        return '; '.join(parts)

    def clear_cookie(self) -> str:
        return self.cookie_for('', 0)

    def _token_from(self, cookie_header: Optional[str]) -> Optional[str]:
        if not cookie_header:
            return None
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(cookie_header)
        except http.cookies.CookieError:
            return None
        morsel = jar.get(self.settings.cookie_name)
        if morsel is None or not morsel.value or len(morsel.value) > 128:
            return None
        return morsel.value

    def token_hash_from(self, cookie_header: Optional[str]) -> Optional[str]:
        token = self._token_from(cookie_header)
        return hashlib.sha256(token.encode('utf-8')).hexdigest() if token else None

    def _create_session(self, db, account_id: int, now: int) -> Tuple[int, str, int]:
        s = self.settings
        token = secrets.token_urlsafe(32)
        absolute = now + s.session_absolute_seconds
        expires = min(now + s.session_idle_seconds, absolute)
        cursor = db.execute(
            'INSERT INTO sessions(token_hash,account_id,created_at,last_seen_at,expires_at,absolute_expires_at) VALUES(?,?,?,?,?,?)',
            (hashlib.sha256(token.encode('utf-8')).hexdigest(), account_id, now, now, expires, absolute))
        db.execute('''DELETE FROM sessions WHERE account_id=? AND id NOT IN
                      (SELECT id FROM sessions WHERE account_id=? ORDER BY last_seen_at DESC, id DESC LIMIT ?)''',
                   (account_id, account_id, s.max_sessions_per_account))
        return cursor.lastrowid, token, expires - now

    def authenticate(self, cookie_header: Optional[str]) -> Principal:
        """Resolve the session Cookie to a Principal or raise 401 AuthError."""
        token = self._token_from(cookie_header)
        if token is None:
            raise AuthError('AUTH_REQUIRED', '请先登录。', 401)
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        now = self._now()
        db = self._connect()
        try:
            row = db.execute('''SELECT s.id,s.account_id,s.last_seen_at,s.expires_at,s.absolute_expires_at,a.username
                                FROM sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=?''', (token_hash,)).fetchone()
        finally:
            db.close()
        if row is None or row[3] <= now or row[4] <= now:
            if row is not None:
                with self._tx() as write:
                    write.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))
            raise AuthError('SESSION_EXPIRED', '登录已过期，请重新登录。', 401, clear_cookie=True)
        cookie = ''
        if now - row[2] >= self.settings.session_touch_interval:
            expires = min(now + self.settings.session_idle_seconds, row[4])
            with self._tx() as write:
                write.execute('UPDATE sessions SET last_seen_at=?,expires_at=? WHERE token_hash=?', (now, expires, token_hash))
            cookie = self.cookie_for(token, expires - now)
        return Principal(row[1], row[5], row[0], token_hash, cookie)

    def session_info(self, cookie_header: Optional[str]) -> Dict[str, object]:
        """Never raises for auth state: {authenticated, account?, reason?, set_cookie?}."""
        if self._token_from(cookie_header) is None:
            return {'authenticated': False}
        try:
            principal = self.authenticate(cookie_header)
        except AuthError as exc:
            return {'authenticated': False, 'reason': exc.code, 'set_cookie': self.clear_cookie()}
        info: Dict[str, object] = {'authenticated': True, 'account': {'username': principal.username}}
        if principal.set_cookie:
            info['set_cookie'] = principal.set_cookie
        return info

    def logout(self, token_hash: Optional[str]) -> None:
        """Delete the session row (idempotent)."""
        if not token_hash:
            return
        with self._tx() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash,))

    # ------------------------------------------------------------ accounts
    def _insert_account(self, db, display: str, key: str, hashed: Tuple[str, bytes, bytes], now: int) -> int:
        """Insert one account row from an already computed (params, salt, digest) triple."""
        params, salt, digest = hashed
        try:
            cursor = db.execute(
                'INSERT INTO accounts(username,username_key,pw_algo,pw_params,pw_salt,pw_hash,created_at,pw_changed_at) VALUES(?,?,?,?,?,?,?,?)',
                (display, key, self.hasher.algo, params, salt, digest, now, now))
        except sqlite3.IntegrityError:
            raise AuthError('USERNAME_TAKEN', '该用户名已被使用。', 409, 'username') from None
        return cursor.lastrowid

    def register(self, username: object, password: object, client_ip: str) -> Tuple[Principal, str]:
        """Create an account and its first session. Returns (principal, token)."""
        if not self.settings.registration_open:
            raise AuthError('REGISTRATION_CLOSED', '当前未开放注册。', 403)
        display, key = self.normalize_username(username)
        self.validate_password(password, key)
        ip = str(client_ip)[:64]
        now = self._now()
        with self._tx() as db:
            self._purge(db, now)
            self._check_register_limit(db, ip, now)
            # USERNAME_TAKEN failures are throttled per source (PRD A7) *before* any scrypt work.
            self._check_lock(db, [('register_fail', ip)], now)
        # Hash before taking the write lock so slow KDF work never blocks auth.db.
        params, salt, digest = self.hasher.hash(password)
        taken = False
        with self._tx() as db:
            self._check_register_limit(db, ip, now)
            try:
                account_id = self._insert_account(db, display, key, (params, salt, digest), now)
            except AuthError:
                taken = True  # recorded below; raised outside the tx so the failure count commits
            else:
                self._count_register(db, ip, now)
                session_id, token, _ = self._create_session(db, account_id, now)
            if taken:
                self._record_failure(db, 'register_fail', ip, self.settings.register_fail_max_failures, now)
        if taken:
            raise AuthError('USERNAME_TAKEN', '该用户名已被使用。', 409, 'username')
        return Principal(account_id, display, session_id, hashlib.sha256(token.encode('utf-8')).hexdigest()), token

    def login(self, username: object, password: object, client_ip: str) -> Tuple[Principal, str]:
        """Verify credentials under rate limits. Unknown user and bad password look identical."""
        key = _key_of(username)
        ip = str(client_ip)[:64]
        s = self.settings
        scopes = (('user_ip', key + '|' + ip, s.login_max_failures), ('user', key, s.login_user_max_failures),
                  ('ip', ip, s.login_ip_max_failures))
        now = self._now()
        with self._tx() as db:
            self._purge(db, now)
            self._check_lock(db, [(a, b) for a, b, _ in scopes], now)
            row = db.execute('SELECT id,username,pw_params,pw_salt,pw_hash FROM accounts WHERE username_key=?', (key,)).fetchone()
        usable = isinstance(password, str) and len(password) <= MAX_PASSWORD_PROBE
        try:
            if usable and row is not None:
                ok = self.hasher.verify(password, row[3], row[4], row[2])
            else:
                self.hasher.verify(password if usable else '', DUMMY_SALT, DUMMY_HASH, self.hasher.current_params())
                ok = False
        except (ValueError, UnicodeEncodeError):
            ok = False
        if not ok:
            with self._tx() as db:
                for scope, scope_key, limit in scopes:
                    self._record_failure(db, scope, scope_key, limit, now)
            raise AuthError('LOGIN_FAILED', '用户名或密码不正确。', 401)
        rehash = self.hasher.hash(password) if self.hasher.needs_rehash(row[2]) else None
        with self._tx() as db:
            db.execute('DELETE FROM login_attempts WHERE scope=? AND key=?', ('user_ip', key + '|' + ip))
            if rehash is not None:
                db.execute('UPDATE accounts SET pw_params=?,pw_salt=?,pw_hash=?,pw_changed_at=? WHERE id=?',
                           (rehash[0], rehash[1], rehash[2], now, row[0]))
            session_id, token, _ = self._create_session(db, row[0], now)
        return Principal(row[0], row[1], session_id, hashlib.sha256(token.encode('utf-8')).hexdigest()), token

    def change_password(self, principal: Principal, old_password: object, new_password: object, client_ip: str = '') -> None:
        """Change the password; every other session of the account is revoked."""
        now = self._now()
        key = str(principal.account_id)
        with self._tx() as db:
            self._check_lock(db, [('password', key)], now)
            row = db.execute('SELECT username_key,pw_params,pw_salt,pw_hash FROM accounts WHERE id=?', (principal.account_id,)).fetchone()
        if row is None:
            raise AuthError('SESSION_EXPIRED', '登录已过期，请重新登录。', 401, clear_cookie=True)
        try:
            ok = isinstance(old_password, str) and len(old_password) <= MAX_PASSWORD_PROBE and \
                self.hasher.verify(old_password, row[2], row[3], row[1])
        except (ValueError, UnicodeEncodeError):
            ok = False
        if not ok:
            with self._tx() as db:
                self._record_failure(db, 'password', key, self.settings.password_max_failures, now)
            raise AuthError('OLD_PASSWORD_INCORRECT', '旧密码不正确。', 400, 'old_password')
        self.validate_password(new_password, row[0], 'new_password')
        params, salt, digest = self.hasher.hash(new_password)
        with self._tx() as db:
            db.execute('UPDATE accounts SET pw_params=?,pw_salt=?,pw_hash=?,pw_changed_at=? WHERE id=?',
                       (params, salt, digest, now, principal.account_id))
            db.execute('DELETE FROM sessions WHERE account_id=? AND id!=?', (principal.account_id, principal.session_id))
            db.execute("DELETE FROM login_attempts WHERE scope='password' AND key=?", (key,))

    # ------------------------------------------------------------ operator API
    def create_account(self, username: str, password: str) -> int:
        """Operator-side creation (ignores the registration switch and IP limits)."""
        display, key = self.normalize_username(username)
        self.validate_password(password, key)
        hashed = self.hasher.hash(password)  # KDF before the write lock
        now = self._now()
        with self._tx() as db:
            return self._insert_account(db, display, key, hashed, now)

    def set_password(self, username: str, new_password: str) -> None:
        """Operator reset: new hash, all sessions and the account's attempt counters cleared."""
        account_id = self.find_account(username)
        if account_id is None:
            raise AuthError('NOT_FOUND', '账号不存在。', 404)
        key = _key_of(username)
        self.validate_password(new_password, key)
        params, salt, digest = self.hasher.hash(new_password)
        now = self._now()
        with self._tx() as db:
            db.execute('UPDATE accounts SET pw_params=?,pw_salt=?,pw_hash=?,pw_changed_at=? WHERE id=?',
                       (params, salt, digest, now, account_id))
            db.execute('DELETE FROM sessions WHERE account_id=?', (account_id,))
            db.execute("DELETE FROM login_attempts WHERE (scope='user' AND key=?) OR (scope='password' AND key=?) "
                       "OR (scope='user_ip' AND substr(key,1,?)=?)", (key, str(account_id), len(key) + 1, key + '|'))

    def find_account(self, username: object) -> Optional[int]:
        """Account id by normalised username, or None (never raises on bad input)."""
        key = _key_of(username)
        if not key:
            return None
        db = self._connect()
        try:
            row = db.execute('SELECT id FROM accounts WHERE username_key=?', (key,)).fetchone()
        finally:
            db.close()
        return row[0] if row else None

    def username_of(self, account_id: int) -> Optional[str]:
        db = self._connect()
        try:
            row = db.execute('SELECT username FROM accounts WHERE id=?', (account_id,)).fetchone()
        finally:
            db.close()
        return row[0] if row else None
