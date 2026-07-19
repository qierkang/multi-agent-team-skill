#!/usr/bin/env python3
"""Fail-closed static validator for a multi-agent-team v2 installation."""

from __future__ import annotations

import argparse
import json
import re
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
    validate_evidence_path,
    validate_evidence_paths,
)
from team_init import apply_model_tiers
from thread_orchestrator import derived_runtime_state, ownership_conflicts
from agents_policy import conflict_messages


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "templates/role-catalog.json").read_text(encoding="utf-8"))
CANONICAL_ROLES = ROOT / "templates/agents"
AGENTS_START = "<!-- multi-agent-team:start -->"
AGENTS_END = "<!-- multi-agent-team:end -->"
CONTROL_AGENT_KEYS = {"max_threads", "max_depth", "job_max_runtime_seconds"}
REQUIRED_DOCS = [
    "docs/协作/任务台账.md",
    "docs/协作/任务包模板.md",
    "docs/协作/最小派发包模板.md",
    "docs/协作/摘要模板.md",
    "docs/协作/状态快照.json",
    "docs/协作/长期线程注册表.md",
    "docs/协作/异常记录.md",
]
ACTIVE_STATES = {"provisioning", "active", "waiting_input", "reviewing", "degraded"}
ALL_STATES = ACTIVE_STATES | {"queued", "escalation_required", "completed", "blocked", "cancelled", "archived"}
RUNTIME_SMOKE_STATES = {"pending", "partial_done", "runtime_validation_done"}
RUNTIME_SMOKE_ROLES = ("explorer", "reviewer")
CONTROL_THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,127}$")
CONTROL_HOST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


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


def valid_smoke_evidence_path(root: Path, raw: str) -> bool:
    try:
        return validate_evidence_path(root, raw) == raw
    except (OSError, ValueError):
        return False


