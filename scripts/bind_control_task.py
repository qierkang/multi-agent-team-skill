#!/usr/bin/env python3
"""Persist a real Codex control-task binding after the client rename/pin succeeds."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from project_title import suggested_title
from runtime_state import now_iso, safe_project_root
from team_init import InstallError, backup_existing, ensure_safe_target, transactional_write


THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,127}$")
HOST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="在客户端完成主控重命名和置顶后持久化真实任务绑定"
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--thread-id", required=True)
    parser.add_argument("--host-id", default="local")
    parser.add_argument("--title", help="已在 Codex 客户端确认生效的主控标题")
    parser.add_argument(
        "--pinned",
        action="store_true",
        help="仅在客户端置顶动作真实成功后传入；strict doctor 要求该证据",
    )
    parser.add_argument("--apply", action="store_true", help="执行写入；默认 dry-run")
    args = parser.parse_args()

    try:
        root = safe_project_root(args.project)
        thread_id = args.thread_id.strip()
        host_id = args.host_id.strip()
        if not THREAD_ID_RE.fullmatch(thread_id):
            raise InstallError("thread id 格式不安全")
        if not HOST_ID_RE.fullmatch(host_id):
            raise InstallError("host id 格式不安全")
        title = (args.title or suggested_title(root)[0]).strip()
        if not title.startswith("主控｜") or len(title) > 160:
            raise InstallError("主控标题必须以 '主控｜' 开头且不超过 160 字符")

        manifest_path = root / ".codex/team-bootstrap.json"
        ensure_safe_target(root, manifest_path)
        if not manifest_path.is_file():
            raise InstallError("缺少 .codex/team-bootstrap.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("skill") != "multi-agent-team":
            raise InstallError("非 multi-agent-team 受管 manifest")
        orchestration = manifest.get("orchestration")
        if not isinstance(orchestration, dict):
            raise InstallError("manifest orchestration 无效")
        binding = {
            "thread_id": thread_id,
            "host_id": host_id,
            "title": title,
            "uri": f"codex://threads/{thread_id}",
            "pinned": bool(args.pinned),
            "designated_at": now_iso(),
        }
        updated = dict(manifest)
        updated["orchestration"] = {**orchestration, "control_task": binding}

        print("===== control task binding =====")
        print(f"PROJECT={root}")
        print(f"THREAD_ID={thread_id}")
        print(f"HOST_ID={host_id}")
        print(f"TITLE={title}")
        print(f"PINNED={str(args.pinned).lower()}")
        if not args.apply:
            print("DRY_RUN=1, no files written.")
            print("STATE=control_task_binding_plan_ready")
            return 0
        if not args.pinned:
            raise InstallError("客户端置顶尚未确认；拒绝写入无效 control task 绑定")

        backup_root = backup_existing(root, [manifest_path])
        transactional_write(
            {manifest_path: json.dumps(updated, ensure_ascii=False, indent=2) + "\n"}
        )
        if backup_root:
            print(f"BACKUP={backup_root}")
        print("STATE=control_task_bound")
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=control_task_binding_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
