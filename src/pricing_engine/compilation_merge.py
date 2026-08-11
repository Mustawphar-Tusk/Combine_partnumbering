from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_STATUSES = {
    "found",
    "call_for_price",
}


def _load_compilation(
    path: Path,
) -> dict[str, Any]:
    data = json.loads(
        path.read_text(
            encoding="utf-8-sig",
        )
    )

    issue_count = int(
        data.get(
            "issue_count",
            0,
        )
    )

    if issue_count != 0:
        raise RuntimeError(
            f"{path} contains "
            f"{issue_count} compilation issues."
        )

    candidates = data.get(
        "candidates",
        [],
    )

    if not candidates:
        raise RuntimeError(
            f"{path} contains no pricing candidates."
        )

    return data


def _condition_key(
    candidate: dict[str, Any],
) -> tuple[
    tuple[
        str,
        str,
        str | None,
    ],
    ...
]:
    conditions = (
        candidate.get(
            "conditions"
        )
        or []
    )

    if not conditions:
        raise RuntimeError(
            "Combined pricing publication requires "
            "generic candidate conditions."
        )

    ordered = sorted(
        conditions,
        key=lambda row: int(
            row.get(
                "sequence_no",
                0,
            )
        ),
    )

    result = []

    for row in ordered:
        field_code = str(
            row.get(
                "field_code"
            )
            or ""
        ).strip().upper()

        operator = str(
            row.get(
                "comparison_operator"
            )
            or "EQ"
        ).strip().upper()

        raw_value = row.get(
            "comparison_value"
        )

        value = (
            None
            if raw_value is None
            else str(raw_value)
        )

        if not field_code:
            raise RuntimeError(
                "Pricing condition is missing field_code."
            )

        if operator != "EQ":
            raise RuntimeError(
                "M022 combined publication currently "
                "supports EQ conditions only."
            )

        result.append(
            (
                field_code,
                operator,
                value,
            )
        )

    return tuple(result)


def merge_compiled_pricing(
    input_paths: Iterable[Path],
) -> dict[str, Any]:
    paths = tuple(
        Path(path)
        for path in input_paths
    )

    if not paths:
        raise ValueError(
            "At least one compiled pricing input is required."
        )

    all_candidates: list[
        dict[str, Any]
    ] = []

    for path in paths:
        data = _load_compilation(
            path
        )

        all_candidates.extend(
            data["candidates"]
        )

    families = {
        str(
            row["family_code"]
        ).strip().upper()
        for row in all_candidates
    }

    if len(families) != 1:
        raise RuntimeError(
            "Combined pricing publication must contain "
            "exactly one family."
        )

    currencies = {
        str(
            row["currency_code"]
        ).strip().upper()
        for row in all_candidates
    }

    if len(currencies) != 1:
        raise RuntimeError(
            "Combined pricing publication must contain "
            "exactly one currency."
        )

    workbooks = {
        str(
            row["workbook_name"]
        ).strip()
        for row in all_candidates
        if row.get(
            "workbook_name"
        )
    }

    if len(workbooks) != 1:
        raise RuntimeError(
            "Combined pricing publication must contain "
            "exactly one source workbook."
        )

    seen: set[
        tuple[
            str,
            str,
            tuple[
                tuple[
                    str,
                    str,
                    str | None,
                ],
                ...
            ],
        ]
    ] = set()

    for row in all_candidates:
        status = str(
            row["pricing_status"]
        ).strip()

        if status not in SUPPORTED_STATUSES:
            raise RuntimeError(
                f"Unsupported pricing status: {status!r}"
            )

        amount = row.get(
            "amount"
        )

        if (
            status == "found"
            and amount is None
        ):
            raise RuntimeError(
                "Found pricing candidate has no amount."
            )

        if (
            status == "call_for_price"
            and amount is not None
        ):
            raise RuntimeError(
                "Call-for-price pricing candidate "
                "contains an amount."
            )

        key = (
            str(
                row.get(
                    "component_code"
                )
                or ""
            ).strip().upper(),
            str(
                row.get(
                    "series_code"
                )
                or ""
            ).strip(),
            _condition_key(
                row
            ),
        )

        if key in seen:
            raise RuntimeError(
                "Duplicate canonical pricing rule exists "
                "across combined inputs."
            )

        seen.add(
            key
        )

    component_counts = Counter(
        str(
            row["component_code"]
        ).strip().upper()
        for row in all_candidates
    )

    status_counts = Counter(
        str(
            row["pricing_status"]
        ).strip()
        for row in all_candidates
    )

    condition_count = sum(
        len(
            _condition_key(
                row
            )
        )
        for row in all_candidates
    )

    return {
        "candidate_count":
            len(
                all_candidates
            ),
        "issue_count": 0,
        "condition_count":
            condition_count,
        "family_code":
            next(
                iter(
                    families
                )
            ),
        "currency_code":
            next(
                iter(
                    currencies
                )
            ),
        "source_workbook":
            next(
                iter(
                    workbooks
                )
            ),
        "component_counts":
            dict(
                sorted(
                    component_counts.items()
                )
            ),
        "status_counts":
            dict(
                sorted(
                    status_counts.items()
                )
            ),
        "source_compilations": [
            str(path)
            for path in paths
        ],
        "candidates":
            all_candidates,
        "issues": [],
    }


def save_combined_compilation(
    data: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
