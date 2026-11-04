"""Served facts (ticket 106): what the room's files say, worked out by nemo and never by the model.

Each function is tested over a room fixture written here, in the seed's own file shapes: the
dependency register's `supplier` fields, the company profile's customer table, the risk register's
rows and the interviews' front matter. A name resolves by case, legal form, its first word, its
abbreviation or one edit, and never by meaning; a name no file carries is "no file names it".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from nemo import facts
from nemo.facts import (
    LABELS,
    NOT_NAMED,
    PROFILE,
    REGISTER,
    RISKS,
    Company,
    Held,
    Mention,
    OnFile,
    Stated,
    _held,
    _one_edit,
    carried,
    companies,
    company,
    in_their_words,
    interviews,
    read,
)
from nemo.interview import INTERVIEWS, OWNER_INTERVIEWS

RISK_ROW = ("| **R-MKT-01** | Customer concentration / delisting (Kornmark 27%) | Market | "
            "Revenue concentration | Revenue loss | Bernd Cramer |")
PROFILE_TEXT = """# Company profile

| Area | Supplier | Contract |
|---|---|---|
| Refrigeration | Frostmark Kältetechnik GmbH | KT-2023-11 |

## Key customers

| Customer / channel | Revenue share |
|---|---|
| Kornmark (discounter) | 27% |
| Frischwert grocery retail group | 19% |
"""
REGISTER_DATA = {
    "synthetic": True,
    "KA-01": {"asset_id": "KA-01", "name": "Central refrigeration plant",
              "supplier": "Frostmark Kältetechnik GmbH"},
    "KA-02": {"asset_id": "KA-02", "name": "Plate freezers",
              "supplier": "Frostmark Kältetechnik GmbH"},
    "UV-CO2-01": {"asset_id": "UV-CO2-01", "name": "CO2 tank",
                  "supplier": "Nordgas Industriegase GmbH (primary) / AirTec Gase AG (second)"},
    "LF-ABP-01": {"asset_id": "LF-ABP-01", "name": "Category 3 collection",
                  "supplier": "Norddeutsche Tierkörperverwertung GmbH (NTV)"},
    "UV-WASSER-01": {"asset_id": "UV-WASSER-01", "name": "Water",
                     "supplier": "Municipal utilities (2 networks) + own well"},
    "UV-DAMPF-01": {"asset_id": "UV-DAMPF-01", "name": "Steam", "supplier": None},
    "IT-ERP-01": {"asset_id": "IT-ERP-01", "name": "ERP",
                  "notes": "Outage led to an OTIF miss at Kornmark.",
                  "consumers": [{"dept": "versand", "notes": "Kornmark's window"}, {"weight": 3}]},
}
AHLGRIM = """---
type: interview-transcript
department: Slaughter
owner: Torsten Ahlgrim
---

**Ahlgrim:** Kornmark is our biggest customer.
**Dohm:** And Frischwert?
"""
LOUVEN = """---
department: Cutting / Deboning
owner: Petra Louven
---

**Louven:** kornmark at twenty-seven percent.
"""
FOLLOW_UP = """---
type: inbox
created: 2026-08-03
---

**Wohlleben:** nothing about customers here.
"""


def room(base: Path) -> Path:
    """A room in the seed's shapes: three interviews in its first home, one in its second."""
    files = {
        PROFILE: PROFILE_TEXT,
        REGISTER: json.dumps(REGISTER_DATA, indent=2),
        RISKS: "# Risk register\n\n| ID | Risk | Owner |\n|---|---|---|\n" + RISK_ROW + "\n"
               "| **R-OPS-01** | Refrigeration failure (Frostmark contract) | Dirk Wohlleben |\n"
               "\nKornmark named outside the table.\n",
        "06_Risk-and-Incidents/incident-history.md":
            "OTIF miss with the major customer Kornmark.\n",
        f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md": AHLGRIM,
        f"{INTERVIEWS}/26_08_24_cutting-louven-interview.md": LOUVEN,
        f"{INTERVIEWS}/26_13_03_maintenance-followup-interview.md": FOLLOW_UP,
        f"{OWNER_INTERVIEWS}/packing-ruser-interview.md": "no front matter; Kornmark.\n",
        f"{INTERVIEWS}/notes.txt": "Kornmark in a file that is not an interview.\n",
        "output/.proto/slaughter.json": '{"said": "Kornmark"}\n',
        "public/graph/index.md": "Kornmark on the public page.\n",
    }
    for path, content in files.items():
        (base / path).parent.mkdir(parents=True, exist_ok=True)
        (base / path).write_text(content)
    return base


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    return room(tmp_path)


