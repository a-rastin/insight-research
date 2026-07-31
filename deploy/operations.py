"""Metadata-only aggregate backup, restore, retention, and rollback orchestration."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


UTC = dt.timezone.utc


class OperationsError(RuntimeError):
    pass


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def run_adapter(policy_path: Path, arguments: list[str]) -> dict:
    command = [sys.executable, str(Path(__file__).with_name("module_backup.py")), "--policy", str(policy_path), *arguments]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        try:
            message = json.loads(result.stderr)["error"]
        except (json.JSONDecodeError, KeyError):
            message = "module operation failed"
        raise OperationsError(message)
    return json.loads(result.stdout)


def backup(args: argparse.Namespace, policy: dict) -> dict:
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    created = dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")
    entries = []
    created_artifacts = []
    try:
        for module in policy["modules"]:
            name = f"{module['id']}_{uuid.uuid4()}.backup"
            artifact = destination / name
            run_adapter(args.policy, ["backup", "--module", module["id"], "--output", str(artifact), "--key-file", str(args.key_file)])
            created_artifacts.append(artifact)
            entries.append({
                "moduleId": module["id"], "moduleVersion": module["moduleVersion"],
                "dataSchemaVersion": module["dataSchemaVersion"],
                "backupFormatVersion": policy["backupFormatVersion"], "createdAt": created,
                "artifactName": name, "byteCount": artifact.stat().st_size, "sha256": digest(artifact),
            })
        manifest = {"manifestSchemaVersion": policy["manifestSchemaVersion"], "createdAt": created, "modules": entries}
        manifest_path = destination / f"manifest_{uuid.uuid4()}.json"
        write_json(manifest_path, manifest)
        return {"manifest": str(manifest_path), "moduleCount": len(entries)}
    except Exception:
        for artifact in created_artifacts:
            artifact.unlink(missing_ok=True)
        raise


def validate_manifest(manifest: dict, policy: dict) -> None:
    if manifest.get("manifestSchemaVersion") != policy["manifestSchemaVersion"]:
        raise OperationsError("unsupported manifest version")
    expected = {item["id"] for item in policy["modules"]}
    actual = [item.get("moduleId") for item in manifest.get("modules", [])]
    if set(actual) != expected or len(actual) != len(expected):
        raise OperationsError("manifest has missing, unknown, or duplicate modules")


def restore(args: argparse.Namespace, policy: dict) -> dict:
    manifest_path = args.manifest.resolve()
    manifest = load(manifest_path)
    validate_manifest(manifest, policy)
    artifacts = []
    for entry in manifest["modules"]:
        artifact = manifest_path.parent / entry["artifactName"]
        if not artifact.is_file() or artifact.stat().st_size != entry["byteCount"] or digest(artifact) != entry["sha256"]:
            raise OperationsError(f"artifact integrity failed for {entry['moduleId']}")
        artifacts.append((entry, artifact))
    reports = []
    for entry, artifact in artifacts:
        verify_arguments = [
            "restore", "--module", entry["moduleId"], "--artifact", str(artifact),
            "--key-file", str(args.key_file), "--staging", str(args.staging),
            "--verify-only",
        ]
        if not args.skip_readiness and not args.verify_only:
            verify_arguments.append("--check-readiness")
        reports.append(run_adapter(args.policy, verify_arguments))
    if not args.verify_only:
        reports = []
        for entry, artifact in artifacts:
            reports.append(run_adapter(args.policy, [
                "restore", "--module", entry["moduleId"], "--artifact", str(artifact),
                "--key-file", str(args.key_file), "--staging", str(args.staging), "--skip-readiness",
            ]))
    report = {
        "restoreReportSchemaVersion": "1.0.0",
        "createdAt": dt.datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "manifestSha256": digest(manifest_path), "success": len(reports) == len(policy["modules"]),
        "modules": reports,
    }
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    return {"report": str(report_path), "success": report["success"]}


def retain(args: argparse.Namespace, policy: dict) -> dict:
    if not args.approved_policy:
        raise OperationsError("approved retention policy is required")
    cutoff = dt.datetime.now(UTC) - dt.timedelta(days=policy["metadataRetentionDays"])
    removed = 0
    for pattern in ("manifest_*.json", "restore-report_*.json"):
        for path in args.metadata.resolve().glob(pattern):
            modified = dt.datetime.fromtimestamp(path.stat().st_mtime, UTC)
            if modified < cutoff:
                path.unlink()
                removed += 1
    return {"removedAggregateMetadata": removed, "moduleArtifactsRemoved": 0, "ownerRecordsRemoved": 0}


def rollback(args: argparse.Namespace, _policy: dict) -> dict:
    releases = load(args.releases)
    current = load(args.current_state)
    try:
        target = next(item for item in releases["releases"] if item["image"] == args.image)
    except StopIteration as exc:
        raise OperationsError("unknown rollback image") from exc
    current_schemas = current["moduleDataSchemas"]
    supported = target["supportedDataSchemas"]
    incompatible = sorted(module for module, version in current_schemas.items() if version not in supported.get(module, []))
    if incompatible:
        raise OperationsError("rollback image cannot read current module schemas: " + ", ".join(incompatible))
    return {"image": target["image"], "digest": target["digest"], "downMigrationsRun": False, "readyForRestart": True}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--policy", type=Path, default=Path(__file__).with_name("backup-policy.json"))
    commands = value.add_subparsers(dest="command", required=True)
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("--destination", type=Path, required=True)
    backup_parser.add_argument("--key-file", type=Path, required=True)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--manifest", type=Path, required=True)
    restore_parser.add_argument("--key-file", type=Path, required=True)
    restore_parser.add_argument("--staging", type=Path, required=True)
    restore_parser.add_argument("--report", type=Path, required=True)
    restore_parser.add_argument("--verify-only", action="store_true")
    restore_parser.add_argument("--skip-readiness", action="store_true")
    retention_parser = commands.add_parser("retain")
    retention_parser.add_argument("--metadata", type=Path, required=True)
    retention_parser.add_argument("--approved-policy", action="store_true")
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("--releases", type=Path, required=True)
    rollback_parser.add_argument("--current-state", type=Path, required=True)
    rollback_parser.add_argument("--image", required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        policy = load(args.policy)
        result = globals()[args.command](args, policy)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OperationsError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
