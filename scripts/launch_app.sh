#!/bin/bash
# Launch the GUI. Requires setup to have been run already.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths.sh
source "$SCRIPT_DIR/paths.sh"
# shellcheck source=macos_dialog.sh
source "$SCRIPT_DIR/macos_dialog.sh"

PROJECT="${EFFICIENCYFINDER_ROOT:-}"
if [[ -z "$PROJECT" ]]; then
  PROJECT="$(resolve_project_root "$SCRIPT_DIR/..")" || {
    macos_alert_error "Could not find the EfficiencyFinder project folder (main.py)."
    exit 1
  }
fi

PYTHON="$PROJECT/.venv/bin/python"
MAIN="$PROJECT/main.py"
LOG="$PROJECT/launch.log"

if [[ ! -x "$PYTHON" ]] || ! "$PYTHON" -c "import PySide6, numpy, matplotlib" 2>/dev/null; then
  macos_alert_error "EfficiencyFinder is not set up yet.

Double-click Setup EfficiencyFinder.command in:
$PROJECT"
  exit 1
fi

clear_quarantine "$PROJECT"

cd "$PROJECT"
export PYTHONUNBUFFERED=1
{
  echo "=== launch $(date) ==="
  echo "project: $PROJECT"
  echo "python: $PYTHON"
} >>"$LOG"

exec "$PYTHON" "$MAIN" >>"$LOG" 2>&1
