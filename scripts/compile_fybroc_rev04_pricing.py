"""Compile Fybroc Rev0.4 pricing into a publisher-ready compilation JSON.

Reads Fybroc Configuration Rev0.4.xlsx (read-only, via a disposable copy so the
authoritative workbook is never touched or locked), extracts pricing blocks per
the Rev0.4 pricing profile, and writes exports/fybroc_rev04_pricing.json in the
shape src/pricing_engine/publisher.py consumes ({issue_count, candidates:[...]}).

By default it compiles the PHASE A block set (BASE_PUMP + SEAL). Pass
--phase b (or --all) to also compile the full component set (Phase B), which
adds the remaining blocks + motor tables via the profile's phase_b config.

Usage:
    python scripts/compile_fybroc_rev04_pricing.py                 # phase A
    python scripts/compile_fybroc_rev04_pricing.py --phase b       # phase A + B
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

from src.compiler.fybroc_rev04_pricing_compiler import (
    detect_blocks,
    extract_block_candidates,
    find_block,
)

ROOT = Path(__file__).resolve().parents[1]


class _Cell:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class _Grid:
    """In-memory worksheet slice that supports ws.cell(row, column).value,
    ws.title, ws.max_row, ws.max_column. Populated by ONE sequential read in
    read-only mode (fast), so the block extractor's random cell access is O(1)
    dict lookups instead of slow openpyxl read-only random access."""

    def __init__(self, title: str, rows: list[tuple], max_col: int):
        self.title = title
        # store as dict[(r,c)] -> value ; rows is 1-based list of row tuples
        self._data: dict[tuple[int, int], object] = {}
        self.max_row = len(rows)
        self.max_column = max_col
        for ri, row in enumerate(rows, start=1):
            for ci, val in enumerate(row, start=1):
                if val is not None:
                    self._data[(ri, ci)] = val

    def cell(self, row: int, column: int) -> _Cell:
        return _Cell(self._data.get((row, column)))


def materialize(ws, max_rows: int, max_col: int) -> _Grid:
    """Read the first `max_rows` rows x `max_col` cols of a read-only worksheet
    in a single sequential pass."""
    rows: list[tuple] = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=max_rows,
                                         max_col=max_col, values_only=True)):
        rows.append(row)
    return _Grid(ws.title, rows, max_col)


def _load_profile() -> dict:
    return json.loads(
        (ROOT / "config" / "pricing_profiles" / "fybroc_rev04.json").read_text(encoding="utf-8")
    )


# Per-sheet read caps (rows, cols). Pricing blocks live in the first few thousand
# rows; the Motor tables (Phase B) are read separately with their own streaming.
SHEET_CAPS = {
    "1500 Pricing": (7000, 126),
    "5500 Pricing": (52500, 77),
    "All Series Pricing": (70, 12),
}


def compile_blocks(wb, profile: dict, block_specs: list[dict]) -> list[dict]:
    workbook_name = profile["workbook_name"]
    candidates: list[dict] = []
    seen_desc: set[tuple[str, str]] = set()
    grids: dict[str, _Grid] = {}
    for spec in block_specs:
        sheet = spec["sheet"]
        if sheet not in grids:
            rmax, cmax = SHEET_CAPS.get(sheet, (7000, 60))
            print(f"  [materialize] {sheet} ({rmax}x{cmax}) ...")
            grids[sheet] = materialize(wb[sheet], rmax, cmax)
        ws = grids[sheet]
        blocks = detect_blocks(ws, max_col=ws.max_column)
        block = find_block(blocks, spec["description_contains"])
        if block is None:
            raise SystemExit(
                f"Block {spec['description_contains']!r} not found on {sheet!r}"
            )
        # Guard against accidentally matching the same block twice.
        key = (sheet, block.description or "")
        if (key, spec["component_code"]) in seen_desc:
            continue
        seen_desc.add((key, spec["component_code"]))

        rows = extract_block_candidates(
            ws, block,
            component_code=spec["component_code"],
            condition_fields=spec["condition_fields"],
            workbook_name=workbook_name,
            row_filter=spec.get("row_filter"),
        )
        print(f"  {sheet} :: {block.description!r} -> {spec['component_code']}: "
              f"{len(rows)} candidates")
        candidates.extend(rows)
    return candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["a", "b"], default="a")
    ap.add_argument("--all", action="store_true", help="phase A + B")
    a = ap.parse_args()

    profile = _load_profile()
    src = ROOT / profile["source_workbook"]
    tdir = Path(tempfile.mkdtemp(prefix="rev04pub_"))
    tmp = tdir / src.name
    shutil.copy2(src, tmp)

    try:
        # read_only=True is fast for the SINGLE sequential pass materialize()
        # does; the block extractor then works against the in-memory _Grid.
        wb = openpyxl.load_workbook(str(tmp), read_only=True, data_only=True)
        specs = list(profile["phase_a_blocks"])
        if a.phase == "b" or a.all:
            specs += list(profile.get("phase_b_blocks", []))
        print(f"Compiling {len(specs)} block spec(s) from {src.name} ...")
        candidates = compile_blocks(wb, profile, specs)
        wb.close()
    finally:
        shutil.rmtree(tdir, ignore_errors=True)

    # De-duplicate exact duplicate candidates (same component + conditions).
    def _key(c):
        conds = tuple((cd["field_code"], cd["comparison_value"]) for cd in c["conditions"])
        return (c["component_code"], c.get("series_code"), conds)
    unique = {}
    dupes = 0
    for c in candidates:
        k = _key(c)
        if k in unique:
            dupes += 1
            continue
        unique[k] = c
    candidates = list(unique.values())

    out = {
        "artifact": "FYBROC_REV04_PRICING",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_workbook": profile["source_workbook"],
        "issue_count": 0,
        "candidate_count": len(candidates),
        "duplicates_removed": dupes,
        "candidates": candidates,
    }
    exports = ROOT / "exports"
    exports.mkdir(exist_ok=True)
    out_path = exports / "fybroc_rev04_pricing.json"
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    by_comp: dict[str, int] = {}
    for c in candidates:
        by_comp[c["component_code"]] = by_comp.get(c["component_code"], 0) + 1
    print(f"\nWrote {out_path}")
    print(f"  candidates: {len(candidates)}  duplicates_removed: {dupes}")
    print(f"  by component: {by_comp}")


if __name__ == "__main__":
    raise SystemExit(main())
