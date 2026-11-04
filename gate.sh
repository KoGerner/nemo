#!/bin/bash
# Run nemo's tests: ./gate.sh [pytest arguments]. No test calls a model.
# The deselected tests read files kept out of this repository: tickets, build tooling, the live launcher.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export NEMO_SEED="$PWD/seed" NEMO_DEP_GRAPH="$PWD/skin/vendor"
args=()
while read -r t; do [ -n "$t" ] && args+=(--deselect "$t"); done <<'LIST'
src/nemo/test_handover.py::test_the_email_branch_is_not_in_the_product_and_the_kept_email_is_off_the_signature
features/test_features.py::test_the_repo_no_longer_states_a_rule_it_does_not_follow
features/test_features.py::test_every_test_module_in_the_tree_loads
features/test_features.py::test_answering_the_stage_4_card_never_hands_me_an_error
features/test_features.py::test_the_isolation_suite_attacks_the_app_the_manager_talks_to
features/test_features.py::test_the_facilitator_is_told_one_browser_holds_one_room
LIST
exec .venv/bin/python -m pytest -q "${args[@]}" "$@"
