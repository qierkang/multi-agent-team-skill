#!/usr/bin/env python3
"""Regression coverage for Goal isolation and ordinary control-plane routing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from goal_policy import UNSUPPORTED, resolve_goal_route
from runtime_state import state_defaults

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    phrases = (
        "主控任务",
        "主控线程",
        "项目主控",
        "当前对话设为项目主控",
    )
    docs = [
        ROOT / "SKILL.md",
        ROOT / "templates/project/AGENTS.block.md",
        ROOT / "README.md",
        ROOT / "docs/README_en.md",
        ROOT / "docs/README_zh-tw.md",
        ROOT / "references/coordination-contract.md",
        ROOT / "governance/DECISIONS.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)
    for phrase in phrases:
        require(phrase in combined, f"missing trigger phrase: {phrase}")
    require("ordinary Codex conversation" in combined, "ordinary conversation distinction missing")
    require("unsupported_for_control_plane_setup" in combined, "active Goal refusal missing")
    require("无需二次确认" in combined or "without a second confirmation" in combined, "no-second-confirmation rule missing")
    require("goal-writer" in combined, "goal-writer prohibition missing")
    require("不复用" in combined and "不新建" in combined, "active Goal non-reuse/non-create rule missing")
    require("static" in combined and "绝对阻止" in combined, "static limitation disclosure missing")

    require(resolve_goal_route(goal_active=False, explicit_goal_request=False).startswith("GOAL_MODE=ordinary"), "ordinary route changed")
    require(resolve_goal_route(goal_active=False, explicit_goal_request=True).startswith("GOAL_MODE=explicit"), "explicit Goal route changed")
    require(resolve_goal_route(goal_active=True, explicit_goal_request=False) == UNSUPPORTED, "active Goal must be unsupported")
    require(resolve_goal_route(goal_active=True, explicit_goal_request=True) == UNSUPPORTED, "active Goal must never be reused")

    policy = state_defaults()[Path(".codex/team/project-state.json")]
    require(policy["thread_creation_mode"] == "controlled-auto", "project control plane default is not controlled-auto")
    require(policy["goal_policy"] == "explicit-only" and policy["control_plane_is_goal"] is False, "Goal policy state drifted")
    template = json.loads((ROOT / "templates/project/team/project-state.template.json").read_text(encoding="utf-8"))
    require(template["goal_policy"] == "explicit-only" and template["control_plane_is_goal"] is False, "template Goal policy drifted")

    result = subprocess.run(["python3", str(ROOT / "scripts/goal_policy.py"), "--goal-active"], text=True, capture_output=True, check=False)
    require(result.returncode == 0 and UNSUPPORTED in result.stdout and "二次确认" not in result.stdout, "active Goal CLI route changed")
    print("PASS trigger phrases, Goal refusal, controlled-auto default, and no-second-confirmation policy")
    print("PASS active Goal reports unsupported_for_control_plane_setup without mutating Goal state")
    print("PASS static Skill limitation is disclosed; client-side instruction violations cannot be absolutely blocked")
    print("STATE=goal_policy_regression_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
