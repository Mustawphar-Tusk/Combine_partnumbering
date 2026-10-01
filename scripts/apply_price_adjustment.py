"""Apply a targeted PERCENT price adjustment to the CURRENT published pricing.

Thin CLI over price.usp_ApplyPriceAdjustment. By default it PREVIEWS (dry-run) and
writes nothing; pass --apply to actually change prices. Every real apply is audited
in price.PriceAdjustment + price.PriceAdjustmentRow (per-rule old/new amount), so a
change is traceable and reversible.

Scope / targeting (a pump SERIES is the "parent"; its priced COMPONENTS are the
"children"):
  --scope ALL_FAMILIES                     every family's current price book
  --scope FAMILY   --family FYBROC         one family (all its series + components)
  --scope SERIES   --family FYBROC --series 1500   one family + one series
  [--component SHAFT_MATERIAL]             optional child narrowing (NULL = all components)

Only the CURRENT (IsCurrent) price book version of each in-scope family is touched.
FAMILY / SERIES scopes NEVER cross families; ALL_FAMILIES is the only cross-family scope.

Examples:
  # preview a 5% rise on all Fybroc shaft-material prices
  python scripts/apply_price_adjustment.py --scope FAMILY --family FYBROC --component SHAFT_MATERIAL --percent 5

  # actually apply a 3% rise to every component on Fybroc 1500
  python scripts/apply_price_adjustment.py --scope SERIES --family FYBROC --series 1500 --percent 3 --apply --reason "2026 list adj" --by jdoe

  # preview a 2.5% rise across ALL pumps
  python scripts/apply_price_adjustment.py --scope ALL_FAMILIES --percent 2.5

Component codes (children) include: BASE_PUMP, SEAL, SHAFT_MATERIAL, PUMP_MATERIAL_ADDER,
FLANGE_TYPE, CASING_DRAINS, SUCTION_DISCHARGE_TAPS, GLAND_HARDWARE, CASING_HARDWARE,
POWER_FRAME_HARDWARE, BEARING_OPTION, COUPLING_GUARD, BASEPLATE, BASEPLATE_HARDWARE,
SLEEVE, CYCLONE_SEPARATOR, FLUSH, SEAL_GUARD, PERFORMANCE_TESTING, VIBRATION_TESTING,
SOUND_LEVEL_TESTING, C_FACE_ADAPTOR, COUPLING, MOTOR, TAILPIPE, ... (see price.PriceRule).

Price rows live in price.PriceRule (Amount column); this proc is the supported way to
update them in bulk.
"""
from __future__ import annotations

import argparse
import sys

import pyodbc

CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")


def _print_resultsets(cur) -> None:
    first = True
    while True:
        if cur.description is not None:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            if first:
                print("\n--- SUMMARY ---")
            else:
                print("\n--- PER-COMPONENT BREAKDOWN ---")
            if rows:
                print(" | ".join(cols))
                for r in rows:
                    print(" | ".join("" if v is None else str(v) for v in r))
            first = False
        if not cur.nextset():
            break


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply a targeted percent price adjustment.")
    ap.add_argument("--scope", required=True,
                    choices=["ALL_FAMILIES", "FAMILY", "SERIES"])
    ap.add_argument("--percent", required=True, type=float,
                    help="Percent change: 5 => +5%%, -2.5 => -2.5%%.")
    ap.add_argument("--family", default=None, help="Required for FAMILY/SERIES scope.")
    ap.add_argument("--series", default=None, help="Required for SERIES scope.")
    ap.add_argument("--component", default=None,
                    help="Optional child component code (NULL = all components).")
    ap.add_argument("--reason", default=None)
    ap.add_argument("--by", dest="applied_by", default=None, help="Who applied it.")
    ap.add_argument("--apply", action="store_true",
                    help="Actually apply. Omit for a dry-run PREVIEW (default).")
    a = ap.parse_args()

    dry_run = 0 if a.apply else 1
    mode = "APPLY" if a.apply else "DRY-RUN (preview only; nothing written)"
    print("=" * 78)
    print(f"PRICE ADJUSTMENT — {mode}")
    print(f"  scope={a.scope} family={a.family} series={a.series} "
          f"component={a.component} percent={a.percent}")
    print("=" * 78)

    conn = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "EXEC price.usp_ApplyPriceAdjustment "
                "@ScopeType=?, @PercentChange=?, @FamilyCode=?, @SeriesCode=?, "
                "@ComponentCode=?, @Reason=?, @AppliedBy=?, @DryRun=?",
                a.scope, a.percent, a.family, a.series, a.component,
                a.reason, a.applied_by, dry_run,
            )
            _print_resultsets(cur)
        except pyodbc.Error as e:
            print(f"\nERROR: {e.args[1] if len(e.args) > 1 else e}")
            return 1
    finally:
        conn.close()

    if dry_run:
        print("\n(No changes written. Re-run with --apply to commit.)")
    else:
        print("\nApplied. Audit: price.PriceAdjustment / price.PriceAdjustmentRow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
