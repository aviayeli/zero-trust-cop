"""The email body must name the OFFICIAL settlement digest when one exists.

Split out of `test_email_attachment` rather than appended to it: that module
covers the envelope, the attachment and the brace-free body, and adding this
section pushed it past the project's 150-line ceiling.

The rule these pin: a series settled off the wire (PRD 20) carries TWO real
digests. The opponent's report quotes the official one, so a body naming only
the historical one reads to a grader as two teams disagreeing about a single
series -- the exact appearance settling it was meant to remove.
"""

from reporting.mime_report import build_message, summary_text

RESULT = {
    "game_uid": "aviayeli",
    "github_commit": "abc123",
    "games": [{"game_number": 1, "terminal_reason": "capture"}],
}

HISTORICAL = "c39d331ce8c45e30823baf2aeae58053020836542aa6e14d584fa2a58af23ee6"
OFFICIAL = "5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373"

SETTLED = dict(RESULT, mutual_agreement={
    "sha256": HISTORICAL,
    "confirmed": True,
    "official_settlement": {
        "sha256": OFFICIAL,
        "byte_length": 3997,
        "serialization": "json.dumps(scope, sort_keys=True, ensure_ascii=False)",
        "method": "independent derivation from our own artifacts, digests compared",
        "channel": "off-the-wire settlement, not earned at submit_audit",
    },
})


def _body(result):
    return summary_text(build_message(result, "grader@example.com"))


def test_the_body_states_the_official_digest_when_one_exists():
    body = _body(SETTLED)

    assert OFFICIAL in body
    assert "3997" in body


def test_the_body_still_states_the_historical_digest():
    """Both are real. The official supersedes for reporting; the historical
    stays on the record and is not quietly dropped."""
    assert HISTORICAL in _body(SETTLED)


def test_the_official_line_keeps_the_body_brace_free():
    assert "{" not in _body(SETTLED)


def test_a_result_without_an_official_settlement_is_unchanged():
    """Every series settled the normal way must render exactly as before."""
    plain = dict(RESULT, mutual_agreement={"sha256": HISTORICAL, "confirmed": True})

    assert "official settlement" not in _body(plain).lower()
