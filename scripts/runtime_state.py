#!/usr/bin/env python3
"""Shared state helpers for controlled long-running thread orchestration."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
SKILL_VERSION = "1.0.1"
TEAM_DIR = Path(".codex/team")
PROJECT_STATE = TEAM_DIR / "project-state.json"
THREAD_REGISTRY = TEAM_DIR / "thread-registry.json"
OWNERSHIP_LOCKS = TEAM_DIR / "ownership-locks.json"
BUDGET_STATE = TEAM_DIR / "budget-state.json"
RECOVERY_JOURNAL = TEAM_DIR / "recovery-journal.json"
MANAGED_STATE_FILES = (
    PROJECT_STATE,
    THREAD_REGISTRY,
    OWNERSHIP_LOCKS,
    BUDGET_STATE,
    RECOVERY_JOURNAL,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# 当前 Codex 默认三档模型。不同订阅可用模型可能不同，安装时可通过
# team_init.py 的 --model-fast/--model-standard/--model-advanced 覆盖。
DEFAULT_MODEL_TIERS = {
    "fast": "gpt-5.6-luna",
    "standard": "gpt-5.6-terra",
    "advanced": "gpt-5.6-sol",
}
MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


def normalize_model_tiers(
    model_tiers: dict[str, str] | None,
) -> dict[str, str]:
    """校验并补全三档模型映射，缺省使用当前 Codex 默认值。"""
    resolved = dict(DEFAULT_MODEL_TIERS)
    if model_tiers:
        for tier, model in model_tiers.items():
            if tier not in DEFAULT_MODEL_TIERS:
                raise ValueError(f"unknown model tier: {tier}")
            if not isinstance(model, str) or not model.strip():
                raise ValueError(f"model tier '{tier}' requires a non-empty model id")
            normalized = model.strip()
            if not MODEL_ID_RE.fullmatch(normalized):
                raise ValueError(
                    f"model tier '{tier}' contains an unsafe model id; "
                    "use letters, numbers, dot, underscore, colon, slash or hyphen"
                )
            resolved[tier] = normalized
    return resolved


def project_policy(
    thread_mode: str = "recommend",
    model_tiers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if thread_mode not in {"recommend", "controlled-auto"}:
        raise ValueError(f"unsupported thread mode: {thread_mode}")
    return {
        "schema_version": SCHEMA_VERSION,
        "skill_version": SKILL_VERSION,
        "thread_creation_mode": thread_mode,
        "creation_threshold": 7,
        "subagent_threshold": 4,
        "max_active_long_threads": 5,
        "max_concurrent_writers": 2,
        "stale_heartbeat_minutes": 30,
        "model_tiers": normalize_model_tiers(model_tiers),
        "token_policy": {
            "summary_line_limit": 10,
            "compact_at_ratio": 0.70,
            "scope_freeze_at_ratio": 0.85,
            "stop_at_ratio": 1.0,
            "default_thread_budget": 120000,
        },
        "retention_policy": {
            "full_days": 30,
            "summary_days": 90,
            "archive_policy": "manual",
        },
        "external_action_policy": "explicit-user-approval",
        "updated_at": now_iso(),
    }


def empty_registry() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "updated_at": now_iso(), "threads": []}


def empty_locks() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "updated_at": now_iso(), "locks": []}


def empty_budget_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": 0,
        "updated_at": now_iso(),
        "project_token_used": 0,
        "threads": {},
    }


def empty_journal() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "updated_at": now_iso(), "events": []}


def state_defaults(
    thread_mode: str = "recommend",
    model_tiers: dict[str, str] | None = None,
) -> dict[Path, dict[str, Any]]:
    return {
        PROJECT_STATE: project_policy(thread_mode, model_tiers),
        THREAD_REGISTRY: empty_registry(),
        OWNERSHIP_LOCKS: empty_locks(),
        BUDGET_STATE: empty_budget_state(),
        RECOVERY_JOURNAL: empty_journal(),
    }


def safe_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"project directory does not exist: {root}")
    return root


def safe_state_path(root: Path, relative: Path) -> Path:
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"managed state path contains symlink: {current.relative_to(root)}")
        if not current.exists():
            break
    target.resolve(strict=False).relative_to(root)
    return target


def load_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise ValueError(f"missing state file: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"state file must contain an object: {path}")
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if previous_mode is not None:
            os.chmod(tmp_name, previous_mode)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


@contextmanager
def runtime_lock(root: Path):
    """Serialize runtime mutations across local orchestrator processes."""
    import fcntl

    lock_dir = Path(tempfile.gettempdir()) / "multi-agent-team-locks"
    lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    lock_path = lock_dir / f"{digest}.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_journal(root: Path, event: str, details: dict[str, Any]) -> None:
    path = safe_state_path(root, RECOVERY_JOURNAL)
    journal = load_json(path)
    events = journal.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError("recovery journal events must be a list")
    events.append({"at": now_iso(), "event": event, "details": details})
    journal["revision"] = int(journal.get("revision", 0)) + 1
    journal["updated_at"] = now_iso()
    atomic_write_json(path, journal)


def model_for_task(policy: dict[str, Any], task: dict[str, Any]) -> tuple[str, str]:
    task_type = str(task.get("task_type", "implementation")).lower()
    risk = str(task.get("risk", "medium")).lower()
    attempts = int(task.get("attempts", 0) or 0)
    if attempts >= 2 or risk in {"high", "critical"} or task_type in {
        "architecture",
        "security",
        "review",
        "migration",
    }:
        tier = "advanced"
    elif risk == "low" and task_type in {"exploration", "chore", "docs", "research"}:
        tier = "fast"
    else:
        tier = "standard"
    models = policy.get("model_tiers", {})
    model = models.get(tier)
    if not isinstance(model, str) or not model:
        raise ValueError(f"missing model tier mapping: {tier}")
    return tier, model


def thread_score(task: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    def add(condition: bool, points: int, reason: str) -> None:
        nonlocal score
        if condition:
            score += points
            reasons.append(f"+{points} {reason}")

    add(float(task.get("expected_days", 0) or 0) > 1, 2, "预计持续超过一天")
    add(int(task.get("task_packages", 1) or 1) >= 3, 2, "至少三个任务包")
    add(bool(task.get("independent_boundary")), 2, "独立业务或目录边界")
    add(bool(task.get("recurring")), 2, "需要持续维护")
    add(bool(task.get("independent_release")), 1, "独立测试或发布")
    add(bool(task.get("decision_retention")), 1, "需要长期保存决策")
    add(bool(task.get("parallelizable")), 1, "可与其他领域并行")
    return score, reasons


def active_threads(registry: dict[str, Any]) -> list[dict[str, Any]]:
    threads = registry.get("threads", [])
    if not isinstance(threads, list):
        raise ValueError("thread registry threads must be a list")
    active_states = {"provisioning", "active", "waiting_input", "reviewing", "degraded"}
    return [item for item in threads if isinstance(item, dict) and item.get("status") in active_states]
