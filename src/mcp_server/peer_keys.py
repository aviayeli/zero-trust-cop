"""Public-key assembly for one peer workspace.

A peer must authenticate BOTH sides of every turn: its own submissions as well
as its opponent's. So each workspace holds both public keys under
``config/<role>/peers/``.

Only PUBLIC key material is read here. The private ``signing_key.pem`` is
gitignored and is needed only to SIGN, which is the client's job — keeping it
out of the server's construction path means a peer still starts in a clean
checkout that has no secrets in it.
"""

from mcp_server.identity import PEER_ROLES, load_peer_public_key


def load_public_keys(own_role: str, config_root: str | None = None) -> dict:
    """Load every peer's public key from ``own_role``'s workspace."""
    return {
        peer: load_peer_public_key(own_role, peer, config_root)
        for peer in PEER_ROLES
    }
