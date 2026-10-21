"""Service settings: one frozen value object shared by auth, routing and the CLI."""
from dataclasses import dataclass
from typing import Any, Tuple

COOKIE_NAME = 'guixu_session'
SECURE_COOKIE_NAME = '__Host-guixu_session'


@dataclass(frozen=True)
class Settings:
    """Deployment and security knobs. Defaults suit a trusted home/LAN setup.

    Only the first four fields are exposed on the command line; the rest are
    tuning values (tests lower kdf_n to keep suites fast).
    """
    allowed_hosts: Tuple[str, ...] = ()
    secure_cookies: bool = False
    registration_open: bool = True
    trust_proxy: bool = False
    session_idle_seconds: int = 604800
    session_absolute_seconds: int = 2592000
    session_touch_interval: int = 60
    max_sessions_per_account: int = 10
    login_max_failures: int = 5
    login_user_max_failures: int = 20
    login_ip_max_failures: int = 50
    password_max_failures: int = 5
    lockout_seconds: int = 300
    failure_window_seconds: int = 900
    register_fail_max_failures: int = 10
    register_per_ip_hour: int = 10
    register_window_seconds: int = 3600
    kdf_n: int = 32768
    kdf_r: int = 8
    kdf_p: int = 1
    hash_concurrency: int = 4

    @property
    def cookie_name(self) -> str:
        """Cookie name; the __Host- prefix is only valid together with Secure."""
        return SECURE_COOKIE_NAME if self.secure_cookies else COOKIE_NAME

    @classmethod
    def from_args(cls, args: Any) -> 'Settings':
        """Build settings from an argparse namespace (missing attributes use defaults)."""
        hosts = tuple(str(h).strip() for h in (getattr(args, 'allowed_host', None) or []) if str(h).strip())
        return cls(
            allowed_hosts=hosts,
            secure_cookies=bool(getattr(args, 'secure_cookies', False)),
            registration_open=not bool(getattr(args, 'no_register', False)),
            trust_proxy=bool(getattr(args, 'trust_proxy', False)),
        )
