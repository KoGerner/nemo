import json

from bia_figures.impact import NO_DATA_HELD, Derivation, derive_rpo
from bia_figures.test_vocabulary import NEW_SEED, new_seed_method, new_seed_only
from bia_figures.vocabulary import duration_of, looseness

METHOD = {
    "rpo_vocabulary": [
        "0 h (no loss)",
        "4 h (ERP order data)",
        "24 h (batch/traceability)",
        "n/a (physical)",
    ]
}
REGISTER = {
    "IT-ERP-01": {"name": "SAP S/4HANA + MES", "rpo": "4 h"},
    "IT-WAAGE-01": {"name": "Waagensystem", "rpo": "24 h"},
    "IT-NULL-01": {"name": "Kassensystem", "rpo": "0 h"},
    "KA-01": {"name": "Schlachtlinie", "rpo": "n/a"},
    "LF-ABP-01": {"name": "Tierkörperabfuhr", "rpo": "n/a"},
}


def test_duration_of_is_the_word_up_to_its_explanation() -> None:
    assert duration_of("4 h (ERP order data)") == "4 h"


def test_looseness_orders_a_duration_by_its_number() -> None:
    assert looseness("0 h") < looseness("4 h") < looseness("24 h") < looseness("n/a")


def test_the_tightest_data_holding_dependency_sets_the_figure() -> None:
    assert derive_rpo(["IT-ERP-01", "IT-WAAGE-01", "KA-01"], REGISTER, METHOD) == Derivation(
        "4 h (ERP order data)", ("IT-ERP-01",)
    )


def test_a_looser_dependency_is_not_named_in_the_reason() -> None:
    derivation = derive_rpo(["IT-WAAGE-01", "IT-ERP-01"], REGISTER, METHOD)
    assert "IT-WAAGE-01" not in derivation.reason


def test_every_dependency_that_ties_at_the_tightest_value_is_named() -> None:
    register = dict(REGISTER) | {"IT-WAAGE-01": {"rpo": "4 h"}}
    derivation = derive_rpo(["IT-ERP-01", "IT-WAAGE-01", "KA-01"], register, METHOD)
    assert derivation == Derivation("4 h (ERP order data)", ("IT-ERP-01", "IT-WAAGE-01"))


def test_an_activity_whose_dependencies_hold_no_data_gets_the_no_data_word() -> None:
    assert derive_rpo(["KA-01", "LF-ABP-01"], REGISTER, METHOD) == Derivation("n/a (physical)")


def test_an_activity_with_no_dependencies_at_all_gets_the_no_data_word() -> None:
    assert derive_rpo([], REGISTER, METHOD) == Derivation("n/a (physical)")


def test_a_tightest_value_of_zero_is_still_a_figure() -> None:
    assert derive_rpo(["IT-NULL-01", "IT-ERP-01"], REGISTER, METHOD) == Derivation(
        "0 h (no loss)", ("IT-NULL-01",)
    )


def test_a_recovery_point_the_vocabulary_has_no_word_for_derives_nothing() -> None:
    register = dict(REGISTER) | {"IT-WAAGE-01": {"rpo": "12 h"}}
    assert derive_rpo(["IT-ERP-01", "IT-WAAGE-01"], register, METHOD) == Derivation(
        None, unmatched=(("IT-WAAGE-01", "12 h"),)
    )


def test_the_figure_is_a_word_of_the_method_not_a_duration_invented_here() -> None:
    derivation = derive_rpo(["IT-WAAGE-01"], REGISTER, METHOD)
    assert derivation.figure in METHOD["rpo_vocabulary"]
    assert derivation.figure == "24 h (batch/traceability)"


REGISTER_WITH_METADATA = {"synthetic": True, **REGISTER}


def test_a_flag_among_the_dependencies_is_never_asked_for_a_recovery_point() -> None:
    """The call that raised `TypeError: 'bool' object is not subscriptable`."""
    derivation = derive_rpo(["IT-ERP-01", "synthetic"], REGISTER_WITH_METADATA, METHOD)
    assert derivation == Derivation(
        "4 h (ERP order data)", ("IT-ERP-01",), unrecognised=("synthetic",)
    )


