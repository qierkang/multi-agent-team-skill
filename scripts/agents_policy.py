#!/usr/bin/env python3
"""Shared fail-closed checks for project AGENTS control-plane policy."""

from __future__ import annotations

import re
from dataclasses import dataclass


MANAGED_BLOCKS = (
    ("<!-- multi-agent-team:start -->", "<!-- multi-agent-team:end -->"),
    ("<!-- team-init:start -->", "<!-- team-init:end -->"),
)


@dataclass(frozen=True)
class AgentsPolicyConflict:
    rule: str
    line: int
    text: str

    def render(self) -> str:
        return f"line {self.line} [{self.rule}]: {self.text}"


CONFLICT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "direct-mode",
        re.compile(r"(?:快速直改|聚焦开发).{0,80}(?:默认|主任务|自行|直接)", re.IGNORECASE),
    ),
    (
        "main-direct-implementation",
        re.compile(
            r"主任务.{0,40}(?:自行完成|自行(?:修改|实现|编码)|直接(?:定位[、,，]?修改|修改|实现|编码))",
            re.IGNORECASE,
        ),
    ),
    (
        "team-opt-in-only",
        re.compile(
            r"(?:安装了.{0,30}multi-agent-team.{0,30}不等于默认启用|多\s*Agent\s*协作.{0,40}仅在)",
            re.IGNORECASE,
        ),
    ),
    (
        "english-main-direct",
        re.compile(
            r"\bmain\s+(?:task|thread|agent).{0,50}\b(?:directly|itself)\b.{0,30}\b(?:implement|edit|modify|code)\b",
            re.IGNORECASE,
        ),
    ),
)


def unmanaged_agents_text(text: str) -> str:
    """Blank managed blocks while preserving line numbers for diagnostics."""
    output = text
    for start_marker, end_marker in MANAGED_BLOCKS:
        pattern = re.compile(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            re.DOTALL,
        )
        output = pattern.sub(lambda match: "\n" * match.group(0).count("\n"), output)
    return output


def find_control_plane_conflicts(text: str) -> list[AgentsPolicyConflict]:
    unmanaged = unmanaged_agents_text(text)
    conflicts: list[AgentsPolicyConflict] = []
    seen: set[tuple[str, int]] = set()
    for line_number, raw_line in enumerate(unmanaged.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("<!--"):
            continue
        for rule, pattern in CONFLICT_RULES:
            key = (rule, line_number)
            if pattern.search(line) and key not in seen:
                seen.add(key)
                conflicts.append(AgentsPolicyConflict(rule, line_number, line[:240]))
    return conflicts


def conflict_messages(text: str) -> list[str]:
    return [item.render() for item in find_control_plane_conflicts(text)]
