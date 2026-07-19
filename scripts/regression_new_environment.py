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
RUNTIME_SMOKE = SKILL_ROOT / "scripts" / "runtime_smoke.py"
UPGRADE = SKILL_ROOT / "scripts" / "team_upgrade.py"
MODEL_ARGS = (
    "--model-fast", "gpt-5.3-codex-spark",
    "--model-standard", "gpt-5.3-codex",
    "--model-advanced", "gpt-5.4",
)


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
        require(
            "STATE=plan_ready" in plan and "DRY_RUN=1" in plan
            and "TITLE_SUGGESTED=主控｜new-project" in plan
            and "RENAME_ACTION=codex_app__set_thread_title" in plan
            and "TITLE_RENAME=pending" in plan,
            "dry-run state/title contract mismatch",
        )
        passed.append("default dry-run writes nothing")

        applied = run(
            "python3", INIT, "--project", project, "--profile", "full",
            "--thread-mode", "controlled-auto", "--apply"
        ).stdout
        require("STATE=team_installed" in applied and "TITLE_RENAME=pending" in applied, "install state/title mismatch")
        role_files = sorted((project / ".codex" / "agents").glob("*.toml"))
        require(len(role_files) == 8, "full profile did not install eight roles")
        manifest = json.loads((project / ".codex" / "team-bootstrap.json").read_text(encoding="utf-8"))
        require(manifest["skill"] == "multi-agent-team", "manifest skill mismatch")
        require(manifest["profile"] == "full", "manifest profile mismatch")
        require(manifest["schema_version"] == "2.0", "manifest schema mismatch")
        require(manifest["skill_version"] == "2.0.4", "manifest skill version mismatch")
        require(manifest["orchestration"]["control_plane"] == "control-plane-only", "control-plane mode mismatch")
        require(manifest["orchestration"]["lanes"] == ["fast", "project"], "lane manifest mismatch")
        require(manifest["orchestration"]["thread_creation_mode"] == "controlled-auto", "thread mode mismatch")
        require(manifest["runtime_smoke_test"] == "pending", "runtime state must remain pending")
        require(
            manifest["runtime_smoke_evidence"] == {"explorer": [], "reviewer": []},
            "pending runtime smoke must start without fabricated evidence",
        )
        state_files = sorted((project / ".codex/team").glob("*.json"))
        require(len(state_files) == 5, "v2 runtime state files missing")
        snapshot = json.loads((project / "docs/协作/状态快照.json").read_text(encoding="utf-8"))
        require(snapshot["schema_version"] == "2.0" and "threads" in snapshot and "tasks" not in snapshot, "snapshot was not upgraded to v2")
        require((project / "docs/协作/最小派发包模板.md").is_file(), "minimal dispatch packet missing")
        passed.append("full profile installs v2 roles, manifest and runtime state")

        doctor = run("python3", DOCTOR, "--project", project).stdout
        require("STATE=static_validation_done" in doctor, "doctor did not pass")
        require("manifest skill=multi-agent-team" in doctor, "doctor skipped manifest skill check")
        passed.append("static doctor accepts generated project")

        artifacts = project / "artifacts"
        artifacts.mkdir()
        explorer_evidence = artifacts / "explorer-smoke.log"
        explorer_evidence.write_text("explorer client smoke passed\n", encoding="utf-8")
        manifest_path = project / ".codex/team-bootstrap.json"
        before_smoke = manifest_path.read_bytes()
        smoke_plan = run(
            "python3", RUNTIME_SMOKE, "--project", project,
            "--explorer-evidence", "artifacts/explorer-smoke.log",
        ).stdout
        require(
            "STATE=runtime_smoke_plan_ready" in smoke_plan and manifest_path.read_bytes() == before_smoke,
            "runtime smoke dry-run wrote manifest",
        )
        missing_evidence = run(
            "python3", RUNTIME_SMOKE, "--project", project,
            "--reviewer-evidence", "artifacts/missing-reviewer.log", "--apply",
            expected=(2,),
        )
        require("evidence file does not exist" in missing_evidence.stderr, "missing smoke evidence was accepted")
        partial = run(
            "python3", RUNTIME_SMOKE, "--project", project,
            "--explorer-evidence", "artifacts/explorer-smoke.log", "--apply",
        ).stdout
        partial_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(
            "STATE=runtime_smoke_partial_done" in partial
            and partial_manifest["runtime_smoke_test"] == "partial_done"
            and partial_manifest["runtime_smoke_evidence"]["reviewer"] == [],
            "one-sided client evidence did not remain partial",
        )
        partial_doctor = run("python3", DOCTOR, "--project", project).stdout
        require("runtime smoke status partial_done is valid" in partial_doctor, "doctor rejected honest partial smoke state")

        reviewer_evidence = artifacts / "reviewer-smoke.log"
        reviewer_evidence.write_text("fresh reviewer client smoke passed\n", encoding="utf-8")
        validated = run(
            "python3", RUNTIME_SMOKE, "--project", project,
            "--reviewer-evidence", "artifacts/reviewer-smoke.log", "--apply",
        ).stdout
        validated_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(
            "STATE=runtime_validation_done" in validated
            and validated_manifest["runtime_smoke_test"] == "runtime_validation_done",
            "two-sided client evidence did not complete runtime validation",
        )
        require(
            "runtime smoke status runtime_validation_done is valid"
            in run("python3", DOCTOR, "--project", project).stdout,
            "doctor rejected evidence-backed runtime validation",
        )
        reviewer_evidence.unlink()
        invalid_doctor = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("runtime smoke evidence files exist" in invalid_doctor, "doctor accepted missing recorded smoke evidence")
        reviewer_evidence.write_text("fresh reviewer client smoke passed\n", encoding="utf-8")
        require("STATE=static_validation_done" in run("python3", DOCTOR, "--project", project).stdout, "restored smoke evidence did not recover doctor")
        passed.append("runtime smoke moves pending to partial/done only with real role evidence and doctor enforcement")

        unsafe = sandbox / "unsafe-model"
        unsafe.mkdir()
        unsafe_result = run(
            "python3", INIT, "--project", unsafe, "--profile", "core", "--apply",
            "--model-fast", 'bad"\nsandbox_mode="danger-full-access"',
            "--model-standard", "gpt-5.3-codex",
            "--model-advanced", "gpt-5.4",
            expected=(2,),
        )
        require("unsafe model id" in unsafe_result.stderr, "unsafe model id was not rejected")
        require(not (unsafe / ".codex").exists(), "unsafe model id wrote files")
        passed.append("unsafe model ids fail closed before writes")

        current = run("python3", UPGRADE, "--project", project).stdout
        require("STATE=already_current" in current, "current v2 team was not recognized")
        reconfiguration_plan = run("python3", UPGRADE, "--project", project, *MODEL_ARGS).stdout
        require("STATE=model_reconfiguration_plan_ready" in reconfiguration_plan, "v2 model reconfiguration dry-run failed")
        reconfigured = run("python3", UPGRADE, "--project", project, "--apply", *MODEL_ARGS).stdout
        require("STATE=models_reconfigured" in reconfigured, "v2 model reconfiguration failed")
        require("STATE=static_validation_done" in run("python3", DOCTOR, "--project", project).stdout, "reconfigured v2 doctor failed")
        passed.append("valid Codex defaults install directly and v2 models reconfigure transactionally")

        # 真实模型 ID 注入：角色 TOML、project-state model_tiers 与 doctor 校验必须三方一致。
        injected = sandbox / "injected-models"
        injected.mkdir()
        run(
            "python3", INIT, "--project", injected, "--profile", "core", "--apply",
            *MODEL_ARGS,
        )
        explorer_toml = (injected / ".codex/agents/explorer.toml").read_text(encoding="utf-8")
        architect_toml = (injected / ".codex/agents/architect.toml").read_text(encoding="utf-8")
        require('model = "gpt-5.3-codex-spark"' in explorer_toml, "fast tier model was not injected into explorer")
        require('model = "gpt-5.4"' in architect_toml, "advanced tier model was not injected into architect")
        require("gpt-5.6-" not in explorer_toml + architect_toml, "default model id leaked after override")
        injected_state = json.loads((injected / ".codex/team/project-state.json").read_text(encoding="utf-8"))
        require(
            injected_state["model_tiers"] == {
                "fast": "gpt-5.3-codex-spark",
                "standard": "gpt-5.3-codex",
                "advanced": "gpt-5.4",
            },
            "project-state model_tiers were not updated by injection",
        )
        injected_doctor = run("python3", DOCTOR, "--project", injected).stdout
        require("STATE=static_validation_done" in injected_doctor, "doctor rejected injected real model ids")
        passed.append("real model ids inject into roles, project-state and pass doctor")

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
        require("team_manifest:2.0" in payload["team_signals"], "manifest signal missing")
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
