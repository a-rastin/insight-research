import os
import time
import hmac
import hashlib
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

import bcrypt
import jwt

try:
    from . import disclaimer_contract
except ImportError:  # Keeps `python main.py` working from this directory.
    import disclaimer_contract

# ponytail: env read inline rather than a pydantic-settings class — config is
# read once at startup; a settings object would re-wrap os.environ for nothing.

DEFAULTS = {
    "AUTH_DB_PATH": "./auth.db",
    "AUTH_JWT_SECRET": "change-me-in-production-use-secrets.token_urlsafe",
    "AUTH_COOKIE_NAME": "insight_session",
    "AUTH_CSRF_COOKIE_NAME": "insight_csrf",
    "AUTH_CSRF_HEADER_NAME": "x-csrf-token",
    "AUTH_CSRF_MAX_AGE_SECONDS": "28800",
    "AUTH_COOKIE_MAX_AGE_SECONDS": "28800",
    "AUTH_SECURE_COOKIE": "false",
    "AUTH_ADMIN_USERNAME": "Admin",
    "AUTH_ADMIN_PASSWORD": "Admin",
    "AUTH_ALLOWED_REDIRECTS": "/dashboard/admin,/dashboard/user",
    "AUTH_LOGIN_FAILURE_LIMIT": "5",
    "AUTH_LOGIN_FAILURE_WINDOW_SECONDS": "300",
    "AUTH_LOGIN_LOCKOUT_SECONDS": "900",
}

SERVICE_NAME = "auth"
REQUIRED_CONFIG = (
    "AUTH_DB_PATH",
    "AUTH_JWT_SECRET",
    "AUTH_COOKIE_NAME",
    "AUTH_CSRF_COOKIE_NAME",
    "AUTH_CSRF_HEADER_NAME",
)


def cfg(key: str) -> str:
    return os.environ.get(key, DEFAULTS[key])


def cfg_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def cfg_bool(key: str) -> bool:
    return os.environ.get(key, "false").lower() == "true"


def _safe_check(ok: bool, status: str) -> dict:
    return {"ok": ok, "status": status}


def readiness_report() -> dict:
    checks = {}
    for key in REQUIRED_CONFIG:
        value = cfg(key)
        checks[key.lower()] = _safe_check(bool(value), "configured" if value else "missing")

    jwt_secret = cfg("AUTH_JWT_SECRET")
    if not jwt_secret or jwt_secret == DEFAULTS["AUTH_JWT_SECRET"] or len(jwt_secret.encode("utf-8")) < 32:
        checks["auth_jwt_secret"] = _safe_check(False, "not_configured_securely")

    try:
        conn = get_conn()
        row = conn.execute("SELECT 1").fetchone()
        schema_ok = schema_version(conn) == LATEST_SCHEMA_VERSION
        db_ok = row is not None and int(row[0]) == 1 and schema_ok
        checks["database"] = _safe_check(db_ok, "reachable" if db_ok else "schema_mismatch")
    except Exception:
        checks["database"] = _safe_check(False, "unreachable")

    ok = all(check["ok"] for check in checks.values())
    return {
        "ok": ok,
        "service": SERVICE_NAME,
        "status": "ready" if ok else "not_ready",
        "checks": checks,
    }


def _now() -> int:
    return int(time.time())


# --- bcrypt password hashing --------------------------------------------------

def hash_password(plain: str) -> str:
    # bcrypt: 12 rounds cost factor — adequate for 2026, leaves the calibration
    # knob in one place. Ponytail: no pepper, no double-hash; bcrypt is enough
    # at a trust boundary. Knob stays — a real CPU may need to bump rounds.
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    # constant-time compare inside bcrypt; tolerant of None/missing rows.
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT session tokens (signed, backed by server-side session state) ----------

ALGORITHM = "HS256"


def issue_token(user_id: int, role: str, expires_in: int | None = None) -> str:
    canonical_role = normalize_role(role)
    now = _now()
    exp = now + (expires_in if expires_in is not None else cfg_int("AUTH_COOKIE_MAX_AGE_SECONDS", 28800))
    payload = {"sub": str(user_id), "role": canonical_role, "iat": now, "exp": exp, "jti": secrets.token_urlsafe(8)}
    token = jwt.encode(payload, cfg("AUTH_JWT_SECRET"), algorithm=ALGORITHM)
    record_session(token, user_id, exp)
    return token


