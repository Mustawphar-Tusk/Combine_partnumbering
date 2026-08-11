from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PATH = (
    ROOT
    / "src"
    / "api"
    / "presenters.py"
)


def main() -> None:
    text = PATH.read_text(
        encoding="utf-8-sig",
    )

    start_marker = (
        "def _present_configuration_pricing("
    )

    end_marker = (
        "def present_persisted_configuration("
    )

    start = text.find(
        start_marker
    )
    end = text.find(
        end_marker,
        start,
    )

    if start < 0 or end < 0:
        raise RuntimeError(
            "M022.6 pricing presenter helper "
            "could not be located."
        )

    replacement = '''def _present_pricing_component(
    component,
):
    return {
        "component_code":
            component.component_code,
        "amount":
            component.amount,
        "status":
            component.status,
        "currency_code":
            component.currency_code,
        "price_book_code":
            component.price_book_code,
        "price_book_version_id":
            component.price_book_version_id,
        "version_code":
            component.version_code,
        "price_rule_id":
            component.price_rule_id,
        "source_worksheet":
            component.source_worksheet,
        "source_table":
            component.source_table,
        "source_cell":
            component.source_cell,
    }


def _present_configuration_pricing(
    pricing,
):
    """
    Present either:

    1. M022 aggregate ConfigurationPricingResult, or
    2. the historical M021 single-component PricingResult.

    Existing callers/tests remain backward compatible while the
    runtime migrates to aggregate pricing.
    """

    if hasattr(
        pricing,
        "components",
    ):
        return {
            "total_amount":
                pricing.total_amount,
            "known_amount":
                pricing.known_amount,
            "status":
                pricing.aggregate_status,
            "currency_code":
                pricing.currency_code_aggregate,
            "price_book_code":
                pricing.price_book_code_aggregate,
            "price_book_version_id":
                pricing.price_book_version_id_aggregate,
            "version_code":
                pricing.version_code_aggregate,
            "components": [
                _present_pricing_component(
                    component
                )
                for component
                in pricing.components
            ],
        }

    status = pricing.status

    known_amount = (
        pricing.amount
        if status == "found"
        else 0
    )

    total_amount = (
        pricing.amount
        if status == "found"
        else 0
    )

    return {
        "total_amount":
            total_amount,
        "known_amount":
            known_amount,
        "status":
            status,
        "currency_code":
            pricing.currency_code,
        "price_book_code":
            pricing.price_book_code,
        "price_book_version_id":
            pricing.price_book_version_id,
        "version_code":
            pricing.version_code,
        "components": [
            _present_pricing_component(
                pricing
            )
        ],
    }


'''

    text = (
        text[:start]
        + replacement
        + text[end:]
    )

    PATH.write_text(
        text,
        encoding="utf-8",
    )

    print(
        f"Patched: {PATH}"
    )
    print(
        "M022.6.1 presenter backward-compatibility "
        "hotfix applied."
    )


if __name__ == "__main__":
    main()
