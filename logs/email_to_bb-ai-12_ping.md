# Outbound #3 — the "we are live" ping to bb-ai-12

Send AS-IS. No placeholders. Verified before writing:

- both peers bound (`0.0.0.0:8801`, `0.0.0.0:8802`) by a running
  `run_reference_match --sub-games 2 --no-artifacts --wait-minutes 45`
- both tunnels return 400, not 502, to a bare GET — a live MCP peer refusing a
  non-session request, which is what only a live peer can do
- `scripts.netcheck --opponent-url <our cop tunnel> --role thief` returned
  READY on all four checks, through the PUBLIC URL, in the role they will play

Window opened 2026-08-25 ~13:0x local, 45 minutes. If it lapses, relaunch the
same command and send this again with a fresh time.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

We are live now — start your thief whenever you are ready.

Our cop peer is up and answering on
https://luxury-pregnancy-wilder.ngrok-free.dev/mcp (our thief is up too, on
https://cardinal-shell-moistness.ngrok-free.dev/mcp, for the sub-games where
the sides swap). We verified from outside the tunnel, dialling as a thief the
way you will: MCP session initialises, all four reference-v3 tools served,
handshake accepted, all 14 terms value-equal.

One thing worth knowing so you do not misread it: a plain GET on our endpoint
returns **HTTP 400**, not 200. That is the MCP server correctly refusing a
non-session request — it is a live peer, not a broken one. 502 is the "nobody
home" signal; 400 means we are answering.

We are holding the window open for **45 minutes** from this message. Our peers
exist only while the run does, so if you need longer than that, say so and we
will relaunch — there is no cost to reopening it.

This run is the **friendly dry-run** we agreed: 2 sub-games, artifacts off, no
report sent. We take cop in sub-game 1, you take thief, alternating after. Once
we have both confirmed a clean turn exchange and the role mapping end to end,
we will relaunch for the graded 6 sub-game series.

Noted on decay — you stay on multiplicative_book_v1, we stay on
subtractive_chebyshev_v1, and nothing either of us depends on changes.

Ping back if your thief cannot reach us and we will look at it from our side
while the window is still open.

Best,
aviayeli
