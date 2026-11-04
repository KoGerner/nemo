"""The shape of the dependency register the caller supplies.

It sits below both layers because both read a register and neither owns it: the floor reads its
ids, the derivation reads its recovery points.
Keeping the shape here is what stops the derivation importing the floor for a data shape it has
nothing else to do with.

A register holds more than assets: it may carry a line about itself — that the room is synthetic
data, who walked it — beside them. An entry an activity may depend on is one that says what kind of
thing it is (`asset_type`: a system, a technology, a role, a supplier, a document) or declares a
recovery point; everything else the register holds is metadata, and no layer above may take it for
a dependency (ticket 184). An asset is the narrower kind, an entry that declares a recovery point:
the only kind the RPO derivation asks for one.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

Register = Mapping[str, Any]

RECOVERY_POINT = "rpo"
KIND = "asset_type"


def is_asset(register: Register, key: str) -> bool:
    """Whether the register holds `key` as an entry declaring a recovery point."""
    entry = register.get(key)
    return isinstance(entry, Mapping) and RECOVERY_POINT in entry


def is_dependable(register: Register, key: str) -> bool:
    """Whether the register holds `key` as an entry an activity may depend on: typed or asset."""
    entry = register.get(key)
    return isinstance(entry, Mapping) and (KIND in entry or RECOVERY_POINT in entry)


def is_metadata(register: Register, key: str) -> bool:
    """Whether the register holds `key` as something no activity may depend on."""
    return key in register and not is_dependable(register, key)


def assets(register: Register) -> list[str]:
    """The ids of the register's assets, in the order the register carries them."""
    return [key for key in register if is_asset(register, key)]


def recovery_point_for(register: Register, asset: str, activity: str | None) -> str | None:
    """The recovery point an entry declares for one activity (190, 16_nemo_check), decided per
    entry: an entry WITH a `consumers` field declares only what its consumer row for that activity
    (`department`) says, else nothing (its own figure is another record's); an entry with no
    `consumers` field at all (the old seed's shape) declares its own for every activity."""
    entry = register.get(asset)
    if not isinstance(entry, Mapping):
        return None
    if "consumers" not in entry:
        top: str | None = entry.get(RECOVERY_POINT)
        return top
    rows = entry["consumers"]
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, Mapping) and row.get("department") == activity and RECOVERY_POINT in row:
            point: str = row[RECOVERY_POINT]
            return point
    return None
