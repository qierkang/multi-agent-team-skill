#!/usr/bin/env python3
"""Static validation for a project managed by multi-agent-team."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any


AGENTS_START = "<!-- multi-agent-team:start -->"
AGENTS_END = "<!-- multi-agent-team:end -->"
SKILL_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROLES = SKILL_ROOT / "templates" / "agents"
CONTROL_AGENT_KEYS = {"max_threads", "max_depth", "job_max_runtime_seconds"}
REQUIRED_DOCS = [
    "docs/协作/任务台账.md",
    "docs/协作/任务包模板.md",
    "docs/协作/摘要模板.md",
    "docs/协作/状态快照.json",
]
READ_ONLY_ROLES = {"explorer", "architect", "reviewer", "evidence-researcher"}
WRITE_ROLES = {"chore", "implementer", "debugger", "e2e-tester"}
EXPECTED_MODELS = {
    "explorer": "gpt-5.6-luna",
    "chore": "gpt-5.6-luna",
    "implementer": "gpt-5.6-terra",
    "debugger": "gpt-5.6-terra",
    "architect": "gpt-5.6-sol",
    "reviewer": "gpt-5.6-sol",
    "e2e-tester": "gpt-5.6-terra",
    "evidence-researcher": "gpt-5.6-terra",
}


def read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"{path}: {exc}") from exc


def check(condition: bool, label: str, failures: list[str]) -> None:
    if condition:
        print(f"OK {label}")
    else:
        print(f"FAIL {label}")
        failures.append(label)


def contains_symlink(root: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
        if not current.exists():
            break
    return False


def git_repository_root(root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    if "not a git repository" in result.stderr.lower():
        return None
    raise ValueError(f"Git 工作树识别失败: {result.stderr.strip() or result.returncode}")


def git_ignored(repo_root: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"受管路径不在 Git 工作树内: {target}") from exc
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "--quiet", "--", str(relative)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise ValueError(f"Git ignore 检查失败: {result.stderr.decode().strip() or result.returncode}")
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 multi-agent-team 静态安装结果")
    parser.add_argument("--project", required=True, help="目标项目根目录")
    args = parser.parse_args()

    root = Path(args.project).expanduser().resolve()
    failures: list[str] = []
    manifest_path = root / ".codex" / "team-bootstrap.json"
    config_path = root / ".codex" / "config.toml"

    check(root.is_dir(), "project directory exists", failures)
    check(manifest_path.is_file(), ".codex/team-bootstrap.json exists", failures)
    check(config_path.is_file(), ".codex/config.toml exists", failures)
    check(not contains_symlink(root, manifest_path), ".codex/team-bootstrap.json has no symlink", failures)
    check(not contains_symlink(root, config_path), ".codex/config.toml has no symlink", failures)
    if failures:
        print("STATE=static_validation_failed")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        config = read_toml(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL parse configuration: {exc}")
        print("STATE=static_validation_failed")
        return 1

    check(manifest.get("skill") == "multi-agent-team", "manifest skill=multi-agent-team", failures)

    features = config.get("features", {})
    agents = config.get("agents", {})
    check(features.get("multi_agent") is True, "features.multi_agent=true", failures)
    check(agents.get("max_depth") == 1, "agents.max_depth=1", failures)
    max_threads = agents.get("max_threads")
    check(isinstance(max_threads, int) and 1 <= max_threads <= 6, "1<=agents.max_threads<=6", failures)
    check(
        agents.get("job_max_runtime_seconds") == manifest.get("defaults", {}).get("job_max_runtime_seconds"),
        "job runtime matches manifest",
        failures,
    )

    roles = manifest.get("roles", [])
    check(isinstance(roles, list) and bool(roles), "manifest contains roles", failures)
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        roles = []
    check(len(roles) == len(set(roles)), "manifest roles are unique", failures)

    config_roles = {
        key
        for key, value in agents.items()
        if key not in CONTROL_AGENT_KEYS and isinstance(value, dict)
    } if isinstance(agents, dict) else set()
    role_dir = root / ".codex" / "agents"
    role_paths = sorted(role_dir.glob("*.toml")) if role_dir.is_dir() else []
    file_roles = {path.stem for path in role_paths}
    manifest_roles = set(roles)
    check(config_roles == manifest_roles, "config role set matches manifest", failures)
    check(file_roles == manifest_roles, "role file set matches manifest", failures)
    for role_path in role_paths:
        check(not contains_symlink(root, role_path), f".codex/agents/{role_path.name} has no symlink", failures)

    for role in roles:
        section = agents.get(role, {}) if isinstance(agents, dict) else {}
        config_file = section.get("config_file") if isinstance(section, dict) else None
        expected_relative = f"agents/{role}.toml"
        check(config_file == expected_relative, f"agents.{role}.config_file", failures)
        role_path = root / ".codex" / expected_relative
        check(role_path.is_file(), f".codex/{expected_relative} exists", failures)
        role_is_safe = not contains_symlink(root, role_path)
        check(role_is_safe, f".codex/{expected_relative} has no symlink", failures)
        if not role_path.is_file() or not role_is_safe:
            continue
        try:
            role_config = read_toml(role_path)
        except ValueError as exc:
            print(f"FAIL parse role {role}: {exc}")
            failures.append(f"parse role {role}")
            continue
        check(role_config.get("name") == role, f"{role}.name", failures)
        check(bool(role_config.get("description")), f"{role}.description", failures)
        check(bool(role_config.get("developer_instructions")), f"{role}.developer_instructions", failures)
        expected_sandbox = "read-only" if role in READ_ONLY_ROLES else "workspace-write"
        if role not in READ_ONLY_ROLES | WRITE_ROLES:
            expected_sandbox = role_config.get("sandbox_mode")
        check(role_config.get("sandbox_mode") == expected_sandbox, f"{role}.sandbox_mode={expected_sandbox}", failures)
        check(
            role_config.get("model") == EXPECTED_MODELS.get(role),
            f"{role}.model={EXPECTED_MODELS.get(role)}",
            failures,
        )
        check(
            role_config.get("model_reasoning_effort") in {"low", "medium", "high"},
            f"{role}.model_reasoning_effort",
            failures,
        )
        canonical = CANONICAL_ROLES / f"{role}.toml"
        check(canonical.is_file(), f"canonical role {role}.toml exists", failures)
        if canonical.is_file():
            check(
                role_path.read_bytes() == canonical.read_bytes(),
                f"{role}.toml matches installed canonical template",
                failures,
            )

    agents_md = root / "AGENTS.md"
    agents_is_safe = not contains_symlink(root, agents_md)
    check(agents_is_safe, "AGENTS.md has no symlink", failures)
    agents_text = agents_md.read_text(encoding="utf-8", errors="ignore") if agents_md.is_file() and agents_is_safe else ""
    check(AGENTS_START in agents_text and AGENTS_END in agents_text, "AGENTS collaboration marker", failures)
    for relative in REQUIRED_DOCS:
        doc_path = root / relative
        check(doc_path.is_file(), f"{relative} exists", failures)
        check(not contains_symlink(root, doc_path), f"{relative} has no symlink", failures)
        check(doc_path.is_file() and doc_path.stat().st_size > 0, f"{relative} is non-empty", failures)

    snapshot_path = root / "docs/协作/状态快照.json"
    if snapshot_path.is_file() and not contains_symlink(root, snapshot_path):
        try:
            json.loads(snapshot_path.read_text(encoding="utf-8"))
            print("OK status snapshot is valid JSON")
        except json.JSONDecodeError as exc:
            print(f"FAIL status snapshot JSON: {exc}")
            failures.append("status snapshot JSON")

    managed_paths = [manifest_path, config_path, agents_md]
    managed_paths.extend(root / relative for relative in REQUIRED_DOCS)
    managed_paths.extend(role_paths)
    try:
        repo_root = git_repository_root(root)
        if repo_root is None:
            print("SKIP managed files git-ignore check: not a Git repository")
        else:
            for path in managed_paths:
                check(not git_ignored(repo_root, path), f"{path.relative_to(root)} is trackable", failures)
    except ValueError as exc:
        print(f"FAIL Git tracking checks: {exc}")
        failures.append("Git tracking checks")

    if failures:
        print(f"FAILURES={len(failures)}")
        print("STATE=static_validation_failed")
        return 1
    print("STATIC_VALIDATION=passed; runtime explorer/reviewer smoke test still required")
    print("STATE=static_validation_done")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        print(f"FAIL unexpected doctor error: {type(exc).__name__}: {exc}")
        print("STATE=static_validation_failed")
        exit_code = 1
    raise SystemExit(exit_code)
