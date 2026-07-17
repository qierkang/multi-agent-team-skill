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
UPGRADE = SKILL_ROOT / "scripts" / "team_upgrade.py"
THREADS = SKILL_ROOT / "examples" / "threads.example.json"
TEMPLATES = SKILL_ROOT / "templates"
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
            "python3", INIT, "--project", project, "--profile", "core", "--apply", *MODEL_ARGS
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

        patch_v2 = repo / "patch-v2"
        shutil.copytree(project, patch_v2)
        patch_manifest_path = patch_v2 / ".codex/team-bootstrap.json"
        patch_state_path = patch_v2 / ".codex/team/project-state.json"
        patch_manifest = json.loads(patch_manifest_path.read_text(encoding="utf-8"))
        patch_state = json.loads(patch_state_path.read_text(encoding="utf-8"))
        patch_manifest["skill_version"] = "1.0.0"
        patch_state["skill_version"] = "1.0.0"
        patch_manifest_path.write_text(json.dumps(patch_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        patch_state_path.write_text(json.dumps(patch_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        patch_business = {path: digest(path) for path in (patch_v2 / "README.md", patch_v2 / "app.py")}
        patch_plan = run("python3", UPGRADE, "--project", patch_v2).stdout
        require("STATE=patch_upgrade_plan_ready" in patch_plan, "v2 patch upgrade dry-run not ready")
        patch_apply = run("python3", UPGRADE, "--project", patch_v2, "--apply").stdout
        require("STATE=team_patch_upgraded" in patch_apply, "v2 patch upgrade did not apply")
        require(all(digest(path) == value for path, value in patch_business.items()), "v2 patch upgrade changed business files")
        require("STATE=static_validation_done" in run("python3", DOCTOR, "--project", patch_v2).stdout, "v2 patch upgrade doctor failed")
        passed.append("managed v2 patch upgrade updates metadata transactionally")

        managed_v1 = repo / "managed-v1"
        shutil.copytree(project, managed_v1)
        for installed_role in (managed_v1 / ".codex/agents").glob("*.toml"):
            shutil.copy2(TEMPLATES / "agents" / installed_role.name, installed_role)
        v1_manifest_path = managed_v1 / ".codex/team-bootstrap.json"
        v1_manifest = json.loads(v1_manifest_path.read_text(encoding="utf-8"))
        v1_manifest["schema_version"] = "1.0"
        v1_manifest["skill_version"] = "0.2.0"
        v1_manifest.pop("orchestration", None)
        v1_manifest_path.write_text(json.dumps(v1_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        shutil.rmtree(managed_v1 / ".codex/team")
        for name in ("长期线程注册表.md", "异常记录.md"):
            (managed_v1 / "docs/协作" / name).unlink()
        snapshot_path = managed_v1 / "docs/协作/状态快照.json"
        snapshot_path.write_text(
            json.dumps({
                "schema_version": "1.0",
                "updated_at": "",
                "max_threads": 6,
                "max_concurrent_writers": 2,
                "tasks": [{
                    "id": "legacy-live",
                    "title": "legacy active task",
                    "status": "in_progress",
                    "summary": "preserve this task",
                    "owned_paths": ["legacy/component"],
                    "evidence_paths": [],
                    "attempts": 1,
                    "needs_user_input": False,
                }],
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        managed_agents_path = managed_v1 / "AGENTS.md"
        managed_agents_path.write_text(
            managed_agents_path.read_text(encoding="utf-8")
            .replace("<!-- multi-agent-team:start -->", "<!-- team-init:start -->")
            .replace("<!-- multi-agent-team:end -->", "<!-- team-init:end -->"),
            encoding="utf-8",
        )
        preserved = [managed_v1 / ".codex/config.toml", managed_v1 / "README.md", managed_v1 / "app.py"]
        preserved_hashes = {path: digest(path) for path in preserved}
        v1_inspection = run("python3", INSPECT, "--project", managed_v1, "--json").stdout
        v1_payload = json.loads(v1_inspection)
        require(v1_payload["route_detail"] == "existing-team:v1", "v1 manifest not detailed to existing-team:v1")
        require(v1_payload["schema_version"] == "1.0", "v1 schema version not surfaced")
        upgrade_plan = run("python3", UPGRADE, "--project", managed_v1, "--thread-mode", "controlled-auto").stdout
        require("STATE=upgrade_plan_ready" in upgrade_plan, "v1 upgrade dry-run not ready")
        require(not (managed_v1 / ".codex/team").exists(), "upgrade dry-run wrote runtime state")
        upgraded = run(
            "python3", UPGRADE, "--project", managed_v1, "--thread-mode", "controlled-auto",
            "--apply", *MODEL_ARGS,
        ).stdout
        require("STATE=team_upgraded" in upgraded, "v1 upgrade did not complete")
        require(all(digest(path) == value for path, value in preserved_hashes.items()), "upgrade changed config or business files")
        require(
            'model = "gpt-5.3-codex-spark"' in (managed_v1 / ".codex/agents/explorer.toml").read_text(encoding="utf-8")
            and 'model = "gpt-5.4"' in (managed_v1 / ".codex/agents/architect.toml").read_text(encoding="utf-8"),
            "upgrade did not inject configured model tiers into managed roles",
        )
        migrated = json.loads(v1_manifest_path.read_text(encoding="utf-8"))
        require(migrated["schema_version"] == "2.0" and migrated["skill_version"] == "1.0.1", "manifest migration mismatch")
        require(migrated["orchestration"]["thread_creation_mode"] == "controlled-auto", "migration thread mode mismatch")
        migrated_registry = json.loads((managed_v1 / ".codex/team/thread-registry.json").read_text(encoding="utf-8"))
        migrated_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        require(
            len(migrated_registry["threads"]) == 1
            and migrated_registry["threads"][0]["id"] == "legacy-live"
            and migrated_registry["threads"][0]["status"] == "active",
            "non-empty v1 task was not preserved in runtime registry",
        )
        require(migrated_snapshot["threads"] == migrated_registry["threads"], "migrated snapshot differs from runtime registry")
        migrated_locks = json.loads((managed_v1 / ".codex/team/ownership-locks.json").read_text(encoding="utf-8"))
        require(migrated_locks["locks"] == [{"path": "legacy/component", "thread_id": "legacy-live"}], "migrated ownership lock missing")
        require("<!-- multi-agent-team:start -->" in managed_agents_path.read_text(encoding="utf-8"), "legacy AGENTS marker was not upgraded")
        require("STATE=static_validation_done" in run("python3", DOCTOR, "--project", managed_v1).stdout, "upgraded v1 doctor failed")
        require(list((managed_v1 / ".codex/backups/multi-agent-team").glob("*/.codex/team-bootstrap.json")), "upgrade manifest backup missing")
        require(list((managed_v1 / ".codex/backups/multi-agent-team").glob("*/.codex/agents/explorer.toml")), "upgrade role backup missing")
        passed.append("managed v1 upgrades transactionally with model injection and preserves business files")

        unknown = repo / "unknown-schema"
        shutil.copytree(managed_v1, unknown)
        unknown_manifest_path = unknown / ".codex/team-bootstrap.json"
        unknown_manifest = json.loads(unknown_manifest_path.read_text(encoding="utf-8"))
        unknown_manifest["schema_version"] = "9.9"
        unknown_manifest_path.write_text(json.dumps(unknown_manifest), encoding="utf-8")
        before_unknown = digest(unknown_manifest_path)
        rejected = run("python3", UPGRADE, "--project", unknown, "--apply", expected=(2,))
        require("STATE=upgrade_failed" in rejected.stdout and digest(unknown_manifest_path) == before_unknown, "unknown schema was not fail-closed")
        passed.append("unknown schema upgrade fails closed without writes")

        snapshot_conflict = repo / "snapshot-conflict"
        (snapshot_conflict / "docs/协作").mkdir(parents=True)
        (snapshot_conflict / "README.md").write_text("# product\n", encoding="utf-8")
        conflict_snapshot = snapshot_conflict / "docs/协作/状态快照.json"
        conflict_snapshot.write_text(json.dumps({"schema_version": "1.0", "tasks": []}), encoding="utf-8")
        conflict_hash = digest(conflict_snapshot)
        conflict_plan = run("python3", INIT, "--project", snapshot_conflict, expected=(2,)).stdout
        require("STATE=plan_blocked" in conflict_plan and "不是 schema 2.0" in conflict_plan, "legacy snapshot conflict was not planned as blocked")
        conflict_apply = run("python3", INIT, "--project", snapshot_conflict, "--apply", expected=(2,)).stdout
        require("STATE=install_failed" in conflict_apply and digest(conflict_snapshot) == conflict_hash, "conflicting snapshot was overwritten")
        require(not (snapshot_conflict / ".codex/team-bootstrap.json").exists(), "blocked snapshot install wrote manifest")
        passed.append("existing incompatible collaboration snapshot blocks installation without writes")

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
