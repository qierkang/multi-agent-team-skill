#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ $# -gt 0 ]]; then
  echo "usage: $0 [--apply]" >&2
  exit 2
fi

TARGETS=(
  "${HOME}/.agents/skills/multi-agent-team-skill"
  "${CODEX_HOME:-${HOME}/.codex}/skills/multi-agent-team-skill"
)

for target in "${TARGETS[@]}"; do
  echo "LINK $target -> $ROOT"
  if [[ $APPLY -eq 1 ]]; then
    mkdir -p "$(dirname "$target")"
    if [[ -e "$target" && ! -L "$target" ]]; then
      echo "FAIL target exists and is not a symlink: $target" >&2
      echo "STATE=sync_failed"
      exit 1
    fi
    ln -sfn "$ROOT" "$target"
  fi
done

if [[ $APPLY -eq 0 ]]; then
  echo "DRY_RUN=1, no links written"
  echo "STATE=sync_plan_ready"
else
  echo "STATE=sync_done"
fi
