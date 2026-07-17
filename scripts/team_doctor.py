#!/usr/bin/env python3
"""Fail-closed static validator for a multi-agent-team v2 installation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from runtime_state import (
    BUDGET_STATE,
    DEFAULT_MODEL_TIERS,
    MANAGED_STATE_FILES,
    OWNERSHIP_LOCKS,
    PROJECT_STATE,
    SCHEMA_VERSION,
    SKILL_VERSION,
    THREAD_REGISTRY,
    active_threads,
    load_json,
    normalize_model_tiers,
    safe_state_path,
)
from team_init import apply_model_tiers
from thread_orchestrator import derived_runtime_state, ownership_conflicts


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "templates/role-catalog.json").read_text(encoding="utf-8"))
CANONICAL_ROLES = ROOT / "templates/agents"
AGENTS_START = "<!-- multi-agent-team:start -->"
AGENTS_END = "<!-- multi-agent-team:end -->"
CONTROL_AGENT_KEYS = {"max_threads", "max_depth", "job_max_runtime_seconds"}
REQUIRED_DOCS = [
    "docs/协作/任务台账.md",
    "docs/协作/任务包模板.md",
    "docs/协作/摘要模板.md",
    "docs/协作/状态快照.json",
    "docs/协作/长期线程注册表.md",
    "docs/协作/异常记录.md",
]
ACTIVE_STATES = {"provisioning", "active", "waiting_input", "reviewing", "degraded"}
ALL_STATES = ACTIVE_STATES | {"completed", "blocked", "cancelled", "archived"}


def check(ok: bool, label: str, failures: list[str]) -> None:
    print(f"{'OK' if ok else 'FAIL'} {label}")
    if not ok:
        failures.append(label)


def contains_symlink(root: Path, target: Path) -> bool:
    try:
        parts = target.relative_to(root).parts
    except ValueError:
        return True
    current = root
    for part in parts:
        current /= part
        if current.is_symlink():
            return True
        if not current.exists():
            break
    return False


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def git_root(root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip()).resolve()
    if "not a git repository" in result.stderr.lower():
        return None
    raise ValueError(result.stderr.strip() or "git root lookup failed")


def ignored(repo: Path, path: Path) -> bool:
    relative = path.resolve(strict=False).relative_to(repo)
    result = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--quiet", "--", str(relative)],
        capture_output=True, check=False,
    )
    if result.returncode not in {0, 1}:
        raise ValueError(result.stderr.decode().strip() or "git ignore check failed")
    return result.returncode == 0


def validate_runtime(root: Path, failures: list[str]) -> list[Path]:
    paths = [safe_state_path(root, relative) for relative in MANAGED_STATE_FILES]
    payloads: dict[Path, dict[str, Any]] = {}
    for relative, path in zip(MANAGED_STATE_FILES, paths):
        check(path.is_file(), f"{relative} exists", failures)
        check(not contains_symlink(root, path), f"{relative} has no symlink", failures)
        if path.is_file() and not contains_symlink(root, path):
            try:
                payloads[relative] = load_json(path)
                check(payloads[relative].get("schema_version") == SCHEMA_VERSION, f"{relative} schema={SCHEMA_VERSION}", failures)
            except ValueError as exc:
                print(f"FAIL parse {relative}: {exc}")
                failures.append(f"parse {relative}")

    policy = payloads.get(PROJECT_STATE, {})
    check(policy.get("skill_version") == SKILL_VERSION, "project state skill version", failures)
    check(policy.get("thread_creation_mode") in {"recommend", "controlled-auto"}, "valid thread creation mode", failures)
    check(policy.get("external_action_policy") == "explicit-user-approval", "external actions require approval", failures)
    check(policy.get("creation_threshold") == 7 and policy.get("subagent_threshold") == 4, "routing thresholds", failures)
    check(policy.get("max_active_long_threads") in range(1, 6), "long-thread limit 1..5", failures)
    token = policy.get("token_policy", {})
    check(
        isinstance(token, dict)
        and token.get("compact_at_ratio") == 0.7
        and token.get("scope_freeze_at_ratio") == 0.85
        and token.get("stop_at_ratio") == 1.0,
        "token guardrails 70/85/100",
        failures,
    )

    registry = payloads.get(THREAD_REGISTRY, {})
    threads = registry.get("threads", [])
    check(isinstance(registry.get("revision"), int), "registry revision", failures)
    check(isinstance(threads, list), "registry threads array", failures)
    if not isinstance(threads, list):
        threads = []
    ids = [item.get("id") for item in threads if isinstance(item, dict)]
    check(len(ids) == len(threads) and all(isinstance(item, str) and item for item in ids), "thread ids present", failures)
    check(len(ids) == len(set(ids)), "thread ids unique", failures)
    active = active_threads({"threads": threads})
    domains = [item.get("domain_key") for item in active]
    check(all(item.get("status") in ALL_STATES for item in threads if isinstance(item, dict)), "thread statuses valid", failures)
    check(len(domains) == len(set(domains)), "active domain keys unique", failures)
    ownership = [path for item in active for path in item.get("owned_paths", [])]
    check(len(ownership) == len(set(ownership)), "active path ownership unique", failures)
    overlaps = [
        conflict
        for index, item in enumerate(active)
        for conflict in ownership_conflicts({"owned_paths": item.get("owned_paths", [])}, active[index + 1 :])
    ]
    check(not overlaps, "active path ownership has no ancestor overlap", failures)
    check(
        sum(bool(item.get("owned_paths")) for item in active) <= int(policy.get("max_concurrent_writers", 2) or 0),
        "active writer count within limit",
        failures,
    )
    check(
        all(item.get("status") != "completed" or item.get("evidence_paths") for item in threads if isinstance(item, dict)),
        "completed threads contain evidence",
        failures,
    )
    if THREAD_REGISTRY in payloads and OWNERSHIP_LOCKS in payloads and BUDGET_STATE in payloads:
        expected_locks, expected_budget = derived_runtime_state(registry)
        locks = payloads[OWNERSHIP_LOCKS]
        budget = payloads[BUDGET_STATE]
        check(locks.get("revision") == registry.get("revision") and locks.get("locks") == expected_locks["locks"], "ownership state matches registry", failures)
        check(
            budget.get("revision") == registry.get("revision")
            and budget.get("threads") == expected_budget["threads"]
            and budget.get("project_token_used") == expected_budget["project_token_used"],
            "budget state matches registry",
            failures,
        )
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 multi-agent-team v2 安装与状态结构")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root = Path(args.project).expanduser().resolve()
    failures: list[str] = []
    manifest_path = root / ".codex/team-bootstrap.json"
    config_path = root / ".codex/config.toml"
    agents_path = root / "AGENTS.md"
    check(root.is_dir(), "project directory exists", failures)
    managed = [manifest_path, config_path, agents_path]
    for path in managed:
        check(path.is_file(), f"{path.relative_to(root)} exists", failures)
        check(not contains_symlink(root, path), f"{path.relative_to(root)} has no symlink", failures)
    if failures:
        print("STATE=static_validation_failed")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        config = read_toml(config_path)
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"FAIL parse configuration: {exc}")
        print("STATE=static_validation_failed")
        return 1
    check(manifest.get("skill") == "multi-agent-team", "manifest skill=multi-agent-team", failures)
    check(manifest.get("schema_version") == SCHEMA_VERSION, f"manifest schema={SCHEMA_VERSION}", failures)
    check(manifest.get("skill_version") == SKILL_VERSION, f"manifest skill version={SKILL_VERSION}", failures)
    check(manifest.get("orchestration", {}).get("control_plane") == "main-task-only", "main task is control plane", failures)

    features = config.get("features", {})
    agents = config.get("agents", {})
    check(features.get("multi_agent") is True, "features.multi_agent=true", failures)
    check(agents.get("max_depth") == 1, "agents.max_depth=1", failures)
    check(isinstance(agents.get("max_threads"), int) and 1 <= agents["max_threads"] <= 6, "1<=agents.max_threads<=6", failures)
    roles = manifest.get("roles", [])
    check(isinstance(roles, list) and len(roles) == len(set(roles)) and bool(roles), "manifest roles valid", failures)
    roles = roles if isinstance(roles, list) else []
    config_roles = {key for key, value in agents.items() if key not in CONTROL_AGENT_KEYS and isinstance(value, dict)}
    role_paths = sorted((root / ".codex/agents").glob("*.toml"))
    check(config_roles == set(roles), "config role set matches manifest", failures)
    check({path.stem for path in role_paths} == set(roles), "role file set matches manifest", failures)
    # 允许安装时覆盖默认模型档位；校验以项目 project-state 的 model_tiers 为准，
    # 角色 TOML 除 model 行外仍必须与已安装模板逐字节一致（防篡改）。
    project_state = load_json(safe_state_path(root, PROJECT_STATE)) if (root / PROJECT_STATE).exists() else {}
    project_tiers = normalize_model_tiers(project_state.get("model_tiers"))
    for role in roles:
        path = root / f".codex/agents/{role}.toml"
        canonical = CANONICAL_ROLES / f"{role}.toml"
        expected_bytes = (
            apply_model_tiers(canonical.read_text(encoding="utf-8"), project_tiers).encode("utf-8")
            if canonical.is_file()
            else b""
        )
        check(path.is_file() and canonical.is_file() and path.read_bytes() == expected_bytes, f"{role}.toml matches installed canonical template", failures)
        check(not contains_symlink(root, path), f".codex/agents/{role}.toml has no symlink", failures)
        if path.is_file():
            try:
                data = read_toml(path)
                expected_tier = CATALOG["roles"][role]["tier"]
                check(data.get("model") == project_tiers[expected_tier], f"{role}.model", failures)
            except (KeyError, tomllib.TOMLDecodeError, OSError) as exc:
                print(f"FAIL parse role {role}: {exc}")
                failures.append(f"parse role {role}")

    agents_text = agents_path.read_text(encoding="utf-8", errors="ignore")
    check(AGENTS_START in agents_text and AGENTS_END in agents_text, "AGENTS collaboration marker", failures)
    for relative in REQUIRED_DOCS:
        path = root / relative
        check(path.is_file() and path.stat().st_size > 0, f"{relative} exists and is non-empty", failures)
        check(not contains_symlink(root, path), f"{relative} has no symlink", failures)
        managed.append(path)
    snapshot = root / "docs/协作/状态快照.json"
    snapshot_payload: dict[str, Any] = {}
    if snapshot.is_file():
        try:
            snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
            check(snapshot_payload.get("schema_version") == SCHEMA_VERSION and isinstance(snapshot_payload.get("threads"), list) and "tasks" not in snapshot_payload, "status snapshot schema 2.0 uses threads", failures)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"FAIL status snapshot JSON: {exc}")
            failures.append("status snapshot JSON")

    try:
        runtime_paths = validate_runtime(root, failures)
        managed.extend(runtime_paths)
        registry = load_json(safe_state_path(root, THREAD_REGISTRY))
        snapshot_threads = snapshot_payload.get("threads", [])
        if isinstance(snapshot_threads, list):
            check(snapshot_threads == registry.get("threads", []), "status snapshot threads match registry", failures)
        repo = git_root(root)
        if repo is None:
            print("SKIP managed files git-ignore check: not a Git repository")
        else:
            for path in managed + role_paths:
                check(not ignored(repo, path), f"{path.relative_to(root)} is trackable", failures)
    except (OSError, ValueError) as exc:
        print(f"FAIL runtime/Git validation: {exc}")
        failures.append("runtime/Git validation")

    if failures:
        print(f"FAILURES={len(failures)}")
        print("STATE=static_validation_failed")
        return 1
    print("STATIC_VALIDATION=passed; runtime explorer/reviewer smoke test still required")
    print("STATE=static_validation_done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL unexpected doctor error: {type(exc).__name__}: {exc}")
        print("STATE=static_validation_failed")
        raise SystemExit(1)
