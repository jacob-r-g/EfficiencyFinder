#!/bin/bash
# Resolve the EfficiencyFinder project folder (contains main.py).

CONFIG_DIR="${HOME}/Library/Application Support/EfficiencyFinder"
INSTALL_ROOT_FILE="$CONFIG_DIR/install_root.txt"

is_translocated() {
  [[ "${1:-}" == *AppTranslocation* ]]
}

project_looks_valid() {
  local dir="${1:-}"
  [[ -n "$dir" && -f "$dir/main.py" && -f "$dir/requirements.txt" && -d "$dir/scripts" ]]
}

venv_is_ready() {
  local dir="${1:-}"
  [[ -x "$dir/.venv/bin/python" ]] || return 1
  "$dir/.venv/bin/python" -c "import PySide6, numpy, matplotlib" 2>/dev/null
}

save_install_root() {
  local dir="${1:-}"
  project_looks_valid "$dir" || return 1
  mkdir -p "$CONFIG_DIR"
  printf '%s\n' "$dir" >"$INSTALL_ROOT_FILE"
}

read_install_root() {
  local dir=""
  [[ -f "$INSTALL_ROOT_FILE" ]] || return 1
  dir="$(<"$INSTALL_ROOT_FILE")"
  project_looks_valid "$dir" || return 1
  echo "$dir"
}

resolve_project_root() {
  local dir="${1:-$(pwd)}"
  if [[ -L "$dir" ]]; then
    dir="$(cd "$(dirname "$dir")" && pwd)/$(basename "$dir")"
  fi
  dir="$(cd "$dir" && pwd)"
  while [[ "$dir" != "/" ]]; do
    if project_looks_valid "$dir"; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

discover_project() {
  local dir candidate
  if [[ -n "${EFFICIENCYFINDER_ROOT:-}" ]] && project_looks_valid "$EFFICIENCYFINDER_ROOT"; then
    echo "$EFFICIENCYFINDER_ROOT"
    return 0
  fi
  if dir="$(read_install_root)"; then
    echo "$dir"
    return 0
  fi
  if [[ -n "${1:-}" ]]; then
    dir="$(resolve_project_root "$1" 2>/dev/null || true)"
    if [[ -n "$dir" ]] && ! is_translocated "$dir"; then
      echo "$dir"
      return 0
    fi
  fi
  for candidate in \
    "/Applications/EfficiencyFinder" \
    "${HOME}/Applications/EfficiencyFinder" \
    "${HOME}/Desktop/EfficiencyFinder" \
    "${HOME}/Downloads/EfficiencyFinder"; do
    if project_looks_valid "$candidate"; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

clear_quarantine() {
  local root="$1"
  xattr -cr "$root" 2>/dev/null || true
}
