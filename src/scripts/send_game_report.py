"""Send a finished series report from the command line.

A THIN entry point over `reporting.email_sender`, not a second sender. The
stack it calls already does the three things that matter and one that would
have been fatal to rebuild:

* the OAuth scope is already `gmail.send` alone (`gmail_transport.SCOPE`) --
  least privilege, and a reporter has no business holding read access;
* `token.json` is reused and refreshed, falling back to the desktop consent
  flow only when absent;
* and the result travels as a base64 `application/json` ATTACHMENT inside
  `multipart/mixed`, never as body text.

That last one is why this module wraps rather than reimplements. A
`MIMEText(json.dumps(result))` message -- the obvious way to "send JSON" --
puts 102 braces in the body and attaches nothing, and a submission whose
report is body text is disqualified on sight. `mime_report` keeps the body
brace-free and asserts it by test; there must not be a second path that does
otherwise.

What is genuinely added here is the rate limit. `gmail_send` retries a
transient fault with the contract's backoff but has no notion of a send RATE,
so a loop reporting a backlog of series could walk into a 429 and, worse, an
automated lockout. A token bucket bounds that without slowing the normal case
of one report per match.
"""

from __future__ import annotations

import argparse
import time

from reporting.email_sender import DEFAULT_RECIPIENT, MODES, send_game_report


class TokenBucket:
    """Bound the outgoing send rate; refill continuously, spend per send.

    A bucket rather than a fixed sleep because the shape of the traffic is
    bursty and rare: one report per match, then nothing for hours. A minimum
    interval would tax the common case to protect against a burst that a
    bucket simply absorbs, and a burst is exactly what a backlog of unsent
    series looks like.
    """

    def __init__(self, rate_per_minute: float, burst: int,
                 clock=time.monotonic, sleeper=time.sleep):
        if rate_per_minute <= 0 or burst <= 0:
            raise ValueError("rate_per_minute and burst must both be positive")
        self._per_second = rate_per_minute / 60.0
        self._burst = float(burst)
        self._tokens = float(burst)
        self._clock = clock
        self._sleep = sleeper
        self._last = clock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self._burst,
                           self._tokens + (now - self._last) * self._per_second)
        self._last = now

    @property
    def tokens(self) -> float:
        """Whole and partial tokens available right now."""
        self._refill()
        return self._tokens

    def take(self) -> float:
        """Spend one token, waiting for it if the bucket is empty.

        Returns the seconds waited, so a caller can report a throttle rather
        than appear to hang.
        """
        self._refill()
        waited = 0.0
        if self._tokens < 1.0:
            waited = (1.0 - self._tokens) / self._per_second
            self._sleep(waited)
            self._refill()
        self._tokens -= 1.0
        return waited


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Email one finished series result as a JSON attachment.")
    parser.add_argument("result", help="path to result_<game_id>.json")
    parser.add_argument("--to", default=DEFAULT_RECIPIENT)
    parser.add_argument("--mode", default="send", choices=MODES,
                        help="'send' reports failure rather than drafting, "
                             "which is what a graded run wants; 'draft' never "
                             "contacts Google")
    parser.add_argument("--logs-dir", default="logs",
                        help="where a draft lands when one is written")
    parser.add_argument("--rate-per-minute", type=float, default=5.0)
    parser.add_argument("--burst", type=int, default=3)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    """Rate-limit, then hand off to the one sender that exists."""
    args = parse_args(argv)
    waited = TokenBucket(args.rate_per_minute, args.burst).take()
    if waited:
        print(f"throttled {waited:.1f}s to stay under "
              f"{args.rate_per_minute}/min", flush=True)

    handled = send_game_report(args.result, recipient=args.to,
                               config_mode=args.mode,
                               draft_dir=args.logs_dir)
    print(f"email_report={'ok' if handled else 'FAILED'} mode={args.mode}")
    return 0 if handled else 1


if __name__ == "__main__":
    raise SystemExit(main())
