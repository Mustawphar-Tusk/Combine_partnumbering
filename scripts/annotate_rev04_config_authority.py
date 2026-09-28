"""Record Fybroc Rev0.4 as the authoritative CONFIG source (non-disruptive).

WHY THIS INSTEAD OF A NEW PUBLICATION:
  cfg.MetadataPublication is SHARED across families and is NOT family-scoped -
  the single Active publication (F140-corrections-v1) carries BOTH the Fybroc
  config AND the Dean config (D110/D140). The Fybroc Rev0.4 constraint/config
  CONTENT is byte-identical to Rev0.3 (verified in docs/evidence/REV04_CONSTRAINTS/
  REV04_vs_REV03_CONSTRAINT_DIFF.md), so minting/activating a NEW config
  publication would require re-publishing BOTH families' entire config for zero
  content change and would risk regressing the frozen Fybroc + in-flight Dean
  work. (This differs from PRICING, where price.PriceBookVersion is a separate,
  family-scoped versioning table that cleanly minted FYBROC-REV04-MERGE-...-V1.)

  Therefore the Rev0.4 supersession is recorded as a PROVENANCE/AUTHORITY change:
  the active publication's Description is annotated to state the Fybroc config
  authority is now Fybroc Configuration Rev0.4.xlsx (supersedes Rev0.3). No row
  counts, no enforced data, and no active-publication identity change. Idempotent.

Run: python scripts/annotate_rev04_config_authority.py
"""
import pyodbc

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)
NOTE = (" | FYBROC config authority: Fybroc Configuration Rev0.4.xlsx "
        "(supersedes Rev0.3; constraint/config content byte-identical, "
        "verified docs/evidence/REV04_CONSTRAINTS/).")


def main():
    cn = pyodbc.connect(CONN, autocommit=True)
    c = cn.cursor()
    row = c.execute(
        "SELECT MetadataPublicationId, Description FROM cfg.MetadataPublication "
        "WHERE Status='Active'").fetchone()
    if row is None:
        raise SystemExit("No active metadata publication.")
    pub_id, desc = int(row[0]), (row[1] or "")
    if "Rev0.4" in desc:
        print(f"pub {pub_id} already annotated for Rev0.4; no change.")
    else:
        c.execute(
            "UPDATE cfg.MetadataPublication SET Description=? WHERE MetadataPublicationId=?",
            (desc + NOTE)[:1000], pub_id)
        print(f"pub {pub_id} Description annotated with Rev0.4 config authority.")

    r = c.execute(
        "SELECT MetadataPublicationId, VersionCode, Status, Description "
        "FROM cfg.MetadataPublication WHERE MetadataPublicationId=?", pub_id).fetchone()
    print(f"  pub {r[0]} [{r[2]}] {r[1]}: {r[3]}")
    n_active = c.execute(
        "SELECT COUNT(*) FROM cfg.MetadataPublication WHERE Status='Active'").fetchone()[0]
    print(f"  Active publications: {n_active} (must be 1)")
    assert n_active == 1, "expected exactly one Active publication"
    cn.close()


if __name__ == "__main__":
    main()
