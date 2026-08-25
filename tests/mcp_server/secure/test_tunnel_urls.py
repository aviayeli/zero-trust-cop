"""Rule 10 / 2.4: the advertised tunnel endpoint is validated, not trusted.

`public_url` is what a league entry hands to the opposing group. Nothing in
this process ever dials it, so a malformed value cannot fail locally — it
fails as the *opponent* being unable to reach us, during a scored match, with
no local symptom to debug. Validating at config load is the only point where
the error is still ours to see.

The rejected shapes are the ones a tunnel dashboard actually produces:
ngrok's TCP forwarder gives `tcp://`, its status pane shows a bare host with
no scheme, and copying from HTML yields a scheme-relative `//host`.
"""

import pytest

from mcp_server.transport import load_network_settings
from mcp_server.tunnel import parse_public_url

# --- accepted ----------------------------------------------------------------

def test_empty_means_loopback_only_and_stays_empty():
    """Local play leaves this blank; blank must not become a validation error."""
    assert parse_public_url("") == ""


@pytest.mark.parametrize("url", [
    "https://1a2b-3c4d.ngrok-free.app",
    "http://1a2b-3c4d.ngrok-free.app",
    "https://zero-trust-cop.eu.ngrok.io",
    "https://avi-cop.localto.net",
    "http://avi-cop.localtonet.com",
    "https://avi-cop.localto.net:8802",
])
def test_ngrok_and_localtonet_endpoints_are_accepted(url):
    assert parse_public_url(url) == url


def test_a_path_is_preserved_because_mcp_lives_under_one():
    assert parse_public_url("https://x.ngrok-free.app/mcp") == (
        "https://x.ngrok-free.app/mcp"
    )


# --- normalised --------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "  https://x.ngrok-free.app  ",
    "https://x.ngrok-free.app/",
    "\thttps://x.ngrok-free.app/\n",
])
def test_surrounding_whitespace_and_a_trailing_slash_are_normalised(raw):
    """A dashboard copy-paste differs from a typed URL by exactly these."""
    assert parse_public_url(raw) == "https://x.ngrok-free.app"


def test_a_trailing_slash_after_a_path_is_dropped_too():
    assert parse_public_url("https://x.localto.net/mcp/") == (
        "https://x.localto.net/mcp"
    )


def test_the_scheme_is_lowercased():
    assert parse_public_url("HTTPS://X.ngrok-free.app") == (
        "https://X.ngrok-free.app"
    )


# --- rejected ----------------------------------------------------------------

@pytest.mark.parametrize("bad, why", [
    ("x.ngrok-free.app", "bare host, no scheme"),
    ("//x.ngrok-free.app", "scheme-relative"),
    ("tcp://0.tcp.ngrok.io:12345", "ngrok TCP forwarder, not HTTP"),
    ("ws://x.ngrok-free.app", "websocket scheme"),
    ("ftp://x.ngrok-free.app", "wrong protocol entirely"),
    ("https://", "scheme but no host"),
    ("https:///mcp", "path but no host"),
    ("http://:8802", "port but no host"),
])
def test_an_unusable_endpoint_is_rejected_loudly(bad, why):
    with pytest.raises(ValueError):
        parse_public_url(bad)


def test_a_non_string_is_rejected():
    """TOML can hand back an int or a list; neither is an endpoint."""
    with pytest.raises(ValueError):
        parse_public_url(8802)


# --- wired into config loading ----------------------------------------------

def test_a_configured_tunnel_url_is_validated_at_load(tmp_path):
    """The whole point: fail here, not at the opponent's first request."""
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        '[network]\nhost = "127.0.0.1"\nmy_port = 8802\n'
        'opponent_url = "http://127.0.0.1:8801/mcp"\n'
        'poll_interval_sec = 0.5\n'
        'public_url = "tcp://0.tcp.ngrok.io:12345"\n'
    )

    with pytest.raises(ValueError):
        load_network_settings("police", config_root=str(tmp_path))


def test_a_valid_configured_tunnel_url_survives_loading(tmp_path):
    role_dir = tmp_path / "thief"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        '[network]\nhost = "0.0.0.0"\nmy_port = 8801\n'
        'opponent_url = "http://127.0.0.1:8802/mcp"\n'
        'public_url = "https://avi-thief.ngrok-free.app/"\n'
        'poll_interval_sec = 0.5\n'
    )

    settings = load_network_settings("thief", config_root=str(tmp_path))

    assert settings.public_url == "https://avi-thief.ngrok-free.app"


def test_the_real_configs_still_load_with_an_empty_tunnel():
    for role in ("police", "thief"):
        assert load_network_settings(role).public_url == ""