def valid_control_task(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    thread_id = value.get("thread_id")
    host_id = value.get("host_id")
    title = value.get("title")
    return (
        isinstance(thread_id, str)
        and bool(CONTROL_THREAD_ID_RE.fullmatch(thread_id))
        and isinstance(host_id, str)
        and bool(CONTROL_HOST_ID_RE.fullmatch(host_id))
        and isinstance(title, str)
        and title.startswith("主控｜")
        and len(title) <= 160
        and value.get("uri") == f"codex://threads/{thread_id}"
        and value.get("pinned") is True
        and isinstance(value.get("designated_at"), str)
        and bool(value["designated_at"].strip())
    )


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
    check(policy.get("control_plane_mode") == "control-plane-only", "control plane is read-only for production code", failures)
    check(policy.get("control_plane_is_goal") is False, "control plane is not a Codex Goal", failures)
    check(policy.get("goal_policy") == "explicit-only", "Goal creation policy is explicit-only", failures)
    check(policy.get("thread_creation_mode") in {"recommend", "controlled-auto"}, "valid thread creation mode", failures)
    check(policy.get("external_action_policy") == "explicit-user-approval", "external actions require approval", failures)
    interaction = policy.get("interaction_policy", {})
    check(
        isinstance(interaction, dict)
        and interaction.get("dispatch_return_immediately") is True
        and interaction.get("wait_same_turn") is False
        and interaction.get("poll_same_turn") is False
        and interaction.get("long_validation_same_turn") is False
        and interaction.get("sync_wait_requires_explicit_user_request") is True
        and interaction.get("sync_wait_requires_warning") is True,
        "dispatch returns immediately and forbids same-turn waiting/polling",
        failures,
    )
    check(
        isinstance(interaction.get("follow_up_processing"), list)
        and set(interaction["follow_up_processing"]) == {
            "user_turn", "completion_event", "health_check", "acceptance", "redispatch"
        },
        "follow-up processing is deferred to later turns/events",
        failures,
    )
    check(policy.get("creation_threshold") == 7, "project-lane routing threshold", failures)
    check(policy.get("max_concurrency_total") == 6, "total concurrency limit is 6", failures)
    check(policy.get("queue_capacity") == "unbounded", "queue capacity is unbounded", failures)
    check(policy.get("max_concurrent_writers") == 2, "writer concurrency limit is 2", failures)
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
    domains = [item.get("domain_key") for item in active if item.get("lane", "project") == "project"]
    check(all(item.get("status") in ALL_STATES for item in threads if isinstance(item, dict)), "thread statuses valid", failures)
    check(len(domains) == len(set(domains)), "active domain keys unique", failures)
    check(len(active) <= int(policy.get("max_concurrency_total", 0) or 0), "active executions within total limit", failures)
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
    evidence_valid = True
    for item in threads:
        if not isinstance(item, dict):
            continue
        try:
            values = item.get("evidence_paths", [])
            if validate_evidence_paths(root, values) != values:
                raise ValueError("evidence_paths must be canonical and unique")
        except (OSError, ValueError) as exc:
            print(f"FAIL thread evidence {item.get('id', 'unknown')}: {exc}")
            evidence_valid = False
    check(evidence_valid, "thread evidence paths are safe, real, non-empty files", failures)
    known_ids = set(ids)
    check(
        all(
            isinstance(item.get("dependencies", []), list)
            and set(item.get("dependencies", [])) <= known_ids
            and int(item.get("depth", 1) or 1) in {1, 2}
            for item in threads
            if isinstance(item, dict)
        ),
        "dependencies and nesting depth valid",
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="完成闸：要求真实主控绑定和 explorer/reviewer runtime smoke 均完成",
    )
    parser.add_argument("--require-control-task", action="store_true")
    parser.add_argument("--require-runtime-smoke", action="store_true")
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
    orchestration = manifest.get("orchestration", {})
    check(orchestration.get("control_plane_is_goal") is False, "manifest control plane is not a Codex Goal", failures)
    check(orchestration.get("goal_policy") == "explicit-only", "manifest Goal policy is explicit-only", failures)
    check(orchestration.get("control_plane") == "control-plane-only", "main task is control-plane-only", failures)
    check(orchestration.get("lanes") == ["fast", "project"], "manifest declares fast/project lanes", failures)
    control_task = orchestration.get("control_task")
    check(
        control_task is None or valid_control_task(control_task),
        "manifest control task binding is valid when present",
        failures,
    )
    if args.strict or args.require_control_task:
        check(valid_control_task(control_task), "required control task is bound and pinned", failures)
    smoke_status = manifest.get("runtime_smoke_test", "pending")
    raw_smoke_evidence = manifest.get(
        "runtime_smoke_evidence", {role: [] for role in RUNTIME_SMOKE_ROLES}
    )
    smoke_shape_valid = (
        isinstance(raw_smoke_evidence, dict)
        and not (set(raw_smoke_evidence) - set(RUNTIME_SMOKE_ROLES))
        and all(
            isinstance(raw_smoke_evidence.get(role, []), list)
            and all(isinstance(item, str) for item in raw_smoke_evidence.get(role, []))
            for role in RUNTIME_SMOKE_ROLES
        )
    )
    smoke_evidence = (
        {role: raw_smoke_evidence.get(role, []) for role in RUNTIME_SMOKE_ROLES}
        if smoke_shape_valid
        else {role: [] for role in RUNTIME_SMOKE_ROLES}
    )
    expected_smoke_status = (
        "runtime_validation_done"
        if all(smoke_evidence[role] for role in RUNTIME_SMOKE_ROLES)
        else "partial_done"
        if any(smoke_evidence[role] for role in RUNTIME_SMOKE_ROLES)
        else "pending"
    )
    check(smoke_shape_valid, "runtime smoke evidence shape is valid", failures)
    check(
        smoke_status in RUNTIME_SMOKE_STATES and smoke_status == expected_smoke_status,
        f"runtime smoke status {smoke_status} is valid",
        failures,
    )
    check(
        all(valid_smoke_evidence_path(root, item) for values in smoke_evidence.values() for item in values),
        "runtime smoke evidence files exist and are non-empty",
        failures,
    )
    if args.strict or args.require_runtime_smoke:
        check(
            smoke_status == "runtime_validation_done",
            "required explorer/reviewer runtime smoke is complete",
            failures,
        )

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
    check(
        orchestration.get("thread_creation_mode") == project_state.get("thread_creation_mode"),
        "manifest and project state thread creation modes match",
        failures,
    )
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
    agents_conflicts = conflict_messages(agents_text)
    for conflict in agents_conflicts:
        print(f"FAIL AGENTS control-plane conflict: {conflict}")
    check(not agents_conflicts, "AGENTS has no control-plane contradictions outside managed block", failures)
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
    if smoke_status == "runtime_validation_done":
        print("STATIC_VALIDATION=passed; runtime explorer/reviewer evidence recorded")
    elif smoke_status == "partial_done":
        print("STATIC_VALIDATION=passed; runtime smoke partial, missing role evidence still required")
    else:
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
