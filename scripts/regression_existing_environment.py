#!/usr/bin/env python3
"""Regression suite for existing projects and existing teams."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import stat
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
INSPECT = SKILL_ROOT / "scripts" / "inspect_team.py"
INIT = SKILL_ROOT / "scripts" / "team_init.py"
AUDIT = SKILL_ROOT / "scripts" / "team_audit.py"
DOCTOR = SKILL_ROOT / "scripts" / "team_doctor.py"
THREADS = SKILL_ROOT / "examples" / "threads.example.json"


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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="multi-agent-team-existing-"))
    passed: list[str] = []
    try:
        repo = sandbox / "repository"
        project = repo / "existing-project"
        (project / ".codex").mkdir(parents=True)
        run("git", "init", "-q", repo)
        readme = project / "README.md"
        source = project / "app.py"
        config = project / ".codex" / "config.toml"
        agents_md = project / "AGENTS.md"
        readme.write_text("# Existing Product\n", encoding="utf-8")
        source.write_text("print('business code')\n", encoding="utf-8")
        original_config = '[custom]\nvalue = "keep"\n'
        original_agents = "# Existing project rules\n\n- keep this rule\n"
        config.write_text(original_config, encoding="utf-8")
        agents_md.write_text(original_agents, encoding="utf-8")
        config.chmod(0o640)
        agents_md.chmod(0o644)
        original_modes = (stat.S_IMODE(config.stat().st_mode), stat.S_IMODE(agents_md.stat().st_mode))
        business_hashes = {path: digest(path) for path in (readme, source)}

        inspection = run("python3", INSPECT, "--project", project).stdout
        require("ROUTE=existing-project" in inspection, "business project route mismatch")
        passed.append("existing business project routes without false team detection")

        plan = run("python3", INIT, "--project", project, "--profile", "core").stdout
        require("STATE=plan_ready" in plan, "existing project plan not ready")
        require(original_config == config.read_text(encoding="utf-8"), "dry-run changed config")
        require(original_agents == agents_md.read_text(encoding="utf-8"), "dry-run changed AGENTS")
        passed.append("existing project dry-run is non-invasive")

        applied = run(
            "python3", INIT, "--project", project, "--profile", "core", "--apply"
        ).stdout
        require("STATE=team_installed" in applied, "existing project install failed")
        require(original_config in config.read_text(encoding="utf-8"), "original config content lost")
        require(original_agents in agents_md.read_text(encoding="utf-8"), "original AGENTS content lost")
        require(all(digest(path) == value for path, value in business_hashes.items()), "business file changed")
        current_modes = (stat.S_IMODE(config.stat().st_mode), stat.S_IMODE(agents_md.stat().st_mode))
        require(current_modes == original_modes, f"existing file modes changed: {original_modes} -> {current_modes}")
        backup_root = project / ".codex" / "backups" / "multi-agent-team"
        require(list(backup_root.glob("*/AGENTS.md")), "AGENTS backup missing")
        require(list(backup_root.glob("*/.codex/config.toml")), "config backup missing")
        require("STATE=static_validation_done" in run("python3", DOCTOR, "--project", project).stdout, "doctor failed")
        passed.append("existing config, AGENTS and business files are preserved with backup")

        marker_only = repo / "marker-only-team"
        marker_only.mkdir()
        marker_agents = marker_only / "AGENTS.md"
        marker_agents.write_text(
            "# Existing rules\n\n<!-- team-init:start -->\nlegacy team rules\n<!-- team-init:end -->\n",
            encoding="utf-8",
        )
        marker_hash = digest(marker_agents)
        marker_inspection = run("python3", INSPECT, "--project", marker_only).stdout
        require("ROUTE=existing-team" in marker_inspection, "legacy marker was not detected")
        marker_apply = run("python3", INIT, "--project", marker_only, "--apply", expected=(3,)).stdout
        require("STATE=needs_audit" in marker_apply, "marker-only team bypassed audit")
        require(digest(marker_agents) == marker_hash, "marker-only AGENTS was modified")
        require(not (marker_only / ".codex" / "team-bootstrap.json").exists(), "marker-only install wrote manifest")
        passed.append("legacy AGENTS marker alone forces audit without writes")

        legacy = repo / "legacy-team"
        (legacy / ".codex").mkdir(parents=True)
        legacy_config = legacy / ".codex" / "config.toml"
        legacy_config.write_text(
            '[features]\nmulti_agent = true\n\n[agents.legacy]\nconfig_file = "agents/legacy.toml"\n',
            encoding="utf-8",
        )
        before = digest(legacy_config)
        legacy_inspect = run("python3", INSPECT, "--project", legacy).stdout
        require("ROUTE=existing-team" in legacy_inspect and "configured_roles:legacy" in legacy_inspect, "legacy route mismatch")
        routed = run("python3", INIT, "--project", legacy, "--apply", expected=(3,)).stdout
        require("STATE=needs_audit" in routed and digest(legacy_config) == before, "legacy team was modified")
        report_relative = "docs/协作/团队迁移报告-回归.md"
        audited = run(
            "python3", AUDIT,
            "--project", legacy,
            "--threads-json", THREADS,
            "--report", report_relative,
        ).stdout
        report = legacy / report_relative
        require("STATE=audit_report_ready" in audited and report.is_file(), "audit report missing")
        require("EXECUTION=not_started" in audited, "audit incorrectly reports execution")
        require(digest(legacy_config) == before, "audit modified team config")
        duplicate = run(
            "python3", AUDIT,
            "--project", legacy,
            "--threads-json", THREADS,
            "--report", report_relative,
            expected=(2,),
        )
        require("STATE=audit_failed" in duplicate.stdout, "audit overwrote report without confirmation")
        passed.append("existing team is audited read-only and reports are non-overwriting")

        ignored = repo / "ignored-child"
        ignored.mkdir()
        (repo / ".gitignore").write_text("ignored-child/docs/协作/\n", encoding="utf-8")
        blocked = run("python3", INIT, "--project", ignored, expected=(2,)).stdout
        require("STATE=plan_blocked" in blocked and not (ignored / ".codex").exists(), "ignored path was written")
        passed.append("parent Git ignore rules block untrackable managed files")

        symlink_case = sandbox / "symlink-case"
        (symlink_case / ".codex" / "backups").mkdir(parents=True)
        (symlink_case / ".codex" / "config.toml").write_text("[features]\n", encoding="utf-8")
        (symlink_case / "AGENTS.md").write_text("# existing\n", encoding="utf-8")
        outside = sandbox / "outside"
        outside.mkdir()
        (symlink_case / ".codex" / "backups" / "multi-agent-team").symlink_to(
            outside, target_is_directory=True
        )
        failed = run("python3", INIT, "--project", symlink_case, "--apply", expected=(2,))
        require("STATE=install_failed" in failed.stdout and not list(outside.iterdir()), "symlink escape was not blocked")
        passed.append("deep backup symlink escape is blocked")

        spec = importlib.util.spec_from_file_location("multi_agent_team_init", INIT)
        require(spec and spec.loader, "cannot import installer for transaction test")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        transaction = sandbox / "transaction"
        transaction.mkdir()
        first, second = transaction / "first.txt", transaction / "nested" / "second.txt"
        first.write_text("old", encoding="utf-8")
        original_write = module.atomic_write
        calls = 0

        def fail_second(path: Path, content: str) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected write failure")
            original_write(path, content)

        module.atomic_write = fail_second
        try:
            module.transactional_write({first: "new", second: "new"})
            raise AssertionError("transaction should fail")
        except module.InstallError:
            pass
        finally:
            module.atomic_write = original_write
        require(first.read_text(encoding="utf-8") == "old" and not second.exists(), "transaction rollback incomplete")
        require(not second.parent.exists(), "transaction rollback left a newly created empty directory")
        passed.append("multi-file installation rolls back files and newly created directories")

        explorer = project / ".codex" / "agents" / "explorer.toml"
        original_explorer = explorer.read_bytes()
        explorer.write_bytes(original_explorer + b"\n# unauthorized drift\n")
        drift = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("STATE=static_validation_failed" in drift, "doctor accepted canonical role drift")
        require("matches installed canonical template" in drift, "doctor did not report role drift")
        explorer.write_bytes(original_explorer)

        extra = project / ".codex" / "agents" / "legacy.toml"
        extra.write_text('name = "legacy"\n', encoding="utf-8")
        extra_check = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("STATE=static_validation_failed" in extra_check, "doctor accepted extra role file")
        require("role file set matches manifest" in extra_check, "doctor did not report extra role")
        extra.unlink()

        gitignore = repo / ".gitignore"
        before_ignore = gitignore.read_text(encoding="utf-8")
        gitignore.write_text(before_ignore + "existing-project/.codex/agents/\n", encoding="utf-8")
        ignored_after = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("STATE=static_validation_failed" in ignored_after, "doctor accepted ignored managed roles")
        require("is trackable" in ignored_after, "doctor did not report ignored managed role")
        gitignore.write_text(before_ignore, encoding="utf-8")
        passed.append("doctor rejects role drift, extra roles and ignored managed files")

        external_role = sandbox / "external-role.toml"
        role = explorer
        external_role.write_bytes(role.read_bytes())
        role.unlink()
        role.symlink_to(external_role)
        doctor = run("python3", DOCTOR, "--project", project, expected=(1,)).stdout
        require("STATE=static_validation_failed" in doctor, "doctor accepted role symlink")
        require("explorer.toml has no symlink" in doctor, "doctor did not report role symlink")
        passed.append("doctor rejects role symlink replacement")

        for item in passed:
            print(f"PASS {item}")
        print(f"STATE=existing_environment_regression_passed; checks={len(passed)}")
        return 0
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
