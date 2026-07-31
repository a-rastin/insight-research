from __future__ import annotations

import json
import os
import signal
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen


POLICY_PATH = Path(os.getenv("INSIGHT_RUNTIME_POLICY", Path(__file__).with_name("runtime-policy.json")))
Probe = Callable[[str, float], bool]


def http_probe(url: str, timeout: float) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except OSError:
        return False


def aggregate(policy: dict[str, Any], probe: Probe = http_probe) -> tuple[int, dict[str, Any]]:
    modules = [module for module in policy["modules"] if module["required"]]

    def check(module: dict[str, Any]) -> str | None:
        url = f"http://{module['host']}:{module['port']}{module['readinessPath']}"
        return None if probe(url, 1.0) else module["id"]

    with ThreadPoolExecutor(max_workers=len(modules)) as executor:
        unavailable = sorted(module_id for module_id in executor.map(check, modules) if module_id)
    if unavailable:
        return 503, {"status": "not-ready", "unavailableModules": unavailable}
    return 200, {"status": "ready", "unavailableModules": []}


class Handler(BaseHTTPRequestHandler):
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def do_GET(self) -> None:
        if self.path != "/readyz":
            self.send_error(404)
            return
        status, payload = aggregate(self.policy)
        body = json.dumps(payload, separators=(",", ":")).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8099), Handler)

    def stop(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
