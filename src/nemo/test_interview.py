"""Properties of the room's evidence reader, stated against the module rather than through it.

`nemo.interview` is the module ticket 12 split out below the walk, and the structure report is
what makes the gap visible: every other module in the package has a `test_` of its own in the
report's top layer, and this one had only `nemo.test_walk`. That is fine while the walk is its
only caller and stops being fine the moment the second one arrives — the docstring names three,
the walk now, the referee when it checks a quote, and ticket 13's interview held in the room. A
module tested only through the layer above it is a module whose contract is whatever that layer
happens to ask for, and the next caller inherits the parts nobody pinned.

So these are the reader's own guarantees, said once, here: a preview is the file's own bytes, a
fingerprint is the digest `sha256sum` would print, a file reads back exactly as it was written,
and an interview is offered under a name a manager can press. The examples in `nemo.test_walk`
stay where they are; they say what stage 2 does with this module, which is a different claim.
"""

import hashlib
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from nemo.interview import (
    INTERVIEWS,
    OWNER_INTERVIEWS,
    PREVIEW,
    _departments_in,
    _name,
    about_to_be_filed,
    departments,
    digest,
    digest_of,
    held,
    paths_about,
    previewed_whole,
    text,
    unreadable,
)
from nemo.record import DEPARTMENT

#: A department as a room's files spell one: no newline, and nothing the front matter's `[ \t]*`
#: would have taken off before it became a process. The same shape `nemo.test_walk` draws.
DEPARTMENTS = st.text(alphabet="abcXY Z0,-", min_size=1, max_size=8).map(str.strip).filter(bool)

#: What a company files an interview under. Underscores and hyphens are the point: they are what
#: `_name` turns back into words, and `26_08_00_interview` is what the seed room actually holds.
STEMS = st.text(alphabet="abcXYZ012_-", min_size=1, max_size=10)

#: An interview's body. Any character at all except a second `department:` line, which would be a
#: test writing front matter by accident rather than the reader finding some.
#:
#: `codec="utf-8"` is the domain, not a narrowing: these examples are written to a file and read
#: back, and a lone surrogate is not a character a file can hold — `"\ud800".encode()` raises
#: before the reader is ever called. Bare `st.characters()` offers them, `st.text()`'s own default
#: alphabet does not, and the gap only showed when hypothesis replayed a stored example: the
#: property ran for two tickets and then failed on a `UnicodeEncodeError` in the test's own
#: `written` helper, which says nothing about `nemo.interview` at all.
BODY = st.text(st.characters(exclude_characters=":", codec="utf-8"), max_size=500)


def written(room_folder, home, stem, department, body=""):
    """One interview on disk in one of the room's two homes, with its own front matter."""
    target = room_folder / home / f"{stem}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(f"---\n{DEPARTMENT}: {department}\n---\n\n{body}".encode())
    return target


def room(scratch):
    """An empty room with both homes, made per example: a shared folder leaks one into the next."""
    folder = Path(scratch) / "demo-1"
    for home in (INTERVIEWS, OWNER_INTERVIEWS):
        (folder / home).mkdir(parents=True)
    return folder


# ── what the file says ───────────────────────────────────────────────────────


@given(st.text(max_size=300))
def test_an_interview_reads_back_exactly_as_it_was_written(content):
    """UTF-8 in, the same characters out — the property `read_bytes().decode()` is spelled for.

    Round-tripped through bytes rather than compared to a string the test also wrote with
    `write_text`, so a locale that is not UTF-8 cannot make both ends agree on the wrong thing.
    """
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "interview.md"
        target.write_bytes(content.encode())
        assert text(target) == content


@given(st.binary(max_size=300))
def test_the_fingerprint_is_the_one_sha256sum_would_print(payload):
    """The whole claim of a fingerprint: an operator can check a binding without the product."""
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "interview.md"
        target.write_bytes(payload)
        assert digest(target) == hashlib.sha256(payload).hexdigest()


@given(st.binary(max_size=300))
def test_a_file_that_is_gone_has_no_fingerprint_and_is_never_mistaken_for_one(payload):
    """"" is not a digest of anything, so a file that vanished can never match what was bound."""
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "interview.md"
        target.write_bytes(payload)
        real = digest(target)
        target.unlink()
        assert digest(target) == ""
        assert real != ""


# ── what is shown beside it ──────────────────────────────────────────────────


