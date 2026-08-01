"""Start both peer servers as real processes, and ALWAYS tear them down.

A crashed match must not leave a listener bound: the next run would fail to
bind its port, or worse, silently talk to the previous match's engine.
"""

import contextlib
import socket
import subprocess
import sys
import time

from mcp_server.transport import load_transport_settings

PEER_ROLES = ("police", "thief")
_POLL_SECONDS = 0.05


def port_is_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Return whether something is accepting connections at host:port."""
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, deadline_seconds: float) -> None:
    """Block until a listener answers, or raise once the deadline passes."""
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if port_is_open(host, port):
            return
        time.sleep(_POLL_SECONDS)
    raise TimeoutError(f"no peer listening on {host}:{port}")


def _spawn(role: str, config_root: str | None) -> subprocess.Popen:
    """Launch one peer server over streamable HTTP."""
    command = [sys.executable, "-m", "mcp_server.server", "--role", role]
    if config_root is not None:
        command += ["--config-root", config_root]
    return subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
    )


@contextlib.contextmanager
def running_peers(config_root: str | None = None, startup_timeout: float = 30.0):
    """Run both peers for the duration of the block, then stop them.

    Yields:
        {role: TransportSettings} once every peer is accepting connections.
    """
    bindings = {role: load_transport_settings(role, config_root) for role in PEER_ROLES}
    processes = []
    try:
        for role in PEER_ROLES:
            processes.append(_spawn(role, config_root))
        for role in PEER_ROLES:
            wait_for_port(bindings[role].host, bindings[role].port, startup_timeout)
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
