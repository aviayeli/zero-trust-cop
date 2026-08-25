#!/usr/bin/env bash
# Keep our peers answering until the match is done.
#
# Our peers exist only while a run does, and a run ends whenever the opponent's
# endpoint goes away -- which for bb-ai-12 is after every sub-game, because
# their peer exits once it has pushed its last turn. Relaunching by hand each
# time means we are down for however long it takes someone to notice.
#
# This supervises: run, and when the run exits, wait and run again. It does NOT
# retry into a series already underway -- each launch is a fresh series, which
# is what `connect_and_play` already refuses to do on its own once a turn has
# been pushed.
#
#   scripts/stay_up.sh                      # supervise until stopped
#   touch .stay_up.stop                     # ask it to stop after this attempt
#   scripts/stay_up.sh --stop               # same, and kill a running attempt
#
# Every attempt's output lands in logs/stay_up/<timestamp>.log, so a run that
# finally settles a sub-game is not lost in a terminal buffer.
set -euo pipefail

PY=${PYTHON:-.venv/bin/python}
STOP_FILE=${STAY_UP_STOP:-.stay_up.stop}
PAUSE=${STAY_UP_PAUSE:-10}
LOG_DIR=${STAY_UP_LOGS:-logs/stay_up}
OPPONENT=${OPPONENT_URL:-https://comic-leverage-paprika.ngrok-free.dev/mcp}
OPPONENT_ID=${OPPONENT_ID:-bb-ai-12}
SUB_GAMES=${SUB_GAMES:-2}
FIRST_ROLE=${FIRST_ROLE:-police}
SEED=${SEED:-20260825}
WAIT_MINUTES=${WAIT_MINUTES:-45}
EXTRA=${STAY_UP_EXTRA:---no-artifacts}

if [[ ${1:-} == "--stop" ]]; then
  touch "$STOP_FILE"
  pkill -f "scripts.run_reference_match --seed $SEED" 2>/dev/null || true
  echo "[ok] stop requested; any running attempt killed"
  exit 0
fi

rm -f "$STOP_FILE"
mkdir -p "$LOG_DIR"
echo "[..] supervising. 'touch $STOP_FILE' or '$0 --stop' to end."

attempt=0
while [[ ! -f $STOP_FILE ]]; do
  attempt=$((attempt + 1))
  stamp=$(date '+%Y%m%d-%H%M%S')
  log="$LOG_DIR/$stamp.log"
  echo "[..] attempt $attempt at $(date '+%H:%M:%S') -> $log"

  set +e
  PYTHONPATH=src "$PY" -u -m scripts.run_reference_match \
      --seed "$SEED" --sub-games "$SUB_GAMES" --first-role "$FIRST_ROLE" \
      --wait-minutes "$WAIT_MINUTES" --opponent-id "$OPPONENT_ID" \
      --opponent-url "$OPPONENT" $EXTRA > "$log" 2>&1
  code=$?
  set -e

  steps=$(grep -c 'pushed MOVE' "$log" || true)
  echo "[--] attempt $attempt exited $code after $steps step(s)"
  # A settled sub-game is the thing worth shouting about.
  if grep -q 'their_audit=accepted' "$log" 2>/dev/null; then
    echo "[ok] AUDIT ACCEPTED in $log -- a sub-game actually settled"
  fi

  [[ -f $STOP_FILE ]] && break
  sleep "$PAUSE"
done

rm -f "$STOP_FILE"
echo "[ok] supervisor stopped after $attempt attempt(s)"