@given(DEPARTMENTS, BODY)
def test_a_preview_is_the_files_own_opening_characters_and_never_a_summary(department, body):
    """A yes is a yes to bytes: what is shown is a prefix of the file, cut and nothing else."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        target = written(folder, INTERVIEWS, "26_08_00_interview", department, body)
        offered = held(folder, department)[0]
        assert offered.preview == text(target)[:PREVIEW]
        assert text(target).startswith(offered.preview)


@given(DEPARTMENTS, BODY)
def test_a_preview_is_never_longer_than_what_a_manager_reads_on_a_phone(department, body):
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        written(folder, INTERVIEWS, "26_08_00_interview", department, body)
        assert len(held(folder, department)[0].preview) <= PREVIEW


# ── an interview that is not on disk yet ─────────────────────────────────────


@given(STEMS, BODY)
def test_an_interview_about_to_be_filed_is_previewed_whole_and_never_cut(stem, content):
    """Ticket 13's preview is the whole of what will be written, not its opening characters: a
    manager endorses the interview they just held, all of it, and `PREVIEW` is about offering a
    file somebody else wrote."""
    offered = about_to_be_filed(f"{OWNER_INTERVIEWS}/{stem}.md", content)
    assert offered.preview == content
    assert offered.path == f"{OWNER_INTERVIEWS}/{stem}.md"
    assert offered.name == _name(Path(f"{OWNER_INTERVIEWS}/{stem}.md"))


@given(STEMS, BODY)
def test_the_fingerprint_of_bytes_not_yet_on_disk_is_the_one_they_will_have(stem, content):
    """The whole claim of the preview: a yes is a yes to named bytes before there are any."""
    offered = about_to_be_filed(f"{OWNER_INTERVIEWS}/{stem}.md", content)
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "interview.md"
        target.write_bytes(content.encode())
        assert digest(target) == offered.fingerprint


@given(STEMS, BODY)
def test_an_interview_about_to_be_filed_is_read_back_as_previewed_whole(stem, content):
    """What tells the two kinds apart without a flag: the bytes in hand are the bytes promised."""
    assert previewed_whole(about_to_be_filed(f"{OWNER_INTERVIEWS}/{stem}.md", content))


@given(DEPARTMENTS, st.integers(min_value=1, max_value=200))
def test_a_file_longer_than_the_preview_is_never_previewed_whole(department, over):
    """A cut preview digests to something else, so nothing may write it back over the file.

    The length is drawn past `PREVIEW` rather than anywhere in a band: a body that happened to fit
    under the cut *is* previewed whole, which is the other half of the property below it.
    """
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        written(folder, INTERVIEWS, "26_08_00_interview", department, "w" * (PREVIEW + over))
        assert not previewed_whole(held(folder, department)[0])


@given(DEPARTMENTS)
def test_a_file_that_fits_under_the_cut_is_previewed_whole(department):
    """Nothing is hidden by the cut, so the preview and the fingerprint say the same thing."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        written(folder, INTERVIEWS, "26_08_00_interview", department, "w")
        assert previewed_whole(held(folder, department)[0])


@given(BODY)
def test_the_two_digests_are_one_digest(content):
    """One `sha256sum`, whether the bytes are on disk or about to be."""
    assert digest_of(content) == hashlib.sha256(content.encode()).hexdigest()


# ── the name on the button ───────────────────────────────────────────────────


@given(STEMS)
def test_a_name_carries_the_same_characters_the_company_filed_it_under(stem):
    """Said in words, never reworded: only the separators change, and the letters are the file's."""
    assert _name(Path(f"{INTERVIEWS}/{stem}.md")).replace(" ", "") == stem.replace(
        "_", "").replace("-", "")


@given(STEMS)
def test_a_name_is_a_button_and_never_a_path(stem):
    """`docs/voice.md` §3.1 keeps a path off a card everywhere but the `Source:` line."""
    name = _name(Path(f"{INTERVIEWS}/{stem}.md"))
    assert "/" not in name
    assert ".md" not in name
    assert not {"_", "-"} & set(name)


# ── which interviews are on file ─────────────────────────────────────────────


@given(st.lists(STEMS, unique=True, max_size=3), st.lists(STEMS, unique=True, max_size=3),
       DEPARTMENTS)
