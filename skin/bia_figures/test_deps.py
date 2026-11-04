import json
import os
import subprocess
import sys

from bia_figures.deps import FILES, PROPOSED, dependencies, elsewhere, floor
from bia_figures.impact import derive_rpo
from bia_figures.register import assets, is_asset, is_dependable, is_metadata, recovery_point_for

REGISTER = {
    "IT-ERP-01": {"name": "SAP S/4HANA + MES", "rpo": "4 h"},
    "IT-WAAGE-01": {"name": "Waagensystem", "rpo": "24 h"},
    "KA-01": {"name": "Schlachtlinie", "rpo": "n/a"},
}


def test_an_id_an_interview_names_is_a_dependency_although_no_model_proposed_it() -> None:
    interview = "Slaughter runs on KA-01; the data go into the ERP, IT-ERP-01, four hours."
    result = dependencies(REGISTER, [interview], ["KA-01"])
    assert result == {"IT-ERP-01": FILES, "KA-01": FILES}


def test_an_id_only_a_model_proposed_is_marked_proposed() -> None:
    result = dependencies(REGISTER, ["Slaughter runs on KA-01."], ["KA-01", "IT-WAAGE-01"])
    assert result == {"KA-01": FILES, "IT-WAAGE-01": PROPOSED}


def test_an_id_the_interviews_name_stays_marked_as_coming_from_the_files() -> None:
    result = dependencies(REGISTER, ["KA-01 and IT-ERP-01."], ["IT-ERP-01"])
    assert result["IT-ERP-01"] == FILES


def test_a_longer_token_that_merely_begins_like_an_id_is_not_a_naming() -> None:
    assert dependencies(REGISTER, ["The line KA-0199 was retired last year."], []) == {}


def test_the_registers_own_consumer_list_is_not_consulted() -> None:
    register = {"IT-ERP-01": {"rpo": "4 h", "consumers": ""}, "KA-01": {"rpo": "n/a"}}
    assert dependencies(register, ["Everything we weigh lands in IT-ERP-01."], []) == {
        "IT-ERP-01": FILES
    }


def test_every_interview_is_read_not_only_the_first() -> None:
    result = dependencies(REGISTER, ["Runs on KA-01.", "Department RPO (IT-ERP-01): 4 h"], [])
    assert result == {"IT-ERP-01": FILES, "KA-01": FILES}


def test_an_id_no_interview_names_and_no_model_proposed_is_absent() -> None:
    assert "IT-WAAGE-01" not in dependencies(REGISTER, ["KA-01 only."], [])


def test_an_id_that_ends_a_longer_token_is_not_a_naming_either() -> None:
    """Whole token in both directions: a prefix in front of the id does not name it."""
    assert floor(REGISTER, ["Die Nebenlinie X-KA-01 steht still."]) == set()


def test_an_underscore_binds_into_the_token_so_the_id_is_not_named() -> None:
    assert floor(REGISTER, ["Die Anlage KA-01_alt wurde ersetzt."]) == set()


def test_an_id_the_interview_spells_differently_is_not_a_naming() -> None:
    """Named means as the register spells it: a different casing is a different id."""
    assert floor(REGISTER, ["Die schlachtlinie ka-01 laeuft."]) == set()


def test_punctuation_around_an_id_does_not_hide_it() -> None:
    assert floor(REGISTER, ["Buchung (IT-ERP-01); Waage: IT-WAAGE-01."]) == {
        "IT-ERP-01",
        "IT-WAAGE-01",
    }


def test_the_two_marks_are_distinct_so_a_caller_can_tell_them_apart() -> None:
    """A manager reads these to know which dependencies nobody had to judge."""
    assert FILES != PROPOSED
    assert (FILES, PROPOSED) == ("files", "proposed")


def test_a_proposal_repeated_is_recorded_once() -> None:
    assert dependencies(REGISTER, [], ["KA-01", "KA-01"]) == {"KA-01": PROPOSED}


def test_a_proposal_the_register_does_not_hold_is_still_carried_as_proposed() -> None:
    """The floor never invents an id, but a model's proposal is the caller's to keep."""
    assert dependencies(REGISTER, [], ["XX-99"]) == {"XX-99": PROPOSED}


REGISTER_WITH_METADATA = {
    "synthetic": True,
    "walked_by": "Konstantin Gerner",
    **REGISTER,
}