# ── part 1: a company by name ───────────────────────────────────────────────────────────────
def test_the_companies_are_the_register_s_suppliers_then_the_profile_s_customers(
        folder: Path) -> None:
    assert companies(folder) == (
        Company("Frostmark Kältetechnik GmbH", "supplier", "", REGISTER,
                ("frostmark kältetechnik", "frostmark")),
        Company("Nordgas Industriegase GmbH", "supplier", "", REGISTER,
                ("nordgas industriegase", "nordgas")),
        Company("AirTec Gase AG", "supplier", "", REGISTER, ("airtec gase", "airtec")),
        Company("Norddeutsche Tierkörperverwertung GmbH", "supplier", "", REGISTER,
                ("norddeutsche tierkörperverwertung", "norddeutsche", "ntv")),
        Company("Kornmark", "Customer / channel", "27%", PROFILE, ("kornmark",)),
        Company("Frischwert grocery retail group", "Customer / channel", "19%", PROFILE,
                ("frischwert grocery retail group", "frischwert")),
    ), "each once, in file order; a supplier without a legal form (utilities, none) is no company"


def test_a_room_without_the_two_files_lists_no_company(tmp_path: Path) -> None:
    assert companies(tmp_path) == ()


@pytest.mark.parametrize("asked", ["Kornmark", "kornmark", "KORNMARK", "Kornmark GmbH",
                                   "  Kornmark GmbH & Co. KG ", "Kornmark (discounter)", "Kornmrk",
                                   "Kornmarkt", "Kormark", "Lornmark"])
def test_a_name_with_another_case_suffix_or_one_typo_resolves(folder: Path, asked: str) -> None:
    found = company(folder, asked)
    assert [c.name for c in found.companies] == ["Kornmark"]
    assert found.said == "" and found.asked == asked


def test_how_it_resolved_is_said_so_the_match_is_explainable(folder: Path) -> None:
    assert company(folder, "Kornmark GmbH").how == "by name"
    assert company(folder, "Kornmrk").how == "one letter off"
    assert company(folder, "Frostmark").how == "by name", "a company's first word is its short name"
    assert company(folder, "ntv").how == "by name", "its abbreviation, from the register's aside"
    assert company(folder, "Kornmark and Frostmark").how == ""


def test_an_exact_match_wins_over_one_edit(folder: Path) -> None:
    """"airtec" is one edit from nothing else, but "nordgas" must not also pull in a near name."""
    assert [c.name for c in company(folder, "Nordgas").companies] == ["Nordgas Industriegase GmbH"]


def test_two_letters_off_is_no_match(folder: Path) -> None:
    found = company(folder, "Kornmxxk")
    assert (found.companies, found.mentions, found.said) == ((), (), NOT_NAMED)


