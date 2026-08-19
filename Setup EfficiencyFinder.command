#!/bin/bash
# First time: install libraries. After that: open the EfficiencyFinder app.

set -u

cd "$(dirname "$0")"
PROJECT="$(pwd)"

# shellcheck source=scripts/paths.sh
source "./scripts/paths.sh"
# shellcheck source=scripts/macos_dialog.sh
source "./scripts/macos_dialog.sh"

clear_quarantine "$PROJECT"
save_install_root "$PROJECT"

if ! venv_is_ready "$PROJECT"; then
  bash "./scripts/first_run_setup.sh" "$PROJECT" || exit 1
fi

save_install_root "$PROJECT"
clear_quarantine "$PROJECT"

# Open the real .app (Finder shortcut / Dock). Do not start Python from Terminal.
open "$PROJECT/EfficiencyFinder.app"