def test_a_register_key_that_declares_no_recovery_point_is_never_a_dependency() -> None:
    """The room says of itself that it is synthetic data; the register says it too."""
    interview = "This room is synthetic data. Slaughter runs on KA-01 and books into IT-ERP-01."
    result = dependencies(REGISTER_WITH_METADATA, [interview], [])
    assert result == {"IT-ERP-01": FILES, "KA-01": FILES}


def test_a_second_piece_of_metadata_is_left_alone_too() -> None:
    interview = "The register was walked_by the consultant, and slaughter depends on KA-01."
    assert dependencies(REGISTER_WITH_METADATA, [interview], []) == {"KA-01": FILES}


def test_a_model_cannot_turn_metadata_into_a_dependency_by_proposing_it() -> None:
    result = dependencies(REGISTER_WITH_METADATA, ["Slaughter runs on KA-01."], ["synthetic"])
    assert result == {"KA-01": FILES}


def test_the_floor_offers_only_assets() -> None:
    assert floor(REGISTER_WITH_METADATA, ["synthetic walked_by KA-01"]) == {"KA-01"}


def test_a_proposal_the_register_does_not_hold_at_all_is_still_carried() -> None:
    """Metadata is refused because the register spoke of it; an unknown id it never did."""
    result = dependencies(REGISTER_WITH_METADATA, ["Slaughter runs on KA-01."], ["AN-SCHLACHT-01"])
    assert result == {"KA-01": FILES, "AN-SCHLACHT-01": PROPOSED}


#: A register that lists its ids in neither the order a manager would sort them nor the order a
#: set reads them, so an order that came from either is visible in the result.
A_ROOM = {
    "KA-01": {"name": "Schlachtlinie", "rpo": "n/a"},
    "UV-STROM-01": {"name": "Strom", "rpo": "n/a"},
    "IT-WAAGE-01": {"name": "Waagensystem", "rpo": "4 h"},
    "IT-ERP-01": {"name": "SAP S/4HANA + MES", "rpo": "4 h"},
    "LF-ABP-01": {"name": "Tierkoerperabfuhr", "rpo": "n/a"},
    "UV-WASSER-01": {"name": "Trinkwasser", "rpo": "n/a"},
}
A_ROOMS_INTERVIEW = ("Slaughter runs on KA-01 and UV-STROM-01, weighs on IT-WAAGE-01, books into "
                     "IT-ERP-01, hands over to LF-ABP-01 and needs UV-WASSER-01.")


def _in_a_fresh_process(hash_seed: str) -> list[str]:
    """The ids `dependencies` answers with, in order, from a process started on this hash seed."""
    script = ("import json; from bia_figures.deps import dependencies; "
              f"print(json.dumps(list(dependencies({A_ROOM!r}, {[A_ROOMS_INTERVIEW]!r}, []))))")
    done = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True,
        env={**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": os.pathsep.join(sys.path)},
    )
    ids: list[str] = json.loads(done.stdout)
    return ids


def test_the_order_the_ids_come_back_in_never_follows_the_hash_seed() -> None:
    """The ids are read out as a sentence a manager signs, so two processes must word it alike.

    The floor is a set, and a set reads in a new order in every new process. Reading that order
    into the mapping signed the same evidence as "(IT-WAAGE-01, IT-ERP-01)" on one process and
    "(IT-ERP-01, IT-WAAGE-01)" on the next.
    """
    orders = [_in_a_fresh_process(seed) for seed in ("1", "2", "3", "4", "5")]
    assert orders == [sorted(A_ROOM)] * len(orders)


#: A register whose ids are slugs, as the Marschkamp seed writes them: no person says
#: `csb-erp-marschkamp`, so the floor has to read the names the register gives them (ticket 184).
#: Planted, not read from a seed.
NAMED = {
    "microsoft-365": {"name": "Microsoft 365", "rpo": "<24 h"},
    "csb-erp-marschkamp": {"name": "CSB ERP Marschkamp", "rpo": "<4 h"},
    "jira": {"name": "Atlassian Jira", "rpo": "<24 h"},
    "jira-service-management": {"name": "Atlassian Jira Service Management", "rpo": "<24 h"},
    "keycloak": {"name": "Keycloak", "rpo": "<1 h"},
}


