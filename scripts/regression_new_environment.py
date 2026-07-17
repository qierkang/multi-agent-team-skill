#!/usr/bin/env python3
"""Regression suite for an empty/new project environment."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INSPECT = SKILL_ROOT / "scripts" / "inspect_team.py"
INIT = SKILL_ROOT / "scripts" / "team_init.py"
DOCTOR = SKILL_ROOT / "scripts" / "team_doctor.py"


def run(*args: object, expected: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(arg) for arg in args], text=True, capture_output=True, check=False)
    if result.returncode not in expected:
        raise AssertionError(
            f"unexpected exit {result.returncode}: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def tree_digest(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        rows.append((str(path.relative_to(root)), path.is_dir(), path.is_symlink()))
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="multi-agent-team-new-"))
    passed: list[str] = []
    try:
        project = sandbox / "new-project"
        project.mkdir()

        inspection = run("python3", INSPECT, "--project", project).stdout
        require("ROUTE=new" in inspection and "STATE=inspection_done" in inspection, "empty route mismatch")
        passed.append("empty directory routes to new")

        before = tree_digest(project)
        plan = run("python3", INIT, "--project", project, "--profile", "full").stdout
        after = tree_digest(project)
        require(before == after, "dry-run changed target tree")
        require("STATE=plan_ready" in plan and "DRY_RUN=1" in plan, "dry-run state mismatch")
        passed.append("default dry-run writes nothing")

        applied = run(
            "python3", INIT, "--project", project, "--profile", "full", "--apply"
        ).stdout
        require("STATE=team_installed" in applied, "install state mismatch")
        role_files = sorted((project / ".codex" / "agents").glob("*.toml"))
        require(len(role_files) == 8, "full profile did not install eight roles")
        manifest = json.loads((project / ".codex" / "team-bootstrap.json").read_text(encoding="utf-8"))
        require(manifest["skill"] == "multi-agent-team", "manifest skill mismatch")
        require(manifest["profile"] == "full", "manifest profile mismatch")
        require(manifest["runtime_smoke_test"] == "pending", "runtime state must remain pending")
        passed.append("full profile installs eight role templates and manifest")

        doctor = run("python3", DOCTOR, "--project", project).stdout
        require("STATE=static_validation_done" in doctor, "doctor did not pass")
        require("manifest skill=multi-agent-team" in doctor, "doctor skipped manifest skill check")
        passed.append("static doctor accepts generated project")

        if shutil.which("codex"):
            features = run("codex", "-C", project, "features", "list").stdout
            multi_agent_line = next(
                (line for line in features.splitlines() if line.strip().startswith("multi_agent ")),
                "",
            )
            require(multi_agent_line.rstrip().endswith("true"), "Codex did not load multi_agent=true")
            passed.append("Codex CLI loads generated multi_agent configuration")
        else:
            print("SKIP Codex CLI configuration load: codex not installed")

        after_inspection = run("python3", INSPECT, "--project", project, "--json").stdout
        payload = json.loads(after_inspection)
        require(payload["route"] == "existing-team", "installed route mismatch")
        require("team_manifest" in payload["team_signals"], "manifest signal missing")
        passed.append("installed project is reclassified as existing team")

        second = run("python3", INIT, "--project", project, "--apply", expected=(3,)).stdout
        require("STATE=needs_audit" in second, "reinstall was not routed to audit")
        passed.append("reinstall is blocked and routed to audit")

        for item in passed:
            print(f"PASS {item}")
        print(f"STATE=new_environment_regression_passed; checks={len(passed)}")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
