"""Call three PHYSICALLY different models behind one signature.

A single model role-playing four auditors shares one set of blind spots, which
is the standing objection to every audit in this repository. These connectors
reach Anthropic, Google and a local Meta model, so a disagreement between them
is evidence rather than a rhetorical device.

Every connector is ``(prompt, model, timeout) -> str`` and raises
``ConnectorError`` on any failure. Availability is PROBED rather than assumed:
OpenAI is configured on this machine and returns `insufficient_quota`, so a
script that trusted the presence of an API key would have produced a silent
two-model debate labelled as three.

Stdlib only, deliberately: this is dev tooling and must not add a runtime
dependency to a submission graded on its dependency list.
"""

import subprocess

import cloud_connectors
from http_post import ConnectorError, post

OLLAMA_URL = "http://localhost:11434/api/generate"
# A cold local model can spend a minute loading weights before its first token.
# The cloud figure was 30s on the theory that a slower reply is a dead one;
# measured, Gemini times out at 30s while this host is paging in a 5GB local
# model and answers fine on retry. The limit was describing our RAM, not their
# latency.
TIMEOUTS = {"ollama": 180.0, "cloud": 60.0}


def claude(prompt: str, model: str, timeout: float) -> str:
    """Anthropic, through the authenticated CLI (no API key on this host)."""
    try:
        done = subprocess.run(
            ["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.SubprocessError) as failure:
        raise ConnectorError(f"claude cli: {failure}") from failure
    if done.returncode != 0:
        raise ConnectorError(f"claude cli exited {done.returncode}: {done.stderr[:200]}")
    return done.stdout.strip()


def ollama(prompt: str, model: str, timeout: float) -> str:
    """A local model, through the Ollama daemon."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    body = post(OLLAMA_URL, payload, timeout)
    if not body.get("response"):
        raise ConnectorError(f"ollama/{model}: empty response")
    return body["response"].strip()


CONNECTORS = {
    "claude": claude, "ollama": ollama, "gemini": cloud_connectors.gemini,
    "anthropic": cloud_connectors.anthropic,
    "groq": cloud_connectors.openai_style("groq"),
    "deepseek": cloud_connectors.openai_style("deepseek"),
}


def timeout_for(connector: str) -> float:
    """A cold local model gets 180s; a cloud API gets 30s."""
    return TIMEOUTS["ollama" if connector == "ollama" else "cloud"]


def probe(connector: str, model: str, timeout: float | None = None) -> str | None:
    """Return None if the model answers, else why it cannot be used.

    Called before the debate so an unreachable model is reported up front
    rather than silently reducing the panel.
    """
    try:
        CONNECTORS[connector](
            "Reply with exactly: OK", model,
            timeout_for(connector) if timeout is None else timeout,
        )
    except ConnectorError as failure:
        return str(failure)
    except KeyError:
        return f"unknown connector: {connector!r}"
    return None
