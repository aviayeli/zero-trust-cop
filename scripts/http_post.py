"""The one HTTP primitive every cloud connector shares.

Extracted so ``model_connectors`` and ``cloud_connectors`` can both use it
without importing each other. Small on purpose: its whole job is to send
well-formed JSON with a browser User-Agent and turn every transport failure
into one exception type.
"""

import json
import urllib.error
import urllib.request

# Some API front ends (Cloudflare in front of Groq) reject urllib's default
# "Python-urllib/3.x" agent with a 403 before the request reaches the API.
# This is our own key against our own account: the header is about getting a
# well-formed request past a bot filter, not about bypassing authentication.
BROWSER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class ConnectorError(RuntimeError):
    """One model could not be reached, or refused."""


def post(url: str, payload: dict, timeout: float, headers: dict | None = None) -> dict:
    """POST JSON and decode the reply, raising ConnectorError on any failure."""
    sent = {"Content-Type": "application/json", "User-Agent": BROWSER_AGENT}
    sent.update(headers or {})
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=sent
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as failure:
        detail = failure.read()[:200].decode("utf-8", "replace")
        raise ConnectorError(f"HTTP {failure.code}: {detail}") from failure
    except (urllib.error.URLError, OSError, ValueError) as failure:
        raise ConnectorError(f"{url.split('/')[2]}: {failure}") from failure
