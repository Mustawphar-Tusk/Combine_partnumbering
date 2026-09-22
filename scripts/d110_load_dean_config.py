"""D110 - publish the authoritative Dean configuration model to SQL for the DEAN
family (PumpFamilyId=1), reusing the Fybroc constraint infrastructure.

Source (authoritative, compiled M023.3):
    exports/m023_dean_source_reconciliation.json
      - logic_option_domains : 70 fields x option domains  -> cfg.SeriesFieldOption
      - dependencies         : 47 ALLOWED_TUPLES tables     -> cfg.FeasibleConstraint
                                                             -> cfg.ConstraintFieldMap
      - model_reconciliation : 206 models / 37 series       -> series list for options

Rules / safety:
  * Family-scoped: writes ONLY PumpFamilyId=DEAN rows; NEVER touches FYBROC rows.
  * Idempotent: deletes existing DEAN rows in the three tables, then reloads.
  * Barrier Plan casing normalized at load ('PLAN 52' -> 'Plan 52') to match the
    Config Options domain (case/space differences were the ~179 blocked tuples).
  * BLOCKED value tuples EXCLUDED + logged (pending engineering):
      - Throttle Bushing = 'Required'   (domain: Not Required / Carbon)
      - Bearing Frame Cooling = 'NONE'  (domain: Not Required / Steel Tube / ...)
  * 4-field quad (Table100) uses Option4Field/Value.

Run:  python scripts/d110_load_dean_config.py
"""
import json
import pyodbc
from pathlib import Path

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
SRC = Path("exports/m023_dean_source_reconciliation.json")
WORKBOOK = "PumpConfiguration_Logic.xlsm"
WORKSHEET_OPTS = "Config Options"
WORKSHEET_DEP = "Codependencies"

# Value-domain normalization (loader-side, matches Fybroc case/space handling).
# Barrier Plan is stored 'Plan NNNN' in the option domain but 'PLAN NNNN' in
# some codependency rows -> title-case the leading token.
def _normalize_value(field_code, value):
    v = str(value).strip()
    if field_code in ("BARRIER_PLAN", "FLUSH_PLAN") and v.upper().startswith("PLAN "):
        # 'PLAN 52' -> 'Plan 52' (keep the numeric/suffix part as-is)
        return "Plan " + v[5:]
    return v


# Tuples to EXCLUDE (value not in the field's domain; pending engineering).
# Keyed by (field_code, normalized_value_lower) -> if a tuple contains this
# (field, value) it is dropped and logged.
BLOCKED_VALUES = {
    ("THROTTLE_BUSHING", "required"),
    ("BEARING_FRAME_COOLING", "none"),
}


