"""The HTTP-reachable half of the panel: Google, Anthropic, and OpenAI-style.

Split from ``model_connectors`` at the cloud/local seam so neither file
approaches the 150-line limit. Everything here shares one property that the
local connectors do not: a bot filter in front of the API can reject the
request before it is ever seen, which is why ``_post`` always sends a browser
User-Agent.
"""

import os

from http_post import ConnectorError, post

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
# OpenAI-compatible /chat/completions services, by connector name.
OPENAI_STYLE = {
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY"),
    "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY"),
}


def gemini(prompt: str, model: str, timeout: float) -> str:
    """Google, through the public generateContent endpoint."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ConnectorError("GEMINI_API_KEY is not set")
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    body = post(f"{GEMINI_URL.format(model=model)}?key={key}", payload, timeout)
    if "error" in body:
        raise ConnectorError(f"gemini: {body['error'].get('message', '')[:200]}")
    try:
        return body["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as failure:
        raise ConnectorError(f"gemini: unexpected response shape: {failure}") from failure


def anthropic(prompt: str, model: str, timeout: float) -> str:
    """Anthropic over HTTP, for hosts that DO carry an API key.

    `claude` (the CLI) is the connector that works here, because this machine
    has no ANTHROPIC_API_KEY. Kept so the panel is portable.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ConnectorError("ANTHROPIC_API_KEY is not set; use the 'claude' connector")
    body = post(
        "https://api.anthropic.com/v1/messages",
        {"model": model, "max_tokens": 1500,
         "messages": [{"role": "user", "content": prompt}]},
        timeout,
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    if "error" in body:
        raise ConnectorError(f"anthropic: {body['error'].get('message', '')[:200]}")
    return body["content"][0]["text"].strip()


def openai_style(name: str):
    """Build a connector for any OpenAI-compatible /chat/completions service."""
    url, key_env = OPENAI_STYLE[name]

    def call(prompt: str, model: str, timeout: float) -> str:
        key = os.environ.get(key_env)
        if not key:
            raise ConnectorError(f"{key_env} is not set")
        body = post(
            url,
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
            timeout,
            {"Authorization": f"Bearer {key}"},
        )
        if "error" in body:
            raise ConnectorError(f"{name}: {body['error'].get('message', '')[:200]}")
        return body["choices"][0]["message"]["content"].strip()

    return call
