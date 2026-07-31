"""Module-side consistent, encrypted backup and isolated restore adapter."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import secrets
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path


MAGIC = b"INSIGHT-BACKUP-V1\n"


class BackupError(RuntimeError):
    pass


def load_policy(path: Path) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in policy["modules"]]
    if len(ids) != len(set(ids)):
        raise BackupError("duplicate module ID in backup policy")
    return policy


def module_config(policy: dict, module_id: str) -> dict:
    try:
        return next(item for item in policy["modules"] if item["id"] == module_id)
    except StopIteration as exc:
        raise BackupError("unknown module ID") from exc


def source_path(config: dict) -> Path:
    return Path(os.environ.get(config["sourceEnv"], config["source"]))


def read_key(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise BackupError("key path must be a regular file")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise BackupError("key file must not be accessible by group or other users")
    key = path.read_bytes().strip()
    if len(key) < 32:
        raise BackupError("backup key must contain at least 32 bytes")
    return key


def _derive(key: bytes, salt: bytes, label: bytes) -> bytes:
    return hmac.new(key, b"insight-backup-v1\0" + label + salt, hashlib.sha256).digest()


def _openssl_crypt(source: Path, target: Path, key: bytes, iv: bytes) -> None:
    result = subprocess.run(
        ["openssl", "enc", "-aes-256-ctr", "-K", key.hex(), "-iv", iv.hex(),
         "-in", str(source), "-out", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise BackupError("OpenSSL backup encryption failed")


def encrypt(source: Path, target: Path, key: bytes) -> None:
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(16)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        ciphertext = Path(temporary.name)
    try:
        _openssl_crypt(source, ciphertext, _derive(key, salt, b"encryption"), iv)
        prefix = MAGIC + salt + iv
        mac = hmac.new(_derive(key, salt, b"authentication"), prefix, hashlib.sha256)
        with target.open("wb") as output, ciphertext.open("rb") as payload:
            output.write(prefix)
            while chunk := payload.read(1024 * 1024):
                output.write(chunk)
                mac.update(chunk)
            output.write(mac.digest())
        os.chmod(target, 0o600)
    finally:
        ciphertext.unlink(missing_ok=True)


def decrypt(source: Path, target: Path, key: bytes) -> None:
    raw = source.read_bytes()
    minimum = len(MAGIC) + 16 + 16 + hashlib.sha256().digest_size
    if len(raw) < minimum or not raw.startswith(MAGIC):
        raise BackupError("unsupported or truncated encrypted backup")
    offset = len(MAGIC)
    salt, iv = raw[offset:offset + 16], raw[offset + 16:offset + 32]
    prefix, ciphertext, supplied = raw[:offset + 32], raw[offset + 32:-32], raw[-32:]
    expected = hmac.new(
        _derive(key, salt, b"authentication"), prefix + ciphertext, hashlib.sha256
    ).digest()
    if not hmac.compare_digest(expected, supplied):
        raise BackupError("backup authentication failed")
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
        encrypted = Path(temporary.name)
        temporary.write(ciphertext)
    try:
        _openssl_crypt(encrypted, target, _derive(key, salt, b"encryption"), iv)
    finally:
        encrypted.unlink(missing_ok=True)


def verify_sqlite(path: Path) -> None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError("SQLite integrity verification failed") from exc
    if result != ("ok",):
        raise BackupError("SQLite integrity verification failed")


def create_package(config: dict, format_version: str, target: Path) -> None:
    source = source_path(config)
    if not source.exists():
        raise BackupError("module storage is missing")
    metadata = {
        "moduleId": config["id"],
        "moduleVersion": config["moduleVersion"],
        "dataSchemaVersion": config["dataSchemaVersion"],
        "backupFormatVersion": format_version,
        "kind": config["kind"],
    }
    with tempfile.TemporaryDirectory() as temporary:
        snapshot = Path(temporary) / "payload"
        if config["kind"] == "sqlite":
            with sqlite3.connect(source) as origin, sqlite3.connect(snapshot) as destination:
                origin.backup(destination)
            verify_sqlite(snapshot)
        elif config["kind"] == "registry":
            shutil.copytree(source, snapshot, symlinks=False)
        else:
            raise BackupError("unsupported module storage kind")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(metadata, sort_keys=True, separators=(",", ":")))
            if snapshot.is_file():
                archive.write(snapshot, "payload/data")
            else:
                for item in sorted(snapshot.rglob("*")):
                    if item.is_file() and not item.is_symlink():
                        archive.write(item, str(Path("payload") / item.relative_to(snapshot)))


def extract_package(package: Path, staging: Path, config: dict, format_version: str) -> Path:
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
            raise BackupError("unsafe backup member path")
        try:
            metadata = json.loads(archive.read("metadata.json"))
        except (KeyError, json.JSONDecodeError) as exc:
            raise BackupError("backup metadata is missing or invalid") from exc
        required = {"moduleId": config["id"], "moduleVersion": config["moduleVersion"],
                    "backupFormatVersion": format_version, "kind": config["kind"]}
        if any(metadata.get(key) != value for key, value in required.items()):
            raise BackupError("backup module or version is incompatible")
        archive.extractall(staging)
    payload = staging / "payload"
    if config["kind"] == "sqlite":
        payload = payload / "data"
        verify_sqlite(payload)
    elif not payload.is_dir() or not any(item.is_file() for item in payload.rglob("*")):
        raise BackupError("registry backup is empty")
    source_schema = metadata.get("dataSchemaVersion")
    target_schema = config["dataSchemaVersion"]
    if source_schema != target_schema:
        migration = next(
            (item for item in config.get("migrations", [])
             if item.get("from") == source_schema and item.get("to") == target_schema),
            None,
        )
        if migration is None or not isinstance(migration.get("command"), list) or not migration["command"]:
            raise BackupError("backup module or version is incompatible")
        environment = os.environ.copy()
        environment["INSIGHT_STAGED_STORAGE"] = str(payload)
        result = subprocess.run(migration["command"], env=environment, capture_output=True, text=True, check=False)
        if result.returncode:
            raise BackupError("module-owned staged migration failed")
        if config["kind"] == "sqlite":
            verify_sqlite(payload)
    return payload


def readiness(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                raise BackupError("module readiness validation failed")
    except OSError as exc:
        raise BackupError("module readiness validation failed") from exc


def activate(replacement: Path, target: Path) -> None:
    if not target.exists() or not target.is_dir():
        os.replace(replacement, target)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise BackupError("atomic registry activation is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(replacement), -100, os.fsencode(target), 2) != 0:
        raise BackupError("atomic registry activation is unavailable")
    shutil.rmtree(replacement)


def backup(args: argparse.Namespace, policy: dict) -> dict:
    config = module_config(policy, args.module)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as temporary:
        package = Path(temporary.name)
    try:
        create_package(config, policy["backupFormatVersion"], package)
        encrypt(package, output, read_key(args.key_file))
    finally:
        package.unlink(missing_ok=True)
    return {"moduleId": config["id"], "artifact": str(output)}


def restore(args: argparse.Namespace, policy: dict) -> dict:
    config = module_config(policy, args.module)
    staging_parent = args.staging.resolve()
    staging_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{config['id']}-", dir=staging_parent) as temporary:
        staging = Path(temporary)
        package = staging / "package.zip"
        decrypt(args.artifact.resolve(), package, read_key(args.key_file))
        payload = extract_package(package, staging / "restored", config, policy["backupFormatVersion"])
        if args.verify_only:
            if args.check_readiness:
                readiness(config["readinessUrl"])
            return {"moduleId": config["id"], "verified": True, "activated": False}
        if not args.skip_readiness:
            readiness(config["readinessUrl"])
        target = source_path(config)
        target.parent.mkdir(parents=True, exist_ok=True)
        replacement = target.parent / f".{target.name}.restore"
        if replacement.exists():
            shutil.rmtree(replacement) if replacement.is_dir() else replacement.unlink()
        shutil.move(str(payload), replacement)
        activate(replacement, target)
    return {"moduleId": config["id"], "verified": True, "activated": True}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--policy", type=Path, default=Path(__file__).with_name("backup-policy.json"))
    commands = value.add_subparsers(dest="command", required=True)
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("--module", required=True)
    backup_parser.add_argument("--output", type=Path, required=True)
    backup_parser.add_argument("--key-file", type=Path, required=True)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--module", required=True)
    restore_parser.add_argument("--artifact", type=Path, required=True)
    restore_parser.add_argument("--key-file", type=Path, required=True)
    restore_parser.add_argument("--staging", type=Path, required=True)
    restore_parser.add_argument("--verify-only", action="store_true")
    restore_parser.add_argument("--check-readiness", action="store_true")
    restore_parser.add_argument("--skip-readiness", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        policy = load_policy(args.policy)
        result = backup(args, policy) if args.command == "backup" else restore(args, policy)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BackupError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"error": str(exc)}), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