def verify_token(token: str) -> dict | None:
    # ponytail: returning None on any failure keeps the router a single guard.
    # A typed Result would be more honest but adds nothing callers use here.
    try:
        return jwt.decode(token, cfg("AUTH_JWT_SECRET"), algorithms=[ALGORITHM])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def cookie_kwargs() -> dict:
    return {
        "key": cfg("AUTH_COOKIE_NAME"),
        "httponly": True,
        "samesite": "lax",
        "secure": cfg_bool("AUTH_SECURE_COOKIE"),
        "max_age": cfg_int("AUTH_COOKIE_MAX_AGE_SECONDS", 28800),
        "path": "/",
    }


# --- CSRF protection ---------------------------------------------------------

def csrf_cookie_kwargs() -> dict:
    return {
        "key": cfg("AUTH_CSRF_COOKIE_NAME"),
        "httponly": False,
        "samesite": "lax",
        "secure": cfg_bool("AUTH_SECURE_COOKIE"),
        "max_age": cfg_int("AUTH_CSRF_MAX_AGE_SECONDS", 28800),
        "path": "/",
    }


def issue_csrf_token() -> str:
    issued_at = _now()
    nonce = secrets.token_urlsafe(32)
    body = f"{nonce}.{issued_at}"
    sig = hmac.new(
        cfg("AUTH_JWT_SECRET").encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{sig}"


def verify_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    if not hmac.compare_digest(cookie_token, header_token):
        return False

    try:
        nonce, issued_at_raw, supplied_sig = cookie_token.rsplit(".", 2)
        issued_at = int(issued_at_raw)
    except (AttributeError, TypeError, ValueError):
        return False

    if not nonce:
        return False
    now = _now()
    max_age = cfg_int("AUTH_CSRF_MAX_AGE_SECONDS", 28800)
    if issued_at > now + 60 or now - issued_at > max_age:
        return False

    body = f"{nonce}.{issued_at}"
    expected_sig = hmac.new(
        cfg("AUTH_JWT_SECRET").encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied_sig, expected_sig)


# --- SQLite data layer --------------------------------------------------------
# ponytail: raw sqlite3 + one connection per thread. SQLAlchemy for two tables
# and a 4-function repository is a 30MB dep for a 30-line win. The single-row
# writes mean a global connection lock is correct; upgrade to per-account locks
# or a pool only if concurrent write contention shows up. Knob left in get_conn.

LATEST_SCHEMA_VERSION = 7

_conn = None
_conn_lock = threading.RLock()


class DuplicateUsernameError(Exception):
    """Raised when account creation conflicts with an existing username."""


class InvalidRoleError(ValueError):
    """Raised when a caller asks for a role outside the auth domain."""


class UserNotFoundError(Exception):
    """Raised when an account-management operation targets a missing user."""


class LastActiveAdminError(Exception):
    """Raised when an operation would remove the final active administrator."""


class SelfManagementError(Exception):
    """Raised when an admin attempts a dangerous operation on their own account."""


class PasswordVerificationError(Exception):
    """Raised when a password-change request fails current-password verification."""


def normalize_role(role: str | None) -> str:
    """Return the canonical API/storage role for accepted role aliases."""
    if role == "user":
        return "psychiatrist"
    if role in ("admin", "psychiatrist"):
        return role
    raise InvalidRoleError(f"invalid role: {role}")


def is_psychiatrist_role(role: str | None) -> bool:
    try:
        return normalize_role(role) == "psychiatrist"
    except InvalidRoleError:
        return False


def get_conn() -> sqlite3.Connection:
    # lazy, thread-local-ish singleton. FastAPI by default is single-process,
    # so a module-global connection guarded by check_same_thread=False is the
    # cheapest correct thing. Switch to a pool when we add multiple workers.
    global _conn
    with _conn_lock:
        if _conn is None:
            path = cfg("AUTH_DB_PATH")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _run_migrations(conn)
            _seed_default_admin(conn)
            conn.commit()
            _conn = conn
    return _conn


def schema_version(conn: sqlite3.Connection | None = None) -> int:
    """Return the SQLite schema version stored in the database header."""
    active_conn = conn or get_conn()
    row = active_conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {int(version)}")


def _run_migrations(conn: sqlite3.Connection) -> None:
    current = schema_version(conn)
    if current > LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            f"auth database schema version {current} is newer than supported version {LATEST_SCHEMA_VERSION}"
        )

    migrations = (
        (1, _migration_001_create_users),
        (2, _migration_002_create_sessions),
        (3, _migration_003_normalize_roles),
        (4, _migration_004_account_state_and_login_failures),
        (5, _migration_005_disclaimer_versions),
        (6, _migration_006_audit_log),
        (7, _migration_007_uuid_identity),
    )
    for version, migration in migrations:
        if current < version:
            migration(conn)
            _set_schema_version(conn, version)
            current = version


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migration_001_create_users(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            role          TEXT NOT NULL CHECK (role IN ('admin', 'user')),
            password_hash TEXT NOT NULL,
            disclaimer_signed BOOLEAN NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _migration_002_create_sessions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token  TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL
        )
        """
    )


def _migration_003_normalize_roles(conn: sqlite3.Connection) -> None:
    _migrate_legacy_user_role(conn)


def _migration_004_account_state_and_login_failures(conn: sqlite3.Connection) -> None:
    _migrate_account_state_columns(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_failures (
            identity        TEXT PRIMARY KEY,
            username_key    TEXT NOT NULL,
            client_key      TEXT NOT NULL,
            failure_count   INTEGER NOT NULL,
            first_failed_at INTEGER NOT NULL,
            last_failed_at  INTEGER NOT NULL,
            locked_until    INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_login_failures_last_failed_at
            ON login_failures(last_failed_at)
        """
    )


