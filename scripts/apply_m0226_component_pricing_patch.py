from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig",
    )


def write(
    path: Path,
    text: str,
) -> None:
    path.write_text(
        text,
        encoding="utf-8",
    )


def insert_after(
    text: str,
    marker: str,
    addition: str,
    *,
    label: str,
) -> str:
    if marker not in text:
        raise RuntimeError(
            f"{label}: marker not found."
        )

    return text.replace(
        marker,
        marker + addition,
        1,
    )


def patch_runtime_registry() -> None:
    path = (
        ROOT
        / "src"
        / "api"
        / "runtime_registry.py"
    )

    text = read(path)

    import_marker = """    from src.pricing_engine.non_blocking import (
        NonBlockingPricingService,
    )
"""

    import_addition = """    from src.pricing_engine.aggregate import (
        ConfigurationPricingService,
    )
    from src.pricing_engine.runtime_profile import (
        load_pricing_runtime_profile,
    )
"""

    if (
        "ConfigurationPricingService"
        not in text
    ):
        text = insert_after(
            text,
            import_marker,
            import_addition,
            label=(
                "runtime registry imports"
            ),
        )

    old = """    pricing_service = NonBlockingPricingService(
        PricingService(
            SqlPricingRepository(
                connection_string=(
                    settings.connection_string
                )
            )
        )
    )
"""

    new = """    pricing_profile = (
        load_pricing_runtime_profile(
            settings.project_root,
            "FYBROC",
        )
    )

    component_pricing_service = (
        NonBlockingPricingService(
            PricingService(
                SqlPricingRepository(
                    connection_string=(
                        settings.connection_string
                    )
                )
            )
        )
    )

    pricing_service = (
        ConfigurationPricingService(
            component_pricing_service,
            component_codes=(
                pricing_profile
                .component_codes
            ),
            legacy_component_code=(
                pricing_profile
                .legacy_component_code
            ),
            default_price_book_code=(
                pricing_profile
                .price_book_code
            ),
        )
    )
"""

    if old in text:
        text = text.replace(
            old,
            new,
            1,
        )
    elif (
        "pricing_profile = ("
        not in text
    ):
        raise RuntimeError(
            "runtime registry pricing-service "
            "construction block not found."
        )

    write(
        path,
        text,
    )

    print(
        f"Patched: {path}"
    )


def patch_api_models() -> None:
    path = (
        ROOT
        / "src"
        / "api"
        / "models.py"
    )

    text = read(path)

    if (
        "from decimal import Decimal"
        not in text
    ):
        if (
            "from __future__ import annotations\n"
            in text
        ):
            text = text.replace(
                "from __future__ import annotations\n",
                (
                    "from __future__ import annotations\n\n"
                    "from decimal import Decimal\n"
                ),
                1,
            )
        else:
            text = (
                "from decimal import Decimal\n"
                + text
            )

    if (
        "class PricingComponentResponse("
        not in text
    ):
        marker = (
            "class FinalizeConfigurationResponse"
            "(ApiModel):"
        )

        if marker not in text:
            raise RuntimeError(
                "FinalizeConfigurationResponse "
                "class marker not found."
            )

        classes = """class PricingComponentResponse(ApiModel):
    component_code: str
    amount: Decimal
    status: str
    currency_code: str | None = None
    price_book_code: str | None = None
    price_book_version_id: int | None = None
    version_code: str | None = None
    price_rule_id: int | None = None
    source_worksheet: str | None = None
    source_table: str | None = None
    source_cell: str | None = None


class ConfigurationPricingResponse(ApiModel):
    total_amount: Decimal
    known_amount: Decimal
    status: str
    currency_code: str | None = None
    price_book_code: str | None = None
    price_book_version_id: int | None = None
    version_code: str | None = None
    components: list[
        PricingComponentResponse
    ]


"""

        text = text.replace(
            marker,
            classes + marker,
            1,
        )

    tree = ast.parse(text)

    node = next(
        (
            item
            for item in tree.body
            if (
                isinstance(
                    item,
                    ast.ClassDef,
                )
                and item.name
                == "FinalizeConfigurationResponse"
            )
        ),
        None,
    )

    if node is None:
        raise RuntimeError(
            "FinalizeConfigurationResponse "
            "AST node not found."
        )

    class_text = "\n".join(
        text.splitlines()[
            node.lineno - 1:
            node.end_lineno
        ]
    )

    if (
        "pricing:"
        not in class_text
    ):
        lines = text.splitlines()

        lines.insert(
            node.end_lineno,
            (
                "    pricing: "
                "ConfigurationPricingResponse "
                "| None = None"
            ),
        )

        text = (
            "\n".join(lines)
            + "\n"
        )

    write(
        path,
        text,
    )

    print(
        f"Patched: {path}"
    )


def find_matching_paren(
    text: str,
    open_index: int,
) -> int:
    depth = 0
    in_single = False
    in_double = False
    escaped = False

    for index in range(
        open_index,
        len(text),
    ):
        char = text[index]

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if (
            char == "'"
            and not in_double
        ):
            in_single = not in_single
            continue

        if (
            char == '"'
            and not in_single
        ):
            in_double = not in_double
            continue

        if in_single or in_double:
            continue

        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1

            if depth == 0:
                return index

    raise RuntimeError(
        "Matching parenthesis was not found."
    )


def patch_presenter() -> None:
    path = (
        ROOT
        / "src"
        / "api"
        / "presenters.py"
    )

    text = read(path)

    helper = """def _present_configuration_pricing(
    pricing,
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
            {
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
            for component
            in pricing.components
        ],
    }


"""

    marker = (
        "def present_persisted_configuration("
    )

    if (
        "_present_configuration_pricing"
        not in text
    ):
        if marker not in text:
            raise RuntimeError(
                "present_persisted_configuration "
                "marker not found."
            )

        text = text.replace(
            marker,
            helper + marker,
            1,
        )

    call_marker = (
        "return FinalizeConfigurationResponse("
    )

    call_start = text.find(
        call_marker
    )

    if call_start < 0:
        raise RuntimeError(
            "FinalizeConfigurationResponse "
            "constructor call not found."
        )

    open_index = text.find(
        "(",
        call_start,
    )

    close_index = find_matching_paren(
        text,
        open_index,
    )

    call_text = text[
        call_start:
        close_index + 1
    ]

    if (
        "_present_configuration_pricing("
        not in call_text
    ):
        # Use a distinct Python argument name only if the
        # response model already has a field named "pricing".
        # The API field itself is "pricing"; this constructor
        # keyword must therefore also be "pricing".
        insertion = """        pricing=(
            _present_configuration_pricing(
                pricing
            )
            if pricing is not None
            else None
        ),
"""

        # Insert immediately before the constructor's final closing
        # parenthesis while preserving that line's indentation.
        line_start = text.rfind(
            "\n",
            0,
            close_index,
        ) + 1

        closing_indent = text[
            line_start:
            close_index
        ]

        text = (
            text[:line_start]
            + insertion
            + closing_indent
            + text[close_index:]
        )

    write(
        path,
        text,
    )

    print(
        f"Patched: {path}"
    )


def main() -> None:
    patch_runtime_registry()
    patch_api_models()
    patch_presenter()

    print()
    print(
        "M022.6 component-aware aggregate "
        "pricing patch applied."
    )
    print(
        "Existing top-level pricing fields "
        "remain projected from BASE_PUMP."
    )
    print(
        "New nested 'pricing' response carries "
        "aggregate and component pricing."
    )


if __name__ == "__main__":
    main()
