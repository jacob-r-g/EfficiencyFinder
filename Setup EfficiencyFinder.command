#!/bin/bash
# Double-click to install or repair EfficiencyFinder, then open the app.
cd "$(dirname "$0")"

source "./scripts/macos_dialog.sh"

if bash "./scripts/first_run_setup.sh" "$(pwd)" --check-only; then
  macos_alert "EfficiencyFinder is already set up. Opening the app now." >/dev/null
else
  bash "./scripts/first_run_setup.sh" "$(pwd)" || exit 1
fi

# Finder often blocks unsigned .app double-clicks; opening from here works,
# and clearing quarantine helps later double-clicks.
find "./EfficiencyFinder.app" -exec xattr -c {} \; 2>/dev/null || true
open "./EfficiencyFinder.app"
