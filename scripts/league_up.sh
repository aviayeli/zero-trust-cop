#!/usr/bin/env bash
# Expose both of our peers as public HTTPS endpoints for a league match.
#
# TWO ngrok agents, one tunnel each, under two SEPARATE accounts. The free
# tier allows one simultaneous agent session per account, so a single agent
# serving both tunnels needs a paid plan; two accounts sidestep that.
#
# The two agents must not share a web API port. Both default to
# 127.0.0.1:4040, and the second to start would exit "address already in use"
# with its tunnel never coming up — so each config pins its own web_addr
# (cop 4040, thief 4041) and each agent's public URL is read from its OWN API.
#
# The declaration is UPDATED here, not merely printed: it ships naming
# 127.0.0.1, and a graded artifact went out advertising loopback for a match
# that was really played over these tunnels. Advertising the URL we just
# created for that role also removes the hand-paste that could swap them.
#
# The ports live in config/<role>/game.toml. They are repeated in the ngrok
# configs because ngrok cannot read TOML, so this script CHECKS the two agree
# and refuses to start on drift rather than tunnelling to a dead port.
#
#   scripts/league_up.sh            # split ports: two agents, two URLs
#   scripts/league_up.sh --unified  # PRD_11b: ONE agent, ONE URL
#   scripts/league_up.sh --stop     # stop whatever this script started
#
# Unified mode is opt-in. The split-port topology is the one that has actually
# carried a live exchange, and it stays the default until the unified one has
# played a graded series.
set -euo pipefail

ROOT=${ZTC_CONFIG_ROOT:-config}
PY=${PYTHON:-.venv/bin/python}
COP_CONFIG=${COP_CONFIG:-scripts/ngrok_cop.yml}
THIEF_CONFIG=${THIEF_CONFIG:-scripts/ngrok_thief.yml}
UNIFIED_CONFIG=${UNIFIED_CONFIG:-scripts/ngrok_unified.yml}
WAIT_SECONDS=${NGROK_WAIT_SECONDS:-30}

UNIFIED=0
[[ ${1:-} == "--unified" ]] && { UNIFIED=1; shift; }

# The port key each mode binds, and the tunnels it expects.
PORT_KEY=my_port
AGENTS=("police:$COP_CONFIG:cop" "thief:$THIEF_CONFIG:thief")
NAMES=(cop thief)
if [[ $UNIFIED == 1 ]]; then
  PORT_KEY=unified_port
  AGENTS=("police:$UNIFIED_CONFIG:unified")
  NAMES=(unified)
fi

if [[ ${1:-} == "--stop" ]]; then
  for name in cop thief unified; do
    pidfile=".ngrok-$name.pid"
    if [[ -f $pidfile ]]; then
      kill "$(cat "$pidfile")" 2>/dev/null || true
      rm -f "$pidfile"
      echo "[ok] $name agent stopped"
    fi
  done
  exit 0
fi

toml_port() {  # role, key -> the port this mode binds for that peer
  "$PY" - "$ROOT/$1/game.toml" "$2" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as handle:
    print(tomllib.load(handle)["network"][sys.argv[2]])
PY
}

yaml_field() {  # config, tunnel name, field -> its value
  "$PY" - "$1" "$2" "$3" <<'PY'
import re, sys
# Deliberately not PyYAML: it is not a dependency of this project, and these
# two files are ours and three keys deep.
text = open(sys.argv[1], encoding="utf-8").read()
block = text.split(f"{sys.argv[2]}:", 1)[-1]
found = re.search(rf"^\s+{sys.argv[3]}:\s*(\S+)", block, re.M)
print(found.group(1) if found else "")
PY
}

