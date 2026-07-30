"""Independent standalone, unified-route, TLS, and recovery verification."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).parents[1]
SECURITY_HEADERS = (
    "strict-transport-security", "content-security-policy", "x-content-type-options",
    "x-frame-options", "referrer-policy",
)


def request(url: str, *, attempts: int = 1) -> tuple[int, dict[str, str], bytes]:
    error: Exception | None = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read()
        except Exception as exc:  # noqa: BLE001 - the retry surface includes transport failures
            error = exc
            time.sleep(1)
    raise RuntimeError(f"deployment check failed for {url}: {error}")


def verify_http(base_url: str, *, unified: bool = False) -> None:
    prefix = "/api/treatment-plan" if unified else ""
    status, _, health = request(base_url.rstrip("/") + prefix + "/health", attempts=30)
    if status != 200 or json.loads(health).get("status") != "ok":
        raise RuntimeError("health smoke test failed")
    status, _, ready = request(base_url.rstrip("/") + prefix + "/ready")
    if status != 200 or json.loads(ready).get("status") != "ready":
        raise RuntimeError("readiness or migration gate failed")
    shell_path = "/modules/treatment-plan" if not unified else "/modules/treatment-plan"
    status, _, body = request(base_url.rstrip("/") + shell_path)
    if status != 200 or b"<!" not in body[:100].lower():
        raise RuntimeError("module route integration test failed")


def verify_tls(url: str) -> None:
    if not url.lower().startswith("https://"):
        raise RuntimeError("TLS verification requires an https URL")
    status, headers, _ = request(url)
    if status != 200:
        raise RuntimeError("TLS endpoint did not return success")
    missing = [name for name in SECURITY_HEADERS if not headers.get(name)]
    if missing:
        raise RuntimeError("missing security headers: " + ", ".join(missing))


def available_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def hardened_run_command(image: str, name: str, volume: str, port: int) -> list[str]:
    return [
        "docker", "run", "--detach", "--name", name, "--user", "10001:10001", "--read-only",
        "--tmpfs", "/tmp:size=32m,mode=1777", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "256", "--stop-timeout", "35",
        "--publish", f"127.0.0.1:{port}:8000", "--volume", f"{volume}:/data",
        "--env", "TP_ENV=development", "--env", "TP_AUTH_STUB_ENABLED=true", image,
    ]


def verify_container(image: str, *, recovery: bool) -> None:
    suffix = uuid4().hex[:10]
    name, volume, port = f"tp-verify-{suffix}", f"tp-verify-{suffix}", available_port()
    run = lambda command: subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    try:
        run(["docker", "volume", "create", volume])
        run(hardened_run_command(image, name, volume, port))
        verify_http(f"http://127.0.0.1:{port}")
        if recovery:
            run(["docker", "kill", name])
            run(["docker", "start", name])
            verify_http(f"http://127.0.0.1:{port}")
        run(["docker", "stop", "--time", "35", name])
        exit_code = json.loads(run(["docker", "inspect", name]).stdout)[0]["State"]["ExitCode"]
        if exit_code != 0:
            raise RuntimeError("graceful shutdown returned a non-zero container exit code")
    finally:
        subprocess.run(["docker", "rm", "--force", name], cwd=ROOT, capture_output=True)
        subprocess.run(["docker", "volume", "rm", "--force", volume], cwd=ROOT, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    http = sub.add_parser("standalone")
    http.add_argument("--base-url", default="http://127.0.0.1:8000")
    unified = sub.add_parser("unified")
    unified.add_argument("--base-url", required=True)
    tls = sub.add_parser("tls")
    tls.add_argument("--url", required=True)
    container = sub.add_parser("container")
    container.add_argument("--image", default="insight-treatment-plan:0.1.0")
    container.add_argument("--recovery", action="store_true")
    args = parser.parse_args()
    if args.command == "standalone":
        verify_http(args.base_url)
    elif args.command == "unified":
        verify_http(args.base_url, unified=True)
    elif args.command == "tls":
        verify_tls(args.url)
    else:
        verify_container(args.image, recovery=args.recovery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
