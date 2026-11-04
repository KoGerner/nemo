# The dependency graph is read-only in v2.0

**Not superseded** (2026-10-01): an earlier note here said ADR-0040 superseded this; ADR-0040 was corrected the same day. The grouped graph stays (his "this graph is totally fine, and dont delete it", 13:10:10Z in 63c012d0); only nemo's own unseen page goes (ticket 243).

The graph stays what it is today: a page rebuilt wholesale from the saved record on every record
write, carrying that record's fingerprint. Clicking a node to open and edit that dependency is
deferred to v2.1.

Making the graph editable makes it an *input*, and an input has to be validated, refereed and written
back. The rule that the graph is rebuilt from the saved record — the one part of the old system that
never failed — stops being true the moment the picture can be edited independently of the record it
came from.
