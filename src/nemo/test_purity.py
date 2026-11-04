"""The seal every pure module's tests are held against, in one place so it says one thing.

A module promises in its own docstring that it reaches neither the disk, the clock nor the
network — `nemo.evidence`, which reads a transcript into a draft. The layers contract in
`pyproject.toml` says who it may import, which is a claim about names; this says what it may *do*,
which is a claim about the process. Both are needed: `re` and `pathlib` are in nobody's layer,
and an import of `nemo.text` is not what makes a module impure.

The seal is a fixture rather than a helper because it is `monkeypatch`'s. It lives here rather than
in `conftest.py` so that `do_not_mutate`'s `*/test_*.py` covers it: a conftest is inside
`source_paths`, and mutants in the scaffolding of a purity test are noise. The conftest beside this
file holds one import and registers it for the package.
"""

import builtins
import datetime
import io
import pathlib
import socket
import time
from collections.abc import Callable

import pytest


@pytest.fixture
def seal(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Nails every door out of the process shut — disk, clock, network — when called."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the builder reached outside the record")

    def nail_shut() -> None:
        monkeypatch.setattr(builtins, "open", refuse)
        monkeypatch.setattr(io, "open", refuse)
        monkeypatch.setattr(pathlib.Path, "read_bytes", refuse)
        monkeypatch.setattr(pathlib.Path, "read_text", refuse)
        monkeypatch.setattr(pathlib.Path, "open", refuse)
        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(time, "time", refuse)
        monkeypatch.setattr(datetime, "datetime", refuse)

    return nail_shut


def test_the_seal_catches_a_read_so_the_purity_tests_are_not_vacuous(
        seal: Callable[[], None], tmp_path: pathlib.Path) -> None:
    unrelated = tmp_path / "dependency-register.json"
    unrelated.write_text("unrelated", encoding="utf-8")
    seal()
    with pytest.raises(AssertionError, match="outside the record"):
        unrelated.read_text(encoding="utf-8")
