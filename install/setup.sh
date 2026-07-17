#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v python3 >/dev/null 2>&1 || {
  echo "FAIL python3 not found"
  echo "STATE=setup_failed"
  exit 1
}

python3 "$ROOT/scripts/health_check.py"
echo "STATE=setup_ready"
