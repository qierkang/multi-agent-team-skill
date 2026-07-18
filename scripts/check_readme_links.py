#!/usr/bin/env python3
"""Check local Markdown and HTML links in all README variants."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
READMES = (ROOT / "README.md", ROOT / "docs/README_en.md", ROOT / "docs/README_zh-tw.md")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
HTML_LINK = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']")


def local_target(document: Path, raw: str) -> Path | None:
    value = raw.strip().split()[0].strip("<>")
    if not value or value.startswith(("#", "http://", "https://", "mailto:", "data:")):
        return None
    value = unquote(value.split("#", 1)[0].split("?", 1)[0])
    return (document.parent / value).resolve()


def main() -> int:
    failures: list[str] = []
    checked = 0
    for document in READMES:
        if not document.is_file():
            failures.append(f"missing README: {document.relative_to(ROOT)}")
            continue
        text = document.read_text(encoding="utf-8")
        for raw in [*MARKDOWN_LINK.findall(text), *HTML_LINK.findall(text)]:
            target = local_target(document, raw)
            if target is None:
                continue
            checked += 1
            try:
                target.relative_to(ROOT)
            except ValueError:
                failures.append(f"outside repository: {document.relative_to(ROOT)} -> {raw}")
                continue
            if not target.exists():
                failures.append(f"missing target: {document.relative_to(ROOT)} -> {raw}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"STATE=readme_links_failed; checked={checked}; failures={len(failures)}")
        return 1
    print(f"PASS README local links and visual references; checked={checked}")
    print("STATE=readme_links_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

