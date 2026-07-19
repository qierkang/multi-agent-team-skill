#!/usr/bin/env python3
"""Regression for AGENTS conflict, strict readiness and control-task binding."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "scripts/team_init.py"
DOCTOR = ROOT / "scripts/team_doctor.py"
AUDIT = ROOT / "scripts/team_audit.py"
UPGRADE = ROOT / "scripts/team_upgrade.py"
SMOKE = ROOT / "scripts/runtime_smoke.py"
BIND = ROOT / "scripts/bind_control_task.py"


def run(*args: object, expected: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(arg) for arg in args], text=True, capture_output=True, check=False)
    if result.returncode not in expected:
        raise AssertionError(
            f"unexpected exit {result.returncode}: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def require(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="multi-agent-team-control-plane-"))
    passed: list[str] = []
    try:
        conflicting = sandbox / "conflicting-project"
        conflicting.mkdir()
        (conflicting / "AGENTS.md").write_text(
            "# Existing rules\n\n- 快速直改（默认）：由主任务直接定位、修改。\n"
            "- 聚焦开发：主任务自行完成。\n",
            encoding="utf-8",
        )
        plan = run("python3", INIT, "--project", conflicting, expected=(2,))
        require("STATE=plan_blocked" in plan.stdout, "installer did not block AGENTS contradiction")
        require("AGENTS.md control-plane conflict" in plan.stdout, "installer omitted contradiction evidence")
        require(not (conflicting / ".codex").exists(), "blocked install wrote managed files")
        passed.append("installer fails closed on unmanaged direct-implementation rules")

        project = sandbox / "managed-project"
        project.mkdir()
        run("python3", INIT, "--project", project, "--profile", "core", "--apply")
        agents = project / "AGENTS.md"
        canonical_agents = agents.read_text(encoding="utf-8")
        agents.write_text(
            "# Existing conflict\n\n- 安装了 multi-agent-team 不等于默认启用团队流程。\n"
            "- 聚焦开发：主任务自行完成。\n\n" + canonical_agents,
            encoding="utf-8",
        )
        doctor = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("AGENTS control-plane conflict" in doctor, "doctor accepted AGENTS contradiction")
        audit = run("python3", AUDIT, "--project", project).stdout
        require("AGENTS control-plane 冲突" in audit, "audit omitted AGENTS contradiction")
        upgrade = run("python3", UPGRADE, "--project", project, expected=(2,))
        require("拒绝升级" in upgrade.stderr, "upgrade accepted AGENTS contradiction")
        agents.write_text(canonical_agents, encoding="utf-8")
        passed.append("doctor, audit and upgrade share contradiction detection")

        strict_pending = run("python3", DOCTOR, "--project", project, "--strict", expected=(1,)).stdout
        require("required control task is bound and pinned" in strict_pending, "strict doctor skipped control binding")
        require("required explorer/reviewer runtime smoke is complete" in strict_pending, "strict doctor skipped runtime smoke")

        artifacts = project / "artifacts"
        artifacts.mkdir()
        (artifacts / "explorer.log").write_text("real explorer smoke\n", encoding="utf-8")
        (artifacts / "reviewer.log").write_text("real fresh reviewer smoke\n", encoding="utf-8")
        run(
            "python3", SMOKE, "--project", project,
            "--explorer-evidence", "artifacts/explorer.log",
            "--reviewer-evidence", "artifacts/reviewer.log", "--apply",
        )

        manifest = project / ".codex/team-bootstrap.json"
        before = digest(manifest)
        bind_plan = run(
            "python3", BIND, "--project", project,
            "--thread-id", "019f79e1-9fbc-73c0-b0ac-a6cdfa34da6c", "--pinned",
        ).stdout
        require("STATE=control_task_binding_plan_ready" in bind_plan, "binding dry-run missing")
        require(digest(manifest) == before, "binding dry-run changed manifest")
        unpinned_apply = run(
            "python3", BIND, "--project", project,
            "--thread-id", "019f79e1-9fbc-73c0-b0ac-a6cdfa34da6c", "--apply",
            expected=(2,),
        )
        require("置顶尚未确认" in unpinned_apply.stderr, "binding accepted an unconfirmed pin")
        require(digest(manifest) == before, "rejected unpinned binding changed manifest")
        run(
            "python3", BIND, "--project", project,
            "--thread-id", "019f79e1-9fbc-73c0-b0ac-a6cdfa34da6c", "--pinned", "--apply",
        )
        strict_done = run("python3", DOCTOR, "--project", project, "--strict").stdout
        require("STATE=static_validation_done" in strict_done, "strict doctor rejected complete binding/smoke")
        passed.append("strict completion requires real binding, pin and two-role smoke evidence")

        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["orchestration"]["control_task"]["pinned"] = False
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        invalid = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("manifest control task binding is valid when present" in invalid, "doctor accepted false pin evidence")
        passed.append("doctor rejects malformed or unpinned persisted control task")

        template_text = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "templates/project/AGENTS.block.md",
                "templates/project/docs/任务包.template.md",
                "templates/project/docs/最小派发包.template.md",
            )
        )
        require("checkout" in template_text and "worktree" in template_text, "cross-worktree boundary missing")
        passed.append("dispatch templates stop writes to another checkout or worktree")

        for item in passed:
            print(f"PASS {item}")
        print(f"STATE=control_plane_policy_regression_passed; checks={len(passed)}")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
