"""D110 - publish the authoritative Dean configuration model to SQL for the DEAN
family (PumpFamilyId=1), reusing the Fybroc constraint infrastructure.

SOURCES (authoritative):
  * Option applicability + values -> workbooks/Dean/PumpConfiguration_Logic.xlsm
    sheet 'Pump Options'. This is the Dean analogue of Fybroc's Selections sheet:
    one row per MODEL (A-Number + Series + Size), each option column marked
    STD (standard default) / X (available) / blank (not offered for that model).
    Applicability is PER-MODEL (series+size) and varies by size in 27/37 series,
    so cfg.SeriesFieldOption rows carry a SizeCode (see d110_add_sizecode.py).
    Pump Options is also the correct VALUE vocabulary: e.g. SEAL_TYPE uses the
    short 'Type N' names that the codependency tables reference (the Config
    Options long descriptive names did NOT match the constraints).
  * Codependencies + field-map -> exports/m023_dean_source_reconciliation.json
    ('dependencies' -> cfg.FeasibleConstraint + cfg.ConstraintFieldMap).

Rules / safety:
  * Family-scoped: writes ONLY PumpFamilyId=DEAN rows; NEVER touches FYBROC rows.
  * Idempotent: deletes existing DEAN rows in the three tables, then reloads.
  * SeriesFieldOption per model: SizeCode = model size; IsStandard=1 +
    SelectionMarker='STD' for STD cells; IsStandard=0 + SelectionMarker='X' for X
    cells; blank cells are NOT loaded (option not offered for that model).
  * BARRIER_PLAN (+ any constraint-leg field with no per-model markers) is loaded
    per-series (SizeCode NULL) from its Pump Options domain, since availability is
    governed by the codependency quad, not the per-model grid.
  * Barrier Plan casing normalized at load ('PLAN 52' -> 'Plan 52').
  * BLOCKED value tuples EXCLUDED + logged (pending engineering):
      - Throttle Bushing = 'Required'   (domain: Not Required / Carbon)
      - Bearing Frame Cooling = 'NONE'  (domain: Not Required / Steel Tube / ...)
  * 4-field quad (Table100) uses Option4Field/Value.

Run:  python scripts/d110_load_dean_config.py
"""
import json
import openpyxl
import pyodbc
from pathlib import Path

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
SRC = Path("exports/m023_dean_source_reconciliation.json")
WB_PATH = Path("workbooks/Dean/PumpConfiguration_Logic.xlsm")
WORKBOOK = "PumpConfiguration_Logic.xlsm"
WORKSHEET_OPTS = "Pump Options"
WORKSHEET_DEP = "Codependencies"

# Fields whose option domain has NO per-model STD/X markers in 'Pump Options'
# (their availability is governed by the codependency quad, not the per-model
# grid) -> loaded per-series with SizeCode NULL from their Pump Options domain.
UNGATED_DOMAIN_FIELDS = {"BARRIER_PLAN"}


# Value-domain normalization (loader-side, matches Fybroc case/space handling).
# Barrier Plan is stored 'Plan NNNN' in the option domain but 'PLAN NNNN' in
# some codependency rows -> title-case the leading token.
def _normalize_value(field_code, value):
    v = str(value).strip()
    if field_code in ("BARRIER_PLAN", "FLUSH_PLAN") and v.upper().startswith("PLAN "):
        return "Plan " + v[5:]
    return v


# Tuples to EXCLUDE (value not in the field's domain; pending engineering).
BLOCKED_VALUES = {
    ("THROTTLE_BUSHING", "required"),
    ("BEARING_FRAME_COOLING", "none"),
}


