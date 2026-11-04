"""The other half of the seal: what the layers contract says about *names*.

`nemo.test_purity` holds the two pure modules to what they may **do** — no disk, no clock, no
network — by nailing those doors shut in the process. This file holds the whole package to what it
may **import**, and it does so by reading `pyproject.toml` and by running `lint-imports` for real
against a copy of the tree. Both halves are needed and neither implies the other: the seal says
nothing about `nemo.card` importing upwards, and the contract says nothing about a module that
opens a socket through `re` and `pathlib`, which are in nobody's layer.

Why a test at all, when `lint-imports` already runs in the cleaner's gate: the gate proves the
contract is *kept*, never that it still *says anything*. Ticket 28's defect was a contract that
passed every gate while two modules sat outside it. Three edits would reopen it, and `lint-imports`
would stay KEPT through all three — deleting `exhaustive = true`, dropping a module out of
`layers`, or parking a real module in `exhaustive_ignores`, which is a list import-linter takes on
trust. The tests below are the gate that goes red on each.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def repo_root(start: Path = Path(__file__)) -> Path:
    """The real tree, found rather than counted off `__file__`.

    The walk-up is `nemo.test_ask.repo_root`'s, for the reason its docstring gives at length:
    `mutmut` runs this suite from a copy under `mutants/`, and counting parents lands inside that
    copy. `pyproject.toml` is the file this module is about and `gate.sh` marks the tree that holds
    the real one (the copy holds a `pyproject.toml` of its own, and no `gate.sh`), so walking up to
    the first ancestor with a `gate.sh` reads the same configuration from either copy. It is not
    imported from `test_ask` because that module reads its recorded fixtures at import time,
    which is a large and unrelated cost to pay here.
    """
    return next(folder for folder in start.resolve().parents if (folder / "gate.sh").is_file())


REPO = repo_root()


def test_the_real_tree_is_found_from_mutmuts_copy(tmp_path: Path) -> None:
    """Ticket 129: the marker outlives `demo_skin/`, and `mutants/` (which holds `pyproject.toml`
    and `src/`) is never taken for the real tree."""
    (tmp_path / "gate.sh").touch()
    copy = tmp_path / "mutants" / "src" / "nemo"
    copy.mkdir(parents=True)
    (tmp_path / "mutants" / "pyproject.toml").touch()
    assert repo_root(copy / "test_this.py") == tmp_path


PACKAGE = REPO / "src" / "nemo"

#: The two files in the package directory that are not modules of the package's own design:
#: `__init__` is the container itself and `conftest` is pytest's, so neither takes a layer.
NOT_A_LAYER = frozenset({"__init__", "conftest"})

#: `lint-imports` out of the interpreter running this suite, rather than off a hard-coded
#: `.venv/bin/`: under `mutmut` the copy of the tree has no venv of its own, but `sys.executable`
#: is still the real one the gate invoked.
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"

#: The line the ticket proved the hole with. `call_lane` moved to `nemo.lane` in ticket 17 and
#: `nemo.ask` re-exports it, so the import still resolves and still points at the package's one
#: socket — and `nemo.evidence` sits *below* `nemo.ask` in the layers, so it is still upward.
THE_OFFENDING_IMPORT = "from nemo.ask import call_lane\n"


def contract() -> dict:
    """The one layers contract, read out of the real `pyproject.toml`."""
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    one, = config["tool"]["importlinter"]["contracts"]
    return one


def named_layers() -> set[str]:
    """Every module named in `layers`, with the sibling groups (`a : b`) split apart."""
    return {name.strip() for line in contract()["layers"] for name in line.split(":")}


def modules_on_disk() -> set[str]:
    """Every module of the package's own design that actually exists."""
    return {path.stem for path in PACKAGE.glob("*.py")
            if path.stem not in NOT_A_LAYER and not path.stem.startswith("test_")}