def test_what_the_files_say_about_it_register_rows_then_interviews_then_the_rest(
        folder: Path) -> None:
    found = company(folder, "Kornmark GmbH")
    assert found.mentions == (
        Mention(RISKS, RISK_ROW, "R-MKT-01"),
        Mention(RISKS, "Kornmark named outside the table.", ""),
        Mention(REGISTER, "Outage led to an OTIF miss at Kornmark.", "IT-ERP-01"),
        Mention(REGISTER, "Kornmark's window", "IT-ERP-01"),
        Mention(f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md",
                "**Ahlgrim:** Kornmark is our biggest customer.", ""),
        Mention(f"{INTERVIEWS}/26_08_24_cutting-louven-interview.md",
                "**Louven:** kornmark at twenty-seven percent.", ""),
        Mention(f"{OWNER_INTERVIEWS}/packing-ruser-interview.md", "no front matter; Kornmark.", ""),
        Mention(PROFILE, "| Kornmark (discounter) | 27% |", ""),
        Mention("06_Risk-and-Incidents/incident-history.md",
                "OTIF miss with the major customer Kornmark.", ""),
    ), "no .txt, nothing nemo wrote under output/, nothing on the public page"


def test_a_supplier_is_found_by_its_short_name_and_its_register_row(folder: Path) -> None:
    found = company(folder, "frostmark")
    assert [m.row for m in found.mentions if m.path == REGISTER] == ["KA-01", "KA-02"]
    assert [m.row for m in found.mentions if m.path == RISKS] == ["R-OPS-01"]


def test_a_name_is_matched_as_a_whole_word_only(folder: Path) -> None:
    (folder / "01_Organisation/other.md").write_text("Kornmarket and XKornmark are not it.\n")
    assert all("Kornmarket" not in m.quote for m in company(folder, "Kornmark").mentions)


def test_a_name_on_no_list_is_still_found_where_a_file_names_it(folder: Path) -> None:
    """"not found" is nemo's answer only when no file names it: a name the lists miss is searched as
    typed, legal form off, across the same files."""
    found = company(folder, "Frischwert GmbH")
    assert found.companies[0].name == "Frischwert grocery retail group"
    unlisted = company(folder, "Dohm")
    assert unlisted.companies == () and unlisted.how == "" and unlisted.said == ""
    assert unlisted.mentions == (Mention(f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md",
                                         "**Dohm:** And Frischwert?", ""),)


@pytest.mark.parametrize("asked", ["Zanderwerk", "Zanderwerk GmbH", "", "GmbH", "  "])
def test_a_name_no_file_carries_says_so_and_is_not_empty(folder: Path, asked: str) -> None:
    found = company(folder, asked)
    assert found.said == NOT_NAMED == "no file names it"
    assert (found.companies, found.mentions) == ((), ())


LETTERS = st.text(alphabet="abc", max_size=6)


def _distance(a: str, b: str) -> int:
    """Levenshtein, the textbook table: the reference `_one_edit` is held to."""
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


@given(LETTERS, LETTERS)
def test_one_edit_is_exactly_a_distance_of_one(a: str, b: str) -> None:
    assert _one_edit(a, b) == (_distance(a, b) == 1)


@pytest.mark.parametrize(("a", "b", "one"), [
    ("kornmark", "kornmrk", True), ("kornmrk", "kornmark", True), ("kornmark", "lornmark", True),
    ("kornmark", "kornmark", False), ("kornmark", "kornmakr", False), ("ab", "ba", False),
    ("abc", "a", False), ("", "a", True), ("", "", False)])
def test_one_edit_examples(a: str, b: str, one: bool) -> None:
    assert _one_edit(a, b) is one


# ── part 2: the interviews ──────────────────────────────────────────────────────────────────
def test_the_interviews_are_every_interview_file_with_who_when_and_about(folder: Path) -> None:
    held = interviews(folder)
    files = [p for home in (INTERVIEWS, OWNER_INTERVIEWS) for p in (folder / home).glob("*.md")]
    assert len(held) == len(files) == 4
    assert held == (
        Held(f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md", "Torsten Ahlgrim",
             "Slaughter", "4 Feb 2026"),
        Held(f"{INTERVIEWS}/26_08_24_cutting-louven-interview.md", "Petra Louven",
             "Cutting / Deboning", "24 Aug 2026"),
        Held(f"{INTERVIEWS}/26_13_03_maintenance-followup-interview.md", "", "", ""),
        Held(f"{OWNER_INTERVIEWS}/packing-ruser-interview.md", "", "", ""),
    ), "a month past 12 is no date, and a file with no front matter names nobody"


