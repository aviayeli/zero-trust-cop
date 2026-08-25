# Outbound draft — reply to bb-ai-12 (match negotiation)

Fill in the two `<...>` URLs from `scripts/league_up.sh` before sending. Every
other value below is read from this repo and is correct as of writing.

---

**Subject:** Re: bb-ai-12 — match negotiation — aviayeli details + interop notes

Hi bb-ai-12,

Glad to set a series up. Our details are below, plus a couple of interop notes
that have cost other pairings a live window — worth two minutes now.

**1. Team code**

`aviayeli`

**2. MCP endpoints**

We run our cop and our thief as two peers behind two tunnels, and the sides
alternate every sub-game. Please dial the endpoint serving the role you are
playing **against**:

| You are playing | Call our endpoint |
|---|---|
| thief | **cop** — `<COP_URL>/mcp` (local 8802) |
| cop | **thief** — `<THIEF_URL>/mcp` (local 8801) |

Both speak the league's reference-v3 surface: `negotiate`, `receive_turn`,
`submit_audit`, `receive_control`. Every message is a single envelope
argument (`negotiate(message={...})`, `submit_audit(payload={...})`) — flat
parameters fail Pydantic validation on the caller's side before reaching us.

**3. Commit–reveal formula**

We use the league kit's **reference form**, not the book's ch.5.3 positional
listing. The book publishes three mutually inconsistent constructions and only
one reproduces the kit's shared vectors, so it is worth stating exactly:

```
commit = SHA256( canonical_json(record) + "|" + nonce )
```

- `record` is the whole sealed move record, not the move alone:
  `{step, state, position, move, intent, hint}`
- `canonical_json` is compact, key-sorted, native UTF-8:
  `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
  (keys sort by Unicode **code point**; JS/Java sort UTF-16 code units and
  order astral keys differently)
- the separator is a **single** pipe `|` (U+007C) — not `||`, not a bare
  concatenation
- `nonce` is 16 random bytes, hex-encoded (32 chars), fresh per step
- `state` is the kit's own label spelling, e.g.
  `grid=7x7;self=[0, 1];barriers=[]` — semicolon-joined, spaces after the
  commas

A worked vector you can check against your implementation:

```
record   {"hint":"heading south","intent":"honest","move":"S","position":[0,1],"state":"grid=7x7;self=[0, 1];barriers=[]","step":1}
nonce    0123456789abcdef0123456789abcdef
commit   ad35a33b985f72fbf1e9c0a60ae69ff219cba4c0df7b3e8b409ae29baa92161e
```

If your digest for that input differs, we will not agree on a single turn, so
it is much cheaper to reconcile it here than mid-series.

The **pre-game handshake signature** uses the same construction over the flat
agreed terms: `signature = SHA256(canonical_json(terms) + "|" + nonce)`, with
`sub_game_number` and `role` riding *beside* `terms`, never inside it — an
extra key there changes the hash both sides are verifying.

Moves stay sealed for the whole sub-game: `receive_turn` carries only the
digest, and the nonces and records are disclosed at `submit_audit`, where each
side re-hashes the other's chain.

**Two notes that have burned live windows before**

- **`role` means the side *that peer* is playing**, not the side of the peer
  being called. Two peers declaring the same role is a mispairing that both
  engines otherwise play through coherently, and it is refused at `negotiate`.
- **The 14 agreed terms must value-match exactly**, or `negotiate` refuses.
  Ours: `axis_origin_corner=top-left`, `axis_start_index=0`, `barriers_max=14`,
  `board_size=7`, `cop_start=[0, 0]`, `decay_per_step=0.1`,
  `emit_intensity=0.9`, `hint_max_words=15`, `max_steps=35`,
  `min_center_intensity=0.5`, `num_games=6`, `setting=New York`,
  `smell_grid_size=5`, `thief_start=[3, 3]`. Pheromone decay is
  **subtractive** on the wire (`v - decay_per_step`, clamped), agreed in this
  league as `subtractive_chebyshev_v1`.

**4. Dry-run or straight to the graded series**

Either suits us. We would suggest a short friendly dry-run first — one or two
sub-games, artifacts off — purely to confirm the digest agreement above and
the role mapping; it usually takes one attempt. After that we are ready for the
graded **6 sub-game** series with alternating roles.

We also have a read-only pre-flight checker that opens no sub-game and pushes
no turn — it just confirms an endpoint is reachable, serves all four tools,
completes a handshake, and that our 14 terms match. Happy to point it at your
URL (and for you to do the same to ours) before we start the clock.

Send your two endpoint URLs and your team code when ready and we will do the
same. If you serve both roles from one endpoint rather than two, tell us — we
support both shapes, but we need to know which.

Best,
aviayeli
