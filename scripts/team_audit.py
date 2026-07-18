#!/usr/bin/env python3
"""Read-only audit for an existing Codex multi-agent project team."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_state import validate_evidence_path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_ROOT / "templates" / "reports" / "团队迁移报告.template.md"
KNOWN_ROLES = {
    "explorer",
    "chore",
    "implementer",
    "debugger",
    "architect",
    "reviewer",
    "e2e-tester",
    "evidence-researcher",
}


class AuditError(RuntimeError):
    pass


def find_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise AuditError(f"项目目录不存在: {root}")
    return root


def read_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, str(exc)


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
    raise AuditError(f"无法识别 Git 工作树: {result.stderr.strip() or result.returncode}")


def git_status(root: Path) -> tuple[list[str], Path | None]:
    repo_root = git_repository_root(root)
    if repo_root is None:
        return [], None
    try:
        scope = root.relative_to(repo_root)
    except ValueError as exc:
        raise AuditError("项目目录不在已识别的 Git 工作树内") from exc
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--short", "--untracked-files=all", "--", str(scope or Path("."))],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AuditError(f"Git 状态检查失败: {result.stderr.strip() or result.returncode}")
    return [line for line in result.stdout.splitlines() if line.strip()], repo_root


def git_ignored(root: Path, path: Path) -> bool:
    repo_root = git_repository_root(root)
    if repo_root is None:
        return False
    try:
        relative = str(path.relative_to(repo_root))
    except ValueError as exc:
        raise AuditError("报告路径不在已识别的 Git 工作树内") from exc
    result = subprocess.run(
        ["git", "-C", str(repo_root), "check-ignore", "--quiet", "--", relative],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise AuditError(f"Git ignore 检查失败: {result.stderr.decode().strip() or result.returncode}")
    return result.returncode == 0


def load_threads(root: Path, path: Path | None) -> tuple[list[dict[str, Any]], list[str]]:
    if path is None:
        return [], ["未提供任务快照，运行时状态尚未核验"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"任务快照不可读取: {exc}") from exc
    warnings: list[str] = []
    if isinstance(payload, dict) and "threads" in payload:
        threads = payload.get("threads")
    elif isinstance(payload, dict) and "tasks" in payload:
        threads = payload.get("tasks")
        warnings.append("检测到 v1 tasks 快照，已只读兼容；升级时将迁移为 v2 threads")
    else:
        threads = payload
    if not isinstance(threads, list):
        raise AuditError("任务快照必须是数组，或包含 threads 数组的对象")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(threads, 1):
        if not isinstance(item, dict):
            warnings.append(f"第 {index} 条任务不是对象，已跳过")
            continue
        entry = dict(item)
        entry.setdefault("id", f"unknown-{index}")
        entry.setdefault("title", "未命名任务")
        entry.setdefault("status", "unknown")
        entry.setdefault("summary", "")
        evidence_paths: list[str] = []
        for field in ("evidence_paths", "evidence"):
            value = entry.get(field, [])
            if value is None:
                continue
            if not isinstance(value, list):
                warnings.append(f"第 {index} 条任务的 {field} 不是数组，已忽略")
                continue
            for raw_path in value:
                path = str(raw_path).strip() if isinstance(raw_path, str) else ""
                if not path:
                    warnings.append(f"第 {index} 条任务的 {field} 包含空路径，已忽略")
                    continue
                try:
                    normalized_path = validate_evidence_path(root, path)
                except (OSError, ValueError) as exc:
                    warnings.append(f"第 {index} 条任务的 {field} 证据无效，已忽略: {exc}")
                    continue
                if normalized_path not in evidence_paths:
                    evidence_paths.append(normalized_path)
        entry["evidence_paths"] = evidence_paths
        entry.setdefault("owned_paths", [])
        entry.setdefault("attempts", 0)
        entry.setdefault("needs_user_input", False)
        normalized.append(entry)
    return normalized, warnings


def map_role(thread: dict[str, Any]) -> tuple[str, str]:
    haystack = " ".join(
        str(thread.get(key, "")) for key in ("title", "summary", "current_role", "role")
    ).lower()
    rules = [
        ("reviewer", ("review", "reviewer", "security", "审查", "评审", "安全")),
        ("architect", ("architect", "architecture", "架构", "迁移设计", "方案设计")),
        ("debugger", ("debug", "bug", "fix", "故障", "排障", "修复")),
        ("e2e-tester", ("e2e", "playwright", "browser", "端到端", "浏览器", "回归测试")),
        ("evidence-researcher", ("evidence", "research", "api", "证据", "调研", "数据源")),
        ("implementer", ("frontend", "backend", "builder", "implement", "code", "前端", "后端", "开发", "实现")),
        ("chore", ("chore", "docs", "documentation", "ops", "整理", "文档", "机械")),
        ("explorer", ("explore", "search", "trace", "探索", "检索", "调用链")),
    ]
    for role, tokens in rules:
        if any(token in haystack for token in tokens):
            return role, "标题/摘要命中候选规则，执行前仍需结合任务包与修改路径确认"
    return "manual-review", "未发现可靠角色信号，需要人工判断"


def suggested_action(thread: dict[str, Any], mapped_role: str) -> str:
    status = str(thread.get("status", "unknown")).lower()
    attempts = thread.get("attempts", 0)
    needs_input = bool(thread.get("needs_user_input")) or status in {"needs_input", "waiting_user"}
    evidence = thread.get("evidence_paths") or []
    if needs_input:
        return "保留任务并等待用户输入，不代答、不归档"
    if status in {"completed", "done", "complete"}:
        return "证据齐全后收口归档" if evidence else "先补齐证据，再收口归档"
    if status in {"blocked", "failed"} or (isinstance(attempts, int) and attempts >= 2):
        target = mapped_role if mapped_role != "manual-review" else "architect/debugger"
        return f"冻结现场，使用全新 {target} 实例重派"
    if status in {"in_progress", "running", "active"}:
        return "允许完成当前最小闭环；发生所有权冲突则冻结后重派"
    if status in {"pending", "queued", "todo"}:
        return f"按 {mapped_role} 候选角色重新派发" if mapped_role != "manual-review" else "补任务包后人工派发"
    return "人工核验状态和现场后决定"


def inspect_roles(root: Path, config: dict[str, Any] | None) -> tuple[list[dict[str, str]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    config_agents = config.get("agents", {}) if isinstance(config, dict) else {}
    config_roles = {
        key for key, value in config_agents.items() if isinstance(value, dict)
    } if isinstance(config_agents, dict) else set()
    file_roles = {path.stem for path in (root / ".codex" / "agents").glob("*.toml")}

    for role in sorted(config_roles | file_roles):
        path = root / ".codex" / "agents" / f"{role}.toml"
        role_config, error = read_toml(path)
        if error:
            warnings.append(f"角色 {role} TOML 无法解析: {error}")
        section = config_agents.get(role, {}) if isinstance(config_agents, dict) else {}
        rows.append(
            {
                "role": role,
                "source": "+".join(filter(None, ["config" if role in config_roles else "", "file" if role in file_roles else ""])),
                "model": str((role_config or {}).get("model", "继承/未知")),
                "sandbox": str((role_config or {}).get("sandbox_mode", "未知")),
                "config_file": str(section.get("config_file", "未登记")) if isinstance(section, dict) else "未登记",
            }
        )
    for role in sorted(config_roles - file_roles):
        warnings.append(f"配置声明角色 {role}，但对应 TOML 文件缺失")
    for role in sorted(file_roles - config_roles):
        warnings.append(f"角色文件 {role}.toml 未在 .codex/config.toml 登记")
    return rows, warnings


def infer_profile(role_names: set[str], mapped_roles: set[str]) -> str:
    combined = role_names | mapped_roles
    has_e2e = "e2e-tester" in combined
    has_evidence = "evidence-researcher" in combined
    if has_e2e and has_evidence:
        return "full"
    if has_e2e:
        return "web"
    if has_evidence:
        return "ai-data"
    return "core"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_无可展示记录_"
    output = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        escaped = [str(item).replace("|", "\\|").replace("\n", " ") for item in row]
        output.append("| " + " | ".join(escaped) + " |")
    return "\n".join(output)


def render_report(root: Path, threads: list[dict[str, Any]], snapshot_warnings: list[str]) -> str:
    config_path = root / ".codex" / "config.toml"
    config, config_error = read_toml(config_path)
    role_rows, warnings = inspect_roles(root, config)
    dirty, repo_root = git_status(root)
    warnings.extend(snapshot_warnings)
    if config_error:
        warnings.append(f".codex/config.toml 无法解析: {config_error}")
    if config is None and config_error is None:
        warnings.append("缺少 .codex/config.toml，现有团队可能未项目化")

    agents = config.get("agents", {}) if isinstance(config, dict) else {}
    features = config.get("features", {}) if isinstance(config, dict) else {}
    if config is not None:
        if features.get("multi_agent") is not True:
            warnings.append("features.multi_agent 未启用")
        if agents.get("max_depth") != 1:
            warnings.append(f"agents.max_depth={agents.get('max_depth')!r}，建议固定为 1")
        max_threads = agents.get("max_threads")
        if not isinstance(max_threads, int) or max_threads > 6:
            warnings.append(f"agents.max_threads={max_threads!r}，建议不超过 6")
    if dirty:
        warnings.append(f"Git 工作树存在 {len(dirty)} 条未提交变更，迁移前必须确认文件所有权")
    if repo_root is None:
        warnings.append("未检测到 Git 工作树，无法验证未提交文件和 .gitignore")
    if not (root / "docs/协作/任务台账.md").is_file():
        warnings.append("缺少外置任务台账")

    ownership: dict[str, list[str]] = {}
    mapped: list[tuple[dict[str, Any], str, str, str]] = []
    for thread in threads:
        role, reason = map_role(thread)
        action = suggested_action(thread, role)
        mapped.append((thread, role, reason, action))
        for path in thread.get("owned_paths") or []:
            ownership.setdefault(str(path), []).append(str(thread.get("id")))
    for path, owners in ownership.items():
        if len(owners) > 1:
            warnings.append(f"文件所有权冲突: {path} 同时属于 {', '.join(owners)}")

    role_names = {row["role"] for row in role_rows}
    mapped_roles = {role for _, role, _, _ in mapped if role in KNOWN_ROLES}
    profile = infer_profile(role_names, mapped_roles)

    current_lines = [
        f"- `.codex/config.toml`：{'存在' if config_path.is_file() else '缺失'}",
        f"- `multi_agent`：{features.get('multi_agent', '未知') if isinstance(features, dict) else '未知'}",
        f"- `max_threads`：{agents.get('max_threads', '未知') if isinstance(agents, dict) else '未知'}",
        f"- `max_depth`：{agents.get('max_depth', '未知') if isinstance(agents, dict) else '未知'}",
        f"- Git 工作树：{repo_root if repo_root is not None else '未检测到'}",
        f"- Git 未提交项：{len(dirty)}",
    ]
    if dirty:
        current_lines.append("- Git 未提交路径：")
        current_lines.extend(f"  - `{line.replace('`', '')}`" for line in dirty[:100])
        if len(dirty) > 100:
            current_lines.append(f"  - 其余 {len(dirty) - 100} 条已截断，请直接运行 `git status --short`")
    current_config = "\n".join(current_lines)
    role_table = markdown_table(
        ["角色", "来源", "模型", "沙箱", "配置引用"],
        [[row["role"], row["source"], row["model"], row["sandbox"], row["config_file"]] for row in role_rows],
    )
    thread_table = markdown_table(
        ["任务", "状态", "候选角色", "建议动作", "映射依据"],
        [
            [
                f"{thread.get('title')} (`{thread.get('id')}`)",
                str(thread.get("status")),
                role,
                action,
                reason,
            ]
            for thread, role, reason, action in mapped
        ],
    )
    if not threads:
        thread_table = "_未提供任务快照。请用客户端任务工具生成快照后重新审计；当前不能判断任务是否应归档。_"
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- 未发现静态异常；仍需运行时核验"
    plan_items = [
        "1. 冻结新增派发，先保存所有进行中任务的短摘要、diff、日志、证据和文件所有权。",
        "2. 处理 Git 脏状态与所有权冲突；不 reset、不覆盖用户修改。",
        "3. 对已完成任务补齐证据后收口归档；等待用户输入的任务保持原状。",
        "4. 对失败或失联任务保存现场，使用干净的一次性角色实例重派。",
        f"5. 用户确认后，以 `$multi-agent-team` 的 `{profile}` 档案部署目标角色，不复用长期 reviewer。",
        "6. 运行静态 doctor，再创建 explorer 与全新 reviewer 做运行态冒烟。",
    ]
    if not role_rows:
        plan_items.insert(0, "0. 当前未发现项目级角色模板；确认后直接使用 `$multi-agent-team` 初始化模式，不要手工拼配置。")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{PROJECT_NAME}}": root.name,
        "{{GENERATED_AT}}": datetime.now(timezone.utc).isoformat(),
        "{{SUGGESTED_PROFILE}}": profile,
        "{{CURRENT_CONFIG}}": current_config,
        "{{ROLE_TABLE}}": role_table,
        "{{THREAD_TABLE}}": thread_table,
        "{{WARNINGS}}": warning_text,
        "{{MIGRATION_PLAN}}": "\n".join(plan_items),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template.rstrip() + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def contains_symlink(root: Path, target: Path) -> bool:
    relative = target.relative_to(root)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
        if not current.exists():
            break
    return False


def resolve_report_path(root: Path, raw: str, overwrite: bool) -> Path:
    candidate = Path(raw).expanduser()
    lexical = Path(os.path.abspath(candidate if candidate.is_absolute() else root / candidate))
    try:
        lexical.relative_to(root)
    except ValueError as exc:
        raise AuditError("报告必须写入目标项目目录内") from exc
    if contains_symlink(root, lexical):
        raise AuditError("报告路径包含符号链接，拒绝写入")
    report = lexical.resolve(strict=False)
    allowed_root = (root / "docs" / "协作").resolve(strict=False)
    try:
        report.relative_to(allowed_root)
    except ValueError as exc:
        raise AuditError("报告只能写入 docs/协作/ 目录") from exc
    if report.suffix.lower() != ".md":
        raise AuditError("审计报告必须使用 .md 扩展名")
    if git_ignored(root, report):
        raise AuditError("报告路径被 .gitignore 忽略，请选择可追踪的项目内路径")
    if report.exists() and not overwrite:
        raise AuditError("报告文件已存在；请使用新文件名，或显式添加 --overwrite-report")
    if report.exists() and not report.is_file():
        raise AuditError("报告目标不是普通文件")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="只读审计已有多智能体团队")
    parser.add_argument("--project", required=True, help="目标项目根目录")
    parser.add_argument("--threads-json", help="由客户端任务工具生成的任务快照")
    parser.add_argument("--report", help="项目内报告路径；省略时只输出到标准输出")
    parser.add_argument("--overwrite-report", action="store_true", help="显式允许覆盖 docs/协作/ 内已有 Markdown 报告")
    args = parser.parse_args()

    try:
        root = find_project_root(args.project)
        snapshot_path = Path(args.threads_json).expanduser().resolve() if args.threads_json else None
        threads, warnings = load_threads(root, snapshot_path)
        report = render_report(root, threads, warnings)
        if args.report:
            report_path = resolve_report_path(root, args.report, args.overwrite_report)
            atomic_write(report_path, report)
            print(f"REPORT={report_path}")
        else:
            print(report, end="")
        print("STATE=audit_report_ready")
        print("EXECUTION=not_started; user confirmation required")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=audit_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
