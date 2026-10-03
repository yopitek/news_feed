#!/usr/bin/env bash
#
# Refresh the Dcard snapshot and publish it.
#
# Dcard is Cloudflare-protected, so the GitHub Actions runner cannot read it; the
# snapshot in data/dcard_latest.json is collected on this machine with Brave and
# committed. This script is the scheduled entry point for that job.
#
# Intended crontab entry (07:30 local, 30 min before the 08:00 digest):
#   30 7 * * * /absolute/path/to/news_feed/tools/daily_dcard_sync.sh
#
# Exit codes: 0 = snapshot unchanged or successfully pushed, 1 = collection or
# push failed (details in the log).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

LOG_DIR="$REPO_ROOT/logs"
LOG_FILE="$LOG_DIR/dcard_sync.log"
mkdir -p "$LOG_DIR"

# cron gives a minimal environment; make `bsk` and a usable python discoverable.
export PATH="$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# The collector is stdlib-only. Clearing PYTHONPATH keeps it hermetic and stops
# any inherited sitecustomize/.pth shim from interfering with the run.
export PYTHONPATH=""

if [ -x "$REPO_ROOT/.venv/bin/python3" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python3"
else
    PYTHON="$(command -v python3)"
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

log "--- start (python=$PYTHON) ---"

if ! "$PYTHON" "$REPO_ROOT/tools/collect_dcard.py" >> "$LOG_FILE" 2>&1; then
    log "collect_dcard.py failed; leaving the existing snapshot untouched"
    exit 1
fi

if git diff --quiet -- data/dcard_latest.json; then
    log "snapshot unchanged; nothing to publish"
    log "--- done ---"
    exit 0
fi

git add data/dcard_latest.json || { log "git add failed"; exit 1; }

if ! git commit -m "chore: refresh Dcard snapshot $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE" 2>&1; then
    log "git commit failed"
    exit 1
fi

if git push origin HEAD >> "$LOG_FILE" 2>&1; then
    log "pushed refreshed snapshot"
    log "--- done ---"
    exit 0
fi

log "git push failed; the commit is local and will be retried on the next run"
exit 1
