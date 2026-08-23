"""Start both peer servers as real processes, and ALWAYS tear them down.

A crashed match must not leave a listener bound: the next run would fail to
bind its port, or worse, silently talk to the previous match's engine.
"""

import contextlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp_server.transport import load_network_settings

PEER_ROLES = ("police", "thief")
_POLL_SECONDS = 0.05
# This package's import root. A spawned peer is a NEW interpreter: pytest's
# `pythonpath = ["src"]` patches the parent's sys.path and reaches no child,
# and `pyproject.toml` declares no [build-system], so nothing installs this
# project into the venv either. The child's path is therefore made explicit
# rather than inherited from an install state nothing declares.
SRC_ROOT = Path(__file__).resolve().parents[1]


def child_environment() -> dict:
    """The parent environment, with this project's src on PYTHONPATH."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    entries = [str(SRC_ROOT)] + [part for part in existing.split(os.pathsep) if part]
    env["PYTHONPATH"] = os.pathsep.join(entries)
    return env


def _startup_failure(process) -> str:
    """Whatever the dead child wrote to stderr, trimmed for a message."""
    try:
        _, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        return "<no output>"
    return (stderr or b"").decode("utf-8", "replace").strip()[-400:] or "<no output>"


def port_is_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Return whether something is accepting connections at host:port."""
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def wait_for_port(host, port, deadline_seconds: float, process=None) -> None:
    """Block until a listener answers, or explain why one never will.

    A child that EXITED is reported immediately with its stderr. Waiting the
    full deadline for a process that is already dead turns a one-line
    ModuleNotFoundError into a 30-second timeout about the wrong thing.

    Raises:
        RuntimeError: the peer process exited before it began listening.
        TimeoutError: the deadline passed with no listener and no corpse.
    """
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if port_is_open(host, port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"peer exited with code {process.returncode} before listening "
                f"on {host}:{port}: {_startup_failure(process)}"
            )
        time.sleep(_POLL_SECONDS)
    raise TimeoutError(f"no peer listening on {host}:{port}")


def _spawn(role: str, config_root: str | None) -> subprocess.Popen:
    """Launch one peer server over streamable HTTP."""
    command = [sys.executable, "-m", "mcp_server.server", "--role", role]
    if config_root is not None:
        command += ["--config-root", config_root]
    return subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        env=child_environment(),
    )


@contextlib.contextmanager
def running_peers(
    config_root: str | None = None,
    startup_timeout: float = 30.0,
    roles=PEER_ROLES,
):
    """Run the named peers for the duration of the block, then stop them.

    ``roles`` defaults to BOTH, which is the local simulation. A league
    match passes only our own: the opposing peer is the other group's
    process, and starting a local stand-in would bind the port their
    tunnel is dialling and quietly play a second local game instead.

    Yields:
        {role: TransportSettings} once every peer is accepting connections.
    """
    bindings = {
        role: load_network_settings(role, config_root) for role in roles
    }
    processes = []
    try:
        for role in roles:
            processes.append(_spawn(role, config_root))
        for role, process in zip(roles, processes):
            wait_for_port(
                bindings[role].dial_host, bindings[role].my_port,
                startup_timeout, process,
            )
        yield bindings
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