def main():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    conn = pyodbc.connect(CS, autocommit=True)
    c = conn.cursor()

    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    assert dean == 1, f"expected DEAN family id 1, got {dean}"
    pub = c.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                    "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    print(f"DEAN family id={dean}  active publication id={pub}")

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
    label_to_code = {}
    for dep in d["dependencies"]:
        for lab, code in zip(dep["field_labels"], dep["canonical_field_codes"]):
            label_to_code[lab.strip()] = code.strip()
    for lab, code in sorted(label_to_code.items()):
        c.execute("INSERT INTO cfg.ConstraintFieldMap (ConstraintFieldName, SFOFieldCode, PumpFamilyId) "
                  "VALUES (?, ?, ?)", lab, code, dean)
    print(f"ConstraintFieldMap: inserted {len(label_to_code)} DEAN label->code rows")

    # ---- 2) SeriesFieldOption: 70 domains x 37 model-series ----
    series = sorted({m["model_key"].split("|")[0] for m in d["model_reconciliation"]})
    n_sfo = 0
    for lod in d["logic_option_domains"]:
        code = lod["canonical_field_code"]
        label = lod["field_label"]
        for row in lod["rows"]:
            val = str(list(row.values())[0]).strip()
            if not val:
                continue
            for sc in series:
                c.execute(
                    "INSERT INTO cfg.SeriesFieldOption "
                    "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
                    " SeriesCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, "
                    " SourceValueCell, SourceSeriesCell, IsActive, CreatedAt, SelectionMarker, IsStandard) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, SYSUTCDATETIME(), '', 0)",
                    pub, dean, code, code, val, sc, WORKBOOK, WORKSHEET_OPTS,
                    0, "", "", "",
                )
                n_sfo += 1
    print(f"SeriesFieldOption: inserted {n_sfo} DEAN option rows "
          f"({len(d['logic_option_domains'])} fields x {len(series)} series)")

    # Field codes that HAVE a non-empty option domain from the Config Options
    # sheet. Any CONSTRAINT LEG whose code is NOT here (and is not the SERIES
    # selector) has no selectable domain, so its codependency leg would be dead.
    # BARRIER_PLAN is such a field: the Config Options sheet only has an (empty)
    # "Barrier Plan Extras" table, while the authoritative Barrier Plan value set
    # lives inside the codependency quad (Table100). We synthesize its domain
    # from the distinct constraint values below (post loop 3).
    domain_codes = {lod["canonical_field_code"] for lod in d["logic_option_domains"]
                    if lod["rows"]}

    # ---- 3) FeasibleConstraint: 47 allow-tuple tables, family DEAN ----
    n_fc = 0
    blocked = []
    synthesized_domains = {}  # field_code -> set of normalized values (no domain)
    for dep in d["dependencies"]:
        tname = dep["table_name"]
        labels = dep["field_labels"]
        codes = dep["canonical_field_codes"]
        for row in dep["rows"]:
            # ordered (code, normalized value) legs
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
                # Track values for any constraint leg with no option domain
                # (except SERIES, which is the model-series selector, not a field).
                if code not in domain_codes and code != "SERIES":
                    synthesized_domains.setdefault(code, set()).add(val)
            if drop:
                blocked.append((tname, {l: v for l, v in legs}))
                continue
            # pad to 4 legs
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

    # ---- 2b) Synthesize SeriesFieldOption domains for constraint-leg fields
    #          that have NO option domain in the Config Options sheet (their
    #          authoritative value set lives only in the codependency table).
    #          Currently: BARRIER_PLAN (from the Table100 quad). Without this the
    #          field projects zero options and its codependency leg is dead. ----
    n_syn = 0
    for code, values in sorted(synthesized_domains.items()):
        clean = sorted({v.strip() for v in values
                        if v.strip()
                        and (code, v.strip().lower()) not in BLOCKED_VALUES})
        for val in clean:
            for sc in series:
                c.execute(
                    "INSERT INTO cfg.SeriesFieldOption "
                    "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
                    " SeriesCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, "
                    " SourceValueCell, SourceSeriesCell, IsActive, CreatedAt, SelectionMarker, IsStandard) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, SYSUTCDATETIME(), '', 0)",
                    pub, dean, code, code, val, sc, WORKBOOK, WORKSHEET_DEP,
                    0, "", "", "",
                )
                n_syn += 1
        print(f"  synthesized domain {code}: {len(clean)} values x {len(series)} "
              f"series = {len(clean) * len(series)} rows  {clean}")
    if n_syn:
        print(f"SeriesFieldOption (synthesized from codependencies): +{n_syn} rows")

    # ---- verify Fybroc unchanged ----
    fy_fc2 = c.execute("SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_cm2 = c.execute("SELECT COUNT(*) FROM cfg.ConstraintFieldMap WHERE PumpFamilyId<>?", dean).fetchone()[0]
    fy_sfo2 = c.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    print(f"post: non-DEAN rows  FC={fy_fc2}  CM={fy_cm2}  SFO={fy_sfo2}")
    assert (fy_fc, fy_cm, fy_sfo) == (fy_fc2, fy_cm2, fy_sfo2), "FYBROC rows changed!"
    print("FYBROC rows unchanged. DONE.")

    conn.close()


if __name__ == "__main__":
    main()