def checked_out(tmp_path: Path) -> Path:
    """A copy of the real tree that `lint-imports` can read: the package, and the real contract.

    The test modules come along, because they are what `exhaustive_ignores` is a list of and a
    copy without them would exercise a contract nobody runs. `__pycache__` does not, because a
    stale `.pyc` of a module the copy no longer has would be a module to grimp.
    """
    shutil.copytree(PACKAGE, tmp_path / "nemo", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(REPO / "pyproject.toml", tmp_path / "pyproject.toml")
    return tmp_path


def verdict(tree: Path) -> subprocess.CompletedProcess[str]:
    """What `lint-imports` says about that tree, run exactly as the cleaner's gate runs it."""
    return subprocess.run([LINT_IMPORTS], cwd=tree, env={"PYTHONPATH": str(tree), "PATH": ""},
                          capture_output=True, text=True, check=False)


# ── what the contract must still say ─────────────────────────────────────────


def declared_dependencies() -> list[str]:
    """What `pyproject.toml` says this package needs at run time, read out of the real file."""
    config = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return list(config["project"]["dependencies"])


def test_the_package_declares_no_runtime_dependency_at_all() -> None:
    """nemo runs on the standard library and nothing else, and that is a property rather than a
    habit — so it is checked here rather than asserted in a document.

    The occasion was the observability lane (ADR-0020, ADR-0024). The record is the turn file this
    package writes; Langfuse sees it only through an export that runs after walks, from
    `~/work/nemo-langfuse`, and nothing in this tree imports it. Tracing at litellm's gateway was
    considered and rejected (ADR-0020), and so was the Langfuse SDK inside `nemo.lane`, which would
    have put the first runtime dependency into a package that has none. That the lane stays outside
    is the whole claim, and a claim nothing checks is a sentence.

    It is deliberately the *whole* list rather than a deny-list of names somebody thought of. A
    deny-list holds the line against `langfuse` and lets `langchain` through, and the next agent
    adding an SDK is exactly the agent who will not think to extend it. `dev` extras are
    untouched: `pytest`, `mutmut` and the rest are the build machine's and never ship.
    """
    assert declared_dependencies() == [], (
        "nemo took a runtime dependency. If that is intended it is an ADR, not a test edit: "
        "the package's zero-dependency claim is load-bearing for the demo skin (ADR-0001) and "
        "for the observability lane staying outside it (the turn file, exported after walks; "
        "ADR-0020)."
    )


def test_the_contract_is_exhaustive_so_an_unwritten_module_is_already_inside_it() -> None:
    """The one line ticket 28 turned on. Without it the array is a list of what was remembered."""
    assert contract()["exhaustive"] is True


def test_every_module_of_the_package_is_named_in_the_layers() -> None:
    """`nemo.evidence` and `nemo.text` were the two that were not, which is the whole ticket."""
    assert modules_on_disk() == named_layers()


def test_no_layer_names_a_module_that_does_not_exist() -> None:
    """A stale name is a layer nothing occupies, and it hides that a real module went missing."""
    assert named_layers() <= modules_on_disk()


def test_nothing_but_a_test_module_is_exempt_from_the_contract() -> None:
    """`exhaustive_ignores` is taken on trust by import-linter, so a real module parked in it
    reopens exactly ticket 28's hole with the contract KEPT. Only pytest's own files belong."""
    exempt = set(contract()["exhaustive_ignores"])
    assert exempt == {name for name in exempt
                      if name.startswith("test_") or name in NOT_A_LAYER}
    assert not exempt & named_layers()


# ── what the contract must still do ──────────────────────────────────────────


def test_the_tree_as_it_stands_is_kept_so_the_two_tests_below_are_not_vacuous(
        tmp_path: Path) -> None:
    kept = verdict(checked_out(tmp_path))
    assert kept.returncode == 0, kept.stdout + kept.stderr


def test_the_lane_reached_from_the_evidence_reader_breaks_the_contract(tmp_path: Path) -> None:
    """Done-when #2, run rather than argued: the import the reviewer got away with is now red."""
    tree = checked_out(tmp_path)
    evidence = tree / "nemo" / "evidence.py"
    evidence.write_text(evidence.read_text(encoding="utf-8") + THE_OFFENDING_IMPORT,
                        encoding="utf-8")
    broken = verdict(tree)
    assert broken.returncode != 0
    assert "evidence" in broken.stdout and "ask" in broken.stdout


def test_a_module_nobody_remembered_to_name_breaks_the_contract(tmp_path: Path) -> None:
    """What `exhaustive` buys that a complete array does not: the modules 16, 17 and 23 add, and
    the ones nobody has written yet, are inside the contract before anyone edits this file."""
    tree = checked_out(tmp_path)
    (tree / "nemo" / "forgotten.py").write_text('"""Added by a ticket that forgot."""\n',
                                                encoding="utf-8")
    broken = verdict(tree)
    assert broken.returncode != 0
    assert "forgotten" in broken.stdout
