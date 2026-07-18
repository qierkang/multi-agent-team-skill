#!/usr/bin/env python3
"""Plan and persist controlled long-running Codex thread orchestration state.

The script is deliberately runtime-adapter neutral: it never creates a Codex
thread itself. The main Codex task calls the client thread tools, then records
the returned thread id with the register command.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from runtime_state import (
    BUDGET_STATE,
    OWNERSHIP_LOCKS,
    PROJECT_STATE,
    SCHEMA_VERSION,
    THREAD_REGISTRY,
    active_threads,
    append_journal,
    atomic_write_json,
    is_light_task,
    load_json,
    model_for_task,
    next_model_tier,
    now_iso,
    runtime_lock,
    safe_project_root,
    safe_state_path,
    thread_score,
    validate_evidence_path,
    validate_evidence_paths,
)


ACTIVE_STATES = {"provisioning", "active", "waiting_input", "reviewing", "degraded"}
TERMINAL_STATES = {"completed", "blocked", "cancelled", "archived"}
TRANSITIONS = {
    "queued": {"blocked", "cancelled"},
    "provisioning": {"active", "blocked", "cancelled"},
    "active": {"active", "waiting_input", "reviewing", "degraded", "completed", "blocked", "cancelled"},
    "waiting_input": {"active", "blocked", "cancelled"},
    "reviewing": {"active", "completed", "blocked", "degraded"},
    "degraded": {"active", "waiting_input", "reviewing", "escalation_required", "blocked", "cancelled"},
    "escalation_required": {"blocked", "cancelled"},
    "blocked": {"active", "cancelled", "archived"},
    "completed": {"archived"},
    "cancelled": {"archived"},
    "archived": set(),
}
STATUS_SNAPSHOT = Path("docs/协作/状态快照.json")
TASK_FIELDS = {
    "domain_key",
    "title",
    "owned_paths",
    "expected_days",
    "task_packages",
    "independent_boundary",
    "recurring",
    "independent_release",
    "decision_retention",
    "parallelizable",
    "task_type",
    "risk",
    "attempts",
    "dependencies",
    "parent_thread_id",
    "timeout_seconds",
}
TASK_BOOL_FIELDS = {
    "independent_boundary",
    "recurring",
    "independent_release",
    "decision_retention",
    "parallelizable",
}
TASK_TYPES = {
    "implementation",
    "exploration",
    "chore",
    "docs",
    "research",
    "architecture",
    "security",
    "review",
    "migration",
}
TASK_RISKS = {"low", "medium", "high", "critical"}


def load_runtime(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_json(safe_state_path(root, PROJECT_STATE))
    registry = load_json(safe_state_path(root, THREAD_REGISTRY))
    if policy.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("project state requires migration to schema 2.0")
    if registry.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("thread registry requires migration to schema 2.0")
    return policy, registry


def load_task(path: str) -> dict[str, Any]:
    task_path = Path(path).expanduser().resolve()
    payload = load_json(task_path)
    unknown = sorted(set(payload) - TASK_FIELDS)
    if unknown:
        raise ValueError("task JSON contains unknown fields: " + ", ".join(unknown))
    domain_key = payload.get("domain_key")
    title = payload.get("title")
    if not isinstance(domain_key, str) or not domain_key.strip():
        raise ValueError("task JSON requires non-empty domain_key")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("task JSON requires non-empty title")
    payload["domain_key"] = domain_key.strip()
    payload["title"] = title.strip()
    owned = payload.get("owned_paths", [])
    if not isinstance(owned, list) or not all(isinstance(item, str) and item for item in owned):
        raise ValueError("owned_paths must be a list of non-empty strings")
    validate_owned_paths(owned)
    for field in TASK_BOOL_FIELDS:
        if field in payload and not isinstance(payload[field], bool):
            raise ValueError(f"{field} must be a boolean")
    expected_days = payload.get("expected_days")
    if expected_days is not None:
        if isinstance(expected_days, bool) or not isinstance(expected_days, (int, float)):
            raise ValueError("expected_days must be a non-negative finite number")
        if not math.isfinite(float(expected_days)) or expected_days < 0:
            raise ValueError("expected_days must be a non-negative finite number")
    for field in ("task_packages", "attempts"):
        value = payload.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f"{field} must be a non-negative integer")
    task_type = payload.get("task_type")
    if task_type is not None and task_type not in TASK_TYPES:
        raise ValueError("task_type is not supported")
    risk = payload.get("risk")
    if risk is not None and risk not in TASK_RISKS:
        raise ValueError("risk is not supported")
    dependencies = payload.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) and item.strip() for item in dependencies
    ):
        raise ValueError("dependencies must be a list of non-empty task ids")
    payload["dependencies"] = list(dict.fromkeys(item.strip() for item in dependencies))
    parent = payload.get("parent_thread_id")
    if parent is not None and (not isinstance(parent, str) or not parent.strip()):
        raise ValueError("parent_thread_id must be a non-empty string")
    if isinstance(parent, str):
        payload["parent_thread_id"] = parent.strip()
    timeout = payload.get("timeout_seconds")
    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
        raise ValueError("timeout_seconds must be a positive integer")
    return payload


def validate_owned_paths(paths: list[str]) -> None:
    for raw in paths:
        candidate = PurePosixPath(raw.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts or str(candidate) in {"", "."}:
            raise ValueError(f"owned path must be project-relative and non-traversing: {raw}")


def ownership_conflicts(task: dict[str, Any], threads: list[dict[str, Any]]) -> list[dict[str, str]]:
    requested = set(task.get("owned_paths", []))
    conflicts: list[dict[str, str]] = []
    for thread in threads:
        for requested_path in requested:
            for owned_path in set(thread.get("owned_paths", [])):
                left = PurePosixPath(requested_path.replace("\\", "/")).parts
                right = PurePosixPath(str(owned_path).replace("\\", "/")).parts
                if left[: len(right)] == right or right[: len(left)] == left:
                    conflicts.append({
                        "path": requested_path,
                        "conflicts_with": str(owned_path),
                        "thread_id": str(thread.get("id", "unknown")),
                    })
    return conflicts


def incomplete_dependencies(registry: dict[str, Any], record: dict[str, Any]) -> list[str]:
    dependencies = [find_thread(registry, str(item)) for item in record.get("dependencies", [])]
    return [
        str(item.get("id"))
        for item in dependencies
        if item.get("status") != "completed"
        and not (item.get("status") == "archived" and item.get("terminal_outcome") == "completed")
    ]


def validate_active_admission(
    policy: dict[str, Any],
    registry: dict[str, Any],
    record: dict[str, Any],
    *,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """Apply dependency, parent, ownership, domain and capacity gates before active state."""
    incomplete = incomplete_dependencies(registry, record)
    if incomplete:
        raise ValueError(prefix + "dependencies are not completed: " + ", ".join(incomplete))
    active = [item for item in active_threads(registry) if item.get("id") != record.get("id")]
    if len(active) >= int(policy.get("max_concurrency_total", 6)):
        raise ValueError(prefix + "total concurrency capacity reached")
    conflicts = ownership_conflicts(record, active)
    if conflicts:
        raise ValueError(prefix + f"owned path conflict: {conflicts}")
    if record.get("owned_paths") and sum(bool(item.get("owned_paths")) for item in active) >= int(
        policy.get("max_concurrent_writers", 2)
    ):
        raise ValueError(prefix + "concurrent writer capacity reached")
    if record.get("lane", "project") == "project":
        if policy.get("thread_creation_mode") != "controlled-auto":
            raise ValueError(prefix + "project-lane activation requires controlled-auto mode")
        if any(
            item.get("domain_key") == record.get("domain_key")
            and item.get("lane", "project") == "project"
            for item in active
        ):
            raise ValueError(prefix + "active project domain already exists")
    if int(record.get("depth", 1) or 1) == 2:
        parent = find_thread(registry, str(record.get("parent_thread_id") or ""))
        if (
            parent.get("status") not in ACTIVE_STATES
            or parent.get("lane", "project") != "project"
            or int(parent.get("depth", 1) or 1) != 1
        ):
            raise ValueError(prefix + "parent must be an active project-lane task")
    return active


def plan(root: Path, task: dict[str, Any]) -> dict[str, Any]:
    policy, registry = load_runtime(root)
    active = active_threads(registry)
    score, reasons = thread_score(task)
    tier, model = model_for_task(policy, task)
    existing = next(
        (
            item
            for item in active
            if item.get("domain_key") == task["domain_key"]
            and item.get("lane", "project") == "project"
        ),
        None,
    )
    conflicts = ownership_conflicts(task, [item for item in active if item is not existing])
    create_threshold = int(policy.get("creation_threshold", 7))
    mode = policy.get("thread_creation_mode", "recommend")
    max_active = int(policy.get("max_concurrency_total", 6))
    max_writers = int(policy.get("max_concurrent_writers", 2))
    active_writers = sum(bool(item.get("owned_paths")) for item in active)
    lane = "project" if score >= create_threshold else "fast"
    light = lane == "fast" and is_light_task(task)
    packet = "minimal" if light else "full"
    risk = str(task.get("risk", "medium")).lower()
    review_policy = (
        "always-fresh-reviewer"
        if risk in {"high", "critical"}
        else "on-failure"
        if light
        else "acceptance-based"
    )

    if lane == "project" and existing:
        decision = "reuse_project_thread"
    elif conflicts:
        decision = f"queue_{lane}_ownership"
    elif len(active) >= max_active:
        decision = f"queue_{lane}_capacity"
    elif task.get("owned_paths") and active_writers >= max_writers:
        decision = f"queue_{lane}_writer"
    elif lane == "project":
        decision = "create_project_thread" if mode == "controlled-auto" else "recommend_project_thread"
    else:
        decision = "dispatch_fast_agent"

    return {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "lane": lane,
        "control_plane_mode": policy.get("control_plane_mode", "control-plane-only"),
        "dispatch_packet": packet,
        "review_policy": review_policy,
        "thread_creation_mode": mode,
        "score": score,
        "reasons": reasons,
        "domain_key": task["domain_key"],
        "title": task["title"],
        "model_tier": tier,
        "model": model,
        "existing_thread_id": existing.get("id") if existing else None,
        "active_long_threads": sum(item.get("lane", "project") == "project" for item in active),
        "active_total": len(active),
        "max_concurrency_total": max_active,
        "queue_capacity": "unbounded",
        "ownership_conflicts": conflicts,
        "next": {
            "create_project_thread": "enqueue the work, create a project task with the client, then bind the returned instance id",
            "recommend_project_thread": "recommend project lane; creation requires an explicit controlled-auto mode upgrade",
            "reuse_project_thread": "enqueue and send the full package to existing_thread_id",
            "dispatch_fast_agent": "dispatch one bounded one-shot agent; the control plane does not edit production code",
            "queue_project_capacity": "enqueue without limit and wait for total concurrency capacity",
            "queue_fast_capacity": "enqueue without limit and wait for total concurrency capacity",
            "queue_project_writer": "enqueue and wait for a writer slot",
            "queue_fast_writer": "enqueue and wait for a writer slot",
            "queue_project_ownership": "enqueue and wait for conflicting ownership to release",
            "queue_fast_ownership": "enqueue and wait for conflicting ownership to release",
        }[decision],
    }


def find_thread(registry: dict[str, Any], thread_id: str) -> dict[str, Any]:
    for item in registry.get("threads", []):
        if isinstance(item, dict) and item.get("id") == thread_id:
            return item
    raise ValueError(f"thread not found: {thread_id}")


def write_registry(root: Path, registry: dict[str, Any]) -> None:
    registry["revision"] = int(registry.get("revision", 0)) + 1
    registry["updated_at"] = now_iso()
    atomic_write_json(safe_state_path(root, THREAD_REGISTRY), registry)


def derived_runtime_state(registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    active = active_threads(registry)
    revision = int(registry.get("revision", 0))
    locks = {
        "schema_version": SCHEMA_VERSION,
        "revision": revision,
        "updated_at": now_iso(),
        "locks": [
            {"path": path, "thread_id": str(thread.get("id"))}
            for thread in active
            for path in thread.get("owned_paths", [])
        ],
    }
    all_threads = [item for item in registry.get("threads", []) if isinstance(item, dict)]
    budget = {
        "schema_version": SCHEMA_VERSION,
        "revision": revision,
        "updated_at": now_iso(),
        "project_token_used": sum(int(item.get("token_used", 0) or 0) for item in all_threads),
        "threads": {
            str(item.get("id")): {
                "used": int(item.get("token_used", 0) or 0),
                "budget": int(item.get("token_budget", 0) or 0),
            }
            for item in all_threads
        },
    }
    return locks, budget


def sync_derived_state(root: Path, registry: dict[str, Any]) -> None:
    locks, budget = derived_runtime_state(registry)
    atomic_write_json(safe_state_path(root, OWNERSHIP_LOCKS), locks)
    atomic_write_json(safe_state_path(root, BUDGET_STATE), budget)
    atomic_write_json(
        safe_state_path(root, STATUS_SNAPSHOT),
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": now_iso(),
            "max_threads": 6,
            "max_concurrent_writers": 2,
            "threads": registry.get("threads", []),
        },
    )


def require_expected_revision(registry: dict[str, Any], expected: int | None) -> None:
    if expected is not None and int(registry.get("revision", 0)) != expected:
        raise ValueError(
            f"stale write: expected revision {expected}, current {registry.get('revision', 0)}"
        )


def model_tier_for(policy: dict[str, Any], model: str) -> str:
    matches = [tier for tier, candidate in policy.get("model_tiers", {}).items() if candidate == model]
    if not matches:
        raise ValueError(f"model is not configured: {model}")
    return matches[-1]


def validate_reference_path(raw: str, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be a non-empty project-relative path")
    value = raw.strip().replace("\\", "/")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or str(candidate) in {"", "."}:
        raise ValueError(f"{label} must be project-relative and non-traversing")
    return value


def dependency_cycle(registry: dict[str, Any], task_id: str, dependencies: list[str]) -> bool:
    graph = {
        str(item.get("id")): [str(dep) for dep in item.get("dependencies", [])]
        for item in registry.get("threads", [])
        if isinstance(item, dict)
    }
    graph[task_id] = dependencies
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(dependency) for dependency in graph.get(node, [])):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return visit(task_id)


def enqueue_work(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    task = load_task(args.task_json)
    task_id = args.task_id.strip()
    if not task_id:
        raise ValueError("task id must be non-empty")
    if any(item.get("id") == task_id for item in registry.get("threads", [])):
        raise ValueError(f"task id already registered: {task_id}")
    dependencies = list(dict.fromkeys([*task.get("dependencies", []), *(args.depends_on or [])]))
    if task_id in dependencies:
        raise ValueError("task cannot depend on itself")
    known_ids = {str(item.get("id")) for item in registry.get("threads", []) if isinstance(item, dict)}
    missing = sorted(set(dependencies) - known_ids)
    if missing:
        raise ValueError("dependencies are not registered: " + ", ".join(missing))
    if dependency_cycle(registry, task_id, dependencies):
        raise ValueError("dependency cycle detected")

    score, reasons = thread_score(task)
    lane = "project" if score >= int(policy.get("creation_threshold", 7)) else "fast"
    parent_id = args.parent_thread_id or task.get("parent_thread_id")
    depth = 1
    if parent_id:
        parent = find_thread(registry, str(parent_id))
        if parent.get("lane", "project") != "project" or parent.get("status") not in ACTIVE_STATES:
            raise ValueError("parent must be an active project-lane task")
        depth = int(parent.get("depth", 1)) + 1
        if depth > int(policy.get("dispatch_policy", {}).get("max_nesting_depth", 2)):
            raise ValueError("maximum nesting depth exceeded")
        if lane != "fast":
            raise ValueError("a project-lane task may only dispatch fast-lane one-shot agents")

    tier, model = model_for_task(policy, task)
    light = lane == "fast" and is_light_task(task)
    risk = str(task.get("risk", "medium")).lower()
    timeout_defaults = policy.get("timeout_policy", {})
    timeout = task.get("timeout_seconds") or int(
        timeout_defaults.get("fast_lane_seconds" if lane == "fast" else "project_lane_seconds", 1800)
    )
    record = {
        "id": task_id,
        "instance_id": None,
        "domain_key": task["domain_key"],
        "title": task["title"],
        "lane": lane,
        "depth": depth,
        "parent_thread_id": parent_id,
        "dependencies": dependencies,
        "model_tier": tier,
        "model": model,
        "status": "queued",
        "owned_paths": sorted(set(task.get("owned_paths", []))),
        "current_stage": "queued",
        "summary": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "started_at": None,
        "last_heartbeat": None,
        "timeout_seconds": timeout,
        "token_budget": int(policy.get("token_policy", {}).get("default_thread_budget", 120000)),
        "token_used": 0,
        "attempts": 0,
        "failure_history": [],
        "needs_user_input": False,
        "evidence_paths": [],
        "handoff_path": None,
        "generation": 0,
        "replaces_instance_id": None,
        "dispatch_packet": "minimal" if light else "full",
        "review_policy": (
            "always-fresh-reviewer"
            if risk in {"high", "critical"}
            else "on-failure"
            if light
            else "acceptance-based"
        ),
        "score": score,
        "score_reasons": reasons,
        "idempotency_key": args.idempotency_key,
    }
    print(json.dumps({"action": "enqueue", "record": record}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=work_enqueue_plan_ready")
        return 0
    registry.setdefault("threads", []).append(record)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "work_enqueued", {"task_id": task_id, "lane": lane, "dependencies": dependencies})
    print("STATE=work_enqueued")
    return 0


def dispatch_work(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    record = find_thread(registry, args.task_id)
    if record.get("status") != "queued":
        raise ValueError("dispatch requires a queued task")
    validate_active_admission(policy, registry, record)
    instance_id = args.instance_id.strip()
    if not instance_id:
        raise ValueError("instance id must be non-empty")
    if any(item.get("instance_id") == instance_id for item in registry.get("threads", [])):
        raise ValueError("instance id already registered")
    changes = {
        "instance_id": instance_id,
        "status": "active",
        "current_stage": "dispatched",
        "started_at": now_iso(),
        "updated_at": now_iso(),
        "last_heartbeat": now_iso(),
        "generation": 1,
    }
    print(json.dumps({"action": "dispatch", "task_id": args.task_id, "changes": changes}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=work_dispatch_plan_ready")
        return 0
    record.update(changes)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "work_dispatched", {"task_id": args.task_id, "instance_id": instance_id})
    print("STATE=work_dispatched")
    return 0


def fail_work(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    record = find_thread(registry, args.task_id)
    if record.get("status") not in ACTIVE_STATES:
        raise ValueError("failure reporting requires an active task")
    fingerprint = args.fingerprint.strip()
    if not fingerprint:
        raise ValueError("failure fingerprint must be non-empty")
    handoff = validate_reference_path(args.handoff, "handoff") if args.handoff else record.get("handoff_path")
    history = list(record.get("failure_history", []))
    history.append({"at": now_iso(), "fingerprint": fingerprint, "instance_id": record.get("instance_id")})
    same_cause = 0
    for item in reversed(history):
        if not isinstance(item, dict) or item.get("fingerprint") != fingerprint:
            break
        same_cause += 1
    escalation = next_model_tier(policy, str(record.get("model"))) if same_cause >= 2 else None
    if same_cause >= 2 and escalation is None:
        desired = "blocked"
        required_tier = None
        required_model = None
    elif same_cause >= 2:
        desired = "escalation_required"
        required_tier, required_model = escalation
    else:
        desired = "degraded"
        required_tier = None
        required_model = None
    changes = {
        "status": desired,
        "current_stage": "failure-recorded",
        "updated_at": now_iso(),
        "last_heartbeat": now_iso(),
        "attempts": int(record.get("attempts", 0)) + 1,
        "failure_history": history,
        "handoff_path": handoff,
        "required_model_tier": required_tier,
        "required_model": required_model,
    }
    print(json.dumps({"action": "fail", "task_id": args.task_id, "same_cause": same_cause, "changes": changes}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=work_failure_plan_ready")
        return 0
    record.update(changes)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "work_failed", {"task_id": args.task_id, "fingerprint": fingerprint, "same_cause": same_cause})
    print("STATE=work_escalation_required" if desired == "escalation_required" else "STATE=work_failure_recorded")
    return 0


def replace_instance(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    record = find_thread(registry, args.task_id)
    if record.get("status") != "escalation_required":
        raise ValueError("replacement requires escalation_required status")
    handoff = validate_evidence_path(root, args.handoff)
    required_model = record.get("required_model")
    if args.new_model != required_model:
        raise ValueError(f"replacement model must be the required higher tier: {required_model}")
    new_instance = args.new_instance_id.strip()
    if not new_instance or new_instance == record.get("instance_id"):
        raise ValueError("replacement must use a new instance id")
    if any(item.get("instance_id") == new_instance for item in registry.get("threads", [])):
        raise ValueError("replacement instance id already registered")
    active = [item for item in active_threads(registry) if item.get("id") != args.task_id]
    if len(active) >= int(policy.get("max_concurrency_total", 6)):
        raise ValueError("total concurrency capacity reached")
    conflicts = ownership_conflicts(record, active)
    if conflicts:
        raise ValueError(f"cannot replace while ownership conflicts: {conflicts}")
    if record.get("owned_paths") and sum(bool(item.get("owned_paths")) for item in active) >= int(
        policy.get("max_concurrent_writers", 2)
    ):
        raise ValueError("concurrent writer capacity reached")
    previous_instance = record.get("instance_id")
    replacement_history = list(record.get("failure_history", []))
    replacement_history.append(
        {"at": now_iso(), "event": "instance_replaced", "from": previous_instance, "to": new_instance}
    )
    changes = {
        "instance_id": new_instance,
        "replaces_instance_id": previous_instance,
        "generation": int(record.get("generation", 1)) + 1,
        "model": args.new_model,
        "model_tier": model_tier_for(policy, args.new_model),
        "status": "active",
        "current_stage": "resumed-from-handoff",
        "handoff_path": handoff,
        "updated_at": now_iso(),
        "started_at": now_iso(),
        "last_heartbeat": now_iso(),
        "failure_history": replacement_history,
        "required_model_tier": None,
        "required_model": None,
    }
    print(json.dumps({"action": "replace", "task_id": args.task_id, "changes": changes}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=instance_replacement_plan_ready")
        return 0
    record.update(changes)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "instance_replaced", {"task_id": args.task_id, "from": previous_instance, "to": new_instance})
    print("STATE=instance_replaced")
    return 0


def register_thread(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    if policy.get("thread_creation_mode") != "controlled-auto":
        raise ValueError("register requires thread_creation_mode=controlled-auto")
    active = active_threads(registry)
    duplicate = next(
        (item for item in registry.get("threads", []) if item.get("idempotency_key") == args.idempotency_key),
        None,
    ) if args.idempotency_key else None
    if duplicate:
        if duplicate.get("id") != args.thread_id or duplicate.get("domain_key") != args.domain_key:
            raise ValueError("idempotency key already belongs to a different thread request")
        print(json.dumps({"action": "register", "idempotent_replay": True, "record": duplicate}, ensure_ascii=False, indent=2))
        print("STATE=thread_already_registered")
        return 0
    if any(item.get("domain_key") == args.domain_key for item in active):
        raise ValueError(f"active domain already registered: {args.domain_key}")
    if any(item.get("id") == args.thread_id for item in registry.get("threads", [])):
        raise ValueError(f"thread id already registered: {args.thread_id}")
    requested = set(args.owned_path or [])
    validate_owned_paths(list(requested))
    conflicts = ownership_conflicts({"owned_paths": list(requested)}, active)
    if conflicts:
        raise ValueError(f"owned path conflict: {conflicts}")
    if len(active) >= int(policy.get("max_concurrency_total", 6)):
        raise ValueError("total concurrency capacity reached")
    if requested and sum(bool(item.get("owned_paths")) for item in active) >= int(policy.get("max_concurrent_writers", 2)):
        raise ValueError("concurrent long-thread writer limit reached")
    budget = args.token_budget or int(policy.get("token_policy", {}).get("default_thread_budget", 120000))
    if budget <= 0:
        raise ValueError("token budget must be positive")
    if not args.thread_id.strip() or not args.domain_key.strip() or not args.title.strip():
        raise ValueError("thread id, domain key and title must be non-empty")
    allowed_models = set(policy.get("model_tiers", {}).values())
    if args.model not in allowed_models:
        raise ValueError("model is not present in project-state model_tiers")
    record = {
        "id": args.thread_id,
        "instance_id": args.thread_id,
        "domain_key": args.domain_key,
        "title": args.title,
        "lane": "project",
        "depth": 1,
        "parent_thread_id": None,
        "dependencies": [],
        "model_tier": model_tier_for(policy, args.model),
        "model": args.model,
        "status": "active",
        "owned_paths": sorted(requested),
        "current_stage": "initialized",
        "summary": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "started_at": now_iso(),
        "last_heartbeat": now_iso(),
        "timeout_seconds": int(policy.get("timeout_policy", {}).get("project_lane_seconds", 86400)),
        "token_budget": budget,
        "token_used": 0,
        "attempts": 0,
        "failure_history": [],
        "needs_user_input": False,
        "evidence_paths": [],
        "handoff_path": None,
        "generation": 1,
        "replaces_instance_id": None,
        "dispatch_packet": "full",
        "review_policy": "acceptance-based",
        "idempotency_key": args.idempotency_key,
    }
    print(json.dumps({"action": "register", "record": record}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=thread_register_plan_ready")
        return 0
    registry.setdefault("threads", []).append(record)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "thread_registered", {"thread_id": args.thread_id, "domain_key": args.domain_key})
    print("STATE=thread_registered")
    return 0


def update_thread(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    require_expected_revision(registry, args.expected_revision)
    thread = find_thread(registry, args.thread_id)
    previous = str(thread.get("status"))
    desired = args.status or previous
    if desired != previous and desired not in TRANSITIONS.get(previous, set()):
        raise ValueError(f"invalid status transition: {previous} -> {desired}")
    changes: dict[str, Any] = {"status": desired, "updated_at": now_iso(), "last_heartbeat": now_iso()}
    if args.stage is not None:
        changes["current_stage"] = args.stage
    if args.summary is not None:
        if len(args.summary.splitlines()) > 10:
            raise ValueError("summary exceeds 10 lines")
        changes["summary"] = args.summary
    current_evidence = validate_evidence_paths(root, thread.get("evidence_paths", []))
    if args.evidence:
        additions = [validate_evidence_path(root, raw) for raw in args.evidence]
        changes["evidence_paths"] = sorted(set(current_evidence) | set(additions))
    if args.token_used is not None:
        if args.token_used < int(thread.get("token_used", 0)):
            raise ValueError("token_used cannot decrease")
        changes["token_used"] = args.token_used
    if args.attempts is not None:
        if args.attempts < 0:
            raise ValueError("attempts cannot be negative")
        changes["attempts"] = args.attempts
    if args.needs_user_input is not None:
        changes["needs_user_input"] = args.needs_user_input
    if desired == "completed" and not changes.get("evidence_paths", current_evidence):
        raise ValueError("completed thread requires at least one evidence path")
    if desired in ACTIVE_STATES and previous not in ACTIVE_STATES:
        if previous != "blocked":
            raise ValueError(f"cannot resume active execution from {previous}")
        instance_id = str(thread.get("instance_id") or "").strip()
        if not instance_id or int(thread.get("generation", 0) or 0) < 1 or not thread.get("started_at"):
            raise ValueError("cannot resume: task has never been dispatched to an instance")
        try:
            parse_time(str(thread.get("started_at")))
        except (TypeError, ValueError) as exc:
            raise ValueError("cannot resume: dispatched instance has an invalid start time") from exc
        if any(
            item.get("id") != args.thread_id and item.get("instance_id") == instance_id
            for item in registry.get("threads", [])
            if isinstance(item, dict)
        ):
            raise ValueError("cannot resume: instance id is already registered elsewhere")
        handoff = args.handoff or thread.get("handoff_path")
        if not handoff:
            raise ValueError("cannot resume: blocked task requires a handoff path")
        try:
            handoff = validate_evidence_path(root, str(handoff))
        except (OSError, ValueError) as exc:
            raise ValueError(f"cannot resume: invalid handoff artifact: {exc}") from exc
        if not thread.get("dispatch_packet") or not thread.get("review_policy"):
            raise ValueError("cannot resume: dispatch metadata is incomplete")
        validate_active_admission(policy, registry, thread, prefix="cannot resume: ")
        changes.update({
            "handoff_path": handoff,
            "current_stage": "resumed-from-handoff",
            "started_at": now_iso(),
            "resumed_from_blocked_at": now_iso(),
        })
    print(json.dumps({"action": "update", "thread_id": args.thread_id, "changes": changes}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=thread_update_plan_ready")
        return 0
    thread.update(changes)
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "thread_updated", {"thread_id": args.thread_id, "from": previous, "to": desired})
    print("STATE=thread_updated")
    return 0


def parse_time(raw: str) -> datetime:
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def health(root: Path, *, as_json: bool) -> int:
    """Read registry and every derived file under the writer's runtime lock."""
    with runtime_lock(root):
        return health_locked(root, as_json=as_json)