def test_an_id_the_register_does_not_hold_does_not_set_the_figure_and_is_reported() -> None:
    derivation = derive_rpo(["IT-ERP-01", "AN-SCHLACHT-01"], REGISTER, METHOD)
    assert derivation.figure == "4 h (ERP order data)"
    assert derivation.reason == ("IT-ERP-01",)
    assert derivation.unrecognised == ("AN-SCHLACHT-01",)


def test_an_unknown_id_alone_leaves_the_no_data_word_and_an_empty_reason() -> None:
    derivation = derive_rpo(["AN-SCHLACHT-01"], REGISTER, METHOD)
    assert derivation == Derivation("n/a (physical)", (), unrecognised=("AN-SCHLACHT-01",))


def test_nothing_is_reported_when_the_register_knew_every_id() -> None:
    derivation = derive_rpo(["IT-ERP-01", "KA-01"], REGISTER, METHOD)
    assert derivation.unrecognised == ()


def test_an_unrecognised_id_is_reported_beside_a_recovery_point_beyond_the_method() -> None:
    register = dict(REGISTER) | {"IT-WAAGE-01": {"rpo": "12 h"}}
    derivation = derive_rpo(["IT-WAAGE-01", "synthetic"], register, METHOD)
    assert derivation.figure is None
    assert derivation.unmatched == (("IT-WAAGE-01", "12 h"),)
    assert derivation.unrecognised == ("synthetic",)


REGISTER_WRITTEN_BOTH_WAYS = {
    "IT-ERP-01": {"name": "SAP S/4HANA + MES", "rpo": "4 h"},
    "IT-WAAGE-01": {"name": "Waagensystem", "rpo": "4 h (ERP order data)"},
    "KA-01": {"name": "Schlachtlinie", "rpo": "n/a (physical)"},
    "UV-STROM-01": {"name": "Strom", "rpo": "n/a (physical)"},
}


def test_an_entry_writing_the_methods_whole_no_data_word_holds_no_data() -> None:
    derivation = derive_rpo(["KA-01", "UV-STROM-01"], REGISTER_WRITTEN_BOTH_WAYS, METHOD)
    assert derivation == Derivation("n/a (physical)")


def test_the_one_entry_holding_data_sets_the_figure_among_entries_writing_the_word() -> None:
    derivation = derive_rpo(
        ["IT-ERP-01", "KA-01", "UV-STROM-01"], REGISTER_WRITTEN_BOTH_WAYS, METHOD
    )
    assert derivation == Derivation("4 h (ERP order data)", ("IT-ERP-01",))


def test_the_same_duration_written_both_ways_ties() -> None:
    derivation = derive_rpo(["IT-ERP-01", "IT-WAAGE-01"], REGISTER_WRITTEN_BOTH_WAYS, METHOD)
    assert derivation == Derivation("4 h (ERP order data)", ("IT-ERP-01", "IT-WAAGE-01"))


def test_a_gloss_the_method_never_wrote_changes_no_duration() -> None:
    register = {"IT-WAAGE-01": {"rpo": "4 h (Auftragsdaten aus der Waage)"}}
    derivation = derive_rpo(["IT-WAAGE-01"], register, METHOD)
    assert derivation == Derivation("4 h (ERP order data)", ("IT-WAAGE-01",))


def test_a_glossed_duration_beyond_the_method_is_reported_as_the_register_wrote_it() -> None:
    register = {"IT-WAAGE-01": {"rpo": "12 h (Wiegedaten)"}}
    derivation = derive_rpo(["IT-WAAGE-01"], register, METHOD)
    assert derivation == Derivation(None, unmatched=(("IT-WAAGE-01", "12 h (Wiegedaten)"),))


# ── 190: the derivation on the new seed, read from the seed (never retyped) ──────────────────────


def new_seed_register() -> dict[str, object]:
    """The new seed's register, as its `03_Dependencies/dependency-register.json` holds it."""
    register: dict[str, object] = json.loads(
        (NEW_SEED / "03_Dependencies" / "dependency-register.json").read_text()
    )
    return register


def new_seed_dependencies(activity: str) -> list[str]:
    """The register entries the seed itself lists the activity among the consumers of."""
    return [
        key
        for key, entry in new_seed_register().items()
        if isinstance(entry, dict)
        and any(consumer["activity"] == activity for consumer in entry.get("consumers") or [])
    ]


