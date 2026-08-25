"""D7: a peer that commits and then goes silent forfeits the match.

Before this, response_timeout_sec guarded MatchState's action buffer — which
under commit-reveal is never half-filled, because reveal_move submits BOTH
moves at once only after both peers reveal. A stalled peer therefore hung the
turn forever. The timeout now lives where the stall actually happens.

The clock is injected throughout: no test sleeps.
"""



from mcp_server.commitments import CommitmentBook


class _Clock:
    """A hand-cranked monotonic clock."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _book(clock, timeout=30.0):
    return CommitmentBook(timeout_seconds=timeout, clock=clock)


def test_nothing_is_stalled_before_the_first_commitment():
    clock = _Clock()
    book = _book(clock)

    clock.advance(10_000)

    assert book.stalled_roles() == []


def test_nothing_is_stalled_before_the_deadline():
    clock = _Clock()
    book = _book(clock)
    book.commit("police", 0, "digest")

    clock.advance(29.0)

    assert book.stalled_roles() == []


def test_a_peer_that_never_commits_is_stalled():
    clock = _Clock()
    book = _book(clock)
    book.commit("police", 0, "digest")

    clock.advance(31.0)

    assert book.stalled_roles() == ["thief"]


def test_a_peer_that_commits_but_never_reveals_is_stalled(commitment_pair):
    """The exact hole D7 was opened for."""
    clock = _Clock()
    book = _book(clock)
    police, thief = commitment_pair
    book.commit("police", 0, police["h_commit"])
    book.commit("thief", 0, thief["h_commit"])
    book.reveal("police", 0, police["state"], police["move"],
                police["intent"], police["nonce"])

    clock.advance(31.0)

    assert book.stalled_roles() == ["thief"]


def test_both_peers_stall_when_neither_reveals(commitment_pair):
    clock = _Clock()
    book = _book(clock)
    police, thief = commitment_pair
    for entry in (police, thief):
        book.commit(entry["role"], 0, entry["h_commit"])

    clock.advance(31.0)

    assert book.stalled_roles() == ["police", "thief"]


def test_a_peer_blocked_by_a_silent_opponent_is_not_blamed(commitment_pair):
    """A reveal is REFUSED until both commit, so the committer is not at fault."""
    clock = _Clock()
    book = _book(clock)
    police, _ = commitment_pair
    book.commit("police", 0, police["h_commit"])

    clock.advance(31.0)

    assert book.stalled_roles() == ["thief"]


def test_a_completed_turn_never_stalls(commitment_pair):
    clock = _Clock()
    book = _book(clock)
    police, thief = commitment_pair
    for entry in (police, thief):
        book.commit(entry["role"], 0, entry["h_commit"])
    for entry in (police, thief):
        book.reveal(entry["role"], 0, entry["state"], entry["move"],
                    entry["intent"], entry["nonce"])

    clock.advance(10_000)

    assert book.stalled_roles() == []


def test_a_book_without_a_timeout_never_stalls():
    """Opting out must stay possible for the in-process trainer."""
    clock = _Clock()
    book = CommitmentBook(timeout_seconds=None, clock=clock)
    book.commit("police", 0, "digest")

    clock.advance(10_000)

    assert book.stalled_roles() == []
