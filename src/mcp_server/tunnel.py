"""Validate the public tunnel endpoint a peer advertises for league play.

`public_url` is the one network field nothing local ever dials: the peers talk
over loopback, so a malformed endpoint produces no local symptom at all. It
surfaces as the *opposing* group being unable to reach us mid-series. Parsing
it at config load moves that failure back to a moment when it is still ours.

ngrok and Localtonet both hand out ordinary http(s) hosts, so no scheme
allowlist beyond http/https is needed and no provider is special-cased —
recognising ``ngrok-free.app`` by name would reject the next tunnel the course
allows. What IS rejected is the shape, because the three mistakes a dashboard
invites (a TCP forwarder URL, a bare host, a scheme-relative copy-paste) all
parse cleanly as strings and none of them is reachable over HTTP.
"""

from urllib.parse import urlsplit, urlunsplit

HTTP_SCHEMES = ("http", "https")


def parse_public_url(value: str) -> str:
    """Return a normalised absolute http(s) endpoint, or ``""`` for none.

    Empty is legal and means loopback-only. Anything else must carry an
    http/https scheme and a host; whitespace and a trailing slash are
    normalised away so two spellings of one endpoint compare equal.

    Raises ValueError on any value that could not be reached over HTTP.
    """
    if not isinstance(value, str):
        raise ValueError(f"public_url must be a string, got {type(value).__name__}")
    candidate = value.strip()
    if not candidate:
        return ""

    parts = urlsplit(candidate)
    scheme = parts.scheme.lower()
    if scheme not in HTTP_SCHEMES:
        raise ValueError(
            f"public_url must use http or https, not {parts.scheme or 'no'} "
            f"scheme: {candidate!r}"
        )
    if not parts.hostname:
        raise ValueError(f"public_url names no host: {candidate!r}")

    return urlunsplit(
        (scheme, parts.netloc, parts.path.rstrip("/"), parts.query, parts.fragment)
    )
