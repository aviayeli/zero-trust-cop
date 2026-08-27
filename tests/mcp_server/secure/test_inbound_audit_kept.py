"""An accepted inbound audit must survive in `app.audits`, and quietly.

The server always did the verification; it kept the result in a list nobody
harvested and logged nothing on acceptance. `claims_runner` now clears that
list per sub-game and harvests it into the sub-game log (PRD 22).

These pin the server half: what lands in the list, what does not, and that
acceptance stays off stdout.
"""

import asyncio
import hashlib

from mcp_server.interop import NONCE_SEPARATOR, canonical_str


def _record(step):
    body = {"step": step, "move": "MOVE:N", "sender": "thief"}
    nonce = f"{step:032x}"
    commit = hashlib.sha256(
        f"{canonical_str(body)}{NONCE_SEPARATOR}{nonce}".encode()).hexdigest()
    return {"payload": body, "nonce": nonce, "commit": commit}


def _audit(records):
    return {"sender": "thief", "records": records, "result_claim": "survival"}


def test_an_accepted_audit_is_kept_with_its_verdict(app):
    records = [_record(1), _record(2)]

    asyncio.run(app.submit_audit(_audit(records)))

    assert len(app.audits) == 1
    kept = app.audits[0]
    assert kept["sender"] == "thief"
    assert kept["records"] == records
    assert kept["verdict"], "a verdict nobody can recheck is what this fixes"


def test_the_kept_records_are_the_bytes_that_arrived(app):
    """They are preimages of digests the opponent pushed. Re-serialising them
    destroys the evidence the verdict rests on."""
    records = [_record(7)]

    asyncio.run(app.submit_audit(_audit(records)))

    assert app.audits[0]["records"] == records


def test_a_refused_audit_never_enters_the_list(app):
    """Appending happens AFTER validation, and must keep doing so."""
    asyncio.run(app.submit_audit(
        {"sender": "", "records": [_record(1)], "result_claim": "survival"}))

    assert app.audits == []


def test_clearing_the_list_is_what_separates_sub_games(app):
    """`claims_runner` clears this per sub-game beside app.inbox. Without the
    clear, sub-game 4's log inherits sub-game 3's audit."""
    asyncio.run(app.submit_audit(_audit([_record(1)])))
    app.audits.clear()
    asyncio.run(app.submit_audit(_audit([_record(2)])))

    assert len(app.audits) == 1
    assert app.audits[0]["records"][0]["payload"]["step"] == 2


def test_accepting_an_audit_writes_nothing_to_stdout(app, capsys):
    """Persistence is the record; a per-sub-game line is stdout spam.
    Refusals keep their warning -- that path is unchanged."""
    asyncio.run(app.submit_audit(_audit([_record(1)])))

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
