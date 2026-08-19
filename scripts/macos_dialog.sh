#!/bin/bash
# Safe macOS dialogs from bash (handles newlines, quotes, and paths).

_macos_dialog() {
  local icon="$1"
  local message="$2"
  osascript \
    -e 'on run argv' \
    -e 'set theMessage to item 1 of argv' \
    -e 'set theIcon to item 2 of argv' \
    -e 'if theIcon is "stop" then' \
    -e '  display dialog theMessage buttons {"OK"} default button 1 with title "EfficiencyFinder" with icon stop' \
    -e 'else' \
    -e '  display dialog theMessage buttons {"OK"} default button 1 with title "EfficiencyFinder" with icon note' \
    -e 'end if' \
    -e 'end run' \
    -- "$message" "$icon"
}

macos_alert() {
  _macos_dialog note "$1"
}

macos_alert_error() {
  _macos_dialog stop "$1"
}

macos_notify() {
  osascript \
    -e 'on run argv' \
    -e 'display notification (item 1 of argv) with title "EfficiencyFinder"' \
    -e 'end run' \
    -- "$1"
}
