"""Dean seal configuration spec resolver (SealNumbering.xlsx).

A seal configuration is the set of seal selections. The Seal Reference Table
(cfg.DeanSealReference: series -> sheet key) names the SealNumbering permutation
sheet that applies to the series; that sheet maps each permutation to a seal code
and price (cfg.DeanSealSpec, loaded by scripts/load_dean_seal_spec.py).

The seal code occupies its own slot in the Dean PN, between the power-frame and
flush groups. This module is import-light (no FastAPI) so loaders/audits share the
exact key construction used at runtime.
"""
from __future__ import annotations

import hashlib
import re

# Fixed order of the seal selections that form the permutation key.
SEAL_KEY_FIELDS = (
    "SEAL_CONFIGURATION", "SEAL_TYPE",
    "INBOARD_ROTATING_FACE_MATERIAL", "INBOARD_STATIONARY_FACE_MATERIAL",
    "INBOARD_ELASTOMER",
    "OUTBOARD_ROTATING_FACE_MATERIAL", "OUTBOARD_STATIONARY_FACE_MATERIAL",
    "OUTBOARD_ELASTOMERS",
    "HYDROPADS", "PUMPING_RING", "THROTTLE_BUSHING", "MIN_FLO_BUSHING",
    "LANTERN_RING", "INBOARD_HARDWARE_MATERIAL", "OUTBOARD_HARDWARE_MATERIAL",
    "SEAL_CHAMBER_CONFIG", "GLAND_TYPE", "GLAND_GASKET", "SHAFT_SLEEVE_MATERIAL",
)
# Only the Misc. sheet carries a Gland Gasket column.
GASKET_SHEETS = {"Misc."}

# SealNumbering permutation-sheet header -> canonical field code.
SHEET_HEADER_TO_FIELD = {
    "seal configuration": "SEAL_CONFIGURATION",
    "seal type": "SEAL_TYPE",
    "inboard rotating face": "INBOARD_ROTATING_FACE_MATERIAL",
    "inboard stationary face": "INBOARD_STATIONARY_FACE_MATERIAL",
    "inboard elastomers": "INBOARD_ELASTOMER",
    "outboard rotating face": "OUTBOARD_ROTATING_FACE_MATERIAL",
    "outboard stationary face": "OUTBOARD_STATIONARY_FACE_MATERIAL",
    "outboard elastomers": "OUTBOARD_ELASTOMERS",
    "hydropads": "HYDROPADS",
    "pumping ring": "PUMPING_RING",
    "throttle bushing": "THROTTLE_BUSHING",
    "min flo bushing": "MIN_FLO_BUSHING",
    "lantern ring": "LANTERN_RING",
    "inboard seal hardware": "INBOARD_HARDWARE_MATERIAL",
    "outboard seal hardware": "OUTBOARD_HARDWARE_MATERIAL",
    "seal chamber config": "SEAL_CHAMBER_CONFIG",
    "gland style": "GLAND_TYPE",
    "gland gasket": "GLAND_GASKET",
    "sleeve material": "SHAFT_SLEEVE_MATERIAL",
}

NO_SEAL_CODE = "000"        # seal not supplied by Dean (Seal Option != Included)
PENDING_SEAL_CODE = "TBD"   # Included, but no coded permutation (engineering)


def _n(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "").strip()).lower()


def normalize_chamber(v: str) -> str:
    """The numbered Seal Chamber Config values (e.g. 'Standard Bore Jacketed',
    'Large Taper Bore') are wider than the SealNumbering sheet vocabulary
    (Standard Bore / Large Bore). Map to the sheet's bore class for matching."""
    s = _n(v)
    if s.startswith("standard bore"):
        return "standard bore"
    if s.startswith("large") and "bore" in s:
        return "large bore"
    return s


def combo_key(values: dict, sheet: str) -> str:
    parts = []
    for f in SEAL_KEY_FIELDS:
        if f == "GLAND_GASKET" and sheet not in GASKET_SHEETS:
            continue
        v = values.get(f, "")
        parts.append(normalize_chamber(v) if f == "SEAL_CHAMBER_CONFIG" else _n(v))
    return "*".join(parts)


def combo_hash(key: str) -> bytes:
    return hashlib.sha256(key.encode("utf-8")).digest()


