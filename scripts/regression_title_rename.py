#!/usr/bin/env python3
"""Regression coverage for deterministic main-thread title suggestions."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from project_title import project_display_name, suggested_title


ROOT = Path(__file__).resolve().parents[1]
INSPECT = ROOT / "scripts" / "inspect_team.py"


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def inspect(project: Path) -> str:
    result = subprocess.run(
        ["python3", str(INSPECT), "--project", str(project)],
        text=True, capture_output=True, check=False,
    )
    require(result.returncode == 0, result.stderr)
    return result.stdout


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="multi-agent-team-title-") as raw:
        sandbox = Path(raw)
        readme = sandbox / "readme-project"
        readme.mkdir()
        (readme / "README.md").write_text("# **Sales [Desk](https://example.test)**\n", encoding="utf-8")
        require(project_display_name(readme) == ("Sales Desk", "README H1"), "README H1 priority/cleaning failed")
        require(suggested_title(readme)[0] == "主控｜Sales Desk", "README title failed")

        manifest = sandbox / "manifest-project"
        manifest.mkdir()
        (manifest / "package.json").write_text(json.dumps({"name": "manifest-app"}), encoding="utf-8")
        require(project_display_name(manifest) == ("manifest-app", "project manifest"), "manifest fallback failed")

        fallback = sandbox / "fallback-project"
        fallback.mkdir()
        require(project_display_name(fallback) == ("fallback-project", "directory basename"), "basename fallback failed")

        for project, expected in ((readme, "主控｜Sales Desk"), (manifest, "主控｜manifest-app"), (fallback, "主控｜fallback-project")):
            output = inspect(project)
            require(f"TITLE_SUGGESTED={expected}" in output, f"inspect title missing for {project.name}")
            require("RENAME_ACTION=codex_app__set_thread_title" in output, "client rename action missing")
            require("TITLE_RENAME=pending" in output, "honest pending state missing")

        team = sandbox / "existing-team"
        (team / ".codex" / "team").mkdir(parents=True)
        (team / "README.md").write_text("# Existing Team\n", encoding="utf-8")
        (team / ".codex" / "team-bootstrap.json").write_text(
            json.dumps({"schema_version": "2.0", "skill_version": "2.0.1"}), encoding="utf-8"
        )
        team_output = inspect(team)
        require("ROUTE_DETAIL=existing-team:v2" in team_output, "existing team route failed")
        require("TITLE_SUGGESTED=主控｜Existing Team" in team_output, "existing team title failed")
        print("PASS title rename regression: new, existing project, fallback, existing team")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