def read_pump_options(label_to_code):
    """Parse the 'Pump Options' sheet.

    Returns:
      models: list of dicts {series, size, cells: {code: {value: 'STD'|'X'}}}
      field_domains: {code: [ordered option values]}  (row3 order, all fields)
    label_to_code maps a Pump Options row2 field label -> canonical field code.
    """
    wb = openpyxl.load_workbook(WB_PATH, data_only=True, read_only=True)
    ws = wb["Pump Options"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    def cell(row, idx):
        return row[idx - 1] if 0 <= idx - 1 < len(row) else None

    row2, row3 = rows[1], rows[2]

    # Assign each option column (col>=4 with a row3 value) to the nearest row2
    # field-group header at or to its left; map that label to a canonical code.
    group_at = {}
    for c in range(1, len(row2) + 1):
        v = cell(row2, c)
        if v is not None and str(v).strip():
            group_at[c] = str(v).strip()
    group_cols = sorted(group_at)

    def group_for(col):
        g = None
        for gc in group_cols:
            if gc <= col:
                g = group_at[gc]
            else:
                break
        return g

    col_to_code = {}          # option column -> canonical code
    col_to_value = {}         # option column -> option value (row3)
    field_domains = {}        # code -> [values in column order]
    for c in range(4, len(row3) + 1):
        v = cell(row3, c)
        if v is None or str(v).strip() == "":
            continue
        label = group_for(c)
        if label is None:
            continue
        code = label_to_code.get(label.strip().lower())
        if not code:
            raise RuntimeError(f"Pump Options field label '{label}' has no code mapping")
        val = str(v).strip()
        col_to_code[c] = code
        col_to_value[c] = val
        field_domains.setdefault(code, []).append(val)

    # Model rows: row 4 onward while Series (col 2) present.
    models = []
    for r in rows[3:]:
        ser = cell(r, 2)
        size = cell(r, 3)
        if ser is None or str(ser).strip() == "":
            continue
        cells = {}
        for c, code in col_to_code.items():
            marker = cell(r, c)
            m = str(marker).strip().upper() if marker is not None else ""
            if m in ("STD", "X"):
                cells.setdefault(code, {})[col_to_value[c]] = m
        models.append({
            "series": str(ser).strip(),
            "size": str(size).strip() if size is not None else "",
            "cells": cells,
        })
    return models, field_domains


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    conn = pyodbc.connect(CS, autocommit=True)
    c = conn.cursor()

    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    assert dean == 1, f"expected DEAN family id 1, got {dean}"
    pub = c.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                    "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    print(f"DEAN family id={dean}  active publication id={pub}")

    # ---- field label -> canonical code (from the option domains + dependencies)
    label_to_code = {}
    for lod in d["logic_option_domains"]:
        label_to_code[str(lod["field_label"]).strip().lower()] = str(lod["canonical_field_code"]).strip()
    for dep in d["dependencies"]:
        for lab, code in zip(dep["field_labels"], dep["canonical_field_codes"]):
            label_to_code.setdefault(str(lab).strip().lower(), str(code).strip())

    # ---- pre-count Fybroc rows (must be unchanged after) ----
    fy_fc = c.execute("SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_cm = c.execute("SELECT COUNT(*) FROM cfg.ConstraintFieldMap WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_sfo = c.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    print(f"pre: non-DEAN rows  FC={fy_fc}  CM={fy_cm}  SFO={fy_sfo}")

    # ---- clear existing DEAN rows (idempotent) ----
    c.execute("DELETE FROM cfg.FeasibleConstraint WHERE PumpFamilyId=?", dean)
    c.execute("DELETE FROM cfg.ConstraintFieldMap WHERE PumpFamilyId=?", dean)
    c.execute("DELETE FROM cfg.SeriesFieldOption WHERE PumpFamilyId=?", dean)

    # ---- 1) ConstraintFieldMap (label -> code), family DEAN ----
    cm_map = {}
    for dep in d["dependencies"]:
        for lab, code in zip(dep["field_labels"], dep["canonical_field_codes"]):
            cm_map[lab.strip()] = code.strip()
    for lab, code in sorted(cm_map.items()):
        c.execute("INSERT INTO cfg.ConstraintFieldMap (ConstraintFieldName, SFOFieldCode, PumpFamilyId) "
                  "VALUES (?, ?, ?)", lab, code, dean)
    print(f"ConstraintFieldMap: inserted {len(cm_map)} DEAN label->code rows")

    # ---- 2) SeriesFieldOption from 'Pump Options', PER MODEL (series+size) ----
    models, field_domains = read_pump_options(label_to_code)
    series_set = sorted({m["series"] for m in models})

    def insert_sfo(code, value, series_code, size_code, is_std, marker, worksheet):
        c.execute(
            "INSERT INTO cfg.SeriesFieldOption "
            "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
            " SeriesCode, SizeCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, "
            " SourceValueCell, SourceSeriesCell, IsActive, CreatedAt, SelectionMarker, IsStandard) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, SYSUTCDATETIME(), ?, ?)",
            pub, dean, code, code, value, series_code, size_code, WORKBOOK, worksheet,
            0, "", "", "", marker, 1 if is_std else 0,
        )

    n_sfo = n_std = 0
    for m in models:
        for code, valmap in m["cells"].items():
            if code in UNGATED_DOMAIN_FIELDS:
                continue  # loaded per-series below, not per-model
            for value, marker in valmap.items():
                is_std = (marker == "STD")
                insert_sfo(code, _normalize_value(code, value),
                           m["series"], m["size"], is_std, marker, WORKSHEET_OPTS)
                n_sfo += 1
                n_std += 1 if is_std else 0
    print(f"SeriesFieldOption (per-model from Pump Options): {n_sfo} rows across "
          f"{len(models)} models / {len(series_set)} series; {n_std} STD defaults")

    # ---- 2b) Ungated domain fields (BARRIER_PLAN): load per-series, SizeCode NULL,
    #          from the Pump Options domain (availability governed by the quad). ----
    n_ungated = 0
    for code in sorted(UNGATED_DOMAIN_FIELDS):
        vals = field_domains.get(code, [])
        clean = [ _normalize_value(code, v) for v in vals
                  if str(v).strip()
                  and (code, str(v).strip().lower()) not in BLOCKED_VALUES ]
        # de-dup preserving order
        seen = set(); ordered = []
        for v in clean:
            k = v.strip().lower()
            if k not in seen:
                seen.add(k); ordered.append(v)
        for v in ordered:
            for sc in series_set:
                insert_sfo(code, v, sc, None, False, "X", WORKSHEET_OPTS)
                n_ungated += 1
        print(f"  ungated domain {code}: {len(ordered)} values x {len(series_set)} "
              f"series (SizeCode NULL) = {len(ordered) * len(series_set)} rows  {ordered}")
    if n_ungated:
        print(f"SeriesFieldOption (ungated domains): +{n_ungated} rows")

    # ---- 3) FeasibleConstraint: 47 allow-tuple tables, family DEAN ----
    domain_codes = set(field_domains) | UNGATED_DOMAIN_FIELDS
    n_fc = 0
    blocked = []
    synthesized_domains = {}  # constraint-leg code with no Pump Options domain
    for dep in d["dependencies"]:
        tname = dep["table_name"]
        labels = dep["field_labels"]
        codes = dep["canonical_field_codes"]
        for row in dep["rows"]:
            legs = []
            drop = False
            for lab, code in zip(labels, codes):
                raw = row.get(lab)
                if raw is None:
                    continue
                val = _normalize_value(code, raw)
                if (code, val.strip().lower()) in BLOCKED_VALUES:
                    drop = True
                legs.append((lab.strip(), val))
                if code not in domain_codes and code != "SERIES":
                    synthesized_domains.setdefault(code, set()).add(val)
            if drop:
                blocked.append((tname, {l: v for l, v in legs}))
                continue
            legs += [(None, None)] * (4 - len(legs))
            (o1f, o1v), (o2f, o2v), (o3f, o3v), (o4f, o4v) = legs[:4]
            c.execute(
                "INSERT INTO cfg.FeasibleConstraint "
                "(TableName, Option1Field, Option1Value, Option2Field, Option2Value, "
                " Option3Field, Option3Value, Option4Field, Option4Value, "
                " Allowed, SeriesApplicability, Description, PumpFamilyId) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Allowed', 'ALL_SERIES', ?, ?)",
                tname, o1f, o1v, o2f, o2v, o3f, o3v, o4f, o4v,
                f"Dean codependency {tname}", dean,
            )
            n_fc += 1
    print(f"FeasibleConstraint: inserted {n_fc} DEAN allow-tuple rows; "
          f"EXCLUDED {len(blocked)} blocked tuples (pending engineering)")
    for tname, legs in blocked:
        print(f"    BLOCKED [{tname}] {legs}")

    # ---- 3b) Any constraint-leg field STILL lacking a domain gets one synthesized
    #          from its distinct constraint values (per-series, SizeCode NULL). ----
    n_syn = 0
    for code, values in sorted(synthesized_domains.items()):
        clean = sorted({v.strip() for v in values
                        if v.strip()
                        and (code, v.strip().lower()) not in BLOCKED_VALUES})
        for val in clean:
            for sc in series_set:
                insert_sfo(code, val, sc, None, False, "X", WORKSHEET_DEP)
                n_syn += 1
        print(f"  synthesized domain {code}: {len(clean)} values x {len(series_set)} "
              f"series = {len(clean) * len(series_set)} rows  {clean}")
    if n_syn:
        print(f"SeriesFieldOption (synthesized from codependencies): +{n_syn} rows")

    # ---- verify Fybroc unchanged ----
    fy_fc2 = c.execute("SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_cm2 = c.execute("SELECT COUNT(*) FROM cfg.ConstraintFieldMap WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_sfo2 = c.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_null = c.execute(
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>? AND SizeCode IS NOT NULL",
        dean).fetchone()[0]
    print(f"post: non-DEAN rows  FC={fy_fc2}  CM={fy_cm2}  SFO={fy_sfo2}  "
          f"(non-DEAN rows with non-NULL SizeCode: {fy_null})")
    assert (fy_fc, fy_cm, fy_sfo) == (fy_fc2, fy_cm2, fy_sfo2), "FYBROC rows changed!"
    assert fy_null == 0, "FYBROC rows got a SizeCode!"
    print("FYBROC rows unchanged. DONE.")

    conn.close()


if __name__ == "__main__":
    main()
