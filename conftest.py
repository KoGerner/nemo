"""The root conftest, which exists to hand pytest-bdd the steps in `features_steps.py`.

pytest-bdd resolves a scenario's steps from the conftests above its module, and
`features/test_features.py` is the specifier's file and defines none. The steps are a module of
their own rather than this file's body for one reason: `tests/isolation/` is run with the scratch
Chainlit venv outside the repo (ADR-0001 — Chainlit is not a nemo dependency and nemo is not a
dependency of that venv), and that interpreter has no pytest-bdd. This conftest is an ancestor of
those tests, so importing pytest-bdd unconditionally here breaks that run before it collects.

Hypothesis is loaded under the same guard and for the same reason, and it is derandomized: the
hardener runs the suite once per mutant, and a property test that finds a mutant on one seed and
misses it on the next would make `mutmut`'s verdicts drift rather than the code's quality.
"""

import importlib.util

import pytest

#: Ticket 185: no test under `testpaths` reaches the model lane or leaves the box (`lane_guard.py`).
pytest_plugins = ["lane_guard"]

#: The one scenario this project ships red on purpose. Ticket 15 binds `run_id` — a walk may only
#: finish over a record its own run produced or advanced — and until it does, a walk that did no
#: work can close over the BIA a claimed room ships. `strict` is the point: the day the binding
#: lands, this scenario passes, the xfail turns the suite red, and the marker has to come out.
UNBUILT = "not-yet-built-ticket-15"


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker(UNBUILT):
            item.add_marker(pytest.mark.xfail(reason=f"unbuilt: {UNBUILT}", strict=True))


if importlib.util.find_spec("pytest_bdd") is not None:
    from features_steps import *  # noqa: F403

if importlib.util.find_spec("hypothesis") is not None:
    from hypothesis import HealthCheck, settings

    settings.register_profile(
        "nemo", derandomize=True, deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    settings.load_profile("nemo")
