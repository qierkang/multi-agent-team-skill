#!/usr/bin/env python3
"""Read-only route inspection for multi-agent-team.

The inspector never mutates the target project. It classifies the target as a
new environment, an existing business project, or an existing team so callers
can choose the safe workflow before running an installer or audit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

from runtime_state import SKILL_VERSION
from project_title import rename_action, suggested_title


CONTROL_AGENT_KEYS = {"max_threads", "max_depth", "job_max_runtime_seconds"}
TEAM_MARKERS = (
    "<!-- multi-agent-team:start -->",
    "<!-- team-init:start -->",
)
IGNORED_ROOT_ENTRIES = {".git", ".DS_Store"}


class InspectError(RuntimeError):
    pass


def project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise InspectError(f"项目目录不存在: {root}")
    return root


def read_config(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise InspectError(f"无法解析 {path}: {exc}") from exc


def inspect_git(root: Path) -> tuple[Path | None, list[str]]:
    top = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if top.returncode != 0:
        if "not a git repository" in top.stderr.lower():
            return None, []
        raise InspectError(f"Git 工作树识别失败: {top.stderr.strip() or top.returncode}")

    repo_root = Path(top.stdout.strip()).resolve()
    try:
        scope = root.relative_to(repo_root)
    except ValueError as exc:
        raise InspectError("目标项目不在识别出的 Git 工作树内") from exc
    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--short", "--untracked-files=all", "--", str(scope or Path("."))],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if status.returncode != 0:
        raise InspectError(f"Git 状态检查失败: {status.stderr.strip() or status.returncode}")
    return repo_root, [line for line in status.stdout.splitlines() if line.strip()]


def team_signals(root: Path, config: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    role_dir = root / ".codex" / "agents"
    role_files = sorted(role_dir.glob("*.toml")) if role_dir.is_dir() else []
    if role_files:
        signals.append(f"role_files:{len(role_files)}")

    agents = config.get("agents", {}) if isinstance(config, dict) else {}
    configured_roles = []
    if isinstance(agents, dict):
        configured_roles = sorted(
            key
            for key, value in agents.items()
            if key not in CONTROL_AGENT_KEYS and isinstance(value, dict)
        )
    if configured_roles:
        signals.append("configured_roles:" + ",".join(configured_roles))

    manifest = root / ".codex" / "team-bootstrap.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            signals.append(f"team_manifest:{payload.get('schema_version', 'unknown')}")
        except (OSError, json.JSONDecodeError):
            signals.append("team_manifest:invalid")

    state_dir = root / ".codex" / "team"
    if state_dir.is_dir() and any(state_dir.glob("*.json")):
        signals.append("runtime_state")

    agents_md = root / "AGENTS.md"
    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in TEAM_MARKERS):
            signals.append("agents_marker")
    return signals


def has_business_content(root: Path) -> bool:
    return any(path.name not in IGNORED_ROOT_ENTRIES for path in root.iterdir())


def inspect(root: Path) -> dict[str, Any]:
    title, title_source = suggested_title(root)
    config = read_config(root / ".codex" / "config.toml")
    signals = team_signals(root, config)
    git_root, dirty = inspect_git(root)
    installed_skill_version = "none"
    if signals:
        route = "existing-team"
        manifest_signal = next((item for item in signals if item.startswith("team_manifest:")), "")
        schema_version = manifest_signal.split(":", 1)[1] if ":" in manifest_signal else "unknown"
        if manifest_signal == "team_manifest:1.0":
            manifest_payload = json.loads((root / ".codex" / "team-bootstrap.json").read_text(encoding="utf-8"))
            installed_skill_version = str(manifest_payload.get("skill_version", "unknown"))
            route_detail = "existing-team:v1"
            next_action = "先 dry-run team_upgrade.py；确认备份与 v1->v2 迁移计划后再 --apply"
        elif manifest_signal == "team_manifest:2.0":
            manifest_payload = json.loads((root / ".codex" / "team-bootstrap.json").read_text(encoding="utf-8"))
            installed_skill_version = str(manifest_payload.get("skill_version", "unknown"))
            if installed_skill_version != SKILL_VERSION:
                route_detail = "existing-team:v2-upgrade"
                next_action = "先 dry-run team_upgrade.py，确定迁移受管协作文件到 Skill 2.0.3"
            else:
                route_detail = "existing-team:v2"
                next_action = "运行 team_doctor.py 和 thread_orchestrator.py health；健康检查后自动重命名主控任务"
        else:
            installed_skill_version = "unknown"
            route_detail = "existing-team:audit"
            next_action = "运行 team_audit.py 生成只读迁移报告；未知 schema 不得自动覆盖"
    elif has_business_content(root):
        route = "existing-project"
        route_detail = "existing-project"
        schema_version = "none"
        installed_skill_version = "none"
        next_action = "先 dry-run team_init.py，确认追加内容、冲突和备份计划后再 --apply"
    else:
        route = "new"
        route_detail = "new"
        schema_version = "none"
        installed_skill_version = "none"
        next_action = "先 dry-run team_init.py，确认角色档案后再 --apply"
    return {
        "project": str(root),
        "route": route,
        "route_detail": route_detail,
        "schema_version": schema_version,
        "installed_skill_version": installed_skill_version,
        "target_skill_version": SKILL_VERSION,
        "team_signals": signals,
        "git_root": str(git_root) if git_root else None,
        "dirty_count": len(dirty),
        "dirty_paths": dirty,
        "next": next_action,
        "title": title,
        "title_source": title_source,
        "rename_action": rename_action(title),
        "title_rename": "pending",
        "state": "inspection_done",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="只读识别 multi-agent-team 安全路由")
    parser.add_argument("--project", required=True, help="目标项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    try:
        result = inspect(project_root(args.project))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"PROJECT={result['project']}")
            print(f"ROUTE={result['route']}")
            print(f"ROUTE_DETAIL={result['route_detail']}")
            print(f"SCHEMA_VERSION={result['schema_version']}")
            print(f"INSTALLED_SKILL_VERSION={result['installed_skill_version']}")
            print(f"TARGET_SKILL_VERSION={result['target_skill_version']}")
            print(f"TEAM_SIGNALS={','.join(result['team_signals']) or 'none'}")
            print(f"GIT_ROOT={result['git_root'] or 'none'}")
            print(f"DIRTY_COUNT={result['dirty_count']}")
            print(f"NEXT={result['next']}")
            print(f"TITLE_SUGGESTED={result['title']}")
            print(f"TITLE_SOURCE={result['title_source']}")
            print(f"RENAME_ACTION={result['rename_action']}")
            print("TITLE_RENAME=pending")
            print("STATE=inspection_done")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=inspection_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
