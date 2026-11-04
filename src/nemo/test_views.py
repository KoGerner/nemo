"""The four views, as properties of one record rather than as four documents anybody wrote.

Everything here hands `render` a record and reads what comes back. There is no room on disk in
this file and no walk in front of it: rendering is a function of the record bytes, so a test that
needed either would be testing something other than the thing this module promises.

`write` is the one function here that touches a room, and what it is held to is that the four land
under the process's own folder and that the store's refusal reaches the caller rather than being
swallowed. What the refusal *is* — the shrink guard, and both byte counts in it — is
`nemo.room_store`'s and is tested there.
"""

import ast
import io
import json
import re
import tokenize

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo import figures, views
from nemo.figures import NOTHING
from nemo.impact import NOT_RATED, crossing
from nemo.room_store import Shrunk
from nemo.test_ask import repo_root
from nemo.views import NOT_SCORED, STILL_OPEN, folder, render, write

METHOD = {
    "time_horizons": ["0–4 h", "8 h", "24 h"],
    "scenarios": [{"id": "financial", "name": "Financial"},
                  {"id": "legal-regulatory", "name": "Legal / regulatory"}],
    "intolerability_threshold": 4,
}

PATH = "07_Interviews/26_08_00_interview.md"
SCORE_QUOTE = "Torsten Ahlgrim: Impact financial: 0–4 h 2, 8 h 3, 24 h 4."
STATED_QUOTE = "Torsten Ahlgrim: MTPD: 24 h for the slaughter process."
OPEN_ITEM = "the sticking-pen conveyor — your register does not model it."

ACTIVITY = {
    "name": "Stunning",
    "impact_grid": {"financial": {"0–4 h": 2, "8 h": 3, "24 h": 4},
                    "legal-regulatory": {"0–4 h": "MISSING", "8 h": "MISSING", "24 h": "MISSING"}},
    "mtpd": "24 h",
    "recovery_target": "8 h",
    "rpo": "4 h (ERP order data)",
    "mbco": "50% cutting capacity, A-customers only, one shift",
    "dependencies": ["KA-01"],
    "evidence": [
        {"type": "transcript_quote", "quote": STATED_QUOTE, "source_path": PATH},
        {"type": "transcript_quote", "quote": SCORE_QUOTE, "source_path": PATH,
         "lens": "financial"},
    ],
}

RECORD = {
    "record_schema_version": 1,
    "run_id": "7c1e9a02-3f5b-4c8d-9e2a-1b3c4d5e6f70",
    "dept": "Slaughter",
    "method": METHOD,
    "open_items": [OPEN_ITEM],
    "activities": [ACTIVITY],
}


def rendered(**changes):
    """The four views of this record, with whatever the test changed about its one activity."""
    return render({**RECORD, "activities": [{**ACTIVITY, **changes}]})


def worksheet(**changes):
    return rendered(**changes)[views.WORKSHEET]


# ── the four, and where they land ────────────────────────────────────────────


def test_a_record_renders_exactly_the_four_views_the_story_names():
    assert list(render(RECORD)) == ["stage1-scope-and-guide.md", "stage2-interview-capture.md",
                                    "stage3-dependency-analysis.md", "stage4-worksheet.md"]


def test_each_view_opens_with_its_own_title_and_the_department_it_is_about():
    """Four documents, four titles: a reader who has one of them open knows which one it is."""
    rendered_all = render(RECORD)

    assert [rendered_all[name].splitlines()[0] for name in views.FOUR] == [
        "# The scope this BIA was agreed over — Slaughter",
        "# The interview this BIA rests on — Slaughter",
        "# What this BIA depends on — Slaughter",
        "# The worksheet — Slaughter",
    ]


def test_every_view_ends_at_its_last_line_with_one_newline_and_nothing_after_it():
    for name, text in render(RECORD).items():
        assert text.endswith(OPEN_ITEM + "\n"), f"{name} ends in something the record does not say"


def test_the_four_land_under_the_process_the_record_is_about():
    assert folder(RECORD) == "output/slaughter"


def test_a_record_that_names_no_department_says_none_rather_than_a_word_standing_for_one():
    """No department is a gap in the record, and a gap prints as a gap — never as `None`."""
    nameless = {key: value for key, value in RECORD.items() if key != "dept"}

    assert render(nameless)[views.SCOPE].splitlines()[0] == (
        "# The scope this BIA was agreed over — ")
    assert folder(nameless) == "output/"


