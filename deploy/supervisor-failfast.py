from __future__ import annotations

import os
import signal
import sys


def main() -> None:
    while True:
        sys.stdout.write("READY\n")
        sys.stdout.flush()
        headers = dict(item.split(":", 1) for item in sys.stdin.readline().split())
        payload = sys.stdin.read(int(headers["len"]))
        event = dict(item.split(":", 1) for item in payload.split())
        if headers["eventname"] == "PROCESS_STATE_FATAL" or event.get("expected") == "0":
            os.kill(os.getppid(), signal.SIGKILL)
            return
        sys.stdout.write("RESULT 2\nOK")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
