"""Every reason nemo would refuse a seed, asked of a directory before anybody mints a room from it.

`walk.seed_problems` is the admission check and runs at the mint; it answers the two questions a
room can be opened or refused on. It is deliberately not everything nemo knows about a seed, and
on 2026-09-17 the demo seed proved the gap in three places: the admission check refused it, a v1
`output/bia-record.json` with no `revision` turned stage 4 into a `KeyError`, and v1 documents
sitting where a walk writes its own turned the first save into a `Shrunk` refusal.

This module is the operator's version of that question. It **asks** nemo's rules and changes none
of them: the admission half is `walk.seed_problems` itself rather than a second list of rules kept
beside it, the revision half is the field `walk._revision` reads, and the document half is the
paths `nemo.views` and `nemo.handover` name. A seed that passes here is one nemo will mint from,
walk, and save out of; a seed that does not is refused with every reason at once, because the
operator putting it right reads the whole list rather than peeling refusals off one at a time.

ADR-0011 is what makes the document half a defect rather than a preference: a minted room ships a
BIA in progress over source files **it did not write**, and holds no document a human is meant to
read as output. The first document is a projection of the record, rendered at stage 4.
"""

import json
import os
from pathlib import Path

from nemo import walk
from nemo.handover import CERTIFICATE
from nemo.views import ANALYSIS, CAPTURE, SCOPE, WORKSHEET

#: Where the seed the demo mints from lives on this box: the playground's seed since ticket 139's
#: contract (ADR-0032). `deploy/seed-manifest.json` pins what it holds; the skin reads the same
#: variable (ADR-0017).
SEED = os.environ.get("NEMO_SEED", "/home/user/work/nemo-playground/seed")

#: The documents a walk writes into `output/<activity>/`. A file already sitting under one of these
#: names is what `room_store.write_document`'s guard has to compare against.
DOCUMENTS = frozenset({SCOPE, CAPTURE, ANALYSIS, WORKSHEET, CERTIFICATE})

WITHOUT_REVISION = ("{path} is a record with no 'revision', so the walk that reads it raises "
                    "KeyError at stage 4")
NOT_NEMOS_TO_OVERWRITE = ("{path} is a document nemo writes itself, so the walk's own save is "
                          "refused and a minted room ships output nobody walked (ADR-0011)")


def problems(seed_folder: Path) -> list[str]:
    """Every reason nemo would refuse this seed, in the order the three of them were found.

    Read-only and deterministic: it opens the seed's own files and writes nothing, so asking is
    free and asking twice says the same thing.
    """
    return (walk.seed_problems(seed_folder)
            + _records_without_a_revision(seed_folder)
            + _documents_nemo_writes_itself(seed_folder))


def _records_without_a_revision(seed_folder: Path) -> list[str]:
    """The records a walk would read whose `revision` is not there to read.

    Both of the room's record homes, because `walk._revision` is the one reader of both: each
    process's BIA record (`walk.record_file`) and every run under `output/.bia-runs/`.
    """
    return [WITHOUT_REVISION.format(path=path) for path in _record_paths(seed_folder)
            if "revision" not in _loaded(seed_folder / path)]


def _record_paths(seed_folder: Path) -> list[str]:
    """Where a record sits in a room, as room-relative paths, the BIA records first."""
    records = sorted(record.relative_to(seed_folder).as_posix()
                     for record in seed_folder.glob(f"output/*/{walk.RECORD_NAME}"))
    runs = sorted(run.name for run in (seed_folder / walk.RUNS).glob("*.json"))
    return records + [f"{walk.RUNS}/{name}" for name in runs]


def _loaded(path: Path) -> dict[str, object]:
    """One record off disk. A file holding anything but an object holds no `revision` either, and
    is reported as the same problem rather than crashing the check that is there to report it."""
    loaded = json.loads(path.read_bytes())
    return loaded if isinstance(loaded, dict) else {}


def _documents_nemo_writes_itself(seed_folder: Path) -> list[str]:
    """The files sitting under a name a walk writes, which it would then refuse to overwrite."""
    return [NOT_NEMOS_TO_OVERWRITE.format(path=f"output/{found.parent.name}/{found.name}")
            for found in sorted((seed_folder / "output").glob("*/*"))
            if found.name in DOCUMENTS]