def test_writing_them_puts_the_four_there_and_nothing_else(tmp_path):
    write(tmp_path, RECORD)

    assert {path.name for path in (tmp_path / "output" / "slaughter").iterdir()} == set(
        views.FOUR)
    assert (tmp_path / "output" / "slaughter" / views.WORKSHEET).read_text(
        encoding="utf-8") == worksheet()


def test_a_write_that_would_shrink_a_view_reaches_the_caller_as_a_refusal(tmp_path):
    write(tmp_path, RECORD)

    with pytest.raises(Shrunk):
        write(tmp_path, {**RECORD, "activities": [], "open_items": []})


# ── a function of the record bytes ───────────────────────────────────────────


def test_the_same_record_renders_the_same_bytes_twice():
    """No clock, no run state and no room: there is nothing in a view for a second run to move."""
    assert render(RECORD) == render(json.loads(json.dumps(RECORD)))


def test_a_changed_record_changes_every_view_that_states_the_figure():
    changed = rendered(mtpd="48 h", recovery_target="12 h")

    for name, before in render(RECORD).items():
        assert changed[name] != before, f"{name} did not follow the record"
        assert "the recovery target is 12 h" in changed[name]
        assert "the recovery target is 8 h" not in changed[name]


def test_the_four_say_one_activity_s_figures_in_the_same_words():
    """Not compared afterwards: one function renders the block, and the four call it."""
    said = [line for line in worksheet().splitlines() if line.startswith("For ")]

    assert said
    for view in render(RECORD).values():
        for line in said:
            assert line in view, f"{line!r} is missing from a view"


# ── the worksheet, clause by clause ──────────────────────────────────────────


def test_the_grid_is_laid_out_over_every_horizon_the_method_covers():
    """A horizon nobody scored is a row saying so, never a row the document leaves out."""
    grid = [line for line in worksheet().splitlines() if line.startswith("| ")]

    for horizon in METHOD["time_horizons"]:
        assert [line for line in grid if line.startswith(f"| {horizon} |")]
    assert grid[-1].count(NOT_SCORED) == 1, "the unscored category was dropped rather than said"


def test_the_grid_is_a_table_a_markdown_reader_renders_rather_than_prints():
    """The header and the rule under it, character for character: a table that is off by one
    pipe is a table a phone shows as a wall of text."""
    grid = [line for line in worksheet().splitlines() if line.startswith("| ")]

    assert grid[0] == "| Horizon | financial | legal-regulatory |"
    assert grid[1] == "| --- | --- | --- |"
    assert grid[2] == "| 0–4 h | 2 | not scored |"


def test_a_band_no_category_rated_says_so_in_every_cell_and_the_rest_keep_their_own_words():
    """Ticket 376 (ADR-0050): a band the source left "–" in every category is "not rated in the
    source", never a score and never a blank; a cell blank beside a scored one is still
    "not scored"."""
    grid = {lens: {**row, "0–4 h": "MISSING"} for lens, row in ACTIVITY["impact_grid"].items()}
    rows = [line for line in worksheet(impact_grid=grid).splitlines() if line.startswith("| ")]

    lenses = list(grid)
    assert rows[2] == _row_of("0–4 h", [NOT_RATED] * len(lenses))
    assert rows[3] == _row_of("8 h", [str(grid[lens]["8 h"]) if isinstance(grid[lens]["8 h"], int)
                                      else NOT_SCORED for lens in lenses])


def _row_of(band, cells):
    return "| " + " | ".join([band, *cells]) + " |"


def test_a_method_that_names_no_horizon_lays_the_grid_over_the_ones_that_were_scored():
    """A grid still has to be readable when the method file says nothing about the bands.

    The fallback is the grid's own bands, sorted, rather than no rows at all: a table of nothing
    but a header reads as an activity nobody scored.
    """
    said = render({**RECORD, "method": {**METHOD, "time_horizons": []}})[views.WORKSHEET]
    bands = [line.split(" | ")[0].removeprefix("| ")
             for line in said.splitlines() if line.startswith("| ")]

    assert bands == ["Horizon", "---", "0–4 h", "24 h", "8 h"]


def test_the_mtpd_is_said_with_the_reason_before_the_figure():
    said = [line for line in worksheet().splitlines() if "intolerable" in line][0]

    assert said.index("reaches") < said.index("stands at 24 h")


