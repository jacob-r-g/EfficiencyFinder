#!/bin/bash
# Resolve the EfficiencyFinder project folder (contains main.py).
resolve_project_root() {
  local dir="${1:-$(pwd)}"
  if [[ -L "$dir" ]]; then
    dir="$(cd "$(dirname "$dir")" && pwd)/$(basename "$dir")"
  fi
  dir="$(cd "$dir" && pwd)"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/main.py" && -f "$dir/requirements.txt" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

# Clear quarantine flags so macOS does not run the app from a temp copy.
clear_quarantine() {
  local root="$1"
  xattr -cr "$root" 2>/dev/null || true
}
