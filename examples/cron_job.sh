#!/usr/bin/env bash

SCRIPT_DIR="$(readlink -m "${0%/*}")"

export PATH="$HOME/.local/bin":$PATH

LOG="$SCRIPT_DIR"/cron_job.log

# rotate log when over 200KB
log_size="$(stat -c%s "$LOG")"
if (( log_size > 256000 )); then
  mv -f "$LOG" "$LOG".1
fi

{ printf "\nRun on " ; date; time "$SCRIPT_DIR"/update_reports.sh; } >> "$LOG" 2>&1