def test_a_grid_that_never_reaches_the_threshold_prints_no_figure_at_all():
    gentle = {lens: dict.fromkeys(row, 3) for lens, row in ACTIVITY["impact_grid"].items()}
    said = worksheet(impact_grid=gentle, mtpd=None,
                     evidence=[item for item in ACTIVITY["evidence"] if item.get("lens")])

    assert "never reaches" in said
    assert "stands at" not in said and "MTPD" not in said


def test_the_figure_the_interview_stated_stands_beside_the_one_the_grid_derives():
    """Both, named to the activity: the record holds two and a view showing one of them would be
    the reader's only sight of it. Where they differ the referee has already said so."""
    assert ("Your interview puts the longest Stunning can be down at 24 h, and the grid was read "
            "beside it rather than instead of it.") in worksheet()


def test_an_activity_the_interview_stated_no_figure_for_says_only_what_the_grid_derives():
    said = worksheet(mtpd=None)

    assert "Your interview puts" not in said
    assert "stands at 24 h" in said


def test_the_recovery_target_and_the_recovery_point_are_given_per_data_set():
    said = worksheet(data_sets=[
        {"name": "ERP order data", "recovery_target": "8 h", "rpo": "4 h (ERP order data)"},
        {"name": "the weighbridge log", "recovery_target": "24 h", "rpo": "24 h"}])

    assert "For ERP order data: the recovery target is 8 h" in said
    assert "For the weighbridge log: the recovery target is 24 h" in said
    assert "as a whole" not in said, "one data set's figure was shown as covering them all"


def test_an_activity_that_names_no_data_set_says_the_figures_stand_for_all_of_it():
    said = worksheet()

    assert ("No data set is named for Stunning in this BIA, so what stands below stands for the "
            "activity as a whole rather than for one set of its data.") in said
    assert ("For Stunning: the recovery target is 8 h, and the recovery point is "
            "4 h (ERP order data).") in said


def test_the_mbco_is_the_record_s_own_string_character_for_character():
    assert ACTIVITY["mbco"] in worksheet()


def test_the_minimum_resources_are_given_with_the_workaround_for_each():
    said = worksheet(resources=[
        {"name": "twelve cutters", "by_when": "8 h", "workaround": "the day shift boning by hand"}])

    assert "The minimum resources Stunning needs over time, and what stands in for each:" in said
    assert "twelve cutters — needed by 8 h" in said
    assert "Without it: the day shift boning by hand." in said


def test_a_record_that_says_nothing_about_the_resources_says_that_rather_than_naming_one():
    said = worksheet()

    assert "minimum resources over time for Stunning were not established" in said
    assert "Without it" not in said


def test_a_figure_the_record_does_not_hold_is_not_established_rather_than_absent():
    said = worksheet(mbco=None)

    assert f"minimum acceptable service for Stunning is {NOTHING}" in said


def test_the_dependencies_are_named_by_the_register_ids_the_record_holds():
    said = worksheet(dependencies=["KA-01", "KA-02"])

    assert "Stunning depends on KA-01 and KA-02, by the ids your dependency register holds" in said
    assert "KA-09" not in said


def test_an_activity_the_register_models_nothing_for_says_so():
    assert "No dependency of Stunning" in worksheet(dependencies=[])


def test_every_scored_category_carries_its_exact_quote_and_the_file_it_came_from():
    said = worksheet()

    assert f"financial — “{SCORE_QUOTE}” ({PATH})" in said
    assert f"“{STATED_QUOTE}” ({PATH})" in said


# ── the scope guide ──────────────────────────────────────────────────────────


def test_the_scope_guide_says_of_each_activity_that_it_is_in_the_scope_agreed():
    """The one line the scope guide carries above the figures, named to its own activity."""
    assert ("Stunning is in the scope of this BIA, and what follows was agreed for it."
            in render(RECORD)[views.SCOPE])


# ── what is open, in every view ──────────────────────────────────────────────


def test_the_open_items_are_the_record_s_own_and_stand_in_every_view():
    for view in render(RECORD).values():
        assert STILL_OPEN in view and OPEN_ITEM in view


def test_a_record_that_leaves_nothing_open_says_so_rather_than_showing_an_empty_heading():
    assert "Nothing in this BIA" in render({**RECORD, "open_items": []})[views.SCOPE]


# ── the three scenarios, as properties of an arbitrary record ────────────────
#
# Everything above renders one hand-built record, and a hand-built record is a record somebody
# chose. The v1 package that held three different MTPDs would have passed every example a person
# thought to write, because the person writing them was the person who believed the four agreed.
# What follows hands `render` records nobody chose: one to six activities, figures present and
# absent, grids that cross and grids that never do.

