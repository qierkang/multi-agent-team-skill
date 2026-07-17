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
    load_json,
    model_for_task,
    now_iso,
    runtime_lock,
    safe_project_root,
    safe_state_path,
    thread_score,
)


ACTIVE_STATES = {"provisioning", "active", "waiting_input", "reviewing", "degraded"}
TERMINAL_STATES = {"completed", "blocked", "cancelled", "archived"}
TRANSITIONS = {
    "provisioning": {"active", "blocked", "cancelled"},
    "active": {"active", "waiting_input", "reviewing", "degraded", "completed", "blocked", "cancelled"},
    "waiting_input": {"active", "blocked", "cancelled"},
    "reviewing": {"active", "completed", "blocked", "degraded"},
    "degraded": {"active", "waiting_input", "reviewing", "blocked", "cancelled"},
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


def plan(root: Path, task: dict[str, Any]) -> dict[str, Any]:
    policy, registry = load_runtime(root)
    active = active_threads(registry)
    score, reasons = thread_score(task)
    tier, model = model_for_task(policy, task)
    existing = next((item for item in active if item.get("domain_key") == task["domain_key"]), None)
    conflicts = ownership_conflicts(task, [item for item in active if item is not existing])
    create_threshold = int(policy.get("creation_threshold", 7))
    subagent_threshold = int(policy.get("subagent_threshold", 4))
    mode = policy.get("thread_creation_mode", "recommend")
    max_active = int(policy.get("max_active_long_threads", 5))
    max_writers = int(policy.get("max_concurrent_writers", 2))
    active_writers = sum(bool(item.get("owned_paths")) for item in active)

    if conflicts:
        decision = "blocked_ownership_conflict"
    elif existing:
        decision = "reuse_thread"
    elif score >= create_threshold and len(active) >= max_active:
        decision = "queue_or_reuse"
    elif score >= create_threshold and task.get("owned_paths") and active_writers >= max_writers:
        decision = "queue_writer_capacity"
    elif score >= create_threshold:
        decision = "create_thread" if mode == "controlled-auto" else "recommend_thread"
    elif score >= subagent_threshold:
        decision = "use_subagents"
    else:
        decision = "handle_in_main"

    return {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "thread_creation_mode": mode,
        "score": score,
        "reasons": reasons,
        "domain_key": task["domain_key"],
        "title": task["title"],
        "model_tier": tier,
        "model": model,
        "existing_thread_id": existing.get("id") if existing else None,
        "active_long_threads": len(active),
        "max_active_long_threads": max_active,
        "ownership_conflicts": conflicts,
        "next": {
            "create_thread": "main task calls the client create_thread tool, then register --apply",
            "recommend_thread": "ask for explicit authorization or re-run upgrade with controlled-auto",
            "reuse_thread": "send the task package to existing_thread_id",
            "use_subagents": "keep work in the current task and delegate bounded subagents",
            "handle_in_main": "execute locally without a long-running thread",
            "queue_or_reuse": "close/archive an inactive thread or reuse a compatible domain",
            "queue_writer_capacity": "wait for a writer slot or narrow ownership to a non-writing task",
            "blocked_ownership_conflict": "resolve owned path conflict before dispatch",
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
    if len(active) >= int(policy.get("max_active_long_threads", 5)):
        raise ValueError("active long-thread limit reached")
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
        "domain_key": args.domain_key,
        "title": args.title,
        "model": args.model,
        "status": "active",
        "owned_paths": sorted(requested),
        "current_stage": "initialized",
        "summary": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_heartbeat": now_iso(),
        "token_budget": budget,
        "token_used": 0,
        "attempts": 0,
        "needs_user_input": False,
        "evidence_paths": [],
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
    if args.evidence:
        changes["evidence_paths"] = sorted(set(thread.get("evidence_paths", [])) | set(args.evidence))
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
    if desired == "completed" and not changes.get("evidence_paths", thread.get("evidence_paths")):
        raise ValueError("completed thread requires at least one evidence path")
    if desired in ACTIVE_STATES and previous not in ACTIVE_STATES:
        others = [item for item in active_threads(registry) if item.get("id") != args.thread_id]
        if any(item.get("domain_key") == thread.get("domain_key") for item in others):
            raise ValueError("cannot resume: active domain already exists")
        conflicts = ownership_conflicts({"owned_paths": thread.get("owned_paths", [])}, others)
        if conflicts:
            raise ValueError(f"cannot resume: owned path conflict: {conflicts}")
        if len(others) >= int(policy.get("max_active_long_threads", 5)):
            raise ValueError("cannot resume: active long-thread limit reached")
        if thread.get("owned_paths") and sum(bool(item.get("owned_paths")) for item in others) >= int(policy.get("max_concurrent_writers", 2)):
            raise ValueError("cannot resume: concurrent writer limit reached")
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
    policy, registry = load_runtime(root)
    failures: list[str] = []
    warnings: list[str] = []
    active = active_threads(registry)
    max_active = int(policy.get("max_active_long_threads", 5))
    if len(active) > max_active:
        failures.append(f"active threads {len(active)} exceed limit {max_active}")
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
        domains.setdefault(str(thread.get("domain_key", "")), []).append(thread_id)
        for path in thread.get("owned_paths", []):
            ownership.setdefault(str(path), []).append(thread_id)
        try:
            if now - parse_time(str(thread.get("last_heartbeat", ""))) > stale_after:
                warnings.append(f"stale heartbeat: {thread_id}")
        except (TypeError, ValueError):
            failures.append(f"invalid heartbeat: {thread_id}")
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
        if isinstance(thread, dict) and thread.get("status") == "completed" and not thread.get("evidence_paths"):
            failures.append(f"completed thread lacks evidence: {thread.get('id')}")

    result = {
        "schema_version": SCHEMA_VERSION,
        "active_threads": len(active),
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
    parser = argparse.ArgumentParser(description="受控长期线程规划、注册、更新和健康检查")
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--project", required=True)
    plan_parser.add_argument("--task-json", required=True)

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
