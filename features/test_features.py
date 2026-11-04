"""Binds every `.feature` beside this file to pytest-bdd, so a scenario is a collectible test.

pytest-bdd collects nothing from a `.feature` on its own: a scenario exists only once a Python
module calls `scenarios()` on it, and that call cannot live in a `conftest.py` (the plugin is not
configured yet when a conftest loads). So `gauntlet init` ships this module, and the specifier's
two files are enough. No steps are defined here: writing them is the coder's job. Do not edit.

The call is skipped while the directory holds no feature at all: `scenarios()` raises on an empty
directory, and that would break `pytest -q` on a project that has not been specified yet.
"""

from pathlib import Path

from pytest_bdd import scenarios

if any(Path(__file__).parent.glob("*.feature")):
    scenarios(".")
