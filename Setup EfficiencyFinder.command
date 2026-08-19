#!/bin/bash
# Double-click to install or repair EfficiencyFinder, then open the app.
cd "$(dirname "$0")"

if bash "./scripts/first_run_setup.sh" "$(pwd)" --check-only; then
  osascript -e 'display dialog "EfficiencyFinder is already set up. Opening the app now." buttons {"OK"} default button 1 with title "EfficiencyFinder" with icon note' >/dev/null
else
  bash "./scripts/first_run_setup.sh" "$(pwd)" || exit 1
fi

open "./EfficiencyFinder.app"