BANDS = ["0–4 h", "8 h", "24 h"]
GRID_LENSES = ["financial", "legal-regulatory"]

#: Short words, from an alphabet with no comma and no `and` in it, so a property may count the
#: separators `listed` put in without a word being able to smuggle one of its own.
WORDS = st.text(alphabet="abc de-", min_size=1, max_size=8).map(str.strip).filter(bool)

CELLS = st.integers(min_value=1, max_value=5) | st.just("MISSING")
IDS = st.lists(st.sampled_from(["KA-01", "KA-02", "KA-03"]), max_size=3, unique=True)

NAMED = st.fixed_dictionaries({"name": WORDS, "recovery_target": st.none() | WORDS,
                               "rpo": st.none() | WORDS})
RESOURCES = st.fixed_dictionaries({"name": WORDS, "by_when": st.none() | WORDS,
                                   "workaround": st.none() | WORDS})
QUOTES = st.fixed_dictionaries({"quote": WORDS, "source_path": st.just(PATH),
                                "lens": st.none() | st.sampled_from(GRID_LENSES)})

ACTIVITIES = st.fixed_dictionaries({
    "name": st.sampled_from(["Stunning", "Chilling", "Boning", "Dispatch", "Weighing", "Loading"]),
    "impact_grid": st.dictionaries(st.sampled_from(GRID_LENSES),
                                   st.fixed_dictionaries(dict.fromkeys(BANDS, CELLS)),
                                   min_size=1),
    "mtpd": st.none() | st.sampled_from(BANDS),
    "recovery_target": st.none() | WORDS,
    "rpo": st.none() | WORDS,
    "mbco": st.none() | WORDS,
    "dependencies": IDS,
    "data_sets": st.lists(NAMED, max_size=2),
    "resources": st.lists(RESOURCES, max_size=2),
    "evidence": st.lists(QUOTES, max_size=2),
})

#: One to six activities, so the story's "at least five" is a band this property covers rather
#: than a single case somebody remembered to write down.
RECORDS = st.fixed_dictionaries({
    "record_schema_version": st.just(1),
    "run_id": st.just(RECORD["run_id"]),
    "dept": WORDS,
    "method": st.just(METHOD),
    "open_items": st.lists(WORDS, max_size=2),
    "activities": st.lists(ACTIVITIES, min_size=1, max_size=6,
                           unique_by=lambda activity: activity["name"]),
})

#: How a figure-bearing sentence opens, taken from the module's own templates rather than retyped:
#: the literal text in front of each template's first `{`. A template whose figure comes first is
#: found by the literal *inside* it instead — `RESOURCE` opens with the resource's own name.
FIGURE_LEADS = tuple(template.split("{")[0] for template in (
    figures.MTPD_SAYS, figures.NO_MTPD_SAYS, figures.STATED, figures.WHOLE, figures.TARGETS,
    figures.MBCO_SAYS, figures.RESOURCES_SAY, figures.NO_RESOURCES))
RESOURCE_MARK = figures.RESOURCE.split("}")[1].split("{")[0]


def figures_in(text):
    """Every paragraph of a view that states a figure, in the order the view states them.

    Not "the figures agree": the paragraphs themselves, so a view that carries one the others do
    not is as loud as a view that is missing one. The v1 package failed both ways at once — the
    worksheet said `0–4 hours` where the record said `24 h`, and it said it in a sentence the
    handover did not carry at all.
    """
    return [block for block in text.split("\n\n")
            if block.startswith(FIGURE_LEADS) or RESOURCE_MARK in block]


@given(RECORDS)
def test_rendering_is_a_function_of_the_record_bytes_and_of_nothing_else(record):
    """Same bytes in, same four out — with a JSON round trip between, so it is the bytes."""
    assert render(record) == render(json.loads(json.dumps(record)))


@given(RECORDS)
def test_no_view_can_hold_a_figure_the_other_three_do_not(record):
    """The scenario the v1 package failed, over records nobody chose.

    The four must state the *same sentences in the same order*, not four figures that happen to
    match. Equality is what makes the test bite both ways: a view missing a figure fails it, and so
    does a view carrying an extra one nobody else states — which is the half a "do they agree?"
    comparison cannot see, because a figure only one document holds has nothing to disagree with.
    """
    rendered_all = render(record)
    said = figures_in(rendered_all[views.SCOPE])

    assert said, "the scope guide stated no figure at all, so this proves nothing"
    for name, text in rendered_all.items():
        assert figures_in(text) == said, f"{name} does not state the same figures"


