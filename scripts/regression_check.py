#!/usr/bin/env python3
"""Run the complete new and existing environment regression suites."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    (
        "inspect",
        ROOT / "scripts" / "regression_inspect_routes.py",
        "STATE=inspect_routes_regression_passed",
    ),
    ("new", ROOT / "scripts" / "regression_new_environment.py", "STATE=new_environment_regression_passed"),
    (
        "existing",
        ROOT / "scripts" / "regression_existing_environment.py",
        "STATE=existing_environment_regression_passed",
    ),
    (
        "runtime",
        ROOT / "scripts" / "regression_runtime_orchestration.py",
        "STATE=runtime_orchestration_regression_passed",
    ),
    (
        "interaction",
        ROOT / "scripts" / "regression_interaction_policy.py",
        "STATE=interaction_policy_regression_passed",
    ),
    (
        "goal-policy",
        ROOT / "scripts" / "regression_goal_policy.py",
        "STATE=goal_policy_regression_passed",
    ),
)


def main() -> int:
    states: dict[str, str] = {}
    for name, script, expected_state in SUITES:
        result = subprocess.run(
            ["python3", str(script)], text=True, capture_output=True, check=False
        )
        print(f"===== {name} environment =====")
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
        if result.returncode != 0 or expected_state not in result.stdout:
            print(f"STATE=regression_failed; suite={name}; exit={result.returncode}")
            return 1
        states[name] = "passed"
    print(
        f"STATE=regression_passed; inspect={states['inspect']}; new={states['new']}; "
        f"existing={states['existing']}; runtime={states['runtime']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