def test_an_interview_that_says_the_registers_names_floors_those_assets() -> None:
    interview = "Henning Barsch: Depends on: Microsoft 365, CSB ERP Marschkamp, Production staff."
    assert floor(NAMED, [interview]) == {"microsoft-365", "csb-erp-marschkamp"}


def test_a_name_that_runs_on_into_a_longer_word_is_not_a_naming() -> None:
    assert floor(NAMED, ["We once ran Microsoft 3650 and Keycloak-Legacy."]) == set()


def test_part_of_a_name_is_not_a_naming() -> None:
    assert floor(NAMED, ["The 365 licences and the CSB ERP of the old site."]) == set()


def test_a_name_is_matched_as_the_register_spells_it() -> None:
    assert floor(NAMED, ["microsoft 365 and csb erp marschkamp"]) == set()


def test_a_name_inside_a_longer_name_the_register_holds_is_not_named_as_well() -> None:
    """Who says "Atlassian Jira Service Management" has not said "Atlassian Jira"."""
    said = "Depends on: Atlassian Jira Service Management."
    assert floor(NAMED, [said]) == {"jira-service-management"}
    assert floor(NAMED, ["Depends on: Atlassian Jira, Keycloak."]) == {"jira", "keycloak"}


def test_an_id_named_interview_still_floors_by_id() -> None:
    assert floor(NAMED, ["Tickets go to jira-service-management."]) == {"jira-service-management"}


def test_a_name_floors_through_to_the_dependencies_marked_as_from_the_files() -> None:
    result = dependencies(NAMED, ["Depends on: CSB ERP Marschkamp."], ["keycloak"])
    assert result == {"csb-erp-marschkamp": FILES, "keycloak": PROPOSED}


def test_metadata_that_happens_to_carry_a_name_is_still_not_a_dependency() -> None:
    register = {**NAMED, "walked_by": {"name": "Konstantin Gerner"}}
    assert floor(register, ["Depends on: Konstantin Gerner, Keycloak."]) == {"keycloak"}


def test_a_longer_name_shields_a_shorter_one_even_when_it_is_no_asset() -> None:
    """The Marschkamp register holds "Atlassian Jira Service Management" with no recovery point
    of its own: it floors nothing, and it still is not a saying of "Atlassian Jira"."""
    register = {**NAMED, "jira-service-management": {"name": "Atlassian Jira Service Management"}}
    assert floor(register, ["Depends on: Atlassian Jira Service Management."]) == set()


#: A register shaped like the Marschkamp seed's (ticket 184, widened): every entry carries an
#: `asset_type`, and only some of the IT systems carry a recovery point of their own. Planted.
WIDE = {
    "synthetic": True,
    "depends_on_evidence_note": "Every quote is rendered the way the seed renders the records.",
    "microsoft-365": {"name": "Microsoft 365", "asset_type": "IT system"},
    "csb-erp-marschkamp": {"name": "CSB ERP Marschkamp", "asset_type": "IT system", "rpo": "4 h"},
    "production-staff": {"name": "Production staff", "asset_type": "Role"},
    "bank": {"name": "Bank", "asset_type": "External supplier"},
    "personnel-mail": {"name": "Personnel mail", "asset_type": "Document"},
    "refrigeration": {"name": "Refrigeration", "asset_type": "Technology"},
}


def test_a_depends_on_line_floors_every_entry_it_names_rpo_or_not() -> None:
    said = "Depends on: Microsoft 365, CSB ERP Marschkamp"
    assert floor(WIDE, [said]) == {"microsoft-365", "csb-erp-marschkamp"}


def test_a_near_miss_on_the_depends_on_line_floors_nothing() -> None:
    said = "Henning Barsch: Depends on: Microsoft 3650, 365, CSB ERP."
    assert floor(WIDE, [said]) == set()


def test_a_role_a_supplier_a_technology_and_a_document_on_the_line_floor() -> None:
    said = "Heike Brodersen: Depends on: Production staff, Bank, Refrigeration, Personnel mail."
    assert floor(WIDE, [said]) == {"production-staff", "bank", "refrigeration", "personnel-mail"}


