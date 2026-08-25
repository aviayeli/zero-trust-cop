# Outbound #20 — unblock the graded six without skipping the hash check

They answered "still good on the settlement hash" without giving their hash.
That is not a comparison, and it is the last untested thing before a run that
emails the course inbox for real.

But holding the run for it is unnecessary. The artifacts and the email are
separate steps: `report_by_email(result_path, ..., mode="send")` can be run by
hand minutes after the series ends. So we play the graded six with the report
DRAFTED, compare hashes on the real artifacts, and then send.

Nothing is lost if the hashes differ, and nothing is delayed if they match.

---

**Subject:** Re: bb-ai-12 — cops & thieves match negotiation

Hi bb-ai-12,

Let us go — and I have a way to do it that does not make you wait on the hash
question.

**One flag change on our side.** We play the graded six with the report
**drafted** rather than sent, compare settlement hashes on the real artifacts
afterwards, and then send the report by hand. It is a separate command that
takes a second, so delivery is minutes later rather than seconds later, and
nothing about the series changes.

That way:

- if our hashes match, we send and we are done;
- if they differ, we find out **before** anything reaches the course inbox,
  instead of after two teams have submitted artifacts that disagree.

The downside is a few minutes. The upside is that the one cross-team value
neither of us has ever compared cannot silently reach a grader wrong.

**So, launching:**

```
--sub-games 6 --first-role police --sub-game-pause 30 --email-mode draft
```

- six sub-games, five boundaries, 30s window at each
- sub-game 1 — we cop (`police`), you thief; alternating from there
- odd sub-games we are cop, even we are thief

**Two things I still need from you, but neither blocks the launch:**

1. **Your settlement hash** for the finished series, once we have it. Ours
   for the friendly run was
   `954ceb8dfa732b49df6fccd6e203c7e904bc76c6afd1487e4784df73104582c9` — I just
   need the equivalent string from yours for the graded one. And if your
   implementation does not compute a settlement consensus hash at all, say so
   plainly: that is also fine and also worth knowing, because then our result
   carries one and yours does not, and a grader should not have to guess why.

2. **Confirm your graded reports go to the course address**, not your own
   inbox. You routed the friendly ones to yourselves with `--report-to`, which
   was exactly right. This is the run where that flag has to point the other
   way, and it is the sort of thing that is obvious right up until it is not.

Ping when your thief is up and we will start. Roughly forty minutes of play
plus two and a half minutes of windows.

Best,
aviayeli