def _migration_005_disclaimer_versions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS disclaimer_acceptances (
            user_id     INTEGER NOT NULL REFERENCES users(id),
            version     TEXT NOT NULL,
            accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, version)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_disclaimer_acceptances_user_id
            ON disclaimer_acceptances(user_id)
        """
    )
    _migrate_disclaimer_acceptances(conn)


def _migration_006_audit_log(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id    INTEGER,
            actor_name  TEXT NOT NULL,
            target_id   INTEGER,
            target_name TEXT,
            action      TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'success',
            metadata    TEXT,
            client_ip   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
            ON audit_log(created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id
            ON audit_log(actor_id)
        """
    )


def _migration_007_uuid_identity(conn: sqlite3.Connection) -> None:
    user_columns = _table_columns(conn, "users")
    if "user_uuid" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN user_uuid TEXT")
    session_columns = _table_columns(conn, "sessions")
    if "session_uuid" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN session_uuid TEXT")

    for row in conn.execute("SELECT id FROM users WHERE user_uuid IS NULL OR user_uuid = ''"):
        conn.execute("UPDATE users SET user_uuid = ? WHERE id = ?", (str(uuid.uuid4()), row["id"]))
    for row in conn.execute("SELECT token FROM sessions WHERE session_uuid IS NULL OR session_uuid = ''"):
        conn.execute(
            "UPDATE sessions SET session_uuid = ? WHERE token = ?",
            (str(uuid.uuid4()), row["token"]),
        )
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_uuid ON users(user_uuid)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_session_uuid ON sessions(session_uuid)")


@contextmanager
def _tx(conn: sqlite3.Connection):
    # sqlite3 isolation is fine; explicit commit/rollback makes intent clear.
    with _conn_lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _seed_default_admin(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM users WHERE username = ?", (cfg("AUTH_ADMIN_USERNAME"),)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (username, role, password_hash, disabled, disclaimer_signed, user_uuid) VALUES (?, ?, ?, 0, 1, ?)",
            (
                cfg("AUTH_ADMIN_USERNAME"),
                "admin",
                hash_password(cfg("AUTH_ADMIN_PASSWORD")),
                str(uuid.uuid4()),
            ),
        )