def test_a_room_with_no_interviews_holds_none(tmp_path: Path) -> None:
    assert interviews(tmp_path) == ()


@pytest.mark.parametrize(("month", "said"), list(enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)))
def test_every_month_is_said_by_its_name(tmp_path: Path, month: int, said: str) -> None:
    (tmp_path / INTERVIEWS).mkdir()
    (tmp_path / INTERVIEWS / f"25_{month:02d}_09_x.md").write_text("")
    assert interviews(tmp_path)[0].when == f"9 {said} 2025"


# ── part 3: the figure the record carries ───────────────────────────────────────────────────
AHLGRIM_PATH = f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md"
NOBODY_PATH = f"{INTERVIEWS}/26_13_03_maintenance-followup-interview.md"


KORNMARK_LINE = "**Ahlgrim:** Kornmark is our biggest customer."
NOBODY_LINE = "**Wohlleben:** nothing about customers here."


def test_the_record_s_figure_comes_first_and_each_interview_s_is_served_in_its_words(
        folder: Path) -> None:
    said = carried(folder, {"MTPD": "0–4 h", "RTO": "4 h"}, "signed",
                   [Stated("MTPD", "about a day", AHLGRIM_PATH, KORNMARK_LINE),
                    Stated("MTPD", "about a day", AHLGRIM_PATH, KORNMARK_LINE),
                    Stated("RTO", "8 h", NOBODY_PATH, NOBODY_LINE),
                    Stated("RPO", "n/a", "07_Interviews/gone.md", "gone")])
    assert said == {
        "MTPD": ("record: 0–4 h (signed)",
                 "Ahlgrim's interview (4 Feb 2026): about a day, "
                 f"in their words: “{KORNMARK_LINE}”"),
        "RTO": ("record: 4 h (signed)",
                "26 13 03 maintenance followup interview: 8 h, "
                f"in their words: “{NOBODY_LINE}”"),
    }, "record first; each interview once, by file name when it names nobody; no file, no line"


def test_an_activity_with_no_record_figure_serves_only_the_interview_s_labelled_as_such(
        folder: Path) -> None:
    said = carried(folder, {"MTPD": None}, "accepted",
                   [Stated("MTPD", "24 h", AHLGRIM_PATH, "Kornmark is our biggest")])
    assert said == {"MTPD": (
        "Ahlgrim's interview (4 Feb 2026): 24 h, in their words: “Kornmark is our biggest”",)}


def test_a_planted_value_whose_quote_the_file_does_not_hold_is_never_served(folder: Path) -> None:
    """The drafting model wrote the value; only a quote the interview file holds word for word
    makes it the interviewee's. A value with a quote the file lacks is left out, record kept."""
    planted = Stated("MTPD", "72 h", AHLGRIM_PATH, "**Ahlgrim:** Three days, easily.")
    assert carried(folder, {"MTPD": "8 h"}, "signed", [planted]) == {
        "MTPD": ("record: 8 h (signed)",)}
    assert carried(folder, {}, "signed", [planted]) == {}


def test_an_item_with_no_quote_is_never_served(folder: Path) -> None:
    assert carried(folder, {}, "signed", [Stated("MTPD", "24 h", AHLGRIM_PATH, "")]) == {}


@pytest.mark.parametrize(("path", "quote", "held"), [
    (AHLGRIM_PATH, KORNMARK_LINE, True), (AHLGRIM_PATH, "Kornmark is our", True),
    (AHLGRIM_PATH, "kornmark is our", True), (AHLGRIM_PATH, "", False), (AHLGRIM_PATH, "**", False),
    (NOBODY_PATH, KORNMARK_LINE, False), ("07_Interviews/gone.md", "x", False),
    (f"{INTERVIEWS}/notes.txt", "Kornmark", False), (RISKS, "Kornmark", False),
    (f"{OWNER_INTERVIEWS}/packing-ruser-interview.md", "Kornmark.", True)])
