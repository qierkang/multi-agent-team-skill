#!/usr/bin/env python3
"""Deterministically derive the Codex main-thread title for a project."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


MAX_NAME_LENGTH = 72
H1_RE = re.compile(r"^\s*#\s+(.+?)\s*#*\s*$")


def _clean(value: object) -> str:
    text = str(value or "")
    text = re.sub(r"!?(?:\[([^\]]+)\]|\(([^)]+)\))", lambda m: m.group(1) or "", text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"\s+", " ", text).strip(" #\t\r\n")
    return text[:MAX_NAME_LENGTH].rstrip()


def _readme_name(root: Path) -> str | None:
    readme = root / "README.md"
    if not readme.is_file():
        return None
    for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = H1_RE.match(line)
        name = _clean(match.group(1)) if match else ""
        if name:
            return name
    return None


def _manifest_name(root: Path) -> str | None:
    package = root / "package.json"
    if package.is_file():
        try:
            name = json.loads(package.read_text(encoding="utf-8")).get("name")
            if _clean(name):
                return _clean(name)
        except (OSError, json.JSONDecodeError):
            pass
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            name = data.get("project", {}).get("name")
            if _clean(name):
                return _clean(name)
        except (OSError, tomllib.TOMLDecodeError):
            pass
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        try:
            name = tomllib.loads(cargo.read_text(encoding="utf-8")).get("package", {}).get("name")
            if _clean(name):
                return _clean(name)
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return None


def project_display_name(root: Path) -> tuple[str, str]:
    """Return (display name, evidence source) using the documented priority."""
    for source, getter in (("README H1", _readme_name), ("project manifest", _manifest_name)):
        name = getter(root)
        if name:
            return name, source
    return _clean(root.name) or "项目", "directory basename"


def suggested_title(root: Path) -> tuple[str, str]:
    name, source = project_display_name(root)
    return f"主控｜{name}", source


def rename_action(title: str) -> str:
    return f"codex_app__set_thread_title(title={title!r})"