@given(RECORDS)
def test_every_activity_in_scope_reaches_every_one_of_the_four(record):
    """Six activities as readily as one: a document that dropped the sixth is a BIA missing it."""
    for name, text in render(record).items():
        for activity in record["activities"]:
            assert f"## {activity['name']}" in text, f"{name} left out {activity['name']}"


@given(RECORDS, WORDS)
def test_a_changed_figure_moves_every_view_that_states_it(record, mbco):
    """The second scenario. `!` is outside the alphabet above, so the new figure is a new one."""
    changed = {**record, "activities": [{**a, "mbco": mbco + "!"} for a in record["activities"]]}
    before, after = render(record), render(changed)

    for name in views.FOUR:
        assert after[name] != before[name], f"{name} did not follow the record"
        assert mbco + "!" in after[name]


@given(RECORDS)
def test_the_mtpd_a_view_states_is_the_one_the_grid_derives_or_no_figure_at_all(record):
    """A view may not name a horizon of its own, and may not print a figure nobody derived."""
    for activity in record["activities"]:
        horizon, _ = crossing(activity["impact_grid"], METHOD)
        said = figures.stands(activity, METHOD)

        if horizon == "no MTPD within horizons":
            assert said == figures.NO_MTPD_SAYS.format(activity=activity["name"])
            assert "stands at" not in said
        else:
            assert said.endswith(f"stands at {horizon}.")
            assert said.index("reaches") < said.index("stands at")


# ── the pure functions the sentences are built out of ────────────────────────


@given(st.lists(WORDS, max_size=5))
def test_a_list_a_manager_reads_holds_every_word_and_no_separator_it_did_not_need(words):
    said = figures.listed(words)

    assert all(word in said for word in words)
    assert said.count(" and ") == (1 if len(words) > 1 else 0)
    assert said.count(", ") == max(len(words) - 2, 0)
    assert (said == "") == (words == [])


@given(st.text(max_size=20))
def test_the_four_always_land_somewhere_a_filesystem_will_take(dept):
    """Whatever the department is called, including in a script this box cannot spell."""
    assert re.fullmatch(r"output/[a-z0-9-]*", folder({"dept": dept}))


@given(st.none() | st.text(max_size=8) | st.integers() | st.lists(st.integers(), max_size=2))
def test_a_figure_is_the_record_s_own_string_or_the_words_for_one_it_does_not_hold(value):
    """Never rounded, never reworded, never blank: the two outcomes are the only two there are."""
    said = figures._held(value)

    assert said in (NOTHING, str(value))
    assert said != ""


@given(st.none() | st.text(max_size=4) | st.integers() | st.just("MISSING"))
def test_a_cell_is_the_score_the_record_holds_or_the_words_for_one_nobody_scored(value):
    """A grid cell is printed or it is said to be unscored; a blank cell reads as a zero."""
    said = views._cell(value)

    assert said in (NOT_SCORED, str(value))
    assert said != ""


# ── ticket 132: his chat confirmation, never inside an interview-quote block ─────────────────────
CONFIRMATION = {"type": "chat_confirmation", "words": "Record RTO 8 h", "on": "2026-09-23",
                "turn_id": "t-7"}


def test_a_chat_confirmation_is_shown_as_his_confirmation_with_its_date_and_never_as_a_quote():
    docs = render({**RECORD, "activities": [{**ACTIVITY,
                                             "evidence": [*ACTIVITY["evidence"], CONFIRMATION]}]})
    line = "The manager's confirmation in chat on 2026-09-23: Record RTO 8 h"
    assert line in docs[views.WORKSHEET]
    assert "“Record RTO 8 h”" not in "".join(docs.values())
    assert "Record RTO 8 h" not in docs[views.CAPTURE]  # the interview's words, and his are not


def test_a_record_signed_with_manager_confirmed_renders_as_it_did():
    """Ruling A: a record signed before ticket 132 is read as it stands. Its `manager_confirmed`
    entry renders as every entry did before, and nothing here asks the referee about it."""
    legacy = {"type": "manager_confirmed", "quote": "Set by the manager in chat: no reason given.",
              "source_path": ""}
    docs = render({**RECORD, "activities": [{**ACTIVITY, "evidence": [legacy]}]})
    # as main renders it (131's fallback was reverted): the empty path it was signed with
    said = "“Set by the manager in chat: no reason given.” ()"
    assert said in docs[views.WORKSHEET] and said in docs[views.CAPTURE]


