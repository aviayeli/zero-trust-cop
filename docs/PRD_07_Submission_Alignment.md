# PRD 07 — Submission Alignment

Status: approved (directive of 2026-08-09).

Four corrections needed before the Moodle submission. Each is a *conformance*
change: the engine's behaviour is already correct, but what it advertises —
identity, ports, report format, documented constants — is not.

## FR1 — One 8-character group identity

Appendix C requires the group identifier to be exactly 8 characters. The tree
carries two identity literals and neither complies:

* `group_name` = `groupa` (6 chars), which also names the artifact directory
  `logs/groupa/`.
* `game_uid`  = `ztc001` (6 chars), which names all four artifact files.

Both become `aviayeli` (8). One identity, one length, everywhere: configs,
committed artifacts, the manual delivery script, and the test suites.

Not in scope: the synthetic uids test suites pass as *arguments* (`ztc042`,
`g1`, `abc`). Those exist to prove the identifier is a parameter rather than a
constant; pinning them to the real uid would delete that guarantee.

## FR2 — Port assignment and tunnel endpoints

The two peers swap listeners: cop binds **8802**, thief binds **8801**, and
each `opponent_url` names the other. `config/declaration.json` advertises what
is actually bound — the declaration and the binding are already tied by test
(`test_declaration_agrees_with_transport`) and must stay tied.

`public_url` becomes a *validated* field rather than a string passed through
untouched (Rule 10, §2.4). A league entry submits this endpoint; a malformed
one is discovered by the opponent failing to reach us, which is too late.
Accept `http`/`https` ngrok and Localtonet endpoints; reject anything that is
not an absolute http(s) URL with a host. Empty stays legal and means
loopback-only.

## FR3 — The report carries the result as an attachment

Rule 34 / §9.3.3: the match report must not be plaintext in the body. The
result travels as a real `application/json` MIME attachment named
`result_<game_uid>.json`, base64-encoded, in a multipart message whose body is
a short human summary only.

The draft fallback must keep recording the *whole* report, attachment payload
included — a fallback that dropped the JSON would make the evidence artifact
useless, which is the one thing it exists for.

## FR4 — The documented decay must match the implemented decay

Config is already correct: `pheromone_center_intensity = 0.9`,
`pheromone_decay = 0.10`, and the 7x7 render stays as it is. Only prose and
comments change, and they must state what the code does.

**Known conflict, deliberately not resolved here.** The recurrence is
geometric — `tau(t+1) = (1 - 0.10) * tau(t)` — so a 0.9 centre still holds
~0.314 at turn 10 and never reaches zero. The phrase "dissipates fully in ~10
steps" describes *subtractive* decay (0.9 - 0.10/turn, zero at turn 9), which
is a different model. Documentation states the geometric behaviour, because
documenting the other would be false. Whether the rulebook intends subtractive
decay is a question for Dr. Segal, and changing it is a behaviour change that
belongs in its own PRD.

## Acceptance

* Every previously passing test still passes; new behaviour arrives with tests
  written first.
* No `.py` over 150 lines; no new tunable inlined as a literal.
* README's self-checked figures (test total, tracked file count, longest file)
  remain accurate.
