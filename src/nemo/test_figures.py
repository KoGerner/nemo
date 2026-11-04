"""The sentences, as properties of one activity rather than as sentences somebody read once.

Everything here hands a function an activity nobody chose and reads the sentence that comes back.
There is no record on disk in this file, no document around the sentences and no walk in front of
them: every function in `nemo.figures` is a function of the activity it is handed and of the method
that activity was scored under, so a test that needed any of the three would be testing something
other than the thing the module promises.

**Why properties rather than examples, here in particular.** The v1 package held MTPD `24 h` in the
record, `8 h` in the handover and `0–4 hours` in the worksheet, and it passed every example a
person thought to write — because the person writing them was the person who believed the three
agreed. What a hand-built activity cannot reach is the shape of the gaps: an activity with no
MBCO, with no resources, with two data sets and no figures in either, with a grid that never
crosses. Those are where a sentence quietly becomes a blank, a `None` or a figure borrowed from
the activity above it, and `st.none() | ...` on every field is what walks into them.

`seal` is the package's, from `nemo.test_purity` by way of the conftest beside it: the module's
docstring says it reaches neither disk nor clock nor network, and this is the file that holds it
to that by nailing those doors shut in the process rather than by reading the source.
"""

import json
import re

from hypothesis import given
from hypothesis import strategies as st

from nemo import figures
from nemo.figures import NOTHING, depends, listed, requirements, says, stands
from nemo.impact import crossing

BANDS = ["0–4 h", "8 h", "24 h"]
GRID_LENSES = ["financial", "legal-regulatory"]

METHOD = {
    "time_horizons": BANDS,
    "scenarios": [{"id": "financial", "name": "Financial"},
                  {"id": "legal-regulatory", "name": "Legal / regulatory"}],
    "intolerability_threshold": 4,
}

#: Short words, from an alphabet with no comma and no `and` in it, so a property may count the
#: separators `listed` put in without a word being able to smuggle one of its own.
WORDS = st.text(alphabet="abc de-", min_size=1, max_size=8).map(str.strip).filter(bool)

#: The scores a method with a threshold of 4 can be handed, named as a band rather than left to
#: `st.integers()`: this suite is derandomized, so a strategy that does not state its own
#: boundaries is a strategy that never offers the one score that crosses.
CELLS = st.integers(min_value=1, max_value=5) | st.just("MISSING")

NAMED = st.fixed_dictionaries({"name": WORDS, "recovery_target": st.none() | WORDS,
                               "rpo": st.none() | WORDS})
RESOURCES = st.fixed_dictionaries({"name": WORDS, "by_when": st.none() | WORDS,
                                   "workaround": st.none() | WORDS})

#: One activity, with every figure it carries free to be absent. A figure that is always present
#: is a gap this file would never render.
ACTIVITIES = st.fixed_dictionaries({
    "name": WORDS,
    "impact_grid": st.dictionaries(st.sampled_from(GRID_LENSES),
                                   st.fixed_dictionaries(dict.fromkeys(BANDS, CELLS)),
                                   min_size=1),
    "mtpd": st.none() | st.sampled_from(BANDS),
    "recovery_target": st.none() | WORDS,
    "rpo": st.none() | WORDS,
    "mbco": st.none() | WORDS,
    "dependencies": st.lists(st.sampled_from(["KA-01", "KA-02", "KA-03"]), max_size=3, unique=True),
    "data_sets": st.lists(NAMED, max_size=2),
    "resources": st.lists(RESOURCES, max_size=2),
})


# ── what every sentence is held to, whatever it is about ─────────────────────


@given(ACTIVITIES)
def test_every_sentence_is_said_about_the_activity_it_was_handed(activity):
    """No sentence about an activity may fail to name it.

    The v1 defect a reader actually meets is a figure under the wrong heading. Each of these is
    rendered under `## <name>` one layer up and read as being about it, so a sentence that does
    not carry the name is one nothing ties to the activity it came from — except the `RESOURCE`
    and `TARGETS` lines, which name the resource and the data set instead and are listed under a
    sentence that does name the activity.
    """
    named = [said for said in requirements(activity, METHOD)
             if not said.startswith(("For ", *[item["name"] for item in activity["resources"]]))]

    assert named, "nothing was said about this activity at all, so this proves nothing"
    for said in named:
        assert activity["name"] in said


@given(ACTIVITIES)
def test_no_sentence_is_blank_and_every_one_of_them_ends_in_a_stop(activity):
    """A gap is said in words. A blank line, a dash, or a sentence that trails off is not one."""
    for said in requirements(activity, METHOD):
        assert said.strip() == said and said != ""
        assert said.endswith((".", ":")), f"this is not a finished sentence: {said!r}"


@given(ACTIVITIES)
def test_the_same_activity_says_the_same_sentences_twice(activity):
    """Same bytes in, same sentences out — with a JSON round trip between, so it is the bytes.

    This is the whole of "the views and the handover cannot disagree": they do not compare
    anything, they call this twice.
    """
    again = json.loads(json.dumps(activity))

    assert requirements(activity, METHOD) == requirements(again, METHOD)
    assert requirements(activity, METHOD) == [*says(activity, METHOD), *depends(activity)]


#: One activity with every figure in it, for the tests a property cannot carry: the seal is
#: `monkeypatch`'s and so is function-scoped, which Hypothesis refuses to re-enter per example.
FULL = {
    "name": "Stunning",
    "impact_grid": {"financial": dict(zip(BANDS, (2, 3, 4), strict=True))},
    "mtpd": "24 h",
    "recovery_target": "8 h",
    "rpo": "4 h (ERP order data)",
    "mbco": "50% cutting capacity, A-customers only, one shift",
    "dependencies": ["KA-01"],
    "data_sets": [{"name": "ERP orders", "recovery_target": "4 h", "rpo": "1 h"}],
    "resources": [{"name": "the stunner", "by_when": "4 h", "workaround": "nothing"}],
}


