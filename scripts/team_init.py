#!/usr/bin/env python3
"""Safely install project-scoped Codex multi-agent role templates.

Dry-run is the default. Use --apply only after the plan has been reviewed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_state import (
    DEFAULT_MODEL_TIERS,
    MANAGED_STATE_FILES,
    SCHEMA_VERSION,
    SKILL_VERSION,
    normalize_model_tiers,
    state_defaults,
)
from project_title import rename_action, suggested_title
from agents_policy import conflict_messages


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL_ROOT / "templates"
CATALOG_PATH = TEMPLATES / "role-catalog.json"
AGENTS_START = "<!-- multi-agent-team:start -->"
AGENTS_END = "<!-- multi-agent-team:end -->"
LEGACY_AGENTS_START = "<!-- team-init:start -->"
TEAM_MARKERS = (AGENTS_START, LEGACY_AGENTS_START)
SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)]\s*(?:#.*)?$")
KEY_RE_TEMPLATE = r"^\s*{key}\s*="

DOC_TEMPLATES = {
    "docs/协作/任务台账.md": "任务台账.template.md",
    "docs/协作/任务包模板.md": "任务包.template.md",
    "docs/协作/最小派发包模板.md": "最小派发包.template.md",
    "docs/协作/摘要模板.md": "摘要.template.md",
    "docs/协作/状态快照.json": "状态快照.template.json",
    "docs/协作/长期线程注册表.md": "长期线程注册表.template.md",
    "docs/协作/异常记录.md": "异常记录.template.md",
}


class InstallError(RuntimeError):
    pass


# 模板默认模型 ID -> 档位键，用于把角色模板替换为用户提供的模型 ID。
PLACEHOLDER_TO_TIER = {
    DEFAULT_MODEL_TIERS["fast"]: "fast",
    DEFAULT_MODEL_TIERS["standard"]: "standard",
    DEFAULT_MODEL_TIERS["advanced"]: "advanced",
}
MODEL_LINE_RE = re.compile(r'^(\s*model\s*=\s*)"([^"]*)"(.*)$')


def apply_model_tiers(toml_text: str, model_tiers: dict[str, str]) -> str:
    """把角色 TOML 的默认 model 替换为对应档位的配置模型 ID。"""

    def repl(match: re.Match[str]) -> str:
        prefix, current, suffix = match.group(1), match.group(2), match.group(3)
        tier = PLACEHOLDER_TO_TIER.get(current)
        if tier is None:
            return match.group(0)
        return f"{prefix}{json.dumps(model_tiers[tier], ensure_ascii=False)}{suffix}"

    return "\n".join(
        MODEL_LINE_RE.sub(repl, line) for line in toml_text.split("\n")
    )


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def find_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise InstallError(f"项目目录不存在: {root}")
    return root


def auto_profile(root: Path) -> tuple[str, list[str]]:
    evidence: list[str] = []
    web_signals = [
        "vite.config.ts",
        "vite.config.js",
        "next.config.js",
        "next.config.mjs",
        "playwright.config.ts",
    ]
    ai_dirs = ["agents", "agent", "notebooks", "models", "pipelines"]

    web = any((root / name).exists() for name in web_signals)
    if not web:
        web = any(
            path.is_dir()
            for name in ("front", "frontend", "web", "mobile")
            for path in root.glob(f"*{name}*")
        )
    if web:
        evidence.append("检测到 Web/E2E 强信号")

    ai_data = any((root / name).is_dir() for name in ai_dirs)
    for candidate in (root / "pyproject.toml", root / "requirements.txt"):
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="ignore").lower()
            if any(token in text for token in ("langchain", "llama-index", "torch", "transformers", "pandas")):
                ai_data = True
                evidence.append(f"{candidate.name} 含 AI/数据依赖")
                break
    if ai_data and not any("AI/数据" in item for item in evidence):
        evidence.append("检测到 agents/notebooks/models/pipelines 目录")

    if web and ai_data:
        return "full", evidence
    if web:
        return "web", evidence
    if ai_data:
        return "ai-data", evidence
    return "core", ["未发现扩展角色的强信号，保守选择 core"]


def git_ignored(root: Path, relative: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        if "not a git repository" in result.stderr.lower():
            return False
        raise InstallError(f"无法识别 Git 工作树: {result.stderr.strip() or result.returncode}")
    repo_root = Path(result.stdout.strip()).resolve()
    target = (root / relative).resolve(strict=False)
    try:
        repo_relative = target.relative_to(repo_root)
    except ValueError as exc:
        raise InstallError(f"受管路径不在 Git 工作树内: {relative}") from exc
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "--quiet", "--", str(repo_relative)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise InstallError(f"Git ignore 检查失败: {result.stderr.decode().strip() or result.returncode}")
    return result.returncode == 0


def ensure_safe_target(root: Path, target: Path) -> None:
    """Reject managed paths that escape the project or traverse symlinks."""
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise InstallError(f"受管路径不在项目内: {target}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise InstallError(f"受管路径包含符号链接，拒绝写入: {current.relative_to(root)}")
        if not current.exists():
            break

    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InstallError(f"受管路径解析后越界: {relative}") from exc


def validate_managed_paths(root: Path, roles: list[str]) -> None:
    managed = [
        root / ".codex",
        root / ".codex" / "config.toml",
        root / ".codex" / "agents",
        root / ".codex" / "team-bootstrap.json",
        root / ".codex" / "team",
        root / ".codex" / "backups",
        root / "AGENTS.md",
        root / "docs",
        root / "docs" / "协作",
    ]
    managed.extend(root / ".codex" / "agents" / f"{role}.toml" for role in roles)
    managed.extend(root / relative for relative in MANAGED_STATE_FILES)
    managed.extend(root / relative for relative in DOC_TEMPLATES)
    for target in managed:
        ensure_safe_target(root, target)


def parse_toml(text: str, label: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text) if text.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise InstallError(f"{label} 不是有效 TOML: {exc}") from exc


def nested_get(data: dict[str, Any], section: str, key: str) -> tuple[bool, Any]:
    current: Any = data
    for part in section.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    if not isinstance(current, dict) or key not in current:
        return False, None
    return True, current[key]


def toml_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"unsupported TOML value: {value!r}")


def insert_key(text: str, section: str, key: str, value: Any) -> str:
    lines = text.splitlines()
    section_start = None
    section_end = len(lines)

    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if not match:
            continue
        if section_start is not None:
            section_end = index
            break
        if match.group(1).strip() == section:
            section_start = index

    entry = f"{key} = {toml_literal(value)}"
    if section_start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([f"[{section}]", entry])
    else:
        lines.insert(section_end, entry)

    return "\n".join(lines).rstrip() + "\n"


def replace_key(text: str, section: str, key: str, value: Any) -> str:
    lines = text.splitlines()
    section_start = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        match = SECTION_RE.match(line)
        if not match:
            continue
        if section_start is not None:
            section_end = index
            break
        if match.group(1).strip() == section:
            section_start = index
    if section_start is None:
        return insert_key(text, section, key, value)

    key_re = re.compile(KEY_RE_TEMPLATE.format(key=re.escape(key)))
    for index in range(section_start + 1, section_end):
        if key_re.match(lines[index]):
            lines[index] = f"{key} = {toml_literal(value)}"
            return "\n".join(lines).rstrip() + "\n"
    return insert_key(text, section, key, value)


def merge_config(
    current_text: str,
    roles: list[str],
    catalog: dict[str, Any],
    replace_conflicts: bool,
) -> tuple[str, list[str], list[str]]:
    text = current_text
    changes: list[str] = []
    conflicts: list[str] = []
    defaults = catalog["defaults"]
    desired: list[tuple[str, str, Any]] = [
        ("features", "multi_agent", True),
        ("agents", "max_threads", defaults["max_threads"]),
        ("agents", "max_depth", defaults["max_depth"]),
        ("agents", "job_max_runtime_seconds", defaults["job_max_runtime_seconds"]),
    ]
    for role in roles:
        metadata = catalog["roles"][role]
        desired.extend(
            [
                (f"agents.{role}", "description", metadata["description"]),
                (f"agents.{role}", "config_file", metadata["config_file"]),
            ]
        )

    for section, key, value in desired:
        data = parse_toml(text, ".codex/config.toml")
        exists, existing = nested_get(data, section, key)
        label = f"{section}.{key}"
        if not exists:
            text = insert_key(text, section, key, value)
            changes.append(f"ADD {label}={value!r}")
        elif existing == value:
            continue
        elif replace_conflicts:
            text = replace_key(text, section, key, value)
            changes.append(f"UPDATE {label}: {existing!r} -> {value!r}")
        else:
            conflicts.append(f"{label}: existing={existing!r}, desired={value!r}")

    parse_toml(text, "合并后的 .codex/config.toml")
    return text, changes, conflicts


def build_agents_text(root: Path) -> tuple[str, str]:
    target = root / "AGENTS.md"
    fragment = (TEMPLATES / "project" / "AGENTS.block.md").read_text(encoding="utf-8").strip()
    if not target.exists():
        return f"# 项目协作规则\n\n{fragment}\n", "ADD"

    current = target.read_text(encoding="utf-8")
    has_start = AGENTS_START in current
    has_end = AGENTS_END in current
    if has_start and has_end:
        return current, "KEEP"
    if has_start != has_end:
        raise InstallError("AGENTS.md 中 multi-agent-team 标记不完整，请先人工修复")
    return current.rstrip() + "\n\n" + fragment + "\n", "APPEND"


def existing_doc_conflicts(root: Path) -> list[str]:
    """Reject same-name runtime documents that cannot be safely adopted."""
    snapshot = root / "docs/协作/状态快照.json"
    if not snapshot.exists():
        return []
    try:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"docs/协作/状态快照.json 无法安全接管: {exc}"]
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        return ["docs/协作/状态快照.json 不是 schema 2.0"]
    threads = payload.get("threads")
    if not isinstance(threads, list):
        return ["docs/协作/状态快照.json 缺少 threads 数组"]
    if threads:
        return ["docs/协作/状态快照.json 已含任务，不能作为新团队空注册表接管"]
    return []


def atomic_write(path: Path, content: str) -> None:
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        if previous_mode is not None:
            os.chmod(tmp_name, previous_mode)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def transactional_write(writes: dict[Path, str]) -> None:
    originals: dict[Path, tuple[str, int]] = {}
    completed: list[Path] = []
    new_directories: set[Path] = set()
    for path in writes:
        if path.exists():
            originals[path] = (path.read_text(encoding="utf-8"), path.stat().st_mode)
        current = path.parent
        while not current.exists():
            new_directories.add(current)
            current = current.parent

    try:
        for path, content in writes.items():
            atomic_write(path, content)
            completed.append(path)
    except Exception as exc:
        rollback_errors: list[str] = []
        for path in reversed(completed):
            try:
                if path in originals:
                    original, mode = originals[path]
                    atomic_write(path, original)
                    os.chmod(path, mode)
                elif path.exists():
                    path.unlink()
            except Exception as rollback_exc:  # pragma: no cover - rare double fault
                rollback_errors.append(f"{path}: {rollback_exc}")
        for directory in sorted(new_directories, key=lambda item: len(item.parts), reverse=True):
            try:
                if directory.exists():
                    directory.rmdir()
            except OSError:
                # A non-empty directory may contain pre-existing or diagnostic files; never delete it.
                pass
        detail = f"写入失败，已回滚: {exc}"
        if rollback_errors:
            detail += f"；回滚异常: {'; '.join(rollback_errors)}"
        raise InstallError(detail) from exc


def backup_existing(root: Path, paths: list[Path]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / ".codex" / "backups" / "multi-agent-team" / stamp
    suffix = 1
    while backup_root.exists():
        backup_root = root / ".codex" / "backups" / "multi-agent-team" / f"{stamp}-{suffix}"
        suffix += 1
    ensure_safe_target(root, backup_root)
    for path in existing:
        relative = path.relative_to(root)
        destination = backup_root / relative
        ensure_safe_target(root, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    return backup_root


def print_plan(
    root: Path,
    profile: str,
    evidence: list[str],
    roles: list[str],
    actions: list[str],
    config_changes: list[str],
    conflicts: list[str],
    ignored: list[str],
    backup_plan: str | None,
    model_tiers: dict[str, str],
) -> None:
    print("===== multi-agent-team install plan =====")
    print(f"PROJECT={root}")
    title, source = suggested_title(root)
    print(f"TITLE_SUGGESTED={title}")
    print(f"TITLE_SOURCE={source}")
    print(f"RENAME_ACTION={rename_action(title)}")
    print("TITLE_RENAME=pending")
    print(f"PROFILE={profile}")
    print(f"ROLES={','.join(roles)}")
    for tier in ("fast", "standard", "advanced"):
        model = model_tiers[tier]
        flag = " (Codex 默认；订阅不支持时用 --model-* 覆盖)" if model == DEFAULT_MODEL_TIERS[tier] else ""
        print(f"MODEL: {tier}={model}{flag}")
    for item in evidence:
        print(f"DETECTION: {item}")
    for item in actions:
        print(f"ACTION: {item}")
    for item in config_changes:
        print(f"CONFIG: {item}")
    for item in ignored:
        print(f"IGNORED: {item}")
    for item in conflicts:
        print(f"CONFLICT: {item}")
    if backup_plan:
        print(f"BACKUP_PLAN={backup_plan}")
    print("==========================")


def main() -> int:
    parser = argparse.ArgumentParser(description="安装项目级受控多智能体团队")
    parser.add_argument("--project", required=True, help="目标项目根目录")
    parser.add_argument("--profile", choices=["auto", "core", "web", "ai-data", "full"], default="auto")
    parser.add_argument("--apply", action="store_true", help="执行写入；默认仅 dry-run")
    parser.add_argument("--replace-conflicts", action="store_true", help="显式替换已存在的冲突配置")
    parser.add_argument("--allow-ignored", action="store_true", help="显式允许写入被 .gitignore 忽略的受管路径")
    parser.add_argument(
        "--thread-mode",
        choices=["recommend", "controlled-auto"],
        default="controlled-auto",
        help="长期任务创建模式；项目主控默认受控自动，仍不放宽外部动作审批",
    )
    parser.add_argument("--model-fast", help="fast 档真实模型 ID（explorer/chore）")
    parser.add_argument("--model-standard", help="standard 档真实模型 ID（implementer/debugger 等）")
    parser.add_argument("--model-advanced", help="advanced 档真实模型 ID（architect/reviewer）")
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
        root = find_project_root(args.project)
        catalog = load_catalog()
        validate_managed_paths(root, [])
        config_path = root / ".codex" / "config.toml"
        current_config = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        existing_config = parse_toml(current_config, ".codex/config.toml")
        agent_section = existing_config.get("agents", {}) if isinstance(existing_config, dict) else {}
        configured_roles = sorted(
            key for key, value in agent_section.items() if isinstance(value, dict)
        ) if isinstance(agent_section, dict) else []
        existing_roles = sorted((root / ".codex" / "agents").glob("*.toml"))
        existing_state = [root / relative for relative in MANAGED_STATE_FILES if (root / relative).exists()]
        existing_manifest = (root / ".codex" / "team-bootstrap.json").exists()
        agents_path = root / "AGENTS.md"
        agents_text = agents_path.read_text(encoding="utf-8", errors="ignore") if agents_path.is_file() else ""
        existing_marker = next((marker for marker in TEAM_MARKERS if marker in agents_text), None)
        if existing_roles or existing_state or configured_roles or existing_manifest or existing_marker:
            print("检测到已有团队配置，请使用 $multi-agent-team 审计模式生成迁移方案:")
            for path in existing_roles:
                print(f"  - {path.relative_to(root)}")
            for role in configured_roles:
                print(f"  - .codex/config.toml [agents.{role}]")
            for path in existing_state:
                print(f"  - {path.relative_to(root)}")
            if existing_manifest:
                print("  - .codex/team-bootstrap.json")
            if existing_marker:
                print(f"  - AGENTS.md marker {existing_marker}")
            print("STATE=needs_audit")
            return 3

        if args.profile == "auto":
            profile, evidence = auto_profile(root)
        else:
            profile, evidence = args.profile, ["用户显式指定档案"]
        roles = list(catalog["profiles"][profile])

        validate_managed_paths(root, roles)
        merged_config, config_changes, conflicts = merge_config(
            current_config,
            roles,
            catalog,
            args.replace_conflicts,
        )
        conflicts.extend(existing_doc_conflicts(root))
        conflicts.extend(
            f"AGENTS.md control-plane conflict: {item}"
            for item in conflict_messages(agents_text)
        )
        agents_text, agents_action = build_agents_text(root)

        manifest_path = root / ".codex" / "team-bootstrap.json"
        managed_files = [
            ".codex/config.toml",
            ".codex/team-bootstrap.json",
            "AGENTS.md",
            *(f".codex/agents/{role}.toml" for role in roles),
            *(str(path) for path in MANAGED_STATE_FILES),
            *DOC_TEMPLATES,
        ]
        if config_path.exists() or (root / "AGENTS.md").exists():
            managed_files.append(".codex/backups/multi-agent-team/.ignore-probe")
        ignored = [relative for relative in managed_files if git_ignored(root, relative)]
        actions = [
            f"{'MODIFY' if config_path.exists() else 'ADD'} .codex/config.toml",
            f"{agents_action} AGENTS.md",
        ]
        actions.extend(f"ADD .codex/agents/{role}.toml" for role in roles)
        actions.extend(f"ADD {path}" for path in MANAGED_STATE_FILES)
        for relative in DOC_TEMPLATES:
            actions.append(f"{'KEEP' if (root / relative).exists() else 'ADD'} {relative}")
        actions.append("ADD .codex/team-bootstrap.json")

        backup_plan = None
        if config_path.exists() or (root / "AGENTS.md").exists():
            backup_plan = ".codex/backups/multi-agent-team/<timestamp>/"
        print_plan(
            root,
            profile,
            evidence,
            roles,
            actions,
            config_changes,
            conflicts,
            ignored,
            backup_plan,
            model_tiers,
        )

        blocked = bool(conflicts) or (bool(ignored) and not args.allow_ignored)
        if not args.apply:
            print("DRY_RUN=1, no files written.")
            print("STATE=plan_blocked" if blocked else "STATE=plan_ready")
            return 2 if blocked else 0
        if blocked:
            raise InstallError("存在配置冲突或 ignored 路径，未执行写入")
        backup_root = backup_existing(root, [config_path, root / "AGENTS.md"])
        if backup_root:
            print(f"BACKUP={backup_root}")

        writes: dict[Path, str] = {
            config_path: merged_config,
            root / "AGENTS.md": agents_text,
        }
        for role in roles:
            source = TEMPLATES / "agents" / f"{role}.toml"
            writes[root / ".codex" / "agents" / f"{role}.toml"] = apply_model_tiers(
                source.read_text(encoding="utf-8"), model_tiers
            )

        for relative, template_name in DOC_TEMPLATES.items():
            destination = root / relative
            if not destination.exists():
                source = TEMPLATES / "project" / "docs" / template_name
                writes[destination] = source.read_text(encoding="utf-8")

        for relative, payload in state_defaults(args.thread_mode, model_tiers).items():
            writes[root / relative] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "skill": "multi-agent-team",
            "skill_version": SKILL_VERSION,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "project_root": ".",
            "profile": profile,
            "roles": roles,
            "defaults": catalog["defaults"],
            "orchestration": {
                "thread_creation_mode": args.thread_mode,
                "registry": str(MANAGED_STATE_FILES[1]),
                "control_plane": "control-plane-only",
                "control_plane_is_goal": False,
                "goal_policy": "explicit-only",
                "lanes": ["fast", "project"],
                "queue_capacity": "unbounded",
                "max_concurrency_total": 6,
                "max_concurrent_writers": 2,
                "runtime_adapter": "codex-client-thread-tools",
                "interaction_policy": "dispatch-return-immediately",
            },
            "runtime_smoke_test": "pending",
            "runtime_smoke_evidence": {"explorer": [], "reviewer": []},
        }
        writes[manifest_path] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        transactional_write(writes)
        print("STATE=team_installed")
        print("NEXT=运行 team_doctor.py，并在目标项目创建全新 explorer/reviewer 做运行态冒烟")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=install_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