def test_every_interview_in_either_home_is_offered_once_and_in_path_order(company, room_held, dept):
    """Both homes are read and neither wins (ADR-0002), each file once, in the order of its path."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for stem in company:
            written(folder, INTERVIEWS, stem, dept)
        for stem in room_held:
            written(folder, OWNER_INTERVIEWS, stem, dept)
        offered = [item.path for item in held(folder, dept)]
        assert offered == sorted(offered)
        assert set(offered) == ({f"{INTERVIEWS}/{stem}.md" for stem in company}
                                | {f"{OWNER_INTERVIEWS}/{stem}.md" for stem in room_held})


@given(st.lists(STEMS, unique=True, max_size=3), DEPARTMENTS, DEPARTMENTS)
def test_an_interview_is_offered_for_the_process_it_names_and_for_no_other(stems, mine, other):
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for stem in stems:
            written(folder, INTERVIEWS, stem, other)
        assert held(folder, mine) == () or mine == other


@given(st.lists(STEMS, unique=True, max_size=3), DEPARTMENTS)
def test_every_path_offered_is_room_relative_and_names_a_file_in_the_room(stems, dept):
    """A path on the `Source:` line the room does not hold is provenance for nothing."""
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for stem in stems:
            written(folder, INTERVIEWS, stem, dept)
        for item in held(folder, dept):
            assert not Path(item.path).is_absolute()
            assert (folder / item.path).is_file()


@given(st.lists(STEMS, unique=True, max_size=3), DEPARTMENTS)
def test_the_scope_is_read_off_the_companys_own_transcripts_and_not_off_ours(stems, dept):
    """An interview the room held itself is evidence for the BIA, never a source for the scope.

    The asymmetry is deliberate and is the one thing about this module a caller would get wrong by
    guessing: `held` reads both homes, `departments` reads only what the company brought.
    """
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for stem in stems:
            written(folder, OWNER_INTERVIEWS, stem, dept)
        assert departments(folder) == set()
        assert len(paths_about(folder, OWNER_INTERVIEWS, dept)) == len(stems)


@given(st.lists(STEMS, unique=True, max_size=3), st.lists(STEMS, unique=True, max_size=3),
       DEPARTMENTS)
def test_a_capture_naming_no_department_is_the_one_this_reader_calls_unreadable(good, bad, dept):
    """What ticket 50's admission check asks the room's evidence, in this reader's own words.

    Both homes, because both are read at stage 2 and neither wins (ADR-0002), and by path so that
    whoever is told has something to open. A file with front matter naming a department is
    evidence for it; one without names nobody, so no stage can bind it and no walk that needs it
    reaches stage 5 — which is a seed a delegate must not be seated in front of, not a file to
    skip quietly.
    """
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for stem in good:
            written(folder, INTERVIEWS, stem, dept)
        for stem in bad:
            (folder / OWNER_INTERVIEWS / f"{stem}.md").write_bytes(b"# an interview\n")
        assert unreadable(folder) == sorted(f"{OWNER_INTERVIEWS}/{stem}.md" for stem in bad)


def test_a_capture_that_is_not_utf_8_is_unreadable_in_either_home_and_offered_for_nothing(tmp_path):
    """Ticket 237: bytes this reader cannot decode name nobody, and no encoding is guessed."""
    folder = room(tmp_path)
    latin = "---\ndepartment: Kühlung\n---\n".encode("latin-1")
    for home in (INTERVIEWS, OWNER_INTERVIEWS):
        written(folder, home, "good", "Kühlung")
        (folder / home / "bad.md").write_bytes(latin)

    assert departments(folder) == {"Kühlung"}
    assert [item.path for item in held(folder, "Kühlung")] == [
        f"{INTERVIEWS}/good.md", f"{OWNER_INTERVIEWS}/good.md"]
    assert unreadable(folder) == [f"{INTERVIEWS}/bad.md", f"{OWNER_INTERVIEWS}/bad.md"]


@given(st.lists(DEPARTMENTS, unique=True, max_size=3))
def test_every_department_the_transcripts_name_is_read_back_each_once(names):
    with tempfile.TemporaryDirectory() as scratch:
        folder = room(scratch)
        for index, name in enumerate(names):
            written(folder, INTERVIEWS, f"26_08_0{index}_interview", name)
        assert departments(folder) == set(names)


# ── the front matter, read on its own ────────────────────────────────────────


@given(st.lists(DEPARTMENTS, max_size=3), BODY)
def test_the_front_matter_names_exactly_the_departments_it_lists(names, body):
    """Pure, so it is stated directly: what comes out is what the lines say, in their order."""
    lines = "".join(f"{DEPARTMENT}: {name}\n" for name in names)
    assert _departments_in(f"---\n{lines}---\n\n{body}") == names


@given(DEPARTMENTS, st.text(alphabet=" \t", max_size=4), st.text(alphabet=" \t", max_size=4))
def test_the_spacing_around_a_department_is_not_part_of_its_name(name, before, after):
    """A manager presses this name, so a trailing tab would be a second, unpressable process."""
    assert _departments_in(f"{DEPARTMENT}:{before}{name}{after}\n") == [name]