def test_the_sentences_are_built_with_the_disk_the_clock_and_the_network_taken_away(seal):
    """The module's own promise, proved rather than read: nailed shut for the length of the call."""
    expected = requirements(FULL, METHOD)
    seal()

    assert requirements(FULL, METHOD) == expected


# ── the figures themselves ───────────────────────────────────────────────────


@given(ACTIVITIES)
def test_the_mtpd_said_is_the_one_the_grid_derives_or_no_figure_at_all(activity):
    """A sentence may not name a horizon of its own, and may not print one nobody derived."""
    horizon, _ = crossing(activity["impact_grid"], METHOD)
    said = stands(activity, METHOD)

    if horizon == "no MTPD within horizons":
        assert said == figures.NO_MTPD_SAYS.format(activity=activity["name"])
        assert "stands at" not in said
    else:
        assert said.endswith(f"stands at {horizon}.")
        assert said.index("reaches") < said.index("stands at")


@given(ACTIVITIES)
def test_a_figure_the_activity_does_not_hold_is_said_to_be_missing_and_never_borrowed(activity):
    """Every figure in the sentences is the activity's own string, or `NOTHING` — never another's.

    The borrowing this forbids is the one the shape invites: where no data set is named, the
    activity's own RTO and RPO stand for the whole of it, and where two are named each says its
    own. A set that carried the activity's figures would read as a figure somebody stated about it.
    """
    said = "\n".join(says(activity, METHOD))
    held = {str(value) for key in ("recovery_target", "rpo", "mbco", "mtpd")
            if (value := activity.get(key))}

    for figure in re.findall(r"recovery target is (.+?), and the recovery point is (.+?)\.", said):
        for value in figure:
            assert value == NOTHING or value in held or any(
                value in (str(item.get("recovery_target")), str(item.get("rpo")))
                for item in activity["data_sets"])


@given(ACTIVITIES)
def test_a_data_set_the_record_names_is_said_for_itself_and_never_for_the_activity(activity):
    """Named sets get one sentence each; no set at all gets the sentence saying so, and one more."""
    said = says(activity, METHOD)
    targets = [line for line in said if line.startswith("For ")]
    whole = figures.WHOLE.format(activity=activity["name"])

    assert len(targets) == max(len(activity["data_sets"]), 1)
    assert (whole in said) == (activity["data_sets"] == [])


@given(ACTIVITIES)
def test_the_resources_section_names_every_resource_or_says_there_are_none(activity):
    """Never a heading with nothing under it, and never a resource the record does not hold."""
    said = says(activity, METHOD)
    listing = [line for line in said if line.endswith(figures.RESOURCES_SAY.split("}")[1])]

    if not activity["resources"]:
        assert listing == [] and figures.NO_RESOURCES.format(activity=activity["name"]) in said
    else:
        assert len(listing) == 1
        for item in activity["resources"]:
            assert any(line.startswith(item["name"] + " — needed by ") for line in said)


@given(ACTIVITIES)
def test_the_dependencies_said_are_the_register_ids_the_record_holds_and_no_others(activity):
    """One sentence either way: the ids, or that none of them resolved to one."""
    said, = depends(activity)
    ids = activity["dependencies"]

    assert all(one in said for one in ids)
    assert ("depends on" in said) == bool(ids)
    for other in {"KA-01", "KA-02", "KA-03"} - set(ids):
        assert other not in said


# ── the two functions every sentence above is built out of ───────────────────


@given(st.lists(WORDS, max_size=5))
def test_a_list_a_manager_reads_holds_every_word_and_no_separator_it_did_not_need(words):
    said = listed(words)

    assert all(word in said for word in words)
    assert said.count(" and ") == (1 if len(words) > 1 else 0)
    assert said.count(", ") == max(len(words) - 2, 0)
    assert (said == "") == (words == [])


@given(st.none() | st.text(max_size=8) | st.integers() | st.lists(st.integers(), max_size=2))
def test_a_figure_is_the_record_s_own_string_or_the_words_for_one_it_does_not_hold(value):
    """Never rounded, never reworded, never blank: the two outcomes are the only two there are."""
    said = figures._held(value)

    assert said in (NOTHING, str(value))
    assert said != ""


# ── ticket 120: the one line after a side whose figure the record does not carry ──────────────

KEPT = st.sampled_from(["72 h", "0–4 h", "8 h", "168 h", "< 4 h"])


@given(KEPT)
def test_a_kept_figure_is_said_exactly_as_handed(kept):
    said = figures.kept_says(kept)
    assert said == f"The tighter figure, {kept}, stands."
    assert said == figures.kept_says(kept)  # the same bytes on a second call


@given(KEPT)
def test_the_manager_s_own_kept_figure_is_his_and_never_the_tighter_one(kept):
    said = figures.kept_says(kept, his=True)
    assert said == f"The manager's own figure, {kept}, stands."
    assert "tighter" not in said


@given(st.sampled_from([None, ""]), st.booleans())
def test_no_kept_figure_says_nothing(kept, his):
    assert figures.kept_says(kept, his=his) == ""


@given(KEPT, st.booleans())
def test_neither_sentence_addresses_the_reader(kept, his):
    words = re.findall(r"[a-z]+", figures.kept_says(kept, his=his).lower())
    assert "you" not in words and "your" not in words


def test_the_kept_sentence_is_built_with_the_disk_the_clock_and_the_network_taken_away(seal):
    expected = (figures.kept_says("72 h"), figures.kept_says("72 h", his=True))
    seal()

    assert (figures.kept_says("72 h"), figures.kept_says("72 h", his=True)) == expected