def _migrate_legacy_user_role(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    table_sql = row["sql"] if row else ""
    if "'psychiatrist'" not in table_sql:
        columns = _table_columns(conn, "users")
        disabled_expr = "disabled" if "disabled" in columns else "0"
        must_change_expr = "must_change_password" if "must_change_password" in columns else "0"
        disclaimer_expr = "disclaimer_signed" if "disclaimer_signed" in columns else "0"
        created_expr = "created_at" if "created_at" in columns else "datetime('now')"
        foreign_keys_enabled = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(
            f"""
            CREATE TABLE users_new (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                role          TEXT NOT NULL CHECK (role IN ('admin', 'psychiatrist')),
                password_hash TEXT NOT NULL,
                disabled      BOOLEAN NOT NULL DEFAULT 0,
                must_change_password BOOLEAN NOT NULL DEFAULT 0,
                disclaimer_signed BOOLEAN NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO users_new (id, username, role, password_hash, disabled, must_change_password, disclaimer_signed, created_at)
            SELECT id,
                   username,
                   CASE role WHEN 'user' THEN 'psychiatrist' ELSE role END,
                   password_hash,
                   {disabled_expr},
                   {must_change_expr},
                   {disclaimer_expr},
                   {created_expr}
              FROM users;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
            """
        )
        conn.execute(f"PRAGMA foreign_keys = {foreign_keys_enabled}")
    else:
        conn.execute("UPDATE users SET role = 'psychiatrist' WHERE role = 'user'")


def _migrate_account_state_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "disabled" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN disabled BOOLEAN NOT NULL DEFAULT 0")
    if "must_change_password" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0")


def _migrate_disclaimer_acceptances(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS count FROM disclaimer_acceptances").fetchone()
    if row is not None and int(row["count"]) > 0:
        return
    conn.execute(
        """
        INSERT OR IGNORE INTO disclaimer_acceptances (user_id, version, accepted_at)
        SELECT id, ?, COALESCE(created_at, datetime('now'))
          FROM users
         WHERE role = 'psychiatrist'
           AND disclaimer_signed = 1
        """,
        (active_disclaimer_version(),),
    )


def active_disclaimer_version() -> str:
    return disclaimer_contract.CURRENT_DISCLAIMER_VERSION


def current_disclaimer() -> dict:
    return disclaimer_contract.current_disclaimer()


def _login_attempt_scope(username: str, client_id: str | None) -> tuple[str, str, str]:
    username_key = (username or "").strip().casefold()
    client_key = (client_id or "unknown").strip()[:128] or "unknown"
    identity = hmac.new(
        cfg("AUTH_JWT_SECRET").encode("utf-8"),
        f"{username_key}\0{client_key}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return identity, username_key, client_key


def _login_failure_limit() -> int:
    return max(0, cfg_int("AUTH_LOGIN_FAILURE_LIMIT", 5))


def _login_failure_window_seconds() -> int:
    return max(1, cfg_int("AUTH_LOGIN_FAILURE_WINDOW_SECONDS", 300))


def _login_lockout_seconds() -> int:
    return max(1, cfg_int("AUTH_LOGIN_LOCKOUT_SECONDS", 900))


def _prune_login_failures(conn: sqlite3.Connection, now: int) -> None:
    cutoff = now - _login_failure_window_seconds()
    conn.execute(
        """
        DELETE FROM login_failures
         WHERE last_failed_at < ?
           AND locked_until < ?
        """,
        (cutoff, now),
    )


def login_attempt_allowed(username: str, client_id: str | None) -> bool:
    """Return whether a login attempt should be evaluated for this principal.

    This is intentionally a small storage seam: the SQLite implementation uses
    one row per username/client key, and a Redis upgrade can preserve the same
    call contract with expiring keys.
    """
    if _login_failure_limit() <= 0:
        return True
    identity, _, _ = _login_attempt_scope(username, client_id)
    now = _now()
    with _conn_lock:
        row = get_conn().execute(
            "SELECT first_failed_at, locked_until FROM login_failures WHERE identity = ?",
            (identity,),
        ).fetchone()
        if row is None:
            return True
        if int(row["locked_until"]) > now:
            return False
        if now - int(row["first_failed_at"]) > _login_failure_window_seconds():
            conn = get_conn()
            with _tx(conn):
                conn.execute("DELETE FROM login_failures WHERE identity = ?", (identity,))
        return True


def record_login_failure(username: str, client_id: str | None) -> None:
    if _login_failure_limit() <= 0:
        return
    identity, username_key, client_key = _login_attempt_scope(username, client_id)
    now = _now()
    conn = get_conn()
    with _tx(conn):
        _prune_login_failures(conn, now)
        row = conn.execute(
            """
            SELECT failure_count, first_failed_at
              FROM login_failures
             WHERE identity = ?
            """,
            (identity,),
        ).fetchone()
        if row is None or now - int(row["first_failed_at"]) > _login_failure_window_seconds():
            failure_count = 1
            first_failed_at = now
        else:
            failure_count = int(row["failure_count"]) + 1
            first_failed_at = int(row["first_failed_at"])

        locked_until = now + _login_lockout_seconds() if failure_count >= _login_failure_limit() else 0
        conn.execute(
            """
            INSERT INTO login_failures (
                identity, username_key, client_key, failure_count,
                first_failed_at, last_failed_at, locked_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity) DO UPDATE SET
                username_key = excluded.username_key,
                client_key = excluded.client_key,
                failure_count = excluded.failure_count,
                first_failed_at = excluded.first_failed_at,
                last_failed_at = excluded.last_failed_at,
                locked_until = excluded.locked_until
            """,
            (identity, username_key, client_key, failure_count, first_failed_at, now, locked_until),
        )


def record_login_success(username: str, client_id: str | None) -> None:
    if _login_failure_limit() <= 0:
        return
    identity, _, _ = _login_attempt_scope(username, client_id)
    conn = get_conn()
    with _tx(conn):
        conn.execute("DELETE FROM login_failures WHERE identity = ?", (identity,))


# --- audit log ----------------------------------------------------------------
# ponytail: writes never carry secrets. caller-name fields hold the *username*
# shown on the request, not a token/hash. target optional — single-actor
# events (login, logout, password change, disclaimer accept) set actor == target.

_AUDIT_ACTIONS = {
    "login",
    "login_failed",
    "logout",
    "register",
    "password_reset",
    "password_change",
    "disable",
    "enable",
    "role_update",
    "disclaimer_accept",
}


def record_audit(
    action: str,
    actor: dict | None = None,
    target: dict | None = None,
    metadata: dict | None = None,
    client_ip: str | None = None,
    status: str = "success",
) -> None:
    """Append one audit row. Never raises — audit must not break auth.

    `actor` / `target` are resolved-session dicts (sub, username, role) or a
    minimal {"id", "username"} mapping. Unknown actions are still recorded
    (we trust the router's vocabulary) but normalized to keep the column small.
    """
    if action not in _AUDIT_ACTIONS:
        action = "unknown"
    import json as _json

    actor_id = None
    actor_name = "system"
    if actor:
        try:
            actor_id = int(actor.get("id") or actor.get("sub"))
        except (TypeError, ValueError):
            actor_id = None
        actor_name = (actor.get("username") or "unknown")[:64]
    target_id = None
    target_name = None
    if target:
        try:
            target_id = int(target.get("id") or target.get("sub"))
        except (TypeError, ValueError):
            target_id = None
        target_name = (target.get("username") or None)
    meta_json = _json.dumps(metadata) if metadata else None
    ip = (client_ip or None)
    if ip is not None:
        ip = ip[:128]
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            """
            INSERT INTO audit_log (
                actor_id, actor_name, target_id, target_name,
                action, status, metadata, client_ip
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (actor_id, actor_name, target_id, target_name, action, status, meta_json, ip),
        )


def list_audit_entries(limit: int = 200, offset: int = 0) -> list[dict]:
    """Return audit rows newest-first, capped. Caller (admin route) paginates."""
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))
    with _conn_lock:
        rows = get_conn().execute(
            """
            SELECT id, actor_id, actor_name, target_id, target_name,
                   action, status, metadata, client_ip, created_at
              FROM audit_log
             ORDER BY id DESC
             LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def get_user(username: str):
    version = active_disclaimer_version()
    with _conn_lock:
        return get_conn().execute(
            """
            SELECT u.id, u.user_uuid, u.username, u.role, u.password_hash, u.disabled,
                   u.must_change_password,
                   CASE
                       WHEN u.role = 'admin' THEN 1
                       WHEN da.user_id IS NOT NULL THEN 1
                       ELSE 0
                   END AS disclaimer_signed,
                   da.version AS disclaimer_version,
                   da.accepted_at AS disclaimer_accepted_at
              FROM users u
              LEFT JOIN disclaimer_acceptances da
                ON da.user_id = u.id
               AND da.version = ?
             WHERE u.username = ?
            """,
            (version, username),
        ).fetchone()


def get_user_by_id(user_id: int):
    version = active_disclaimer_version()
    with _conn_lock:
        return get_conn().execute(
            """
            SELECT u.id, u.user_uuid, u.username, u.role, u.disabled, u.must_change_password,
                   CASE
                       WHEN u.role = 'admin' THEN 1
                       WHEN da.user_id IS NOT NULL THEN 1
                       ELSE 0
                   END AS disclaimer_signed,
                   da.version AS disclaimer_version,
                   da.accepted_at AS disclaimer_accepted_at
              FROM users u
              LEFT JOIN disclaimer_acceptances da
                ON da.user_id = u.id
               AND da.version = ?
             WHERE u.id = ?
            """,
            (version, user_id),
        ).fetchone()


def list_users():
    version = active_disclaimer_version()
    with _conn_lock:
        return get_conn().execute(
            """
            SELECT u.id, u.username, u.role, u.disabled, u.must_change_password,
                   CASE
                       WHEN u.role = 'admin' THEN 1
                       WHEN da.user_id IS NOT NULL THEN 1
                       ELSE 0
                   END AS disclaimer_signed,
                   u.created_at
              FROM users u
              LEFT JOIN disclaimer_acceptances da
                ON da.user_id = u.id
               AND da.version = ?
             ORDER BY u.id
            """,
            (version,),
        ).fetchall()


def register_user(username: str, role: str, password: str) -> int:
    canonical_role = normalize_role(role)
    password_hash = hash_password(password)
    conn = get_conn()
    with _tx(conn):
        try:
            cur = conn.execute(
                "INSERT INTO users (username, role, password_hash, disclaimer_signed, user_uuid) VALUES (?, ?, ?, ?, ?)",
                (
                    username,
                    canonical_role,
                    password_hash,
                    1 if canonical_role == "admin" else 0,
                    str(uuid.uuid4()),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUsernameError(username) from exc
        return cur.lastrowid


def _active_admin_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE role = 'admin' AND disabled = 0"
    ).fetchone()
    return int(row["count"])


def set_user_disabled(user_id: int, disabled: bool, actor_user_id: int | None = None) -> None:
    conn = get_conn()
    with _tx(conn):
        user = conn.execute(
            "SELECT id, role, disabled FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)
        if disabled and actor_user_id == user_id:
            raise SelfManagementError("admins cannot disable their own account")
        if disabled and user["role"] == "admin" and not user["disabled"] and _active_admin_count(conn) <= 1:
            raise LastActiveAdminError("cannot disable the last active admin")
        conn.execute("UPDATE users SET disabled = ? WHERE id = ?", (1 if disabled else 0, user_id))
        if disabled:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def reset_user_password(user_id: int, temporary_password: str | None = None) -> str:
    new_password = temporary_password or secrets.token_urlsafe(18)
    conn = get_conn()
    with _tx(conn):
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)
        conn.execute(
            """
            UPDATE users
               SET password_hash = ?,
                   must_change_password = 1
             WHERE id = ?
            """,
            (hash_password(new_password), user_id),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    return new_password


def change_user_password(user_id: int, current_password: str, new_password: str) -> None:
    conn = get_conn()
    with _tx(conn):
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)
        if not verify_password(current_password, user["password_hash"]):
            raise PasswordVerificationError()
        conn.execute(
            """
            UPDATE users
               SET password_hash = ?,
                   must_change_password = 0
             WHERE id = ?
            """,
            (hash_password(new_password), user_id),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def update_user_role(user_id: int, role: str, actor_user_id: int | None = None) -> None:
    canonical_role = normalize_role(role)
    conn = get_conn()
    with _tx(conn):
        user = conn.execute(
            "SELECT id, role, disabled FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)
        if actor_user_id == user_id and user["role"] != canonical_role:
            raise SelfManagementError("admins cannot change their own role")
        if (
            user["role"] == "admin"
            and canonical_role != "admin"
            and not user["disabled"]
            and _active_admin_count(conn) <= 1
        ):
            raise LastActiveAdminError("cannot demote the last active admin")
        disclaimer_signed = 1 if canonical_role == "admin" else 0
        conn.execute(
            "UPDATE users SET role = ?, disclaimer_signed = ? WHERE id = ?",
            (canonical_role, disclaimer_signed, user_id),
        )
        if canonical_role == "psychiatrist":
            conn.execute("DELETE FROM disclaimer_acceptances WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def set_disclaimer_signed(user_id: int) -> None:
    conn = get_conn()
    with _tx(conn):
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)
        version = active_disclaimer_version()
        conn.execute(
            "UPDATE users SET disclaimer_signed = 1 WHERE id = ?", (user_id,)
        )
        conn.execute(
            """
            INSERT INTO disclaimer_acceptances (user_id, version, accepted_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id, version) DO UPDATE SET
                accepted_at = excluded.accepted_at
            """,
            (user_id, version),
        )


def record_session(token: str, user_id: int, expires_at: int) -> None:
    conn = get_conn()
    with _tx(conn):
        conn.execute(
            """
            INSERT INTO sessions (token, user_id, expires_at, session_uuid)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                user_id = excluded.user_id,
                expires_at = excluded.expires_at
            """,
            (token, user_id, expires_at, str(uuid.uuid4())),
        )


def revoke_session(token: str | None) -> None:
    if not token:
        return
    conn = get_conn()
    with _tx(conn):
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def revoke_sessions_for_user(user_id: int) -> None:
    """Invalidate all active sessions for account disable or password reset."""
    conn = get_conn()
    with _tx(conn):
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def _get_session_record(token: str):
    with _conn_lock:
        return get_conn().execute(
            "SELECT token, user_id, expires_at, session_uuid FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()


def resolve_session(
    token: str,
    require_disclaimer: bool = True,
    require_password_change: bool = True,
) -> dict | None:
    """
    Resolve a token into the current account state.

    JWTs are only signed snapshots. Every caller that relies on authorization
    should cross this seam so revocation, deleted users, role changes, and
    disclaimer state are enforced from the database.
    """
    payload = verify_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return None

    session = _get_session_record(token)
    if session is None:
        return None
    if int(session["user_id"]) != user_id or int(session["expires_at"]) != expires_at:
        return None
    if int(session["expires_at"]) < _now():
        revoke_session(token)
        return None

    user = get_user_by_id(user_id)
    if user is None:
        return None
    if user["disabled"]:
        revoke_sessions_for_user(user_id)
        return None
    try:
        token_role = normalize_role(payload.get("role"))
        stored_role = normalize_role(user["role"])
    except InvalidRoleError:
        return None
    if token_role != stored_role:
        return None
    if require_password_change and user["must_change_password"]:
        return None
    if require_disclaimer and stored_role == "psychiatrist" and not user["disclaimer_signed"]:
        return None

    return {
        "sub": str(user["id"]),
        "user_uuid": user["user_uuid"],
        "session_uuid": session["session_uuid"],
        "role": stored_role,
        "username": user["username"],
        "must_change_password": bool(user["must_change_password"]),
        "disclaimer_signed": bool(user["disclaimer_signed"]),
        "disclaimer_version": user["disclaimer_version"],
        "disclaimer_accepted_at": user["disclaimer_accepted_at"],
        "expires_at": expires_at,
    }


# --- timing-safe username compare for future use ----------------------------

def username_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