# ── ticket 171: the register row the derived RPO rests on, said as the register's, never as a quote
REGISTER_ROW = {"type": "register_row", "activity": "packing", "asset_id": "erp",
                "quote": "4 h (order data)",
                "source_path": "03_Dependencies/dependency-register.json"}


def test_a_register_row_is_said_as_the_register_s_and_never_as_an_interview_quote():
    docs = render({**RECORD, "activities": [{**ACTIVITY,
                                             "evidence": [*ACTIVITY["evidence"], REGISTER_ROW]}]})
    line = ("The dependency register gives erp a recovery point of 4 h (order data) for packing "
            "(03_Dependencies/dependency-register.json)")
    assert line in docs[views.WORKSHEET]
    assert "4 h (order data)" not in docs[views.CAPTURE]  # the interview's words, and it is not
    assert "“4 h (order data)”" not in "".join(docs.values())


def test_the_register_giving_no_rpo_is_said_as_the_register_s_with_what_it_read():
    """t171-shape (DRAFT, awaiting the owner): the no-RPO row, in the register's name."""
    row = {"type": "register_no_rpo", "activity": "dispatch", "asset_ids": ["fleet", "staff"],
           "source_path": "03_Dependencies/dependency-register.json"}
    none = {**row, "asset_ids": []}
    docs = render({**RECORD, "activities": [{**ACTIVITY,
                                             "evidence": [*ACTIVITY["evidence"], row, none]}]})
    assert ("The dependency register gives no recovery point for dispatch in its rows for fleet, "
            "staff (03_Dependencies/dependency-register.json)") in docs[views.WORKSHEET]
    assert ("The dependency register gives no recovery point for dispatch in its rows for no "
            "dependency (03_Dependencies/dependency-register.json)") in docs[views.WORKSHEET]
    assert "fleet, staff" not in docs[views.CAPTURE]


# ── What the renderer reaches for: the record, and nothing else ──────────────────────────────────
# From `tests/ui/walk/test_stage_4b_the_four_views.py` step 28 (ticket 16), last held at 602cc648,
# which ticket 165's last slice retired with that walk file. Read off the real tree found by walking
# up, never mutmut's rewritten copy; the seal proves the same thing rather than reading it.


def _source_of(name):
    return (repo_root() / "src" / "nemo" / name).read_text(encoding="utf-8")


def _code_without_prose(source):
    """A module's code with its comments and strings taken out, spaced token by token: `nemo.views`
    names `nemo.referee` and the transcripts in its own docstring, and prose about a door is not a
    door."""
    return " " + " ".join(
        token.string for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type not in (tokenize.COMMENT, tokenize.STRING)) + " "


def test_the_four_are_rendered_with_the_disk_the_clock_and_the_network_taken_away(seal):
    expected = render(RECORD)
    seal()

    assert render(RECORD) == expected


def test_the_renderer_and_its_sentences_reach_for_nothing_outside_the_record():
    for name in ("views.py", "figures.py"):
        written = _code_without_prose(_source_of(name))
        for reach in ("read_text", "read_bytes", "datetime", "time", "uuid", "random", "urllib",
                      "requests", "glob", "iterdir", "open", "interview", "evidence", "referee",
                      "walk", "conduct"):
            assert f" {reach} " not in written, f"step 28: `nemo.{name}` reaches for {reach!r}"
    imports = {name: sorted({line.split()[1] for line in _source_of(name).splitlines()
                             if line.startswith("from nemo.")})
               for name in ("views.py", "figures.py")}
    assert imports["views.py"] == ["nemo.figures", "nemo.impact", "nemo.method", "nemo.record",
                                   "nemo.room_store"], f"step 28: the renderer imports {imports}"
    assert imports["figures.py"] == ["nemo.impact", "nemo.record"], (
        f"step 28: the sentences import {imports}, and one of them is above them")


def test_the_one_door_onto_the_disk_is_used_by_write_alone():
    source = _source_of("views.py")
    assert source.count("write_document") == 2, (
        "step 28: the one door onto the disk is used somewhere other than the import and `write`")
    assert "write_document" not in _source_of("figures.py"), (
        "step 28: the sentences reach the disk, and the handover says them too")
    [rendering] = [node for node in ast.parse(source).body
                   if isinstance(node, ast.FunctionDef) and node.name == "render"]
    assert "write_document" not in ast.unparse(rendering), "step 28: rendering a view writes one"
