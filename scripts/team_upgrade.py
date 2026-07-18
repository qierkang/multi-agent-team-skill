#!/usr/bin/env python3
"""Transactionally upgrade a managed multi-agent-team v1 installation to v2."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

from runtime_state import (
    MANAGED_STATE_FILES,
    BUDGET_STATE,
    DEFAULT_MODEL_TIERS,
    OWNERSHIP_LOCKS,
    PROJECT_STATE,
    RECOVERY_JOURNAL,
    SCHEMA_VERSION,
    SKILL_VERSION,
    THREAD_REGISTRY,
    active_threads,
    now_iso,
    normalize_model_tiers,
    project_policy,
    runtime_lock,
    safe_project_root,
    state_defaults,
    validate_evidence_paths,
)
from team_init import (
    AGENTS_END,
    AGENTS_START,
    DOC_TEMPLATES,
    InstallError,
    TEMPLATES,
    LEGACY_AGENTS_START,
    apply_model_tiers,
    backup_existing,
    ensure_safe_target,
    git_ignored,
    transactional_write,
)
from thread_orchestrator import derived_runtime_state, ownership_conflicts
from project_title import rename_action, suggested_title


SUPPORTED_FROM = {"1.0"}
LEGACY_AGENTS_END = "<!-- team-init:end -->"


def replace_managed_agents_block(text: str) -> str:
    candidates = ((AGENTS_START, AGENTS_END), (LEGACY_AGENTS_START, LEGACY_AGENTS_END))
    present = [(start_marker, end_marker) for start_marker, end_marker in candidates if start_marker in text or end_marker in text]
    if not present:
        raise InstallError("AGENTS.md 缺少完整 multi-agent-team 标记，需要人工审计")
    if len(present) != 1:
        raise InstallError("AGENTS.md 同时含新旧团队标记，拒绝猜测替换")
    start_marker, end_marker = present[0]
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        raise InstallError("AGENTS.md 团队标记不唯一，需要人工审计")
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < start:
        raise InstallError("AGENTS.md 团队标记不完整，需要人工审计")
    end += len(end_marker)
    canonical = (TEMPLATES / "project" / "AGENTS.block.md").read_text(encoding="utf-8").strip()
    return text[:start] + canonical + text[end:]


def migrate_snapshot(path: Path) -> tuple[str, list[dict[str, Any]]]:
    if not path.is_file():
        return (TEMPLATES / "project" / "docs" / "状态快照.template.json").read_text(encoding="utf-8"), []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"状态快照无法迁移: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") not in {None, "1.0", "2.0"}:
        raise InstallError("状态快照 schema 未知，拒绝自动迁移")
    threads = payload.pop("tasks", payload.get("threads", []))
    if not isinstance(threads, list):
        raise InstallError("状态快照 tasks/threads 必须为数组")
    for index, item in enumerate(threads, 1):
        if not isinstance(item, dict):
            raise InstallError(f"v1 快照第 {index} 项不是对象")
        if not str(item.get("id") or "").strip():
            item["id"] = f"legacy-{index}"
    payload["schema_version"] = SCHEMA_VERSION
    payload["threads"] = threads
    payload.setdefault("updated_at", "")
    payload.setdefault("max_threads", 6)
    payload.setdefault("max_concurrent_writers", 2)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n", threads


def migrate_threads(root: Path, items: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    status_map = {
        "pending": "provisioning", "queued": "provisioning", "todo": "provisioning",
        "in_progress": "active", "running": "active", "active": "active",
        "needs_input": "waiting_input", "waiting_user": "waiting_input",
        "reviewing": "reviewing", "degraded": "degraded", "unknown": "degraded",
        "completed": "completed", "done": "completed", "complete": "completed",
        "blocked": "blocked", "failed": "blocked", "cancelled": "cancelled", "archived": "archived",
    }
    now = now_iso()
    default_model = policy["model_tiers"]["standard"]
    legacy_model_map = {
        model: policy["model_tiers"][tier]
        for tier, model in DEFAULT_MODEL_TIERS.items()
    }
    default_budget = int(policy["token_policy"]["default_thread_budget"])
    migrated: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise InstallError(f"v1 快照第 {index} 项不是对象")
        thread_id = str(item.get("id") or f"legacy-{index}").strip()
        if not thread_id or thread_id in seen_ids:
            raise InstallError(f"v1 快照存在空或重复任务 ID: {thread_id!r}")
        seen_ids.add(thread_id)
        owned_paths = item.get("owned_paths") or []
        if not isinstance(owned_paths, list) or not all(isinstance(path, str) and path for path in owned_paths):
            raise InstallError(f"v1 任务 {thread_id} owned_paths 非法")
        for raw in owned_paths:
            path = PurePosixPath(raw.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
                raise InstallError(f"v1 任务 {thread_id} 包含不安全所有权路径: {raw}")
        evidence_values: list[Any] = []
        for field in ("evidence_paths", "evidence"):
            values = item.get(field, [])
            if values is None:
                values = []
            if not isinstance(values, list):
                raise InstallError(f"v1 任务 {thread_id} {field} 非法")
            evidence_values.extend(values)
        try:
            evidence = validate_evidence_paths(root, evidence_values)
        except (OSError, ValueError) as exc:
            raise InstallError(f"v1 任务 {thread_id} evidence_paths 非法: {exc}") from exc
        status = status_map.get(str(item.get("status", "unknown")).lower(), "degraded")
        if status == "completed" and not evidence:
            status = "reviewing"
        summary = "\n".join(str(item.get("summary", "")).splitlines()[:10])
        model = legacy_model_map.get(
            str(item.get("model") or default_model),
            str(item.get("model") or default_model),
        )
        matching_tiers = [
            tier for tier, candidate in policy["model_tiers"].items() if candidate == model
        ]
        model_tier = matching_tiers[-1] if matching_tiers else "standard"
        migrated.append({
            "id": thread_id,
            "instance_id": thread_id,
            "domain_key": str(item.get("domain_key") or f"legacy::{thread_id}"),
            "title": str(item.get("title") or "未命名迁移任务"),
            "lane": "project",
            "depth": 1,
            "parent_thread_id": None,
            "dependencies": [],
            "model_tier": model_tier,
            "model": model,
            "status": status,
            "owned_paths": sorted(set(owned_paths)),
            "current_stage": str(item.get("current_stage") or "migrated-from-v1"),
            "summary": summary,
            "created_at": str(item.get("created_at") or now),
            "updated_at": str(item.get("updated_at") or now),
            "started_at": str(item.get("started_at") or item.get("created_at") or now),
            "last_heartbeat": str(item.get("last_heartbeat") or now),
            "timeout_seconds": int(item.get("timeout_seconds") or policy["timeout_policy"]["project_lane_seconds"]),
            "token_budget": int(item.get("token_budget") or default_budget),
            "token_used": int(item.get("token_used") or 0),
            "attempts": int(item.get("attempts") or 0),
            "failure_history": list(item.get("failure_history") or []),
            "needs_user_input": bool(item.get("needs_user_input")),
            "evidence_paths": sorted(set(evidence)),
            "handoff_path": item.get("handoff_path"),
            "generation": int(item.get("generation") or 1),
            "replaces_instance_id": item.get("replaces_instance_id"),
            "dispatch_packet": str(item.get("dispatch_packet") or "full"),
            "review_policy": str(item.get("review_policy") or "acceptance-based"),
            "idempotency_key": item.get("idempotency_key"),
        })
    return migrated


def replacement_required_records(threads: list[dict[str, Any]]) -> list[dict[str, str]]:
    """List resumable/non-terminal instances that must not be remapped in place."""
    immutable_terminal = {"completed", "cancelled", "archived"}
    active_or_replacement_states = {
        "provisioning", "active", "waiting_input", "reviewing", "degraded", "escalation_required"
    }
    return [
        {
            "id": str(item.get("id", "unknown")),
            "instance_id": str(item.get("instance_id", "unknown")),
            "status": str(item.get("status", "unknown")),
            "model": str(item.get("model", "unknown")),
        }
        for item in threads
        if isinstance(item, dict)
        and str(item.get("status")) not in immutable_terminal
        and (item.get("instance_id") or str(item.get("status")) in active_or_replacement_states)
    ]


def report_replacement_required(records: list[dict[str, str]]) -> int:
    print("REPLACEMENT_REQUIRED=" + json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    print("PRESERVE=active instance ids,models,generations and handoff state")
    print("NEXT=finish the instances or replace them through thread_orchestrator.py fail/replace")
    print("STATE=replacement_required")
    return 2


def validate_v1_managed_assets(root: Path, manifest: dict[str, Any]) -> None:
    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles or not all(isinstance(role, str) for role in roles):
        raise InstallError("v1 manifest 角色列表无效")
    if len(roles) != len(set(roles)):
        raise InstallError("v1 manifest 存在重复角色")
    catalog = json.loads((TEMPLATES / "role-catalog.json").read_text(encoding="utf-8"))
    if not set(roles) <= set(catalog["roles"]):
        raise InstallError("v1 manifest 包含未知角色，请先审计")
    config_path = root / ".codex/config.toml"
    if not config_path.is_file():
        raise InstallError("v1 团队缺少 .codex/config.toml")
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InstallError(f"v1 团队配置无法解析: {exc}") from exc
    agents = config.get("agents", {})
    configured = {key for key, value in agents.items() if isinstance(value, dict)} if isinstance(agents, dict) else set()
    if configured != set(roles) or config.get("features", {}).get("multi_agent") is not True:
        raise InstallError("v1 config 与 manifest 角色或 multi_agent 状态不一致")
    if agents.get("max_depth") != 1 or not isinstance(agents.get("max_threads"), int) or agents["max_threads"] > 6:
        raise InstallError("v1 config 并发/派生边界不符合安全升级条件")
    for role in roles:
        installed = root / f".codex/agents/{role}.toml"
        canonical = TEMPLATES / f"agents/{role}.toml"
        if not installed.is_file() or installed.read_bytes() != canonical.read_bytes():
            raise InstallError(f"v1 角色 {role} 缺失或已自定义，为避免覆盖请先审计")


def validate_migrated_threads(threads: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    active = active_threads({"threads": threads})
    if len(active) > int(policy["max_concurrency_total"]):
        raise InstallError("v1 活跃任务数超过 v2 上限，请先只读审计")
    domains = [item["domain_key"] for item in active]
    if len(domains) != len(set(domains)):
        raise InstallError("v1 快照存在重复活跃 domain_key，请先只读审计")
    if sum(bool(item["owned_paths"]) for item in active) > int(policy["max_concurrent_writers"]):
        raise InstallError("v1 快照的活跃写任务超过 v2 上限")
    for index, item in enumerate(active):
        if ownership_conflicts({"owned_paths": item["owned_paths"]}, active[index + 1 :]):
            raise InstallError("v1 快照存在活跃所有权重叠，请先只读审计")
    allowed_models = set(policy["model_tiers"].values())
    if any(item["model"] not in allowed_models for item in active):
        raise InstallError("v1 活跃任务使用未在 v2 model_tiers 登记的模型")
    if any(item["token_budget"] <= 0 or item["token_used"] < 0 for item in threads):
        raise InstallError("v1 快照包含非法 Token 计数")


def remap_registered_models(
    threads: list[dict[str, Any]],
    old_tiers: dict[str, str],
    new_tiers: dict[str, str],
) -> list[dict[str, Any]]:
    """Remap persisted thread models without guessing ambiguous old tier mappings."""
    reverse: dict[str, list[str]] = {}
    for tier, model in old_tiers.items():
        reverse.setdefault(model, []).append(tier)
    remapped = json.loads(json.dumps(threads))
    for item in remapped:
        model = item.get("model")
        tiers = reverse.get(model, [])
        if len(tiers) == 1:
            item["model"] = new_tiers[tiers[0]]
            continue
        if len(tiers) > 1:
            candidates = {new_tiers[tier] for tier in tiers}
            if len(candidates) == 1:
                item["model"] = candidates.pop()
                continue
            raise InstallError(
                f"任务 {item.get('id', 'unknown')} 的旧模型 {model!r} 同时属于多个档位，"
                "无法安全推断新档位"
            )
        if model not in set(new_tiers.values()):
            raise InstallError(
                f"任务 {item.get('id', 'unknown')} 使用未登记模型 {model!r}，拒绝猜测迁移"
            )
    return remapped


def upgrade_v2_records(threads: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """Deterministically add v2.0.3 queue, interaction and replacement fields to schema-2 records."""
    upgraded = json.loads(json.dumps(threads))
    now = now_iso()
    model_tiers = policy["model_tiers"]
    for item in upgraded:
        thread_id = str(item.get("id") or "").strip()
        if not thread_id:
            raise InstallError("schema 2 注册表包含空任务 ID")
        model = str(item.get("model") or model_tiers["standard"])
        matches = [name for name, candidate in model_tiers.items() if candidate == model]
        if not matches:
            raise InstallError(f"任务 {thread_id} 使用未登记模型 {model!r}")
        tier = matches[-1]
        status = str(item.get("status") or "degraded")
        item.setdefault("instance_id", thread_id if status != "queued" else None)
        item.setdefault("lane", "project")
        item.setdefault("depth", 1)
        item.setdefault("parent_thread_id", None)
        item.setdefault("dependencies", [])
        item["model_tier"] = tier
        item.setdefault("started_at", item.get("created_at") or now)
        item.setdefault(
            "timeout_seconds",
            int(policy["timeout_policy"]["fast_lane_seconds" if item["lane"] == "fast" else "project_lane_seconds"]),
        )
        item.setdefault("failure_history", [])
        item.setdefault("handoff_path", None)
        item.setdefault("generation", 1 if item.get("instance_id") else 0)
        item.setdefault("replaces_instance_id", None)
        item.setdefault("dispatch_packet", "full")
        item.setdefault("review_policy", "acceptance-based")
        item.setdefault("required_model_tier", None)
        item.setdefault("required_model", None)
    return upgraded


def reconfigure_v2_models(
    root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    model_overrides: dict[str, str],
    *,
    thread_mode: str | None,
    apply: bool,
    allow_ignored: bool,
) -> int:
    title, source = suggested_title(root)
    state_path = root / PROJECT_STATE
    registry_path = root / THREAD_REGISTRY
    locks_path = root / OWNERSHIP_LOCKS
    budget_path = root / BUDGET_STATE
    journal_path = root / RECOVERY_JOURNAL
    snapshot_path = root / "docs/协作/状态快照.json"
    for target in (state_path, registry_path, locks_path, budget_path, journal_path, snapshot_path):
        ensure_safe_target(root, target)
        if not target.is_file():
            raise InstallError(f"v2 团队缺少受管文件: {target.relative_to(root)}")

    state = json.loads(state_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if state.get("schema_version") != SCHEMA_VERSION or registry.get("schema_version") != SCHEMA_VERSION:
        raise InstallError("v2 运行态 schema 不一致，请先审计")
    if snapshot.get("threads") != registry.get("threads"):
        raise InstallError("状态快照与线程注册表不一致，请先 reconcile")

    old_tiers = normalize_model_tiers(state.get("model_tiers"))
    current_thread_mode = str(state.get("thread_creation_mode", "recommend"))
    requested_thread_mode = thread_mode or current_thread_mode
    if requested_thread_mode not in {"recommend", "controlled-auto"}:
        raise InstallError(f"不支持的 thread mode: {requested_thread_mode}")
    mode_change = requested_thread_mode != current_thread_mode
    new_tiers = normalize_model_tiers({**old_tiers, **model_overrides})
    model_change = new_tiers != old_tiers
    version_sync = (
        manifest.get("skill_version") != SKILL_VERSION
        or state.get("skill_version") != SKILL_VERSION
        or state.get("control_plane_mode") != "control-plane-only"
        or state.get("interaction_policy") != project_policy(current_thread_mode, old_tiers)["interaction_policy"]
        or manifest.get("orchestration", {}).get("control_plane_is_goal") is not False
        or manifest.get("orchestration", {}).get("goal_policy") != "explicit-only"
        or manifest.get("orchestration", {}).get("interaction_policy") != "dispatch-return-immediately"
    )
    if not model_change and not mode_change and not version_sync:
        print(f"SCHEMA={SCHEMA_VERSION}; SKILL_VERSION={manifest.get('skill_version')}")
        print("STATE=already_current")
        print(f"TITLE_SUGGESTED={title}")
        print(f"TITLE_SOURCE={source}")
        print(f"RENAME_ACTION={rename_action(title)}")
        print("TITLE_RENAME=pending")
        return 0

    roles = manifest.get("roles")
    if not isinstance(roles, list) or not roles or not all(isinstance(role, str) for role in roles):
        raise InstallError("v2 manifest 角色列表无效")
    role_targets = [root / f".codex/agents/{role}.toml" for role in roles]
    role_writes: dict[Path, str] = {}
    for role, target in zip(roles, role_targets):
        ensure_safe_target(root, target)
        canonical = TEMPLATES / "agents" / f"{role}.toml"
        expected = apply_model_tiers(canonical.read_text(encoding="utf-8"), old_tiers)
        if not target.is_file() or target.read_text(encoding="utf-8") != expected:
            raise InstallError(f"v2 角色 {role} 已漂移，拒绝覆盖")
        role_writes[target] = apply_model_tiers(canonical.read_text(encoding="utf-8"), new_tiers)

    threads = registry.get("threads")
    if not isinstance(threads, list):
        raise InstallError("线程注册表 threads 必须为数组")
    for item in threads:
        if not isinstance(item, dict):
            raise InstallError("线程注册表包含非对象记录")
        try:
            evidence = item.get("evidence_paths", [])
            if validate_evidence_paths(root, evidence) != evidence:
                raise ValueError("evidence_paths 必须规范且唯一")
        except (OSError, ValueError) as exc:
            raise InstallError(f"任务 {item.get('id', 'unknown')} evidence_paths 非法: {exc}") from exc
    if model_change:
        replacement_required = replacement_required_records(threads)
        if replacement_required:
            return report_replacement_required(replacement_required)
    remapped_threads = remap_registered_models(threads, old_tiers, new_tiers)
    upgraded_threads = upgrade_v2_records(
        remapped_threads,
        project_policy(requested_thread_mode, new_tiers),
    )
    now = now_iso()
    updated_state = project_policy(requested_thread_mode, new_tiers)
    for key in ("creation_threshold", "stale_heartbeat_minutes"):
        if key in state:
            updated_state[key] = state[key]
    for key in ("token_policy", "retention_policy"):
        if isinstance(state.get(key), dict):
            updated_state[key] = {**updated_state[key], **state[key]}
    if isinstance(state.get("external_action_policy"), str):
        updated_state["external_action_policy"] = state["external_action_policy"]
    updated_state["updated_at"] = now
    updated_registry = dict(registry)
    updated_registry.update({
        "threads": upgraded_threads,
        "revision": int(registry.get("revision", 0)) + 1,
        "updated_at": now,
    })
    updated_snapshot = dict(snapshot)
    updated_snapshot.update({
        "threads": upgraded_threads,
        "updated_at": now,
        "max_threads": int(updated_state["max_concurrency_total"]),
        "max_concurrent_writers": int(updated_state["max_concurrent_writers"]),
    })
    updated_locks, updated_budget = derived_runtime_state(updated_registry)
    updated_journal = dict(journal)
    events = list(journal.get("events", []))
    event = (
        "model_tiers_reconfigured"
        if model_change
        else "thread_mode_reconfigured"
        if mode_change
        else "skill_patch_upgraded"
    )
    events.append({
        "at": now,
        "event": event,
        "details": {
            "model_tiers": {"from": old_tiers, "to": new_tiers},
            "thread_creation_mode": {"from": current_thread_mode, "to": requested_thread_mode},
        },
    })
    updated_journal.update({
        "events": events,
        "revision": int(journal.get("revision", 0)) + 1,
        "updated_at": now,
    })
    updated_manifest = dict(manifest)
    updated_manifest.update({"skill_version": SKILL_VERSION, "updated_at": now})
    updated_manifest.setdefault("runtime_smoke_test", "pending")
    updated_manifest.setdefault("runtime_smoke_evidence", {"explorer": [], "reviewer": []})
    updated_manifest["orchestration"] = {
        **dict(manifest.get("orchestration", {})),
        "thread_creation_mode": updated_state["thread_creation_mode"],
        "registry": ".codex/team/thread-registry.json",
        "control_plane": "control-plane-only",
        "control_plane_is_goal": False,
        "goal_policy": "explicit-only",
        "lanes": ["fast", "project"],
        "queue_capacity": "unbounded",
        "max_concurrency_total": updated_state["max_concurrency_total"],
        "max_concurrent_writers": updated_state["max_concurrent_writers"],
        "runtime_adapter": "codex-client-thread-tools",
        "interaction_policy": "dispatch-return-immediately",
    }
    if model_change:
        updated_manifest["model_tiers_updated_at"] = now
    if mode_change:
        updated_manifest["thread_mode_updated_at"] = now

    agents_path = root / "AGENTS.md"
    ensure_safe_target(root, agents_path)
    if not agents_path.is_file():
        raise InstallError("v2 团队缺少 AGENTS.md")
    updated_agents = replace_managed_agents_block(agents_path.read_text(encoding="utf-8"))
    doc_writes: dict[Path, str] = {}
    for relative, template_name in DOC_TEMPLATES.items():
        destination = root / relative
        ensure_safe_target(root, destination)
        if not destination.exists():
            doc_writes[destination] = (TEMPLATES / "project" / "docs" / template_name).read_text(encoding="utf-8")

    targets = [
        manifest_path,
        agents_path,
        state_path,
        registry_path,
        locks_path,
        budget_path,
        journal_path,
        snapshot_path,
        *role_targets,
        *doc_writes,
    ]
    ignored = [str(path.relative_to(root)) for path in targets if git_ignored(root, str(path.relative_to(root)))]
    print("===== multi-agent-team v2 patch/model upgrade =====")
    print(f"PROJECT={root}")
    print(f"TITLE_SUGGESTED={title}")
    print(f"TITLE_SOURCE={source}")
    print(f"RENAME_ACTION={rename_action(title)}")
    print("TITLE_RENAME=pending")
    for tier in ("fast", "standard", "advanced"):
        print(f"MODEL: {tier}={old_tiers[tier]}->{new_tiers[tier]}")
    print(f"THREAD_MODE={current_thread_mode}->{requested_thread_mode}")
    print(f"REMAPPED_THREADS={len(upgraded_threads)}")
    print("PRESERVE=.codex/config.toml,business files,thread ids/status/evidence")
    print("BACKUP_PLAN=.codex/backups/multi-agent-team/<timestamp>/")
    if ignored and not allow_ignored:
        print("IGNORED=" + ",".join(ignored))
        print("STATE=upgrade_plan_blocked")
        return 2
    if not apply:
        print("DRY_RUN=1, no files written.")
        print(
            "STATE=model_reconfiguration_plan_ready"
            if model_change
            else "STATE=thread_mode_reconfiguration_plan_ready"
            if mode_change
            else "STATE=patch_upgrade_plan_ready"
        )
        return 0

    writes = {
        **role_writes,
        **doc_writes,
        agents_path: updated_agents,
        manifest_path: json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n",
        state_path: json.dumps(updated_state, ensure_ascii=False, indent=2) + "\n",
        registry_path: json.dumps(updated_registry, ensure_ascii=False, indent=2) + "\n",
        locks_path: json.dumps(updated_locks, ensure_ascii=False, indent=2) + "\n",
        budget_path: json.dumps(updated_budget, ensure_ascii=False, indent=2) + "\n",
        journal_path: json.dumps(updated_journal, ensure_ascii=False, indent=2) + "\n",
        snapshot_path: json.dumps(updated_snapshot, ensure_ascii=False, indent=2) + "\n",
    }
    backup_root = backup_existing(root, targets)
    transactional_write(writes)
    if backup_root:
        print(f"BACKUP={backup_root}")
    print(
        "STATE=models_reconfigured"
        if model_change
        else "STATE=thread_mode_reconfigured"
        if mode_change
        else "STATE=team_patch_upgraded"
    )
    print("NEXT=运行 team_doctor.py 和 thread_orchestrator.py health")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="将已管理的 multi-agent-team v1 安全升级到 v2")
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--thread-mode",
        choices=["recommend", "controlled-auto"],
        help="显式更新项目级线程模式；v2 未提供时保留现值，v1 默认 controlled-auto",
    )
    parser.add_argument("--apply", action="store_true", help="执行写入；默认 dry-run")
    parser.add_argument("--allow-ignored", action="store_true")
    parser.add_argument("--model-fast", help="fast 档真实模型 ID")
    parser.add_argument("--model-standard", help="standard 档真实模型 ID")
    parser.add_argument("--model-advanced", help="advanced 档真实模型 ID")
    args = parser.parse_args()
    model_overrides = {
        tier: value
        for tier, value in (
            ("fast", args.model_fast),
            ("standard", args.model_standard),
            ("advanced", args.model_advanced),
        )
        if value
    }

    try:
        model_tiers = normalize_model_tiers(model_overrides)
        root = safe_project_root(args.project)
        manifest_path = root / ".codex" / "team-bootstrap.json"
        agents_path = root / "AGENTS.md"
        if not manifest_path.is_file():
            raise InstallError("缺少团队 manifest；请先运行 team_audit.py")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("skill") != "multi-agent-team":
            raise InstallError("非 multi-agent-team 受管 manifest，拒绝自动升级")
        current_schema = str(manifest.get("schema_version", ""))
        if current_schema == SCHEMA_VERSION:
            if args.apply:
                with runtime_lock(root):
                    locked_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    return reconfigure_v2_models(
                        root,
                        manifest_path,
                        locked_manifest,
                        model_overrides,
                        thread_mode=args.thread_mode,
                        apply=True,
                        allow_ignored=args.allow_ignored,
                    )
            return reconfigure_v2_models(
                root,
                manifest_path,
                manifest,
                model_overrides,
                thread_mode=args.thread_mode,
                apply=args.apply,
                allow_ignored=args.allow_ignored,
            )
        if current_schema not in SUPPORTED_FROM:
            raise InstallError(f"不支持从 schema {current_schema or 'missing'} 自动升级")
        if not agents_path.is_file():
            raise InstallError("缺少 AGENTS.md，需要人工审计")
        validate_v1_managed_assets(root, manifest)
        unexpected_state = [str(relative) for relative in MANAGED_STATE_FILES if (root / relative).exists()]
        if unexpected_state:
            raise InstallError(
                "v1 manifest 与已存在的 v2 运行态文件冲突，请先审计: "
                + ", ".join(unexpected_state)
            )

        role_targets = [root / f".codex/agents/{role}.toml" for role in manifest["roles"]]
        targets = [manifest_path, agents_path, root / "docs/协作/状态快照.json", *role_targets]
        targets.extend(root / relative for relative in MANAGED_STATE_FILES)
        targets.extend(root / relative for relative in DOC_TEMPLATES)
        for target in targets:
            ensure_safe_target(root, target)
        ignored = [str(path.relative_to(root)) for path in targets if git_ignored(root, str(path.relative_to(root)))]
        if ignored and not args.allow_ignored:
            print("IGNORED=" + ",".join(ignored))
            print("STATE=upgrade_plan_blocked")
            return 2

        snapshot_text, legacy_threads = migrate_snapshot(root / "docs/协作/状态快照.json")
        requested_thread_mode = args.thread_mode or "controlled-auto"
        state_payloads = state_defaults(requested_thread_mode, model_tiers)
        registry = state_payloads[THREAD_REGISTRY]
        registry["threads"] = migrate_threads(root, legacy_threads, state_payloads[PROJECT_STATE])
        validate_migrated_threads(registry["threads"], state_payloads[PROJECT_STATE])
        model_change = model_tiers != DEFAULT_MODEL_TIERS
        if model_change:
            replacement_required = replacement_required_records(registry["threads"])
            if replacement_required:
                return report_replacement_required(replacement_required)
        snapshot_text = json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "updated_at": now_iso(),
                "max_threads": int(manifest.get("defaults", {}).get("max_threads", 6)),
                "max_concurrent_writers": int(
                    state_payloads[PROJECT_STATE]["max_concurrent_writers"]
                ),
                "threads": registry["threads"],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
        locks, budget = derived_runtime_state(registry)
        state_payloads[OWNERSHIP_LOCKS] = locks
        state_payloads[BUDGET_STATE] = budget
        replace_managed_agents_block(agents_path.read_text(encoding="utf-8"))

        print("===== multi-agent-team upgrade plan =====")
        print(f"PROJECT={root}")
        title, source = suggested_title(root)
        print(f"TITLE_SUGGESTED={title}")
        print(f"TITLE_SOURCE={source}")
        print(f"RENAME_ACTION={rename_action(title)}")
        print("TITLE_RENAME=pending")
        print(f"SCHEMA={current_schema}->{SCHEMA_VERSION}")
        print(f"SKILL_VERSION={manifest.get('skill_version')}->{SKILL_VERSION}")
        print(f"THREAD_MODE={requested_thread_mode}")
        for tier in ("fast", "standard", "advanced"):
            print(f"MODEL: {tier}={model_tiers[tier]}")
        print(f"MIGRATED_THREADS={len(registry['threads'])}")
        print("PRESERVE=.codex/config.toml,business files")
        print("UPDATE=.codex/agents/* model lines from canonical managed templates")
        print("REPLACE=managed AGENTS block,status snapshot,manifest")
        print("ADD=.codex/team/*,long-thread registry doc,anomaly doc")
        print("BACKUP_PLAN=.codex/backups/multi-agent-team/<timestamp>/")
        if not args.apply:
            print("DRY_RUN=1, no files written.")
            print("STATE=upgrade_plan_ready")
            return 0
        journal = state_payloads[RECOVERY_JOURNAL]
        journal["events"] = [{
            "at": now_iso(),
            "event": "schema_migrated",
            "details": {"from": current_schema, "to": SCHEMA_VERSION},
        }]
        writes: dict[Path, str] = {
            agents_path: replace_managed_agents_block(agents_path.read_text(encoding="utf-8")),
            root / "docs/协作/状态快照.json": snapshot_text,
        }
        for role in manifest["roles"]:
            canonical = TEMPLATES / "agents" / f"{role}.toml"
            writes[root / ".codex" / "agents" / f"{role}.toml"] = apply_model_tiers(
                canonical.read_text(encoding="utf-8"), model_tiers
            )
        for relative, payload in state_payloads.items():
            destination = root / relative
            writes[destination] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        for relative, template_name in DOC_TEMPLATES.items():
            destination = root / relative
            if not destination.exists():
                writes[destination] = (TEMPLATES / "project" / "docs" / template_name).read_text(encoding="utf-8")

        upgraded = dict(manifest)
        upgraded.update({
            "schema_version": SCHEMA_VERSION,
            "skill_version": SKILL_VERSION,
            "upgraded_at": now_iso(),
            "orchestration": {
                "thread_creation_mode": requested_thread_mode,
                "registry": ".codex/team/thread-registry.json",
                "control_plane": "control-plane-only",
                "control_plane_is_goal": False,
                "goal_policy": "explicit-only",
                "lanes": ["fast", "project"],
                "queue_capacity": "unbounded",
                "max_concurrency_total": state_payloads[PROJECT_STATE]["max_concurrency_total"],
                "max_concurrent_writers": state_payloads[PROJECT_STATE]["max_concurrent_writers"],
                "runtime_adapter": "codex-client-thread-tools",
                "interaction_policy": "dispatch-return-immediately",
            },
            "runtime_smoke_test": "pending",
            "runtime_smoke_evidence": {"explorer": [], "reviewer": []},
        })
        writes[manifest_path] = json.dumps(upgraded, ensure_ascii=False, indent=2) + "\n"

        backup_targets = [manifest_path, agents_path, root / "docs/协作/状态快照.json", *role_targets]
        backup_root = backup_existing(root, backup_targets)
        transactional_write(writes)
        if backup_root:
            print(f"BACKUP={backup_root}")
        print("STATE=team_upgraded")
        print("NEXT=运行 team_doctor.py 和 thread_orchestrator.py health")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=upgrade_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
