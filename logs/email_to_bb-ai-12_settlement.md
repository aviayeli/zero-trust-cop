# Outbound #19 — one comparison before the graded six

Both records agree on the play. What has NEVER been compared is the thing the
grader actually joins on: the settlement consensus hash. Each side computes it
independently from its own view of the match, and they must be identical.

Ours: `954ceb8dfa732b49df6fccd6e203c7e904bc76c6afd1487e4784df73104582c9`

If theirs differs, the two teams submit artifacts that disagree — and the
friendly run is precisely where that should be found.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Confirmed identical on our side, including the outcomes:

```
sub_game=1 role=police steps=35 outcome=survival   their_audit=accepted  hs=counter-signed
sub_game=2 role=thief  steps=35 outcome=capture    their_audit=accepted  hs=counter-signed
```

Your thief survived our cop, your cop caught our thief. Both records agree on
every field, which is the first time that has been true of a whole series.
Well played — you took both.

**Before the graded six, one comparison we have never actually made.**

Both sides compute a settlement consensus hash independently, from their own
view of the match, over the trimmed symmetric outcome. Two honest teams must
reach the *same* string. If we do not, we submit artifacts that disagree with
each other, and a grader sees that rather than a clean match.

Ours, for the friendly series:

```
sha256 = 954ceb8dfa732b49df6fccd6e203c7e904bc76c6afd1487e4784df73104582c9
```

computed over:

```json
{"aggregate": {"series_tie": false,
               "sub_games_won": {"aviayeli": 0, "bb-ai-12": 2},
               "ties": 0,
               "total_score": {"aviayeli": 10, "bb-ai-12": 30},
               "winner_group": "bb-ai-12"},
 "game_id": "aviayeli-vs-bb-ai-12",
 "sub_games": [
   {"result": "survival", "roles": {"cop": "aviayeli", "thief": "bb-ai-12"},
    "score": {"aviayeli": 5, "bb-ai-12": 10},
    "sub_game_number": 1, "winner_group": "bb-ai-12"},
   {"result": "capture",  "roles": {"cop": "bb-ai-12", "thief": "aviayeli"},
    "score": {"aviayeli": 5, "bb-ai-12": 20},
    "sub_game_number": 2, "winner_group": "bb-ai-12"}]}
```

Note the sub-game rows carry **five** keys — `tie` is derivable from
`winner_group is None` and stays out of the preimage — and the serialisation
is the spaced canonical form, not the compact one used for move commits.

**What is your hash for this series?** If it matches, we go to the graded six
with the last untested thing tested. If it does not, this friendly run is
exactly where we want to find that out.

**Two small things while we wait.**

*Your reports.* You said both sub-games' reports were emailed — I assume to
your own inbox via `--report-to`, as you described. Worth confirming, only
because on the graded run they need to go to the course address instead, and
that is a flag that has to change in exactly one direction at exactly one
moment.

*A correction, and it is minor.* You cited "your earlier 30→60 raise on the
same class of issue" as precedent for raising your handshake timeout. We never
made that change — our `response_timeout_sec: 30` and `watchdog_timeout_sec:
60` are two different fields, both set once in the commit that created
`config/game.json` and never raised. Raising yours was still the right call;
I only flag it in case that precedent ends up in your write-up.

**Ready for the graded six on your word:**

```
--sub-games 6 --first-role police --sub-game-pause 30 --email-mode send
```

Six sub-games, five boundary crossings, roles alternating from us as cop. That
run reports to the course inbox for real, so we will confirm the hash first
and then launch.

Best,
aviayeli
