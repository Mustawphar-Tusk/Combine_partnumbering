"""D120 - publish the compiled Dean pricing (exports/dean_pricing_matrix.json,
authoritative Dean Pricing Matrix) into PumpConfiguratorDB for the DEAN family.

Reuses the existing pricing publisher (src/pricing_engine/publisher.py). Publishing
@FamilyCode='DEAN' creates/uses the DEAN_STANDARD PriceBook (PumpFamilyId=1) and a
new PriceBookVersion set IsCurrent=1, superseding the empty DEV1 seed. Fybroc's
FYBROC_STANDARD pricebook/version is untouched (family-scoped at PriceBook level).

Run:
  python scripts/publish_dean_pricing.py --version-code DEAN-MATRIX-20260826-V1 \
         --effective-from 2026-08-26
"""
from pathlib import Path
from datetime import date
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pricing_engine.publisher import publish_compiled_pricing


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Dean pricing into PumpConfiguratorDB.")
    parser.add_argument("--version-code", required=True)
    parser.add_argument("--effective-from", required=True, help="YYYY-MM-DD")
    parser.add_argument("--input", default="exports/dean_pricing_matrix.json")
    args = parser.parse_args()

    result = publish_compiled_pricing(
        ROOT / args.input,
        version_code=args.version_code,
        effective_from=date.fromisoformat(args.effective_from),
    )

    print("=" * 80)
    print("D120 DEAN PRICING PUBLICATION")
    print("=" * 80)
    print(f"Load Batch ID         : {result.load_batch_id}")
    print(f"Price Book ID         : {result.price_book_id}")
    print(f"Price Book Version ID : {result.price_book_version_id}")
    print(f"Version Code          : {result.version_code}")
    print(f"Family                : {result.family_code}")
    print(f"Currency              : {result.currency_code}")
    print(f"Published rule count  : {result.published_rule_count}")
    print(f"Published condition ct: {result.published_condition_count}")
    print(f"Found                 : {result.found_count}")
    print(f"Call-for-price        : {result.call_for_price_count}")


if __name__ == "__main__":
    main()
