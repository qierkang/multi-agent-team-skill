#!/usr/bin/env python3
"""Deterministic contract regression for non-blocking main-task dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from runtime_state import state_defaults


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    policy = state_defaults("recommend")[Path(".codex/team/project-state.json")]
    interaction = policy["interaction_policy"]
    require(interaction["dispatch_return_immediately"] is True, "dispatch must return immediately")
    for key in ("wait_same_turn", "poll_same_turn", "long_validation_same_turn"):
        require(interaction[key] is False, f"{key} must be false")
    require(
        interaction["sync_wait_requires_explicit_user_request"] is True
        and interaction["sync_wait_requires_warning"] is True,
        "synchronous waiting requires explicit request and warning",
    )
    template = json.loads(
        (ROOT / "templates/project/team/project-state.template.json").read_text(encoding="utf-8")
    )
    require(template["interaction_policy"] == interaction, "project-state template drifted")

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    agents = (ROOT / "templates/project/AGENTS.block.md").read_text(encoding="utf-8")
    for text, name in ((skill, "SKILL.md"), (agents, "AGENTS template")):
        require("dispatch-and-return" in text, f"{name} omits dispatch-and-return")
        require(
            "wait_agent" in text and ("same-turn" in text or "同一派发 turn" in text),
            f"{name} omits same-turn wait ban",
        )
        require("用户新消息" in text or "new user messages" in text, f"{name} omits new-message priority")
    require(
        "无法控制客户端 turn 结束" in skill or "Python cannot control" in skill,
        "SKILL.md must state client turn limitation",
    )
    print("PASS dispatch output contract rejects same-turn wait/poll/long validation")
    print("PASS Python limitation is documented; no real UI concurrency is fabricated")
    print("STATE=interaction_policy_regression_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