# --- one source of truth for the ports -------------------------------------
for spec in "${AGENTS[@]}"; do
  IFS=: read -r role config name <<< "$spec"
  [[ -f $config ]] || { echo "[!!] missing $config"; exit 1; }
  configured=$(toml_port "$role" "$PORT_KEY")
  tunnelled=$(yaml_field "$config" "$name" addr)
  if [[ $configured != "$tunnelled" ]]; then
    echo "[!!] $name: $config tunnels port $tunnelled, but"
    echo "     $ROOT/$role/game.toml says $PORT_KEY = $configured."
    echo "     Fix one of them; tunnelling to a dead port looks exactly like"
    echo "     the opponent being unreachable, from their side."
    exit 1
  fi
  echo "[ok] $name port $configured agrees with $config"
done

# --- start both agents -----------------------------------------------------
declare -A API
for spec in "${AGENTS[@]}"; do
  IFS=: read -r role config name <<< "$spec"
  pidfile=".ngrok-$name.pid"
  if [[ -f $pidfile ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "[!!] a $name agent from a previous run is still up (pid $(cat "$pidfile"))"
    echo "     run '$0 --stop' first"
    exit 1
  fi
  web=$(yaml_field "$config" agent web_addr)
  [[ -n $web ]] || { echo "[!!] $config pins no agent.web_addr; two agents would collide on 4040"; exit 1; }
  API[$name]="http://$web/api/tunnels"

  ngrok start "$name" --config "$config" --log stdout > ".ngrok-$name.log" 2>&1 &
  echo $! > "$pidfile"
  echo "[..] $name agent pid $(cat "$pidfile"), api $web"
done

# --- read each agent's public URL from its OWN api -------------------------
# Polled rather than slept: a tunnel up in two seconds should not cost fifteen,
# and one that never comes up must say so rather than leaving a URL-shaped
# blank in the operator's hand.
declare -A PUBLIC
for name in "${NAMES[@]}"; do
  for _ in $(seq "$WAIT_SECONDS"); do
    url=$("$PY" - "${API[$name]}" "$name" <<'PY' || true
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as answer:
        tunnels = json.load(answer)["tunnels"]
except Exception:
    raise SystemExit(1)
for tunnel in tunnels:
    if tunnel["proto"] == "https" and tunnel["name"].split(" ")[0] == sys.argv[2]:
        print(tunnel["public_url"])
        break
else:
    raise SystemExit(1)
PY
)
    [[ -n ${url:-} ]] && break
    sleep 1
  done
  if [[ -z ${url:-} ]]; then
    echo "[!!] the $name tunnel did not come up in ${WAIT_SECONDS}s; see .ngrok-$name.log"
    exit 1
  fi
  PUBLIC[$name]=$url
done

echo
if [[ $UNIFIED == 1 ]]; then
  echo "[ok] unified ${PUBLIC[unified]}/mcp"
  echo
  echo "SEND THAT ONE URL. Both our roles answer it, so there is no rule for"
  echo "the opponent to get backwards. Serve it with:"
  echo "  PYTHONPATH=src $PY -m scripts.unified_serve --first-role police"
  echo
  echo "Advertised for BOTH roles in the declaration the opponent reads:"
  PYTHONPATH=src $PY -m scripts.setup_league_match --role police --public-url "${PUBLIC[unified]}" | head -1
  PYTHONPATH=src $PY -m scripts.setup_league_match --role thief  --public-url "${PUBLIC[unified]}" | head -1
else
  echo "[ok] cop   ${PUBLIC[cop]}/mcp"
  echo "[ok] thief ${PUBLIC[thief]}/mcp"
  echo
  echo "SEND BOTH TO THE OPPONENT. They dial the side they are playing AGAINST:"
  echo "as their thief they call our cop URL, as their cop our thief URL."
  echo
  echo "Advertised in the declaration the opponent reads:"
  PYTHONPATH=src $PY -m scripts.setup_league_match --role police --public-url "${PUBLIC[cop]}"   | head -1
  PYTHONPATH=src $PY -m scripts.setup_league_match --role thief  --public-url "${PUBLIC[thief]}" | head -1
fi
