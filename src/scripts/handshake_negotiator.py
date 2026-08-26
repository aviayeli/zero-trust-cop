"""Generate a renegotiation proposal for contract term changes.

This module generates PROPOSALS, not instantly accepted payloads. Two of the
parameters -- decay_per_step and emit_intensity -- are signed contract terms.
A peer running defaults will REFUSE any proposal with different values. The
generator exists to help construct multi-team handshakes where both sides need
to agree on the pheromone model before playing.
"""

from __future__ import annotations

import argparse
import json
import secrets

from mcp_server import interop
from mcp_server.terms import terms_from_config


def proposal(overrides: dict, config_path="config/game.json", nonce=None) -> dict:
    """Generate a renegotiation proposal with signed contract terms.

    Loads the contract from config_path, applies overrides to the pheromones
    section, extracts the flat terms, generates (or uses the given) nonce,
    signs the terms, and returns a proposal dict with all signable material.
    Raises KeyError if a required config key is missing.
    """
    with open(config_path) as f:
        config = json.load(f)

    # Apply overrides to pheromones section
    if "pheromones" in overrides:
        config["pheromones"].update(overrides["pheromones"])

    # Build flat terms and compute signature
    terms = terms_from_config(config)
    if nonce is None:
        nonce = secrets.token_hex(16)
    signature = interop.terms_signature(terms, nonce)

    # Detect changed terms by comparing with unmodified config
    with open(config_path) as f:
        original_config = json.load(f)
    original_terms = terms_from_config(original_config)

    changed = {}
    for key, value in terms.items():
        if value != original_terms[key]:
            changed[key] = {"from": original_terms[key], "to": value}

    note = "Opponent must adopt the same values or the handshake is refused."

    return {
        "terms": terms,
        "nonce": nonce,
        "signature": signature,
        "changed": changed,
        "note": note,
    }


def main(argv=None):
    """Read CLI flags and write a renegotiation proposal as indented JSON.

    Supports --decay-per-step and --emit-intensity as contract terms, and
    --max-consecutive-stay as a local-only value (does not require agreement).
    """
    parser = argparse.ArgumentParser(
        description="Generate a contract renegotiation proposal"
    )
    parser.add_argument(
        "--decay-per-step",
        type=float,
        help="Pheromone decay per step",
    )
    parser.add_argument(
        "--emit-intensity",
        type=float,
        help="Pheromone center intensity",
    )
    parser.add_argument(
        "--max-consecutive-stay",
        type=int,
        help="Max consecutive stay moves (local only, does not require agreement)",
    )
    parser.add_argument(
        "--out",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args(argv)

    # Build overrides dict for contract terms
    overrides = {"pheromones": {}}
    if args.decay_per_step is not None:
        overrides["pheromones"]["pheromone_decay"] = args.decay_per_step
    if args.emit_intensity is not None:
        overrides["pheromones"]["pheromone_center_intensity"] = args.emit_intensity

    # Generate the proposal
    result = proposal(overrides if overrides["pheromones"] else {})

    # Add local_only if max_consecutive_stay is specified
    if args.max_consecutive_stay is not None:
        result["local_only"] = {"max_consecutive_stay": args.max_consecutive_stay}

    # Output as indented JSON
    output = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