@new_seed_only
def test_on_the_new_seed_it_helpdesk_derives_the_tightest_of_its_holders_words() -> None:
    """IT helpdesk and support, its own consumer rows: `cisco-telephony` `<24 h`; `bmc-remedy`,
    `microsoft-365` and `jira-service-management` `<1 h`; `it-helpdesk-staff` none."""
    dependencies = new_seed_dependencies("IT helpdesk and support")
    derivation = derive_rpo(
        dependencies, new_seed_register(), new_seed_method(), activity="helpdesk-and-support"
    )
    assert derivation.figure == "<1 h"
    assert set(derivation.reason) == {"bmc-remedy", "microsoft-365", "jira-service-management"}
    assert derivation.unmatched == ()


BOUNDS_ONLY = {"rpo_vocabulary": ["<1 h", "<24 h"]}


def test_a_method_without_a_no_data_word_derives_no_figure_where_nothing_holds_data() -> None:
    """190 item 2, the owner's (a) "No RPO at all": no figure, the no-data reason, apart from
    `unmatched` (a figure the method has no word for is a human's business; no data is not)."""
    register = {"IT-HELP-01": {"rpo": "<24 h"}, "ROLE-01": {"name": "a role"}}
    assert derive_rpo(["ROLE-01"], register, BOUNDS_ONLY) == Derivation(
        None, (NO_DATA_HELD,), unrecognised=("ROLE-01",)
    )
    assert derive_rpo([], register, BOUNDS_ONLY) == Derivation(None, (NO_DATA_HELD,))


def test_the_no_data_reason_says_so_in_words() -> None:
    assert NO_DATA_HELD == "none of the systems it depends on gives one for this activity"


def test_a_method_without_a_no_data_word_still_derives_from_its_holders() -> None:
    register = {"IT-HELP-01": {"rpo": "<24 h"}, "IT-TIX-01": {"rpo": "<1 h"}}
    assert derive_rpo(["IT-HELP-01", "IT-TIX-01"], register, BOUNDS_ONLY) == Derivation(
        "<1 h", ("IT-TIX-01",)
    )


@new_seed_only
def test_on_the_new_seed_without_the_activity_top_level_rpos_alone_hold_no_data_here() -> None:
    """Raw material procurement's dependencies declare no top-level RPO: asked without the activity,
    nothing reads its consumer rows, so no figure (the derivation before PER-CONSUMER)."""
    dependencies = new_seed_dependencies("Raw material procurement")
    derivation = derive_rpo(dependencies, new_seed_register(), new_seed_method())
    assert derivation == Derivation(None, (NO_DATA_HELD,), unrecognised=tuple(dependencies))
    assert dependencies


# ── 190 PER-CONSUMER (16_nemo_check): a dependency's RPO for THIS activity is its consumer row's ──


@new_seed_only
def test_on_the_new_seed_raw_material_procurement_derives_its_consumer_rows_tightest() -> None:
    """`microsoft-365`'s row says `<24 h`, `sharepoint-online`'s `<168 h`; `buyer`'s, 250's
    `raw-material-suppliers` (a supplier the records name, no figure, ADR-0034) and 251's three
    authored roles on every core activity (positions only, no figure, ADR-0034 Part B) none, nor
    303's `refrigeration` row (receiving at the ramp, marked, no figure, ADR-0034 Part E 13), nor
    325's `veterinary-and-qa-release` row (record 1.1's section 5, marked, no figure), nor 328's
    `marschkamp-headquarters` site row (marked, no figure, ADR-0034 Part E 16d), nor 348's
    `csb-erp-marschkamp` row (marked, no figure). The silent set is read off the seed: every
    dependency whose row for the activity states no RPO, each authored row among them."""
    dependencies = new_seed_dependencies("Raw material procurement")
    register = new_seed_register()
    derivation = derive_rpo(
        dependencies, register, new_seed_method(), activity="raw-material-procurement"
    )
    rows = {
        key: next(
            consumer
            for consumer in register[key]["consumers"]  # type: ignore[index]
            if consumer["activity"] == "Raw material procurement"
        )
        for key in dependencies
    }
    silent = tuple(key for key in dependencies if not rows[key].get("rpo"))
    assert {key for key, row in rows.items() if row.get("authored")} <= set(silent)
    assert derivation == Derivation("<24 h", ("microsoft-365",), unrecognised=silent)


