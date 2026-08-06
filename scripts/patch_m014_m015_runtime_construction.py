from __future__ import annotations

"""
Compatibility note.

M016.1 changes the AvailableOptionsService constructor only by adding an
optional value_equivalences argument. Existing M014/M015 diagnostic
scripts continue to run, but to exercise vocabulary reconciliation they
should construct the service through build_fybroc_runtime or load:

ValueEquivalenceProfile.from_mapping(
    json.loads(
        Path(
            "config/runtime_profiles/"
            "fybroc_value_equivalences.json"
        ).read_text(encoding="utf-8")
    )
)

The complete M016 session already uses build_fybroc_runtime and requires
no manual script edit.
"""