def health_locked(root: Path, *, as_json: bool) -> int:
    policy, registry = load_runtime(root)
    failures: list[str] = []
    warnings: list[str] = []
    active = active_threads(registry)
    if policy.get("control_plane_mode") != "control-plane-only":
        failures.append("control plane must be control-plane-only")
    max_active = int(policy.get("max_concurrency_total", 6))
    if len(active) > max_active:
        failures.append(f"active executions {len(active)} exceed total limit {max_active}")
    active_writers = sum(bool(item.get("owned_paths")) for item in active)
    max_writers = int(policy.get("max_concurrent_writers", 2))
    if active_writers > max_writers:
        failures.append(f"active writers {active_writers} exceed limit {max_writers}")

    domains: dict[str, list[str]] = {}
    ownership: dict[str, list[str]] = {}
    stale_after = timedelta(minutes=int(policy.get("stale_heartbeat_minutes", 30)))
    now = datetime.now(timezone.utc)
    token_policy = policy.get("token_policy", {})
    compact_ratio = float(token_policy.get("compact_at_ratio", 0.70))
    freeze_ratio = float(token_policy.get("scope_freeze_at_ratio", 0.85))
    stop_ratio = float(token_policy.get("stop_at_ratio", 1.0))

    locks = load_json(safe_state_path(root, OWNERSHIP_LOCKS))
    budget_state = load_json(safe_state_path(root, BUDGET_STATE))
    snapshot = load_json(safe_state_path(root, STATUS_SNAPSHOT))
    expected_locks, expected_budget = derived_runtime_state(registry)
    if locks.get("schema_version") != SCHEMA_VERSION or budget_state.get("schema_version") != SCHEMA_VERSION:
        failures.append("derived state schema mismatch")
    if locks.get("revision") != registry.get("revision") or locks.get("locks") != expected_locks["locks"]:
        failures.append("ownership locks drift from registry; run reconcile --apply")
    if (
        budget_state.get("revision") != registry.get("revision")
        or budget_state.get("threads") != expected_budget["threads"]
        or budget_state.get("project_token_used") != expected_budget["project_token_used"]
    ):
        failures.append("budget state drifts from registry; run reconcile --apply")
    if (
        snapshot.get("schema_version") != SCHEMA_VERSION
        or snapshot.get("threads") != registry.get("threads")
    ):
        failures.append("status snapshot drifts from registry; run reconcile --apply")

    for thread in active:
        thread_id = str(thread.get("id", "unknown"))
        if not thread.get("domain_key"):
            failures.append(f"missing domain key: {thread_id}")
        if thread.get("model") not in set(policy.get("model_tiers", {}).values()):
            failures.append(f"unapproved model: {thread_id}")
        if thread.get("lane", "project") == "project":
            domains.setdefault(str(thread.get("domain_key", "")), []).append(thread_id)
        for path in thread.get("owned_paths", []):
            ownership.setdefault(str(path), []).append(thread_id)
        try:
            if now - parse_time(str(thread.get("last_heartbeat", ""))) > stale_after:
                warnings.append(f"stale heartbeat: {thread_id}")
        except (TypeError, ValueError):
            failures.append(f"invalid heartbeat: {thread_id}")
        try:
            started = parse_time(str(thread.get("started_at", "")))
            timeout_seconds = int(thread.get("timeout_seconds", 0) or 0)
            if timeout_seconds <= 0:
                failures.append(f"invalid timeout: {thread_id}")
            elif now - started > timedelta(seconds=timeout_seconds):
                failures.append(f"execution timeout exceeded: {thread_id}")
        except (TypeError, ValueError):
            failures.append(f"invalid start time: {thread_id}")
        budget = int(thread.get("token_budget", 0) or 0)
        used = int(thread.get("token_used", 0) or 0)
        if budget <= 0:
            failures.append(f"invalid token budget: {thread_id}")
        else:
            ratio = used / budget
            if ratio >= stop_ratio:
                failures.append(f"token budget exhausted: {thread_id}")
            elif ratio >= freeze_ratio:
                warnings.append(f"scope freeze required: {thread_id}")
            elif ratio >= compact_ratio:
                warnings.append(f"context compaction required: {thread_id}")

    for domain, owners in domains.items():
        if domain and len(owners) > 1:
            failures.append(f"duplicate active domain {domain}: {owners}")
    for path, owners in ownership.items():
        if len(owners) > 1:
            failures.append(f"ownership conflict {path}: {owners}")
    for index, thread in enumerate(active):
        conflicts = ownership_conflicts(
            {"owned_paths": thread.get("owned_paths", [])}, active[index + 1 :]
        )
        for conflict in conflicts:
            failures.append(
                f"ownership overlap {thread.get('id')}:{conflict['path']} with "
                f"{conflict['thread_id']}:{conflict['conflicts_with']}"
            )
    for thread in registry.get("threads", []):
        if not isinstance(thread, dict):
            continue
        thread_id = str(thread.get("id", "unknown"))
        try:
            evidence = thread.get("evidence_paths", [])
            if validate_evidence_paths(root, evidence) != evidence:
                raise ValueError("evidence_paths must be canonical and unique")
        except (OSError, ValueError) as exc:
            failures.append(f"invalid evidence path for {thread_id}: {exc}")
        if thread.get("status") == "completed" and not thread.get("evidence_paths"):
            failures.append(f"completed thread lacks evidence: {thread_id}")
    all_records = [item for item in registry.get("threads", []) if isinstance(item, dict)]
    known_ids = {str(item.get("id")) for item in all_records}
    instance_ids = [str(item.get("instance_id")) for item in all_records if item.get("instance_id")]
    if len(instance_ids) != len(set(instance_ids)):
        failures.append("instance ids are not unique")
    for record in all_records:
        record_id = str(record.get("id", "unknown"))
        dependencies = record.get("dependencies", [])
        if not isinstance(dependencies, list) or any(str(item) not in known_ids for item in dependencies):
            failures.append(f"invalid dependencies: {record_id}")
        depth = int(record.get("depth", 1) or 1)
        if depth not in {1, 2}:
            failures.append(f"invalid nesting depth: {record_id}")
        if depth == 2:
            parent_id = record.get("parent_thread_id")
            try:
                parent = find_thread(registry, str(parent_id))
                if parent.get("lane", "project") != "project" or int(parent.get("depth", 1)) != 1:
                    failures.append(f"invalid project parent: {record_id}")
            except ValueError:
                failures.append(f"missing project parent: {record_id}")
        if record.get("status") == "escalation_required":
            warnings.append(f"model escalation required: {record_id}")
        if record.get("status") in ACTIVE_STATES:
            if not record.get("instance_id") or int(record.get("generation", 0) or 0) < 1:
                failures.append(f"active execution lacks dispatch instance: {record_id}")
            try:
                incomplete = incomplete_dependencies(registry, record)
                if incomplete:
                    failures.append(f"active execution has incomplete dependencies {record_id}: {incomplete}")
            except ValueError as exc:
                failures.append(f"active execution has invalid dependencies {record_id}: {exc}")

    result = {
        "schema_version": SCHEMA_VERSION,
        "active_threads": len(active),
        "queued_tasks": sum(item.get("status") == "queued" for item in all_records),
        "failures": failures,
        "warnings": warnings,
        "state": "failed" if failures else "degraded" if warnings else "passed",
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in failures:
            print(f"FAIL {item}")
        for item in warnings:
            print(f"WARN {item}")
        if not failures and not warnings:
            print("OK runtime registry, ownership, heartbeat and token budgets")
    if failures:
        print("STATE=runtime_health_failed")
        return 1
    if warnings:
        print("STATE=runtime_health_degraded")
        return 2
    print("STATE=runtime_health_passed")
    return 0


def compact(root: Path, args: argparse.Namespace) -> int:
    policy, registry = load_runtime(root)
    days = args.days or int(policy.get("retention_policy", {}).get("full_days", 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    candidates: list[str] = []
    for thread in registry.get("threads", []):
        if not isinstance(thread, dict) or thread.get("status") not in TERMINAL_STATES:
            continue
        try:
            if parse_time(str(thread.get("updated_at", ""))) < cutoff:
                candidates.append(str(thread.get("id")))
        except (TypeError, ValueError):
            continue
    print(json.dumps({"action": "compact", "days": days, "candidates": candidates}, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=compact_plan_ready")
        return 0
    for thread in registry.get("threads", []):
        if isinstance(thread, dict) and thread.get("id") in candidates:
            thread["terminal_outcome"] = thread.get("terminal_outcome") or thread.get("status")
            thread["status"] = "archived"
            thread["owned_paths"] = []
            thread["current_stage"] = "archived"
            thread["updated_at"] = now_iso()
    write_registry(root, registry)
    sync_derived_state(root, registry)
    append_journal(root, "registry_compacted", {"thread_ids": candidates, "retention_days": days})
    print("STATE=registry_compacted")
    return 0


def reconcile(root: Path, *, apply: bool) -> int:
    _, registry = load_runtime(root)
    locks, budget = derived_runtime_state(registry)
    print(json.dumps({"action": "reconcile", "revision": registry.get("revision"), "locks": len(locks["locks"]), "threads": len(budget["threads"])}, ensure_ascii=False, indent=2))
    if not apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=reconcile_plan_ready")
        return 0
    sync_derived_state(root, registry)
    append_journal(root, "derived_state_reconciled", {"registry_revision": registry.get("revision")})
    print("STATE=runtime_state_reconciled")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="control-plane-only 双通道任务规划、队列、调度与健康检查")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--project", required=True)
    plan_parser.add_argument("--task-json", required=True)

    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--project", required=True)
    enqueue.add_argument("--task-json", required=True)
    enqueue.add_argument("--task-id", required=True)
    enqueue.add_argument("--depends-on", action="append", default=[])
    enqueue.add_argument("--parent-thread-id")
    enqueue.add_argument("--idempotency-key")
    enqueue.add_argument("--expected-revision", type=int)
    enqueue.add_argument("--apply", action="store_true")

    dispatch = sub.add_parser("dispatch")
    dispatch.add_argument("--project", required=True)
    dispatch.add_argument("--task-id", required=True)
    dispatch.add_argument("--instance-id", required=True)
    dispatch.add_argument("--expected-revision", type=int)
    dispatch.add_argument("--apply", action="store_true")

    fail = sub.add_parser("fail")
    fail.add_argument("--project", required=True)
    fail.add_argument("--task-id", required=True)
    fail.add_argument("--fingerprint", required=True)
    fail.add_argument("--handoff")
    fail.add_argument("--expected-revision", type=int)
    fail.add_argument("--apply", action="store_true")

    replace = sub.add_parser("replace")
    replace.add_argument("--project", required=True)
    replace.add_argument("--task-id", required=True)
    replace.add_argument("--new-instance-id", required=True)
    replace.add_argument("--new-model", required=True)
    replace.add_argument("--handoff", required=True)
    replace.add_argument("--expected-revision", type=int)
    replace.add_argument("--apply", action="store_true")

    register = sub.add_parser("register")
    register.add_argument("--project", required=True)
    register.add_argument("--domain-key", required=True)
    register.add_argument("--thread-id", required=True)
    register.add_argument("--title", required=True)
    register.add_argument("--model", required=True)
    register.add_argument("--owned-path", action="append", default=[])
    register.add_argument("--token-budget", type=int)
    register.add_argument("--idempotency-key")
    register.add_argument("--expected-revision", type=int)
    register.add_argument("--apply", action="store_true")

    update = sub.add_parser("update")
    update.add_argument("--project", required=True)
    update.add_argument("--thread-id", required=True)
    update.add_argument("--status", choices=sorted(TRANSITIONS))
    update.add_argument("--stage")
    update.add_argument("--summary")
    update.add_argument("--evidence", action="append", default=[])
    update.add_argument("--handoff")
    update.add_argument("--token-used", type=int)
    update.add_argument("--attempts", type=int)
    update.add_argument("--expected-revision", type=int)
    input_group = update.add_mutually_exclusive_group()
    input_group.add_argument("--needs-user-input", dest="needs_user_input", action="store_true")
    input_group.add_argument("--no-needs-user-input", dest="needs_user_input", action="store_false")
    update.set_defaults(needs_user_input=None)
    update.add_argument("--apply", action="store_true")

    health_parser = sub.add_parser("health")
    health_parser.add_argument("--project", required=True)
    health_parser.add_argument("--json", action="store_true")

    compact_parser = sub.add_parser("compact")
    compact_parser.add_argument("--project", required=True)
    compact_parser.add_argument("--days", type=int)
    compact_parser.add_argument("--apply", action="store_true")
    reconcile_parser = sub.add_parser("reconcile")
    reconcile_parser.add_argument("--project", required=True)
    reconcile_parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        root = safe_project_root(args.project)
        if args.command == "plan":
            result = plan(root, load_task(args.task_json))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("STATE=thread_plan_ready")
            return 0
        if args.command == "enqueue":
            if args.apply:
                with runtime_lock(root):
                    return enqueue_work(root, args)
            return enqueue_work(root, args)
        if args.command == "dispatch":
            if args.apply:
                with runtime_lock(root):
                    return dispatch_work(root, args)
            return dispatch_work(root, args)
        if args.command == "fail":
            if args.apply:
                with runtime_lock(root):
                    return fail_work(root, args)
            return fail_work(root, args)
        if args.command == "replace":
            if args.apply:
                with runtime_lock(root):
                    return replace_instance(root, args)
            return replace_instance(root, args)
        if args.command == "register":
            if args.apply:
                with runtime_lock(root):
                    return register_thread(root, args)
            return register_thread(root, args)
        if args.command == "update":
            if args.apply:
                with runtime_lock(root):
                    return update_thread(root, args)
            return update_thread(root, args)
        if args.command == "health":
            return health(root, as_json=args.json)
        if args.command == "compact":
            if args.apply:
                with runtime_lock(root):
                    return compact(root, args)
            return compact(root, args)
        if args.command == "reconcile":
            if args.apply:
                with runtime_lock(root):
                    return reconcile(root, apply=True)
            return reconcile(root, apply=False)
        raise ValueError(f"unsupported command: {args.command}")
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=thread_orchestration_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
