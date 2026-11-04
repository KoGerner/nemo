"""No test the coder gate runs reaches the model lane, or leaves the box (ticket 185).

Registered by the root conftest. While a test under the configured `testpaths` runs (setup, call
and teardown), every socket connect is checked: one to `nemo.lane.lane_url()`, read at the moment
of the connect so `NEMO_LANE_URL` moves it, or to any address off loopback, is refused before a
byte leaves, and the test fails naming itself and the address. Code under test may swallow the
refusal (`nemo.conduct` turns a dead lane into a note), so the failure is raised by the guard after
the phase, not left to the code.

A path outside `testpaths` (`tests/ui` was the qa gate's live suite until the owner dropped that
line, 2026-09-30) is never guarded. A subprocess a test starts is its own interpreter and is not
guarded.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest


class LaneGuarded(ConnectionError):
    """What a guarded connect meets instead of the network."""


def _lane_addresses() -> tuple[set[str], int, str]:
    from nemo.lane import lane_url

    url = lane_url()
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        hosts = {str(info[4][0]) for info in socket.getaddrinfo(host, None)}
    except OSError:
        hosts = set()
    return hosts | {host}, parts.port or (443 if parts.scheme == "https" else 80), url


def refusal(address: Any) -> str | None:
    """Why a connect to `address` is refused, or None when it may go ahead."""
    if not isinstance(address, tuple):
        return None  # a unix socket stays on the box
    host, port = str(address[0]), int(address[1])
    hosts, lane_port, url = _lane_addresses()
    if host in hosts and port == lane_port:
        return f"reached the model lane at {url}"
    try:
        loopback = ipaddress.ip_address(host.split("%")[0]).is_loopback
    except ValueError:
        loopback = host == "localhost"
    return None if loopback else f"left the box for {host}:{port}"


def _guarded(item: pytest.Item) -> bool:
    root = item.config.rootpath
    return any(Path(item.path).is_relative_to(root / path)
               for path in item.config.getini("testpaths"))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    return (yield from _phase(item))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Iterator[None]:
    return (yield from _phase(item))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Iterator[None]:
    return (yield from _phase(item))


_ORIGINAL = socket.socket.connect, socket.socket.connect_ex
#: What the running phase was refused. Cleared at the start of each guarded phase.
_REFUSED: list[str] = []


def _check(address: Any) -> None:
    why = refusal(address)
    if why:
        _REFUSED.append(why)
        raise LaneGuarded(f"lane_guard: {why}")


def _connect(sock: socket.socket, address: Any) -> None:
    _check(address)
    _ORIGINAL[0](sock, address)


def _connect_ex(sock: socket.socket, address: Any) -> int:
    _check(address)
    return _ORIGINAL[1](sock, address)


@contextmanager
def _patched() -> Iterator[None]:
    socket.socket.connect, socket.socket.connect_ex = _connect, _connect_ex  # type: ignore[method-assign,assignment]
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = _ORIGINAL  # type: ignore[method-assign]


def _phase(item: pytest.Item) -> Iterator[None]:
    if not _guarded(item):
        return (yield)
    _REFUSED.clear()
    try:
        with _patched():
            return (yield)
    finally:
        if _REFUSED:  # raised here, so it replaces whatever the refused code made of the refusal
            pytest.fail(f"{item.nodeid} {'; '.join(dict.fromkeys(_REFUSED))} (ticket 185: no "
                        "test the coder gate runs may reach the model lane or leave the box)",
                        pytrace=False)
