"""Seed cfg.ConstraintFieldMap: bridge between Feasible Constraint field labels
and SFO FieldCodes.

The mapping is derived from the actual data on both sides (constraint
Option*Field labels vs cfg.SeriesFieldOption FieldCodes). 27 of 29 labels match
by normalized token; the 2 spelling variants ('C-Face Adapter'/'CycloneSep')
are mapped explicitly. This script validates that EVERY distinct constraint
field label present in cfg.FeasibleConstraint is covered before committing, so
enforcement can never silently skip a field.
"""
from pathlib import Path
import pyodbc

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "sql" / "21_Create_Constraint_Field_Map.sql"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;")

# constraint field label -> SFO FieldCode (verified against live data, task 1)
MAP = {
    "Alt Size": "ALT_SIZE",
    "CouplingGuard": "COUPLING_GUARD",
    "Flange Type": "FLANGE_TYPE",
    "Flush": "FLUSH",
    "Flush Material": "FLUSH_MATERIAL",
    "ImpellerTrim": "IMPELLER_TRIM",
    "Length": "LENGTH",
    "Motor Control": "MOTOR_CONTROL",
    "MotorOption": "MOTOR_OPTION",
    "Paint Upgrade": "PAINT_UPGRADE",
    "Pump Material": "PUMP_MATERIAL",
    "Casing Drains": "CASING_DRAINS",
    "Seal Guard": "SEAL_GUARD",
    "Seal Mfg": "SEAL_MFG",
    "Seal Option": "SEAL_OPTION",
    "Seal Type": "SEAL_TYPE",
    "Setting": "SETTING",
    "Setting/Length": "SETTING/LENGTH",
    "Shaft Grounding": "SHAFT_GROUNDING",
    "Shaft Material": "SHAFT_MATERIAL",
    "Sleeve": "SLEEVE",
    "Suction Discharge Taps": "SUCTION_DISCHARGE_TAPS",
    "Tailpipe Length": "TAILPIPE_LENGTH",
    "Tailpipe Option": "TAILPIPE_OPTION",
    "Wetted Hardware": "WETTED_HARDWARE",
    "Wetted Hardware Selection": "WETTED_HARDWARE_SELECTION",
    # explicit spelling variants (do not auto-normalize-match)
    "C-Face Adapter": "C_FACE_ADAPTOR",
    "CycloneSep": "CYCLONE_SEPERATOR",
}


def main():
    cn = pyodbc.connect(CONN, autocommit=True)
    cur = cn.cursor()

    for batch in DDL.read_text(encoding="utf-8").split("\nGO"):
        if batch.strip():
            cur.execute(batch)

    # Validate: every distinct constraint field label in the data is mapped.
    labels = set()
    for col in ("Option1Field", "Option2Field", "Option3Field"):
        for r in cur.execute(
            f"SELECT DISTINCT {col} FROM cfg.FeasibleConstraint "
            f"WHERE {col} IS NOT NULL AND {col} <> ''"):
            labels.add(r[0].strip())
    missing = sorted(labels - set(MAP))
    if missing:
        raise SystemExit(
            f"ABORT: constraint field labels present in data but NOT mapped: {missing}"
        )

    # Validate: every target SFO code actually exists in SeriesFieldOption.
    sfo_codes = {r[0] for r in cur.execute(
        "SELECT DISTINCT FieldCode FROM cfg.SeriesFieldOption")}
    bad_targets = sorted(v for v in MAP.values() if v not in sfo_codes)
    if bad_targets:
        raise SystemExit(
            f"ABORT: mapped SFO FieldCodes not present in SeriesFieldOption: {bad_targets}"
        )

    cur.execute("DELETE FROM cfg.ConstraintFieldMap")
    cur.executemany(
        "INSERT INTO cfg.ConstraintFieldMap (SFOFieldCode, ConstraintFieldName) VALUES (?, ?)",
        [(sfo, label) for label, sfo in MAP.items()],
    )

    total = cur.execute("SELECT COUNT(*) FROM cfg.ConstraintFieldMap").fetchone()[0]
    print(f"cfg.ConstraintFieldMap rows: {total}")
    print(f"constraint field labels in data: {len(labels)} (all mapped)")
    for r in cur.execute(
        "SELECT ConstraintFieldName, SFOFieldCode FROM cfg.ConstraintFieldMap "
        "ORDER BY ConstraintFieldName"):
        print(f"  {r[0]:28s} -> {r[1]}")
    cn.close()


if __name__ == "__main__":
    main()
