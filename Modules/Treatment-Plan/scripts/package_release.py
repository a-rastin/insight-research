"""Cross-platform release image build, SBOM, scan, and human-gated promotion."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=capture)


def clinical_release_gates() -> None:
    run([sys.executable, "scripts/check_tp01_release_gate.py"])
    run([sys.executable, "scripts/check_tp21_clinical_safety_case.py"])


def build(image: str) -> None:
    run([
        "docker", "buildx", "build", "--file", "Dockerfile.release", "--load",
        "--sbom=true", "--provenance=mode=max", "--tag", image, ".",
    ])
    metadata = json.loads(run(["docker", "image", "inspect", image], capture=True).stdout)[0]
    user = metadata.get("Config", {}).get("User", "")
    if user not in {"10001", "10001:10001"}:
        raise RuntimeError("release image is not configured for the non-root runtime user")


def sbom(image: str, output: Path) -> None:
    result = run(["docker", "sbom", "--format", "spdx-json", image], capture=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout, encoding="utf-8")


def scan(image: str) -> None:
    if shutil.which("trivy"):
        run(["trivy", "image", "--exit-code", "1", "--severity", "HIGH,CRITICAL", image])
        return
    result = subprocess.run(
        ["docker", "scout", "cves", "--exit-code", "--only-severity", "critical,high", image],
        cwd=ROOT,
    )
    if result.returncode:
        raise RuntimeError("image scan failed, or neither Trivy nor Docker Scout is available")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "sbom", "scan", "promote"))
    parser.add_argument("--image", default="insight-treatment-plan:0.1.0")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "treatment-plan.spdx.json")
    args = parser.parse_args()
    if args.command == "build":
        build(args.image)
    elif args.command == "sbom":
        sbom(args.image, args.output)
    elif args.command == "scan":
        scan(args.image)
    else:
        clinical_release_gates()
        scan(args.image)
        print("promotion gates passed; deploy the immutable image digest, not a mutable tag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
