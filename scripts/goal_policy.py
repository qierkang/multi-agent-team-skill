#!/usr/bin/env python3
"""Pure routing contract for keeping Codex Goals out of the team control plane."""

from __future__ import annotations

import argparse


UNSUPPORTED = "GOAL_MODE=unsupported_for_control_plane_setup"


def resolve_goal_route(*, goal_active: bool, explicit_goal_request: bool) -> str:
    """Return a reportable route; never creates, reuses, completes, or deletes a Goal."""
    if goal_active:
        return UNSUPPORTED
    if explicit_goal_request:
        return "GOAL_MODE=explicit_goal_request; CONTROL_PLANE=ordinary_codex_conversation"
    return "GOAL_MODE=ordinary_conversation; CONTROL_PLANE=ordinary_codex_conversation"


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Goal 与 multi-agent 控制面的隔离路由")
    parser.add_argument("--goal-active", action="store_true")
    parser.add_argument("--explicit-goal-request", action="store_true")
    args = parser.parse_args()
    print(resolve_goal_route(goal_active=args.goal_active, explicit_goal_request=args.explicit_goal_request))
    if args.goal_active:
        print("ACTION=建议在普通新线程执行；不复用、新建、完成或删除已有 Goal")
    elif args.explicit_goal_request:
        print("ACTION=仅按用户明确目标模式请求处理；本 Skill 不把 Goal 当控制面")
    else:
        print("ACTION=继续 ordinary Codex control plane；初始化/升级 dry-run 无冲突后直接 apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
