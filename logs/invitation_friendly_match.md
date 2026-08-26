# Outbound — friendly match invitation, written for the opponent's agent

Everything below is verified against this repo before sending:

- both tunnels live, returning 502 (up, peers not started) at time of writing
- `config/declaration.json` advertises the two real URLs, not loopback
- the signature and test vector round-trip through `mcp_server.interop`
- terms are the SHIPPED defaults, unchanged: no renegotiation to fail on

Send as-is. Fill in nothing.

---

Hi — ready for the friendly match whenever you are. This message is written to
be handed straight to your agent; everything it needs is below.

## Who we are

- **Team code:** `aviayeli`
- **Commit:** `ea6166f`
- **Wire:** reference-v3 (`negotiate`, `receive_turn`, `submit_audit`,
  `receive_control`)

## Our two endpoints

We run cop and thief as two peers behind two tunnels, and the sides alternate
every sub-game. Dial the endpoint serving the role you are playing
**against**:

| You are playing | Call our endpoint |
|---|---|
| thief | our **cop** — `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp` |
| cop | our **thief** — `https://cardinal-shell-moistness.ngrok-free.dev/mcp` |

If you serve both your roles from a single endpoint, that is fine — tell us
and we will dial one URL for the whole series. We support both shapes.

**Reading our health from outside:** a plain `GET` on those URLs returns
**HTTP 400**, not 200. That is the MCP server correctly refusing a non-session
request, and it means a live peer. **502** means our peers are not started
yet — they exist only while a match run is up, by design.

## Handshake

Every message is a **single envelope argument**:
`negotiate(message={...})`, `receive_turn(message={...})`,
`submit_audit(payload={...})`, `receive_control(message={...})`. Flat
parameters fail schema validation on the caller's side before reaching us.

```
signature = SHA256( canonical_json(terms) + "|" + nonce )
```

- `canonical_json` is compact, key-sorted, native UTF-8:
  `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
- the separator is a **single** pipe `|` (U+007C) — not `||`, not a bare
  concatenation
- `sub_game_number` and `role` ride **beside** `terms`, never inside it: the
  terms are a flat signed set and an extra key changes the hash both sides
  are verifying

**We are playing the shipped contract defaults — no renegotiation.** All
fourteen terms:

```json
{"axis_origin_corner": "top-left", "axis_start_index": 0, "barriers_max": 14,
 "board_size": 7, "cop_start": [0, 0], "decay_per_step": 0.1,
 "emit_intensity": 0.9, "hint_max_words": 15, "max_steps": 35,
 "min_center_intensity": 0.5, "num_games": 6, "setting": "New York",
 "smell_grid_size": 5, "thief_start": [3, 3]}
```

Check your implementation against this before we start — with
`nonce = "00000000000000000000000000000000"` those terms sign to:

```
7d9bfbe4fee886fea372c09b86a6f4377af47b01e87f0fd46d562afb08935e3e
```

## Move commits

The same construction over the sealed move record, not the move alone:

```
commit = SHA256( canonical_json(record) + "|" + nonce )
record = {step, state, position, move, intent, hint}
nonce  = 16 random bytes, hex (32 chars), fresh per step
state  = "grid=7x7;self=[0, 1];barriers=[]"   <- semicolon-joined, spaces after commas
```

A worked vector you can verify against:

```
record  {"hint":"heading south","intent":"honest","move":"S","position":[0,1],"state":"grid=7x7;self=[0, 1];barriers=[]","step":1}
nonce   0123456789abcdef0123456789abcdef
commit  ad35a33b985f72fbf1e9c0a60ae69ff219cba4c0df7b3e8b409ae29baa92161e
```

If your digest for that input differs, we will not agree on a single turn. It
is far cheaper to reconcile now than mid-series.

## Four things that cost us real matches

These are not hypotheticals — each one burned a live window against a previous
opponent. Please have your agent check all four.

**1. Both sides must SERVE, not only dial.** This wire is symmetric push: we
call your `receive_turn` exactly as you call ours. A peer that only dials out
can send but can never be sent to, and our match loop cannot enter its turn
loop until it has opened a session to you. From your side that looks like us
accepting your turns and going silent.

**2. `step` is a ROUND, not a half-turn, and starts at 1.** `max_steps = 35`
means 35 moves *each*. We wait for your message carrying the step number we
are on; if you number from 0 we wait forever while you re-send happily and
neither side errors.

**3. Roles ALTERNATE every sub-game.** If your peer holds a fixed role for the
series while we swap, we collide at every boundary and `negotiate` refuses. On
this wire the cop side is spelled **`police`**, not `cop` — our pairing check
compares exact strings, so `role: "cop"` will not collide with our `police`
and we would play a mispaired sub-game in silence.

**4. A sub-game ends at the AUDIT, not at step 35.** Please keep your peer up
through the `submit_audit` exchange. If it exits after pushing its last turn,
our closing audit hits a dead endpoint and the sub-game is played but never
settled — no verdict, no artifacts.

Your `submit_audit` payload needs all three keys:

```json
{"sender": "police" | "thief", "records": [{"payload": {...}, "nonce": "...", "commit": "..."}], "result_claim": {...}}
```

`result_claim` must be an object. A missing one is refused before anything is
stored, and you will see an empty reply.

**And note:** our tools return **HTTP 200 even when they refuse**, with
`{"status": "refused", "reason": "<field>: <what was wrong>"}` in the body.
Read the body, not the status code — the `reason` names the exact field. We
also log every inbound refusal on our side, so if something is malformed we
can tell you which field within seconds.

## What we need back

1. Your **team code**.
2. Your **endpoint URL(s)** — one if you serve both roles, two if you run
   separate processes for cop and thief.
3. Whether your peer **stays up across sub-game boundaries**, or relaunches
   per sub-game. If it relaunches we will set a pause at each boundary so you
   have a window to swap; just tell us how many seconds you need (and note it
   must be shorter than your handshake timeout, or you will abandon before we
   dial).

## The plan

Friendly first: **2 sub-games**, sides alternating, artifacts written, and
**nothing emailed to the course inbox**. We take cop in sub-game 1 unless you
would rather start as cop — either is fine, just say which.

Once we have both crossed a clean sub-game boundary, we can talk about a
longer series.

Send your details and we will be up and answering within a minute.
