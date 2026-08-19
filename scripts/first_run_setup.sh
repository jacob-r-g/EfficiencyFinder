#!/bin/bash
# One-time setup: create .venv and install Python dependencies.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=macos_dialog.sh
source "$SCRIPT_DIR/macos_dialog.sh"

PROJECT="$1"
LOG="$PROJECT/setup.log"
HOST_ARCH="$(uname -m)"

python_ok() {
  local py="$1"
  [[ -n "$py" && -x "$py" ]] || return 1
  "$py" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

python_arch() {
  "$1" -c 'import platform; print(platform.machine())' 2>/dev/null
}

python_version() {
  "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null
}

# Prefer a Python whose CPU matches this Mac, and prefer 3.10–3.13 over 3.14
# (3.14 on Intel often has no matching numpy wheel, which caused the setup loop).
find_python() {
  local candidate best="" best_score=-1 score ver arch
  local seen=""
  for candidate in \
    "${PYTHON3:-}" \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/bin/python3.12 \
    /opt/homebrew/bin/python3.11 \
    /opt/homebrew/bin/python3.10 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3.13 \
    /usr/local/bin/python3.12 \
    /usr/local/bin/python3.11 \
    /usr/local/bin/python3.10 \
    /usr/local/bin/python3 \
    "$(command -v python3 2>/dev/null || true)" \
    /usr/bin/python3; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    case " $seen " in
      *" $candidate "*) continue ;;
    esac
    seen="$seen $candidate"
    python_ok "$candidate" || continue
    ver="$(python_version "$candidate")"
    arch="$(python_arch "$candidate")"
    score=0
    [[ "$arch" == "$HOST_ARCH" ]] && score=$((score + 100))
    case "$ver" in
      3.12) score=$((score + 20)) ;;
      3.13) score=$((score + 18)) ;;
      3.11) score=$((score + 16)) ;;
      3.10) score=$((score + 14)) ;;
      3.14) score=$((score + 2)) ;;
      *) score=$((score + 5)) ;;
    esac
    if [[ "$score" -gt "$best_score" ]]; then
      best="$candidate"
      best_score="$score"
    fi
  done
  [[ -n "$best" ]] || return 1
  echo "$best"
}

venv_ready() {
  [[ -x "$PROJECT/.venv/bin/python" ]] || return 1
  "$PROJECT/.venv/bin/python" -c "import PySide6, numpy, matplotlib" 2>/dev/null
}

install_deps() {
  local py="$1"
  rm -rf "$PROJECT/.venv"
  echo "--- creating virtual environment ---"
  echo "host arch: $HOST_ARCH"
  echo "python arch: $(python_arch "$py")"
  "$py" -m venv "$PROJECT/.venv"
  echo "--- upgrading pip ---"
  "$PROJECT/.venv/bin/python" -m pip install --upgrade pip
  echo "--- installing requirements (matching this Mac's CPU) ---"
  "$PROJECT/.venv/bin/pip" install --no-cache-dir --force-reinstall -r "$PROJECT/requirements.txt"
  echo "--- verifying imports ---"
  "$PROJECT/.venv/bin/python" -c "import PySide6, numpy, matplotlib; print('OK')"
}

run_setup() {
  local py
  if venv_ready && [[ "${FORCE_SETUP:-}" != "1" ]]; then
    return 0
  fi

  py="$(find_python)" || {
    macos_alert_error "Python 3.10 or newer is required but was not found.

Install Python 3.12 from https://www.python.org/downloads/
(check Add Python to PATH), then try again."
    return 1
  }

  {
    echo "=== EfficiencyFinder setup $(date) ==="
    echo "Using Python: $py ($("$py" --version 2>&1))"
    echo "Python CPU: $(python_arch "$py")   Mac CPU: $HOST_ARCH"
  } >"$LOG"

  macos_alert "First-time setup will download the app libraries (about 2-5 minutes).

You need an internet connection. Click OK to continue."

  macos_notify "Downloading libraries... this may take a few minutes." >/dev/null 2>&1 || true

  if ! install_deps "$py" >>"$LOG" 2>&1; then
    macos_alert_error "Setup failed. Details were saved to:

$LOG

This Mac may have mixed Intel/Apple Silicon Python.
Install Python 3.12 from python.org, delete the .venv folder
inside EfficiencyFinder, then run Setup again."
    return 1
  fi

  echo "=== setup complete $(date) ===" >>"$LOG"
  macos_alert "Setup finished. You can close this Terminal window after the app opens."
  return 0
}

if [[ "${2:-}" == "--check-only" ]]; then
  venv_ready
  exit $?
fi

run_setup
