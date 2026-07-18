#!/usr/bin/env python3
"""Record honest explorer/reviewer client-smoke evidence in a managed team."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from runtime_state import (
    atomic_write_json,
    now_iso,
    runtime_lock,
    safe_project_root,
    validate_evidence_path,
)


MANIFEST = Path(".codex/team-bootstrap.json")
ROLES = ("explorer", "reviewer")
STATES = {"pending", "partial_done", "runtime_validation_done"}


def evidence_path(root: Path, raw: str) -> str:
    return validate_evidence_path(root, raw)


def load_manifest(root: Path) -> tuple[Path, dict[str, Any]]:
    path = root / MANIFEST
    if path.is_symlink() or not path.is_file():
        raise ValueError("managed team manifest is missing or is a symlink")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid managed team manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("skill") != "multi-agent-team":
        raise ValueError("manifest is not managed by multi-agent-team")
    return path, manifest


def normalized_evidence(root: Path, manifest: dict[str, Any]) -> dict[str, list[str]]:
    raw_evidence = manifest.get("runtime_smoke_evidence", {role: [] for role in ROLES})
    if not isinstance(raw_evidence, dict) or set(raw_evidence) - set(ROLES):
        raise ValueError("runtime_smoke_evidence must contain only explorer/reviewer lists")
    evidence: dict[str, list[str]] = {}
    for role in ROLES:
        values = raw_evidence.get(role, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"runtime_smoke_evidence.{role} must be a string array")
        evidence[role] = []
        for raw_path in values:
            path = evidence_path(root, raw_path)
            if path not in evidence[role]:
                evidence[role].append(path)
    return evidence


def status_for(evidence: dict[str, list[str]]) -> str:
    if all(evidence[role] for role in ROLES):
        return "runtime_validation_done"
    if any(evidence[role] for role in ROLES):
        return "partial_done"
    return "pending"


def update(root: Path, args: argparse.Namespace) -> int:
    manifest_path, manifest = load_manifest(root)
    current_status = manifest.get("runtime_smoke_test", "pending")
    if current_status not in STATES:
        raise ValueError(f"unknown runtime smoke status: {current_status!r}")
    evidence = normalized_evidence(root, manifest)
    if current_status != status_for(evidence):
        raise ValueError("runtime smoke status and recorded evidence are inconsistent")

    additions = {
        "explorer": args.explorer_evidence,
        "reviewer": args.reviewer_evidence,
    }
    if not any(additions.values()):
        raise ValueError("at least one explorer/reviewer evidence path is required")
    for role, values in additions.items():
        for raw_path in values:
            path = evidence_path(root, raw_path)
            if path not in evidence[role]:
                evidence[role].append(path)

    next_status = status_for(evidence)
    result = {
        "action": "record_runtime_smoke",
        "from": current_status,
        "to": next_status,
        "evidence": evidence,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN=1, no files written.")
        print("STATE=runtime_smoke_plan_ready")
        return 0

    manifest["runtime_smoke_test"] = next_status
    manifest["runtime_smoke_evidence"] = evidence
    manifest["runtime_smoke_updated_at"] = now_iso()
    atomic_write_json(manifest_path, manifest)
    print(
        "STATE=runtime_validation_done"
        if next_status == "runtime_validation_done"
        else "STATE=runtime_smoke_partial_done"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="记录真实 explorer/reviewer 客户端冒烟证据")
    parser.add_argument("--project", required=True)
    parser.add_argument("--explorer-evidence", action="append", default=[])
    parser.add_argument("--reviewer-evidence", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="执行写入；默认 dry-run")
    args = parser.parse_args()
    try:
        root = safe_project_root(args.project)
        if args.apply:
            with runtime_lock(root):
                return update(root, args)
        return update(root, args)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("STATE=runtime_smoke_failed")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
