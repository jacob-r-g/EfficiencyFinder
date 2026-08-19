#!/bin/bash
# One-time setup: create .venv and install Python dependencies.
# Called automatically on first launch, or via "Setup EfficiencyFinder.command".

set -u

PROJECT="$1"
LOG="$PROJECT/setup.log"

alert() {
  osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with title \"EfficiencyFinder\" with icon note"
}

alert_error() {
  osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with title \"EfficiencyFinder\" with icon stop"
}

find_python() {
  local candidate
  for candidate in \
    "${PYTHON3:-}" \
    "$(command -v python3 2>/dev/null || true)" \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    /usr/bin/python3; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

venv_ready() {
  [[ -x "$PROJECT/.venv/bin/python" ]] || return 1
  "$PROJECT/.venv/bin/python" -c "import PySide6, numpy, matplotlib" 2>/dev/null
}

run_setup() {
  local py
  if venv_ready && [[ "${FORCE_SETUP:-}" != "1" ]]; then
    return 0
  fi

  py="$(find_python)" || {
    alert_error "Python 3.10 or newer is required but was not found.

Install Python from https://www.python.org/downloads/ (check \"Add to PATH\"), then try again."
    return 1
  }

  {
    echo "=== EfficiencyFinder setup $(date) ==="
    echo "Using Python: $py ($("$py" --version 2>&1))"
  } >"$LOG"

  if ! venv_ready; then
    alert "First-time setup will download the app libraries (about 2–5 minutes).

You need an internet connection. Click OK to continue."
  fi

  osascript -e 'display notification "Downloading libraries… this may take a few minutes." with title "EfficiencyFinder"' >/dev/null 2>&1 || true

  {
    echo "--- creating virtual environment ---"
    "$py" -m venv "$PROJECT/.venv"
    echo "--- upgrading pip ---"
    "$PROJECT/.venv/bin/python" -m pip install --upgrade pip
    echo "--- installing requirements ---"
    "$PROJECT/.venv/bin/pip" install -r "$PROJECT/requirements.txt"
    echo "--- verifying imports ---"
    "$PROJECT/.venv/bin/python" -c "import PySide6, numpy, matplotlib; print('OK')"
    echo "=== setup complete $(date) ==="
  } >>"$LOG" 2>&1 || {
    alert_error "Setup failed. Details were saved to:

$LOG

Common fixes:
• Check your internet connection
• Install Python 3.10+ from python.org
• Double-click \"Setup EfficiencyFinder.command\" to try again"
    return 1
  }

  alert "Setup finished. EfficiencyFinder will open now."
  return 0
}

if [[ "${2:-}" == "--check-only" ]]; then
  venv_ready
  exit $?
fi

run_setup
