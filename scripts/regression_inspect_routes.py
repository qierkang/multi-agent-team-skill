#!/usr/bin/env python3
"""Deterministic inspect-first routing regression for all supported project states."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSPECT = ROOT / "scripts/inspect_team.py"
INIT = ROOT / "scripts/team_init.py"


def run(*args: object, expected: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(item) for item in args], text=True, capture_output=True, check=False)
    if result.returncode not in expected:
        raise RuntimeError(f"exit={result.returncode} args={args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def require(value: object, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def digest_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def inspect(path: Path) -> dict[str, object]:
    return json.loads(run("python3", INSPECT, "--project", path, "--json").stdout)


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="multi-agent-team-inspect-"))
    passed: list[str] = []
    try:
        new = sandbox / "new"
        new.mkdir()
        before = digest_tree(new)
        require(inspect(new)["route_detail"] == "new" and digest_tree(new) == before, "new route is not read-only")
        passed.append("empty directory routes to new without writes")

        existing = sandbox / "existing"
        existing.mkdir()
        (existing / "README.md").write_text("# product\n", encoding="utf-8")
        before = digest_tree(existing)
        require(inspect(existing)["route_detail"] == "existing-project" and digest_tree(existing) == before, "existing project route mismatch")
        passed.append("business content routes to existing-project without writes")

        managed = sandbox / "managed"
        managed.mkdir()
        run("python3", INIT, "--project", managed, "--profile", "core", "--apply")
        current = inspect(managed)
        require(current["route_detail"] == "existing-team:v2", "current team route mismatch")
        manifest_path = managed / ".codex/team-bootstrap.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["skill_version"] = "1.0.1"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        stale = inspect(managed)
        require(stale["route_detail"] == "existing-team:v2-upgrade", "stale managed team did not route to deterministic upgrade")
        passed.append("managed current and stale v2 teams route to doctor or upgrade")

        unknown = sandbox / "unknown"
        (unknown / ".codex").mkdir(parents=True)
        (unknown / ".codex/team-bootstrap.json").write_text(
            json.dumps({"schema_version": "9.9", "skill": "multi-agent-team"}), encoding="utf-8"
        )
        require(inspect(unknown)["route_detail"] == "existing-team:audit", "unknown schema did not fail closed to audit")
        passed.append("unknown team schema routes to read-only audit")

        for item in passed:
            print(f"PASS {item}")
        print(f"STATE=inspect_routes_regression_passed; checks={len(passed)}")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

