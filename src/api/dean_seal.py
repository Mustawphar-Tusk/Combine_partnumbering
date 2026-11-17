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

# Seal Reference key -> per-sheet spec table suffix (cfg.DeanSealSpec_<suffix>, sql/39)
SHEET_TABLE = {
    '1.000" Shafts': "S1000", '1.375" Shafts': "S1375", '1.750" Shafts': "S1750",
    '2.125" Shafts': "S2125", '2.250" Shafts': "S2250", '3.000" Shafts': "S3000",
    "Misc.": "Misc",
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


# Permutation-sheet spelling -> Master spelling (normalized) for values that are the
# SAME option written differently. Applied to every value going into a permutation
# key, so sheet rows and Master-spelled selections meet on one key. Only exact
# equivalents belong here (verified by scripts/audit_dean_seal_options.py).
SHEET_TO_MASTER = {
    "SEAL_TYPE": {
        "type 8bith/8-1t": "jc type 8bith/8-1t",            # 'JC ' prefix missing on sheets
        "fas type vtsms 300 psi": "fas type vtsms (300 psi)",  # parentheses missing on Misc.
        # owner decisions 2026-08-27:
        "sib - pusher wedge seal": "balanced pusher wedge seal",
        "siu - pusher wedge seal": "siu - pusher wedge seal (thin cross section)",
        "fas type vtsms - double": "fas type vtsms",       # Double/Tandem is carried
        "fas type vtsms - tandem": "fas type vtsms",       # by Seal Configuration
        "jc type 5620pr - double": "jc type 5620pr",
        "jc type 5620pr - tandem": "jc type 5620pr",
        "jc type s8b1/8-1t": "jc type 8bith/8-1t",         # same seal (Master lists both)
    },
    "LANTERN_RING": {
        "none": "not required",
    },
}


def canon_value(field: str, v) -> str:
    s = _n(v)
    return SHEET_TO_MASTER.get(field, {}).get(s, s)


def combo_key(values: dict, sheet: str) -> str:
    parts = []
    for f in SEAL_KEY_FIELDS:
        if f == "GLAND_GASKET" and sheet not in GASKET_SHEETS:
            continue
        v = values.get(f, "")
        parts.append(normalize_chamber(v) if f == "SEAL_CHAMBER_CONFIG" else canon_value(f, v))
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
    # the sheet's own table (permutation-unique; duplicates were resolved at load)
    for (k,) in cursor.execute(f"SELECT ComboKey FROM cfg.DeanSealSpec_{SHEET_TABLE[ref]}"):
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


# Seal Configuration and Seal Type DRIVE the seal: their value (STD or chosen)
# always narrows the other seal fields. Every other seal field's STD value is a
# DEFAULT from Pump Constraints: the defaults are independent per-field markers
# and together often do not form one permutation (e.g. Outboard Rotating Face
# 'Carbon' is only valid for double seals), so a field that still holds its STD
# value never narrows any other field. Once the user changes it, it narrows.
DRIVER_FIELDS = ("SEAL_CONFIGURATION", "SEAL_TYPE")


def _is_soft(f, selections, std):
    return (f not in DRIVER_FIELDS and std is not None
            and _n(std.get(f, "")) != "" and _n(selections.get(f, "")) == _n(std.get(f, "")))


def _context(selections, fields, skip=None, std=None):
    ctx = {}
    for f in fields:
        if f == skip or _is_soft(f, selections, std):
            continue
        v = canon_value(f, selections.get(f, ""))
        if v and v != "c/f":
            ctx[f] = v
    return ctx


def _candidates(fields, rows, by_type, ctx):
    pool = by_type.get(ctx["SEAL_TYPE"], []) if "SEAL_TYPE" in ctx else rows
    items = [(fields.index(f), v) for f, v in ctx.items() if f != "SEAL_TYPE"]
    if not items:
        return pool
    return [r for r in pool if all(r[i] == v for i, v in items)]


def _upper_std(std):
    return {str(k).upper(): v for k, v in (std or {}).items()} if std is not None else None


def filter_options(cursor, series, selections, allowable, std=None) -> None:
    """Narrow `allowable` (field -> option list, mutated in place) for the seal
    fields: an option stays only if some permutation on the series' Seal Reference
    sheet carries it together with every OTHER selected seal field that is a driver
    (Seal Configuration / Seal Type) or has been changed from its STD default.
    Series with no sheet (ref 'X'/none) are not narrowed."""
    targets = [f for f in CASCADE_FIELDS if f in allowable]
    if not targets:
        return
    ref = seal_ref_key(cursor, series)
    if not ref or ref == "X":
        return
    fields, rows, by_type = _sheet_rows(cursor, ref)
    if not rows:
        return
    std = _upper_std(std)
    for t in targets:
        if t not in fields:
            allowable[t] = []      # e.g. Gland Gasket on a sheet without that column
            continue
        ti = fields.index(t)
        ctx = _context(selections, fields, skip=t, std=std)
        cand = {r[ti] for r in _candidates(fields, rows, by_type, ctx)}
        allowable[t] = [o for o in allowable[t] if canon_value(t, o) in cand]


def prune_seed(cursor, series, selections) -> dict:
    """Validate the STD seed against the series' sheet. Drivers (Seal
    Configuration, then Seal Type) must form a permutation together; every other
    seeded default is kept if it is valid with the kept drivers (checked one at a
    time - defaults do not have to agree with each other). Invalid seeds are
    dropped. Mutates `selections`; returns {field: ''} for each dropped field."""
    ref = seal_ref_key(cursor, series)
    if not ref or ref == "X":
        return {}
    fields, rows, by_type = _sheet_rows(cursor, ref)
    dropped, drivers = {}, {}
    for f in DRIVER_FIELDS:
        v = canon_value(f, selections.get(f, ""))
        if not v:
            continue
        if _candidates(fields, rows, by_type, {**drivers, f: v}):
            drivers[f] = v
        else:
            selections.pop(f, None)
            dropped[f] = ""
    for f in fields:
        if f in DRIVER_FIELDS:
            continue
        v = canon_value(f, selections.get(f, ""))
        if v and not _candidates(fields, rows, by_type, {**drivers, f: v}):
            selections.pop(f, None)
            dropped[f] = ""
    return dropped


def stale_defaults(cursor, series, selections, std) -> list:
    """Seal fields still at their STD default whose value no longer fits the
    current drivers / changed fields (e.g. after the user picks a Seal Type). They
    are cleared by the caller instead of being reported as user conflicts."""
    ref = seal_ref_key(cursor, series)
    if not ref or ref == "X":
        return []
    fields, rows, by_type = _sheet_rows(cursor, ref)
    std = _upper_std(std)
    out = []
    for f in fields:
        if not _is_soft(f, selections, std):
            continue
        ti = fields.index(f)
        ctx = _context(selections, fields, skip=f, std=std)
        if canon_value(f, selections.get(f)) not in {r[ti] for r in _candidates(fields, rows, by_type, ctx)}:
            out.append(f)
    return out

def resolve_seal_spec(cursor, series, selections) -> dict:
    """Resolve the seal slot.

    Returns {code, status, ref_key, price_amount, price_status, detail}
      status: 'none'      no seal configuration field selected -> code '000'
              'resolved'  a coded permutation matched          -> sheet code
              'pending'   seal configuration started but not resolvable -> 'TBD'
                          (no sheet for the series, incomplete/C-F selection, or
                          permutation not enumerated); engineering review.

    The PN seal slot is driven ONLY by the seal configuration fields (SEAL_KEY_FIELDS)
    and the series' Seal Reference sheet. SEAL_OPTION and SEAL_MANUFACTURER are not
    permutation fields and never affect the code. supplied (Seal Option ==
    Included) is reported for PRICING only.
    """
    out = {"code": NO_SEAL_CODE, "status": "none", "ref_key": None,
           "price_amount": None, "price_status": None, "detail": "",
           "supplied": _n(selections.get("SEAL_OPTION", "")) == "included"}
    if not any(_n(selections.get(f, "")) not in ("", "c/f") for f in CASCADE_FIELDS):
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
    if ref not in SHEET_TABLE:
        out["detail"] = "no spec table for Seal Reference " + ref
        return out
    h = combo_hash(combo_key(vals, ref))
    row = cursor.execute(
        f"SELECT SealCode, PriceAmount, PriceStatus FROM cfg.DeanSealSpec_{SHEET_TABLE[ref]} "
        f"WHERE ComboHash = ?", h).fetchone()
    if row is None:
        out["detail"] = "seal permutation not enumerated for " + ref
        return out
    out.update(code=row[0], status="resolved",
               price_amount=float(row[1]) if row[1] is not None else None,
               price_status=row[2], detail=ref)
    return out
