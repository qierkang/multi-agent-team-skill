#!/usr/bin/env python3
"""Validate the multi-agent-team Skill package itself.

This is different from team_doctor.py: health_check validates the reusable
Skill source, while team_doctor validates one generated target project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from runtime_state import state_defaults


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
EXPECTED_ROLES = {
    "explorer",
    "chore",
    "implementer",
    "debugger",
    "architect",
    "reviewer",
    "e2e-tester",
    "evidence-researcher",
}
REQUIRED_FILES = {
    "SKILL.md",
    "START-HERE.md",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "templates/README.md",
    "templates/role-catalog.json",
    "references/INDEX.md",
    "references/completion-gate.md",
    "governance/INDEX.md",
    "governance/health-check.md",
    "governance/PRODUCTION-SCORECARD.md",
    "references/github-publish.md",
    "assets/asset-manifest.json",
    "assets/social-preview.png",
    "assets/architecture/zh-CN/team-orchestration-overview.png",
    "assets/architecture/zh-CN/safe-existing-skill-upgrade.png",
    "assets/architecture/en/team-orchestration-overview.png",
    "assets/architecture/en/safe-existing-skill-upgrade.png",
    "docs/README_en.md",
    "docs/README_zh-tw.md",
    "examples/task-input.example.json",
    "examples/regression-evidence-2026-07-19-v2.0.4.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    "install/setup.sh",
    "install/sync.sh",
    "install/doctor.sh",
    "scripts/runtime_state.py",
    "scripts/runtime_smoke.py",
    "scripts/agents_policy.py",
    "scripts/bind_control_task.py",
    "scripts/thread_orchestrator.py",
    "scripts/team_upgrade.py",
    "scripts/regression_runtime_orchestration.py",
    "scripts/regression_inspect_routes.py",
    "scripts/check_readme_links.py",
    "scripts/project_title.py",
    "scripts/regression_title_rename.py",
    "scripts/regression_interaction_policy.py",
    "scripts/goal_policy.py",
    "scripts/regression_goal_policy.py",
    "scripts/regression_control_plane_policy.py",
    "references/runtime-orchestration.md",
    "references/long-thread-policy.md",
    "references/health-anomaly-token.md",
    "references/schema-migration.md",
}
FORBIDDEN_REFERENCES = (
    "assets/agents/",
    "assets/docs/",
    "assets/role-catalog.json",
    "assets/团队迁移报告.template.md",
    "assets/threads.example.json",
)


def emit(ok: bool, label: str, failures: list[str]) -> None:
    print(f"{'PASS' if ok else 'FAIL'} {label}")
    if not ok:
        failures.append(label)


def parse_role(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 multi-agent-team-skill 自身健康状态")
    parser.add_argument("--deep", action="store_true", help="额外运行新环境和已有环境完整回归")
    args = parser.parse_args()
    failures: list[str] = []

    for relative in sorted(REQUIRED_FILES):
        path = ROOT / relative
        emit(path.is_file() and not path.is_symlink(), f"required file {relative}", failures)

    skill_path = ROOT / "SKILL.md"
    skill_text = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
    emit(len(skill_text.splitlines()) <= 80, "SKILL.md stays within 80 lines", failures)
    emit(35 <= len(skill_text.splitlines()) <= 50, "SKILL.md stays near 40 lines", failures)
    emit(bool(re.search(r"(?m)^name:\s*multi-agent-team\s*$", skill_text)), "stable skill name", failures)
    emit('version: "2.0.4"' in skill_text, "Skill metadata version 2.0.4", failures)
    emit("references/" in skill_text and "scripts/" in skill_text, "root entry routes progressively", failures)
    emit("control-plane-only" in skill_text and "fast lane" in skill_text and "project lane" in skill_text, "v2 control plane and lanes documented", failures)
    emit("control_plane_is_goal" in skill_text and "explicit-only" in skill_text, "Goal is explicit-only and not the control plane", failures)
    emit("create_goal(" not in skill_text and "call goal-writer" not in skill_text, "no executable Goal/goal-writer route in Skill", failures)
    emit("handle_in_main" not in skill_text and "use_subagents" not in skill_text, "no main-task implementation route", failures)

    try:
        catalog = json.loads((TEMPLATES / "role-catalog.json").read_text(encoding="utf-8"))
        catalog_roles = set(catalog.get("roles", {}))
        profiles = catalog.get("profiles", {})
        emit(catalog_roles == EXPECTED_ROLES, "role catalog contains exactly eight roles", failures)
        emit(catalog.get("schema_version") == "2.0", "role catalog schema 2.0", failures)
        emit(catalog.get("skill_version") == "2.0.4", "role catalog skill version 2.0.4", failures)
        emit(
            isinstance(profiles, dict)
            and bool(profiles)
            and all(set(roles) <= EXPECTED_ROLES for roles in profiles.values()),
            "all profiles reference known roles",
            failures,
        )
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"FAIL parse role catalog: {exc}")
        failures.append("parse role catalog")
        catalog_roles = set()

    role_paths = sorted((TEMPLATES / "agents").glob("*.toml"))
    emit({path.stem for path in role_paths} == EXPECTED_ROLES, "role template set matches catalog", failures)
    for path in role_paths:
        try:
            role = parse_role(path)
            emit(role.get("name") == path.stem, f"role name matches {path.name}", failures)
            emit(bool(role.get("model")), f"role model declared {path.name}", failures)
            emit(role.get("sandbox_mode") in {"read-only", "workspace-write"}, f"role sandbox declared {path.name}", failures)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"FAIL parse role {path.name}: {exc}")
            failures.append(f"parse role {path.name}")

    for relative in (
        "project/AGENTS.block.md",
        "project/config.snippet.toml",
        "project/docs/任务台账.template.md",
        "project/docs/任务包.template.md",
        "project/docs/最小派发包.template.md",
        "project/docs/摘要.template.md",
        "project/docs/状态快照.template.json",
        "project/docs/长期线程注册表.template.md",
        "project/docs/异常记录.template.md",
        "project/team/project-state.template.json",
        "project/team/thread-registry.template.json",
        "project/team/ownership-locks.template.json",
        "project/team/budget-state.template.json",
        "project/team/recovery-journal.template.json",
        "reports/团队迁移报告.template.md",
    ):
        emit((TEMPLATES / relative).is_file(), f"template exists {relative}", failures)

    try:
        tomllib.loads((TEMPLATES / "project/config.snippet.toml").read_text(encoding="utf-8"))
        json.loads((TEMPLATES / "project/docs/状态快照.template.json").read_text(encoding="utf-8"))
        for path in (TEMPLATES / "project/team").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))
        print("PASS project TOML and JSON templates parse")
    except (OSError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        print(f"FAIL parse project templates: {exc}")
        failures.append("parse project templates")

    try:
        for relative, expected in state_defaults("controlled-auto").items():
            template = TEMPLATES / "project/team" / f"{relative.stem}.template.json"
            actual = json.loads(template.read_text(encoding="utf-8"))
            expected = dict(expected)
            expected["updated_at"] = ""
        emit(actual == expected, f"runtime template matches generator {template.name}", failures)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"FAIL compare runtime templates: {exc}")
        failures.append("compare runtime templates")

    text_files = [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts
        and path.resolve() != Path(__file__).resolve()
        and path.suffix.lower() in {".md", ".py", ".sh", ".toml", ".json", ".yaml", ".yml"}
    ]
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in text_files)
    for forbidden in FORBIDDEN_REFERENCES:
        emit(forbidden not in combined, f"no stale template path {forbidden}", failures)
    emit(not re.search(r"/Users/[^/<\s]+/", combined), "no local absolute user path", failures)

    for script in sorted((ROOT / "scripts").glob("*.py")):
        try:
            compile(script.read_text(encoding="utf-8"), str(script), "exec")
            print(f"PASS compile {script.name}")
        except (OSError, SyntaxError) as exc:
            print(f"FAIL compile {script.name}: {exc}")
            failures.append(f"compile {script.name}")

    asset_result = subprocess.run(
        ["bash", str(ROOT / "scripts/verify_assets.sh"), str(ROOT)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(asset_result.stdout, end="")
    emit(
        asset_result.returncode == 0 and "STATE=asset_done" in asset_result.stdout,
        "formal visual assets and README references",
        failures,
    )

    link_result = subprocess.run(
        ["python3", str(ROOT / "scripts/check_readme_links.py")],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    print(link_result.stdout, end="")
    emit(
        link_result.returncode == 0 and "STATE=readme_links_passed" in link_result.stdout,
        "README local links",
        failures,
    )

    if args.deep and not failures:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/regression_check.py")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(result.stdout, end="")
        emit(
            result.returncode == 0 and "STATE=regression_passed" in result.stdout,
            "new and existing environment regression",
            failures,
        )
        optimized_env = dict(os.environ)
        optimized_env["PYTHONOPTIMIZE"] = "1"
        optimized = subprocess.run(
            ["python3", str(ROOT / "scripts/regression_check.py")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=optimized_env,
        )
        print(optimized.stdout, end="")
        emit(
            optimized.returncode == 0 and "STATE=regression_passed" in optimized.stdout,
            "regressions pass with PYTHONOPTIMIZE=1",
            failures,
        )
        title_result = subprocess.run(
            ["python3", str(ROOT / "scripts/regression_title_rename.py")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(title_result.stdout, end="")
        emit(
            title_result.returncode == 0 and "PASS title rename regression" in title_result.stdout,
            "deterministic title rename regression",
            failures,
        )
        interaction_result = subprocess.run(
            ["python3", str(ROOT / "scripts/regression_interaction_policy.py")],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        print(interaction_result.stdout, end="")
        emit(
            interaction_result.returncode == 0
            and "STATE=interaction_policy_regression_passed" in interaction_result.stdout,
            "deterministic dispatch-return regression",
            failures,
        )

    if failures:
        print(f"FAILURES={len(failures)}")
        print("STATE=skill_health_failed")
        return 1
    print("STATE=skill_health_passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL unexpected health-check error: {type(exc).__name__}: {exc}")
        print("STATE=skill_health_failed")
        raise SystemExit(1)
