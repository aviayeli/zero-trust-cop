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

import json
import os
import subprocess
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ConnectorError(RuntimeError):
    """One model could not be reached, or refused."""


def _post(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as failure:
        raise ConnectorError(f"{url.split('/')[2]}: {failure}") from failure


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


def gemini(prompt: str, model: str, timeout: float) -> str:
    """Google, through the public generateContent endpoint."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ConnectorError("GEMINI_API_KEY is not set")
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    body = _post(f"{GEMINI_URL.format(model=model)}?key={key}", payload, timeout)
    if "error" in body:
        raise ConnectorError(f"gemini: {body['error'].get('message', '')[:200]}")
    try:
        return body["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as failure:
        raise ConnectorError(f"gemini: unexpected response shape: {failure}") from failure


def ollama(prompt: str, model: str, timeout: float) -> str:
    """A local model, through the Ollama daemon."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    body = _post(OLLAMA_URL, payload, timeout)
    if not body.get("response"):
        raise ConnectorError(f"ollama/{model}: empty response")
    return body["response"].strip()


CONNECTORS = {"claude": claude, "gemini": gemini, "ollama": ollama}


def probe(connector: str, model: str, timeout: float = 60.0) -> str | None:
    """Return None if the model answers, else why it cannot be used.

    Called before the debate so an unreachable model is reported up front
    rather than silently reducing the panel.
    """
    try:
        CONNECTORS[connector](
            "Reply with exactly: OK", model, timeout
        )
    except ConnectorError as failure:
        return str(failure)
    except KeyError:
        return f"unknown connector: {connector!r}"
    return None