@new_seed_only
def test_on_the_new_seed_data_protection_derives_its_consumer_rows_tightest() -> None:
    """`microsoft-365`, `sharepoint-online` and `jira-service-management` each say `<1 h` for it;
    the two roles say nothing."""
    dependencies = new_seed_dependencies("Data protection management")
    derivation = derive_rpo(
        dependencies, new_seed_register(), new_seed_method(), activity="data-protection"
    )
    assert derivation.figure == "<1 h"
    assert set(derivation.reason) == {
        "microsoft-365", "sharepoint-online", "jira-service-management"
    }


def test_a_consumer_row_for_the_activity_is_what_the_entry_declares_for_it() -> None:
    register = {
        "IT-1": {"rpo": "<24 h", "consumers": [{"department": "a", "rpo": "<1 h"},
                                               {"department": "b"}]},
        "IT-2": {"consumers": [{"department": "b", "rpo": "<168 h"}, "not a row"]},
        "IT-3": {"consumers": "not a list"},
    }
    one = derive_rpo(["IT-1"], register, BOUNDS_ONLY, activity="a")
    assert one == Derivation("<1 h", ("IT-1",))
    assert derive_rpo(["IT-1", "IT-2"], register, BOUNDS_ONLY, activity="b") == Derivation(
        None, unmatched=(("IT-2", "<168 h"),), unrecognised=("IT-1",)
    )
    # CONSUMER-ELSE-NONE: IT-1 has consumers and its row for b declares nothing, so nothing for b
    own = derive_rpo(["IT-1"], register, BOUNDS_ONLY, activity="b")
    assert own == Derivation(None, (NO_DATA_HELD,), unrecognised=("IT-1",))
    assert derive_rpo(["IT-2", "IT-3"], register, BOUNDS_ONLY, activity="c") == Derivation(
        None, (NO_DATA_HELD,), unrecognised=("IT-2", "IT-3")
    )


# ── 190 CONSUMER-ELSE-NONE (16_nemo_check): top-level rpo only for an entry with no consumers


def test_an_entry_with_consumers_but_no_row_for_the_activity_declares_nothing_for_it() -> None:
    """The top-level figure is another record's; it is never imported into this activity."""
    register = {"IT-1": {"rpo": "<1 h", "consumers": [{"department": "helpdesk", "rpo": "<1 h"}]}}
    assert derive_rpo(["IT-1"], register, BOUNDS_ONLY, activity="incident") == Derivation(
        None, (NO_DATA_HELD,), unrecognised=("IT-1",)
    )


def test_an_entry_with_no_consumers_field_declares_its_own_rpo_for_every_activity() -> None:
    """The old seed's shape: no consumer rows at all, so the entry's own figure stands."""
    register = {"IT-1": {"rpo": "<24 h"}, "IT-2": {"rpo": "<1 h", "consumers": []}}
    assert derive_rpo(["IT-1", "IT-2"], register, BOUNDS_ONLY, activity="any") == Derivation(
        "<24 h", ("IT-1",), unrecognised=("IT-2",)
    )


@new_seed_only
def test_on_the_new_seed_incident_management_derives_its_own_rows_not_the_helpdesk_s() -> None:
    """The dependencies its record lists (the draft's): bmc-remedy has no incident row, so its
    top-level <1 h (helpdesk's record's) is not imported; jira-service-management's row says <24 h,
    cisco-call-manager's and microsoft-teams' >168 h, the roles none."""
    listed = ["cisco-call-manager", "bmc-remedy", "microsoft-teams", "jira-service-management",
              "lead-incident-manager", "manager-on-duty", "recovery-team"]
    derivation = derive_rpo(
        listed, new_seed_register(), new_seed_method(), activity="incident-and-problem-management"
    )
    assert derivation.figure == "<24 h"
    assert derivation.reason == ("jira-service-management",)


@new_seed_only
def test_on_the_new_seed_time_recording_derives_no_rpo() -> None:
    """Record HR 3.0 has no resource table: payroll-system and time-recording-system have no
    time-recording row, so neither declares anything for it."""
    derivation = derive_rpo(
        ["payroll-system", "time-recording-system"], new_seed_register(), new_seed_method(),
        activity="time-recording",
    )
    assert derivation.figure is None
    assert derivation.reason == (NO_DATA_HELD,)
