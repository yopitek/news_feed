#!/usr/bin/env bash
#
# Refresh the locally-collected snapshots and publish them.
#
# Two sources cannot be read from GitHub Actions and are snapshotted here instead:
#
#   Dcard  Cloudflare-protected — 403 + Turnstile challenge for every server-side
#          request. Collected with Brave via tools/collect_dcard.py.
#   PTT    Not Cloudflare, but the board pages 403 datacenter IP ranges. Every
#          board and every Atom fallback is 403 from an Actions runner (Azure,
#          US) while all return 200 from this machine. Collected over plain HTTP
#          via tools/collect_ptt.py — no browser needed.
#
# Intended schedule: 07:30 local, 30 minutes before the 08:00 digest, so CI
# renders a snapshot from the same morning. Installed as the LaunchAgent
# ~/Library/LaunchAgents/com.benny.social-sync.plist.
#
# Exit codes: 0 = snapshots unchanged or successfully pushed, 1 = at least one
# collector failed (details in the log).
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

LOG_DIR="$REPO_ROOT/logs"
LOG_FILE="$LOG_DIR/social_sync.log"
mkdir -p "$LOG_DIR"

# launchd/cron give a minimal environment; make `bsk` and a usable python
# discoverable, and give git a chance to find gh for the credential helper.
export PATH="$HOME/.local/bin:$HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
# Clearing PYTHONPATH keeps the run hermetic and stops any inherited
# sitecustomize/.pth shim from interfering.
export PYTHONPATH=""
# Fail fast instead of hanging on a credential prompt: nobody is watching this job.
export GIT_TERMINAL_PROMPT=0

if [ -x "$REPO_ROOT/.venv/bin/python3" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python3"
else
    PYTHON="$(command -v python3)"
fi

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

log "--- start (python=$PYTHON) ---"

failed=0

# PTT first: it is fast (plain HTTP, ~10s) and gives us an early read on
# network/credential problems before the slower browser-based Dcard pass.
if "$PYTHON" "$REPO_ROOT/tools/collect_ptt.py" >> "$LOG_FILE" 2>&1; then
    log "collect_ptt.py ok"
else
    log "collect_ptt.py failed; leaving the existing PTT snapshot untouched"
    failed=1
fi

if "$PYTHON" "$REPO_ROOT/tools/collect_dcard.py" >> "$LOG_FILE" 2>&1; then
    log "collect_dcard.py ok"
else
    log "collect_dcard.py failed; leaving the existing Dcard snapshot untouched"
    failed=1
fi

SNAPSHOTS="data/dcard_latest.json data/ptt_latest.json"

if git diff --quiet -- $SNAPSHOTS; then
    log "snapshots unchanged; nothing to publish"
    log "--- done (failed=$failed) ---"
    [ "$failed" -eq 0 ] || exit 1
    exit 0
fi

git add $SNAPSHOTS || { log "git add failed"; exit 1; }

if ! git commit -m "chore: refresh social snapshots $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE" 2>&1; then
    log "git commit failed"
    exit 1
fi

# The 08:00 digest workflow also commits to main (docs/index.html and the
# output JSON), so an unattended push from here regularly lands behind the
# remote. Rebase first — the two jobs touch disjoint paths, so it is clean —
# and only then push. Without this the job fails every day the digest has run
# since the last snapshot, which is most days.
if ! git pull --rebase --autostash origin main >> "$LOG_FILE" 2>&1; then
    log "git pull --rebase failed; leaving the commit local and aborting the rebase"
    git rebase --abort >> "$LOG_FILE" 2>&1 || true
    exit 1
fi

if git push origin HEAD >> "$LOG_FILE" 2>&1; then
    log "pushed refreshed snapshots"
    log "--- done (failed=$failed) ---"
    [ "$failed" -eq 0 ] || exit 1
    exit 0
fi

log "git push failed; the commit is local and will be retried on the next run"
exit 1
