from datetime import date
from pathlib import Path
import argparse
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.pricing_engine.publisher import (
    publish_compiled_pricing,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Publish compiled pricing metadata "
            "into PumpConfiguratorDB."
        )
    )

    parser.add_argument(
        "--version-code",
        required=True,
    )

    parser.add_argument(
        "--effective-from",
        required=True,
        help="YYYY-MM-DD",
    )

    parser.add_argument(
        "--input",
        default=(
            "exports/"
            "fybroc_base_pump_pricing.json"
        ),
    )

    args = parser.parse_args()

    compilation_path = (
        ROOT
        / args.input
    )

    effective_from = (
        date.fromisoformat(
            args.effective_from
        )
    )

    result = publish_compiled_pricing(
        compilation_path,
        version_code=(
            args.version_code
        ),
        effective_from=(
            effective_from
        ),
    )

    print("=" * 80)
    print(
        "M021.2.1 PRICING PUBLICATION"
    )
    print("=" * 80)

    print(
        f"Load Batch ID        : "
        f"{result.load_batch_id}"
    )

    print(
        f"Price Book ID        : "
        f"{result.price_book_id}"
    )

    print(
        f"Price Book Version ID: "
        f"{result.price_book_version_id}"
    )

    print(
        f"Version Code         : "
        f"{result.version_code}"
    )

    print(
        f"Family               : "
        f"{result.family_code}"
    )

    print(
        f"Currency             : "
        f"{result.currency_code}"
    )

    print(
        f"Staged               : "
        f"{result.staged_count}"
    )

    print(
        f"Published Rules      : "
        f"{result.published_rule_count}"
    )

    print(
        f"Published Conditions : "
        f"{result.published_condition_count}"
    )

    print(
        f"Found                : "
        f"{result.found_count}"
    )

    print(
        f"Call For Price       : "
        f"{result.call_for_price_count}"
    )


if __name__ == "__main__":
    main()
