# Prompt for bb-ai-12's Claude — the clean dry-run

Measured 2026-08-25 18:19-18:21 before writing:

- their endpoint returns **404** (not 502) to a bare GET on `/`, `/mcp`,
  `/mcp/` and `/sse` — so something IS listening; ngrok is reaching an
  upstream.
- but an MCP session cannot be opened: `McpError: Session terminated`, three
  samples in a row. Not a flap.
- our peers: up, supervised, auto-relaunching; a bare GET returns 400.

---

You are working on team **bb-ai-12**'s cop-and-thief league peer. Your
opponent is **aviayeli**. We settled one sub-game together earlier today; this
is the clean friendly dry-run. One blocker first.

## Your endpoint is up but its MCP session will not open

We probed three times just now, spaced a few seconds apart, and got the same
thing each time:

```
netcheck https://comic-leverage-paprika.ngrok-free.dev/mcp
  [FAIL] reachable: McpError: Session terminated
NOT READY
```

This is **different from the earlier failures**, and the difference is
diagnostic:

- A bare GET now returns **404**, not 502. 502 was "ngrok has no upstream";
  404 means ngrok reached your process and your process did not recognise the
  route. So your peer is running.
- The MCP session then dies with `Session terminated` — the transport opens
  and is torn down before initialise completes.

For comparison, ours answer a bare GET with **400** (an MCP server refusing a
non-session request). A 404 on every path we tried — `/`, `/mcp`, `/mcp/`,
`/sse` — suggests the streamable-HTTP route is mounted somewhere else, or the
app in front of it is not the MCP app.

Worth checking: is the peer you just brought up the same one that played this
morning, and is it still mounting streamable HTTP at `/mcp`? If your framework
changed the mount point, or something restarted it behind a different app, it
would look exactly like this.

## Once that is fixed — the run we agreed

**2 sub-games, alternating. We take cop in sub-game 1, you take thief. Sides
swap for sub-game 2.**

**Artifacts ON, on both sides.** We proposed them off originally and that was
wrong: the graded series should not be the first time either of us exercises
the four-file path and the cross-team settlement hash. If those disagree, this
friendly game is where we want to find out. Our side writes them and drafts
the email rather than sending it — nothing reaches the course inbox from a
dry-run.

## Two things still outstanding from your side

**1. Your `negotiate` reply is not counter-signed.** Our record of the settled
sub-game says `handshake=UNVERIFIED`. Your reply is a bare acceptance with no
`terms`, `nonce` or `signature`, so two of our three handshake checks had
nothing to run against. That flag is written into `result_<game_id>.json` as
`handshake_counter_signed: false`, which a marker reads. Please answer with:

```json
{"status": "accepted",
 "terms": {...the same 14...},
 "nonce": "<your fresh nonce>",
 "signature": "SHA256(canonical_json(terms) + \"|\" + nonce)",
 "role": "<the side YOU are playing>",
 "sub_game_number": <n>}
```

Same construction you already verified for the move commits, with the terms in
place of the move record.

**2. `submit_audit` needs `result_claim`.** It was missing in the earlier
attempts and our validator refused it verbatim:
`result_claim: required object`. All three keys, `result_claim` an object.

## The restart protocol — please agree to this explicitly

Neither of us can resume a series mid-way. Our runner always starts at
sub-game 1; we verified that and it is not changing before this run. Earlier
today that desynced us badly: our run died at a sub-game boundary, relaunched
at sub-game 1 as cop, while you had correctly advanced to sub-game 2 as cop —
so we were both playing the same side into different inboxes, silently.

So: **if either side's run dies mid-series, both of us stop and restart from
sub-game 1.** Do not half-continue. Say so on the wire and we will both reset.

## We are up and supervised

Our peers relaunch automatically, so you will not find us in a gap:

- you as thief → our **cop**: `https://luxury-pregnancy-wilder.ngrok-free.dev/mcp`
- you as cop → our **thief**: `https://cardinal-shell-moistness.ngrok-free.dev/mcp`

A bare GET on those returns **400**, not 200 — that is the MCP server
correctly refusing a non-session request, and it is what a healthy peer of
ours looks like from outside.

Ping when your session opens and we will start.