def test_a_quote_counts_only_verbatim_in_an_interview_file_of_the_room(
        folder: Path, path: str, quote: str, held: bool) -> None:
    assert in_their_words(folder, Stated("RTO", "8 h", path, quote)) is held


def test_one_reading_holds_every_interview_and_its_words(folder: Path) -> None:
    on_file = read(folder)
    assert on_file == OnFile(interviews(folder), {
        h.path: (folder / h.path).read_text() for h in interviews(folder)})
    assert list(on_file.words) == [h.path for h in on_file.held]
    assert f"{INTERVIEWS}/notes.txt" not in on_file.words


def test_one_reading_reads_each_interview_once_and_a_call_handed_it_reads_none(
        folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ticket 309: a build serving twenty activities read every interview ~76 times."""
    reads: list[str] = []
    real = facts.text

    def counted(path: Path) -> str:
        reads.append(path.relative_to(folder).as_posix())
        return real(path)

    monkeypatch.setattr(facts, "text", counted)
    on_file = read(folder)
    assert sorted(reads) == sorted(h.path for h in on_file.held)
    reads.clear()
    stated = [Stated("MTPD", "a day", AHLGRIM_PATH, KORNMARK_LINE)]
    for _ in range(3):
        carried(folder, {"MTPD": "4 h"}, "signed", stated, on_file)
    assert reads == []


def test_a_call_handed_a_reading_serves_what_it_would_read_itself(folder: Path) -> None:
    stated = [Stated("MTPD", "about a day", AHLGRIM_PATH, KORNMARK_LINE),
              Stated("RTO", "8 h", NOBODY_PATH, NOBODY_LINE),
              Stated("RPO", "1 h", AHLGRIM_PATH, "**Ahlgrim:** Three days, easily."),
              Stated("RPO", "n/a", "07_Interviews/gone.md", "gone")]
    alone = carried(folder, {"MTPD": "0–4 h"}, "signed", stated)
    assert carried(folder, {"MTPD": "0–4 h"}, "signed", stated, read(folder)) == alone
    assert set(alone) == {"MTPD", "RTO"}


def test_a_call_handed_a_reading_serves_from_it_and_not_from_the_disk(folder: Path) -> None:
    on_file = read(folder)
    (folder / AHLGRIM_PATH).unlink()
    said = carried(folder, {}, "signed",
                   [Stated("MTPD", "a day", AHLGRIM_PATH, KORNMARK_LINE)], on_file)
    assert said == {"MTPD": (
        f"Ahlgrim's interview (4 Feb 2026): a day, in their words: “{KORNMARK_LINE}”",)}
    assert carried(folder, {}, "signed",
                   [Stated("MTPD", "a day", AHLGRIM_PATH, KORNMARK_LINE)]) == {}


def test_a_figure_nobody_holds_is_left_out(folder: Path) -> None:
    assert carried(folder, {}, "accepted", []) == {}
    assert LABELS == ("MTPD", "RTO", "RPO")


def test_a_line_of_prose_is_cut_to_the_sentences_that_name_it_its_speaker_kept(
        folder: Path) -> None:
    path = f"{INTERVIEWS}/26_02_04_slaughter-ahlgrim-interview.md"
    (folder / path).write_text(
        "**Ahlgrim:** We slaughter pigs. Kornmark buys a lot! Frischwert less? Kornmark again.\n"
        "Plain prose names KORNMARK here. And nothing there.\n"
        "| a table row | Kornmark. Two sentences. |\n")
    assert [m.quote for m in company(folder, "Kornmark").mentions if m.path == path] == [
        "**Ahlgrim:** Kornmark buys a lot! … Kornmark again.",
        "Plain prose names KORNMARK here.",
        "| a table row | Kornmark. Two sentences. |"]


# ── the hardener's cases: each pins one rule the examples above left loose ─────────────────
def test_a_json_file_of_the_room_is_read_as_well_as_markdown(folder: Path) -> None:
    (folder / "02_BCM-Method").mkdir()
    (folder / "02_BCM-Method/method.json").write_text('{"customer": "Kornmark, 27%"}\n')
    assert Mention("02_BCM-Method/method.json", '{"customer": "Kornmark, 27%"}', "") in \
        company(folder, "Kornmark").mentions


def test_a_table_is_read_by_its_cells_whatever_they_start_or_end_with(folder: Path) -> None:
    (folder / RISKS).write_text("| ID | Risk |\n|---|---|\n|X-1|Kornmark|\n")
    assert company(folder, "Kornmark").mentions[0] == Mention(RISKS, "|X-1|Kornmark|", "X-1")


def test_a_table_with_no_separator_line_still_has_its_first_row_as_its_header(
        tmp_path: Path) -> None:
    (tmp_path / PROFILE).parent.mkdir(parents=True)
    (tmp_path / PROFILE).write_text("| Customer | Share |\n| Kornmark | 27% |\n| X | : |\n")
    assert [(c.name, c.share) for c in companies(tmp_path)] == [("Kornmark", "27%"), ("X", ":")]


def test_whose_interview_is_said_by_the_surname_and_an_undated_one_by_no_date(
        tmp_path: Path) -> None:
    (tmp_path / INTERVIEWS).mkdir()
    (tmp_path / INTERVIEWS / "sauer.md").write_text("---\nowner: Dr Katrin Sauer\n---\n")
    said = carried(tmp_path, {}, "accepted",
                   [Stated("RPO", "4 h", f"{INTERVIEWS}/sauer.md", "owner")])
    assert said == {"RPO": ("Sauer's interview: 4 h, in their words: “owner”",)}


def test_who_is_the_interviewee_and_the_owner_only_when_no_interviewee_is_named(
        tmp_path: Path) -> None:
    """Ticket 337: `owner:` is the process owner, who may not be the one interviewed; `who` is
    `interviewee:`, else `owner:`. The file is read in-process, so mutmut maps the call."""
    both = tmp_path / "26_10_02_dispatch-petke-interview.md"
    both.write_text("---\ninterviewee: Diana Petke\nowner: Henning Barsch\n---\nsaid\n")
    owner_only = tmp_path / "26_10_01_production-barsch-interview.md"
    owner_only.write_text("---\nowner: Henning Barsch\n---\nsaid\n")
    assert _held(f"{INTERVIEWS}/{both.name}", both.read_text()) == Held(
        f"{INTERVIEWS}/{both.name}", "Diana Petke", "", "2 Oct 2026")
    assert _held(f"{INTERVIEWS}/{owner_only.name}", owner_only.read_text()) == Held(
        f"{INTERVIEWS}/{owner_only.name}", "Henning Barsch", "", "1 Oct 2026")


def test_a_quote_that_differs_only_in_typography_is_served_and_a_reworded_one_is_not(
        folder: Path) -> None:
    """Fix round 2: the referee's comparison (`nemo.text.norm`, typography only, never wording).
    Curly quotes, dashes, emphasis marks and runs of white space are folded; words are not."""
    (folder / AHLGRIM_PATH).write_text(
        "---\nowner: Torsten Ahlgrim\n---\n**Ahlgrim:** It's \"about a day\" - then   it tears.\n")
    typographic = Stated("MTPD", "24 h", AHLGRIM_PATH,
                         "Ahlgrim: It’s “about a day” – then it tears.")
    reworded = Stated("MTPD", "24 h", AHLGRIM_PATH,
                      "Ahlgrim: It's \"about two days\" - then it tears.")
    assert in_their_words(folder, typographic) and not in_their_words(folder, reworded)
    assert carried(folder, {}, "signed", [typographic, reworded]) == {"MTPD": (
        f"Ahlgrim's interview (4 Feb 2026): 24 h, in their words: “{typographic.quote}”",)}