#: The Brodersen interviews' case: "Bank" said in passing, off the interviewee's own line.
BANK_IN_PASSING = ("Heike Brodersen: IT systems. HR master data system: RPO <1 h. Workaround: Bank "
                   "details are taken from the personnel file, and the bank confirms each run.\n"
                   "Heike Brodersen: Our Production staff never book into CSB ERP Marschkamp.\n")


def test_a_name_said_off_the_depends_on_line_floors_nothing() -> None:
    assert floor(WIDE, [BANK_IN_PASSING]) == set()


def test_the_same_name_said_on_the_line_floors() -> None:
    said = BANK_IN_PASSING + "Heike Brodersen: Depends on: Bank.\n\nFranziska Dohm: Thank you.\n"
    assert floor(WIDE, [said]) == {"bank"}


def test_only_what_the_line_itself_says_floors_not_the_lines_around_it() -> None:
    said = "Heike Brodersen: Depends on: Bank.\nFranziska Dohm: And Microsoft 365?\n"
    assert floor(WIDE, [said]) == {"bank"}


def test_the_facilitators_depends_on_line_is_not_the_interviewees_own() -> None:
    said = ("---\ninterviewee: Heike Brodersen\nfacilitator: Franziska Dohm\n---\n"
            "Franziska Dohm: Depends on: Bank, perhaps?\n"
            "Heike Brodersen: Depends on: Production staff.\n")
    assert floor(WIDE, [said]) == {"production-staff"}


def test_an_id_still_floors_anywhere_in_the_text_as_today() -> None:
    assert floor(WIDE, ["Orders book into csb-erp-marschkamp overnight."]) == {"csb-erp-marschkamp"}


def test_an_id_that_is_an_ordinary_word_floors_nothing_off_the_line() -> None:
    """`bank` is the register's id for the Bank; "the bank confirms" is no naming of it."""
    assert floor(WIDE, ["The bank confirms; refrigeration was fine."]) == set()


def test_a_models_proposal_of_an_entry_with_no_recovery_point_is_kept_as_proposed() -> None:
    result = dependencies(WIDE, ["Depends on: CSB ERP Marschkamp."], ["microsoft-365", "bank"])
    assert result == {"csb-erp-marschkamp": FILES, "microsoft-365": PROPOSED, "bank": PROPOSED}


def test_a_metadata_key_proposed_is_still_dropped() -> None:
    proposed = ["synthetic", "depends_on_evidence_note", "production-staff"]
    assert dependencies(WIDE, [], proposed) == {"production-staff": PROPOSED}


def test_an_entry_is_dependable_by_its_type_or_its_rpo_and_the_rest_is_metadata() -> None:
    register = {**WIDE, "KA-01": {"rpo": "n/a"}, "note": {"name": "no type, no rpo"}}
    for key in ("microsoft-365", "csb-erp-marschkamp", "production-staff", "bank", "KA-01"):
        assert is_dependable(register, key) and not is_metadata(register, key)
    for key in ("synthetic", "depends_on_evidence_note", "note"):
        assert is_metadata(register, key) and not is_dependable(register, key)
    assert not is_dependable(register, "AN-SCHLACHT-01")


def test_a_role_on_the_line_is_a_dependency_and_never_a_recovery_point() -> None:
    """The RPO arithmetic reads assets only: a floored role sets no figure."""
    origin = dependencies(WIDE, ["Depends on: Production staff, CSB ERP Marschkamp."], [])
    assert origin == {"csb-erp-marschkamp": FILES, "production-staff": FILES}
    assert not is_asset(WIDE, "production-staff")
    assert assets(WIDE) == ["csb-erp-marschkamp"]
    assert recovery_point_for(WIDE, "csb-erp-marschkamp", activity=None) == "4 h"
    derived = derive_rpo(origin, WIDE, {"rpo_vocabulary": ["4 h (ERP)", "n/a"]})
    assert derived.reason == ("csb-erp-marschkamp",)


def test_another_departments_interview_lists_nothing_for_this_activity() -> None:
    """A payroll draft may rest on the payments interview; payments' own line is not payroll's."""
    said = "Heike Brodersen: Depends on: Production staff, Bank.\nBooks go to csb-erp-marschkamp.\n"
    assert floor(WIDE, [elsewhere(said)]) == {"csb-erp-marschkamp"}
    assert floor(WIDE, [said]) == {"production-staff", "bank", "csb-erp-marschkamp"}
