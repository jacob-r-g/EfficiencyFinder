#!/bin/bash
# Double-click to set up (first time) and open EfficiencyFinder.
# Use this every time to launch the app — do not rely on EfficiencyFinder.app alone.

set -u

cd "$(dirname "$0")"
PROJECT="$(pwd)"

# shellcheck source=scripts/paths.sh
source "./scripts/paths.sh"
# shellcheck source=scripts/macos_dialog.sh
source "./scripts/macos_dialog.sh"

clear_quarantine "$PROJECT"

if ! bash "./scripts/first_run_setup.sh" "$PROJECT" --check-only; then
  bash "./scripts/first_run_setup.sh" "$PROJECT" || exit 1
fi

EFFICIENCYFINDER_ROOT="$PROJECT" exec bash "./scripts/launch_app.sh"
