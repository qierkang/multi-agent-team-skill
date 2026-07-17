#!/usr/bin/env bash
set -euo pipefail

# 用法：bash scripts/verify_assets.sh [skill-root]
# 校验正式视觉资产及 README 中的本地图片引用。

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
if [[ ! -d "$ROOT" ]]; then
  echo "FAIL skill root not found: $ROOT" >&2
  exit 2
fi

python3 - "$ROOT" <<'PY'
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
manifest_path = root / "assets" / "asset-manifest.json"
fails = []
oks = []

if not manifest_path.is_file():
    print("FAIL asset manifest missing")
    print("STATE=asset_failed")
    raise SystemExit(1)

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
entries = manifest.get("required", []) + manifest.get("extra", [])
registered = {entry.get("path") for entry in entries if entry.get("path")}
for entry in manifest.get("required", []):
    relative = entry.get("path", "")
    image_path = root / relative
    if not entry.get("generated_at") or entry.get("generated_by") != "image_gen":
        fails.append(f"missing image_gen provenance: {relative}")
    elif not image_path.is_file():
        fails.append(f"required asset missing: {relative}")
    else:
        oks.append(f"required asset: {relative}")

social = root / "assets" / "social-preview.png"
if not social.is_file():
    fails.append("social preview missing")
elif social.stat().st_size >= 1024 * 1024:
    fails.append(f"social preview exceeds 1 MiB: {social.stat().st_size}")
else:
    oks.append(f"social preview under 1 MiB: {social.stat().st_size}")

image_refs = set()
for readme in (root / "README.md", root / "docs" / "README_en.md"):
    if not readme.is_file():
        fails.append(f"README missing: {readme.relative_to(root)}")
        continue
    text = readme.read_text(encoding="utf-8", errors="ignore")
    for path in re.findall(r'<img[^>]+src="([^"?]+)', text) + re.findall(r'!\[[^]]*\]\(([^)?]+)', text):
        if path.startswith(("http://", "https://", "#")):
            continue
        target = (readme.parent / path).resolve()
        try:
            relative = str(target.relative_to(root))
        except ValueError:
            continue
        image_refs.add(relative)
        if relative not in registered:
            fails.append(f"README asset not registered: {readme.relative_to(root)} -> {relative}")

for relative in registered:
    if relative not in image_refs and relative != "assets/social-preview.png":
        fails.append(f"registered asset not referenced by README: {relative}")

for message in oks:
    print(f"PASS {message}")
for message in fails:
    print(f"FAIL {message}")
if fails:
    print("STATE=asset_failed")
    raise SystemExit(1)
print("STATE=asset_done")
PY
