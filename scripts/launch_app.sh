#!/bin/bash
# Launch the GUI from the real project folder (never a translocated temp copy).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=paths.sh
source "$SCRIPT_DIR/paths.sh"
# shellcheck source=macos_dialog.sh
source "$SCRIPT_DIR/macos_dialog.sh"

HINT="${1:-$SCRIPT_DIR/..}"
PROJECT="$(discover_project "$HINT")" || {
  macos_alert_error "Could not find the EfficiencyFinder folder.

Put the whole EfficiencyFinder folder in Applications, then double-click Setup EfficiencyFinder.command once."
  exit 1
}

save_install_root "$PROJECT"
clear_quarantine "$PROJECT"

if ! venv_is_ready "$PROJECT"; then
  bash "$PROJECT/scripts/first_run_setup.sh" "$PROJECT" || exit 1
fi

if ! venv_is_ready "$PROJECT"; then
  macos_alert_error "EfficiencyFinder still cannot start.

Double-click Setup EfficiencyFinder.command in:
$PROJECT"
  exit 1
fi

PYTHON="$PROJECT/.venv/bin/python"
MAIN="$PROJECT/main.py"
LOG="$PROJECT/launch.log"

cd "$PROJECT"
export PYTHONUNBUFFERED=1
export EFFICIENCYFINDER_ROOT="$PROJECT"
{
  echo "=== launch $(date) ==="
  echo "project: $PROJECT"
  echo "python: $PYTHON"
} >>"$LOG"

# Do not exec: keep this process as the .app so the Dock shows EfficiencyFinder,
# not a generic Python icon.
"$PYTHON" "$MAIN" >>"$LOG" 2>&1