def seal_ref_key(cursor, series) -> str | None:
    row = cursor.execute(
        "SELECT SealRefKey FROM cfg.DeanSealReference WHERE SeriesCode = ?",
        str(series or "").strip()).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Option cascade: the Seal Reference sheet (and then the chosen Seal Type and
# every other selected seal field) decides which seal options are applicable.
# ---------------------------------------------------------------------------
import time as _time

# Seal fields filtered by the cascade. Seal Chamber Config is wet-end owned and is
# neither filtered nor used as context.
CASCADE_FIELDS = tuple(f for f in SEAL_KEY_FIELDS if f != "SEAL_CHAMBER_CONFIG")
_ROW_CACHE: dict = {}
_CACHE_TTL = 600.0


def clear_cache() -> None:
    _ROW_CACHE.clear()


def _fields_for(ref: str) -> tuple:
    return tuple(f for f in CASCADE_FIELDS
                 if not (f == "GLAND_GASKET" and ref not in GASKET_SHEETS))


def _sheet_rows(cursor, ref: str):
    """-> (fields, rows, by_type) for a sheet; rows are tuples of normalized values
    in `fields` order (chamber omitted). Cached per process (TTL; loader reloads
    are picked up after the TTL or clear_cache())."""
    hit = _ROW_CACHE.get(ref)
    if hit and _time.monotonic() - hit[0] < _CACHE_TTL:
        return hit[1]
    all_fields = tuple(f for f in SEAL_KEY_FIELDS
                       if not (f == "GLAND_GASKET" and ref not in GASKET_SHEETS))
    keep = [i for i, f in enumerate(all_fields) if f != "SEAL_CHAMBER_CONFIG"]
    fields = tuple(all_fields[i] for i in keep)
    seen = set()
    for (k,) in cursor.execute("SELECT ComboKey FROM cfg.DeanSealSpec WHERE SealRefKey = ?", ref):
        p = k.split("*")
        seen.add(tuple(p[i] for i in keep))
    rows = list(seen)
    ti = fields.index("SEAL_TYPE")
    by_type: dict = {}
    for r in rows:
        by_type.setdefault(r[ti], []).append(r)
    data = (fields, rows, by_type)
    _ROW_CACHE[ref] = (_time.monotonic(), data)
    return data


def _context(selections, fields, skip=None):
    ctx = {}
    for f in fields:
        if f == skip:
            continue
        v = _n(selections.get(f, ""))
        if v and v != "c/f":
            ctx[f] = v
    return ctx


def _candidates(fields, rows, by_type, ctx):
    pool = by_type.get(ctx["SEAL_TYPE"], []) if "SEAL_TYPE" in ctx else rows
    items = [(fields.index(f), v) for f, v in ctx.items() if f != "SEAL_TYPE"]
    if not items:
        return pool
    return [r for r in pool if all(r[i] == v for i, v in items)]


def filter_options(cursor, series, selections, allowable) -> None:
    """Narrow `allowable` (field -> option list, mutated in place) for the seal
    fields: an option stays only if some permutation on the series' Seal Reference
    sheet carries it together with every OTHER selected seal field (Seal Type
    included). Series with no sheet (ref 'X'/none) are not narrowed."""
    targets = [f for f in CASCADE_FIELDS if f in allowable]
    if not targets:
        return
    ref = seal_ref_key(cursor, series)
    if not ref or ref == "X":
        return
    fields, rows, by_type = _sheet_rows(cursor, ref)
    if not rows:
        return
    for t in targets:
        if t not in fields:
            allowable[t] = []      # e.g. Gland Gasket on a sheet without that column
            continue
        ti = fields.index(t)
        ctx = _context(selections, fields, skip=t)
        cand = {r[ti] for r in _candidates(fields, rows, by_type, ctx)}
        allowable[t] = [o for o in allowable[t] if _n(o) in cand]


def prune_seed(cursor, series, selections) -> dict:
    """STD-seeded seal fields that do not form one permutation on the series'
    sheet are dropped (the later one of any conflicting pair). Mutates
    `selections`; returns {field: ''} for each dropped field."""
    ref = seal_ref_key(cursor, series)
    if not ref or ref == "X":
        return {}
    fields, rows, by_type = _sheet_rows(cursor, ref)
    dropped, keep = {}, {}
    for f in ("SEAL_CONFIGURATION", "SEAL_TYPE") + tuple(
            x for x in fields if x not in ("SEAL_CONFIGURATION", "SEAL_TYPE")):
        v = _n(selections.get(f, ""))
        if not v or f not in fields:
            continue
        trial = {**keep, f: v}
        if _candidates(fields, rows, by_type, trial):
            keep[f] = v
        else:
            selections.pop(f, None)
            dropped[f] = ""
    return dropped


def resolve_seal_spec(cursor, series, selections) -> dict:
    """Resolve the seal slot.

    Returns {code, status, ref_key, price_amount, price_status, detail}
      status: 'none'      Seal Option is not Included          -> code '000'
              'resolved'  a coded permutation matched          -> sheet code
              'pending'   Included but not resolvable          -> 'TBD'
                          (no sheet for the series, incomplete/C-F selection, or
                          permutation not enumerated); engineering review.
    """
    opt = _n(selections.get("SEAL_OPTION", ""))
    out = {"code": NO_SEAL_CODE, "status": "none", "ref_key": None,
           "price_amount": None, "price_status": None, "detail": ""}
    if opt != "included":
        return out
    out["code"], out["status"] = PENDING_SEAL_CODE, "pending"
    ref = seal_ref_key(cursor, series)
    out["ref_key"] = ref
    if not ref or ref == "X":
        out["detail"] = "series has no seal numbering sheet"
        return out
    vals = {f: selections.get(f, "") for f in SEAL_KEY_FIELDS}
    needed = [f for f in SEAL_KEY_FIELDS
              if not (f == "GLAND_GASKET" and ref not in GASKET_SHEETS)]
    missing = [f for f in needed if _n(vals.get(f)) in ("", "c/f")]
    if missing:
        out["detail"] = "incomplete seal selection: " + ", ".join(missing[:4])
        return out
    key = combo_key(vals, ref)
    row = cursor.execute(
        "SELECT TOP 1 SealCode, PriceAmount, PriceStatus FROM cfg.DeanSealSpec "
        "WHERE SealRefKey = ? AND ComboHash = ? ORDER BY SealCode",
        ref, combo_hash(key)).fetchone()
    if row is None:
        out["detail"] = "seal permutation not enumerated for " + ref
        return out
    out.update(code=row[0], status="resolved",
               price_amount=float(row[1]) if row[1] is not None else None,
               price_status=row[2], detail=ref)
    return out
