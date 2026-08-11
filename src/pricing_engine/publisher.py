from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pyodbc


SUPPORTED_STATUSES = {
    "found",
    "call_for_price",
}


@dataclass(frozen=True)
class PricingPublicationResult:
    load_batch_id: str
    price_book_id: int
    price_book_version_id: int
    version_code: str
    family_code: str
    currency_code: str
    staged_count: int
    published_rule_count: int
    published_condition_count: int
    found_count: int
    call_for_price_count: int



def _normalized_conditions(
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    raw = candidate.get("conditions") or []
    normalized: list[dict[str, Any]] = []

    if raw:
        ordered = sorted(
            raw,
            key=lambda row: int(row.get("sequence_no") or 0),
        )
        for index, row in enumerate(ordered, start=1):
            field_code = str(row.get("field_code") or "").strip().upper()
            operator = str(
                row.get("comparison_operator") or "EQ"
            ).strip().upper()
            value = row.get("comparison_value")

            if not field_code:
                raise RuntimeError("Pricing condition has no field_code.")
            if operator != "EQ":
                raise RuntimeError(
                    "M022 generic pricing currently supports EQ only. "
                    f"Received: {operator!r}"
                )

            normalized.append(
                {
                    "sequence_no": index,
                    "field_code": field_code,
                    "comparison_operator": operator,
                    "comparison_value": None if value is None else str(value),
                }
            )
    else:
        size_value = candidate.get("size_value")
        if size_value is not None:
            normalized.append(
                {
                    "sequence_no": 1,
                    "field_code": "SIZE",
                    "comparison_operator": "EQ",
                    "comparison_value": str(size_value),
                }
            )

        option_field = candidate.get("option_field_code")
        option_value = candidate.get("option_value")
        if option_field is not None and option_value is not None:
            normalized.append(
                {
                    "sequence_no": len(normalized) + 1,
                    "field_code": str(option_field).strip().upper(),
                    "comparison_operator": "EQ",
                    "comparison_value": str(option_value),
                }
            )

    if not normalized:
        raise RuntimeError("Pricing candidate contains no runtime conditions.")

    return tuple(normalized)


def _canonical_conditions_json(candidate: dict[str, Any]) -> str:
    return json.dumps(
        _normalized_conditions(candidate),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _legacy_transport_values(
    candidate: dict[str, Any],
    conditions_json: str,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    conditions = _normalized_conditions(candidate)
    legacy_size = candidate.get("size_value")
    legacy_field = candidate.get("option_field_code")
    legacy_value = candidate.get("option_value")

    legacy_shape = (
        len(conditions) == 2
        and conditions[0]["field_code"] == "SIZE"
        and str(conditions[0]["comparison_value"]) == str(legacy_size)
        and legacy_field is not None
        and legacy_value is not None
        and conditions[1]["field_code"] == str(legacy_field).strip().upper()
        and str(conditions[1]["comparison_value"]) == str(legacy_value)
    )

    if legacy_shape:
        return (
            None if legacy_size is None else str(legacy_size),
            candidate.get("source_size_value"),
            str(legacy_field),
            str(legacy_value),
            candidate.get("source_option_value"),
        )

    size_value = next(
        (
            row["comparison_value"]
            for row in conditions
            if row["field_code"] == "SIZE"
            and row["comparison_operator"] == "EQ"
        ),
        None,
    )

    digest = hashlib.sha256(conditions_json.encode("utf-8")).hexdigest()

    return (
        None if size_value is None else str(size_value),
        candidate.get("source_size_value"),
        "__CONDITION_SET__",
        digest,
        candidate.get("source_option_value"),
    )


def _default_connection_string() -> str:
    drivers = pyodbc.drivers()

    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    ]

    driver = next(
        (
            candidate
            for candidate in preferred
            if candidate in drivers
        ),
        None,
    )

    if driver is None:
        raise RuntimeError(
            "No supported SQL Server ODBC driver was found. "
            f"Installed drivers: {drivers}"
        )

    return (
        f"DRIVER={{{driver}}};"
        "SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )


def _load_compilation(
    compilation_path: Path,
) -> dict[str, Any]:

    data = json.loads(
        compilation_path.read_text(
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
            "Pricing compilation contains issues. "
            "Publication is blocked."
        )

    candidates = data.get(
        "candidates",
        [],
    )

    if not candidates:
        raise RuntimeError(
            "Pricing compilation contains no candidates."
        )

    return data


def _validate_candidates(
    candidates: list[dict[str, Any]],
) -> tuple[
    str,
    str,
    str,
]:

    families = {
        str(row["family_code"])
        .strip()
        .upper()
        for row in candidates
    }

    if len(families) != 1:
        raise RuntimeError(
            "A publication must contain exactly one family."
        )

    currencies = {
        str(row["currency_code"])
        .strip()
        .upper()
        for row in candidates
    }

    if len(currencies) != 1:
        raise RuntimeError(
            "A publication must contain exactly one currency."
        )

    workbooks = {
        str(row["workbook_name"])
        .strip()
        for row in candidates
        if row.get("workbook_name")
    }

    if len(workbooks) != 1:
        raise RuntimeError(
            "A publication must contain exactly one source workbook."
        )

    seen: set[
        tuple[
            str,
            str,
            str,
            str,
            str,
        ]
    ] = set()

    for row in candidates:
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
                "Found pricing record has no amount."
            )

        if (
            status == "call_for_price"
            and amount is not None
        ):
            raise RuntimeError(
                "Call-for-price record unexpectedly "
                "contains a numeric amount."
            )

        normalized_conditions = _normalized_conditions(row)

        key = (
            str(row.get("component_code") or ""),
            str(row.get("series_code") or ""),
            tuple(
                (
                    condition["field_code"],
                    condition["comparison_operator"],
                    condition["comparison_value"],
                )
                for condition in normalized_conditions
            ),
        )

        if key in seen:
            raise RuntimeError(
                "Duplicate pricing key detected: "
                f"{key}"
            )

        seen.add(
            key
        )

    return (
        next(iter(families)),
        next(iter(currencies)),
        next(iter(workbooks)),
    )


def publish_compiled_pricing(
    compilation_path: Path,
    *,
    version_code: str,
    effective_from: date,
    connection_string: str | None = None,
) -> PricingPublicationResult:

    data = _load_compilation(
        compilation_path
    )

    candidates = data[
        "candidates"
    ]

    (
        family_code,
        currency_code,
        source_workbook,
    ) = _validate_candidates(
        candidates
    )

    load_batch_id = uuid.uuid4()

    connection_string = (
        connection_string
        or _default_connection_string()
    )

    connection = pyodbc.connect(
        connection_string,
        autocommit=False,
    )

    try:
        cursor = connection.cursor()

        insert_sql = """
        INSERT INTO stg.PricingExtract
        (
            LoadBatchId,
            FamilyCode,
            ComponentCode,
            SeriesCode,
            SourceSeriesCode,

            SizeValue,
            SourceSizeValue,

            OptionFieldCode,
            OptionValue,
            SourceOptionValue,
            ConditionsJson,

            Amount,
            PricingStatus,
            SourcePriceValue,

            CurrencyCode,

            SourceWorkbook,
            SourceWorksheet,
            SourceTable,
            SourceCell
        )
        VALUES
        (
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?,
            ?, ?, ?,
            ?,
            ?, ?, ?, ?
        );
        """

        rows = []

        for candidate in candidates:
            raw_source_price = candidate.get(
                "source_price_value"
            )

            source_price_value = (
                None
                if raw_source_price is None
                else str(raw_source_price)
            )

            conditions_json = _canonical_conditions_json(candidate)

            (
                transport_size_value,
                transport_source_size_value,
                transport_option_field_code,
                transport_option_value,
                transport_source_option_value,
            ) = _legacy_transport_values(
                candidate,
                conditions_json,
            )

            rows.append(
                (
                    str(load_batch_id),
                    family_code,
                    candidate["component_code"],
                    candidate.get("series_code"),
                    candidate.get("source_series_code"),

                    transport_size_value,
                    transport_source_size_value,

                    transport_option_field_code,
                    transport_option_value,
                    transport_source_option_value,
                    conditions_json,

                    candidate.get("amount"),
                    candidate["pricing_status"],
                    source_price_value,

                    currency_code,

                    candidate.get("workbook_name"),
                    candidate.get("worksheet_name"),
                    candidate.get("table_name"),
                    candidate.get("source_cell"),
                )
            )

        cursor.fast_executemany = True

        cursor.executemany(
            insert_sql,
            rows,
        )

        cursor.execute(
            """
            EXEC price.usp_PublishPricingFromStaging
                @LoadBatchId = ?,
                @FamilyCode = ?,
                @VersionCode = ?,
                @EffectiveFrom = ?,
                @SourceWorkbook = ?;
            """,
            str(load_batch_id),
            family_code,
            version_code,
            effective_from,
            source_workbook,
        )

        publication_row = cursor.fetchone()

        if publication_row is None:
            raise RuntimeError(
                "Pricing publication procedure returned "
                "no result."
            )

        price_book_id = int(
            publication_row[0]
        )

        price_book_version_id = int(
            publication_row[1]
        )

        returned_version_code = str(
            publication_row[2]
        )

        returned_family_code = str(
            publication_row[3]
        )

        returned_currency_code = str(
            publication_row[4]
        )

        published_rule_count = int(
            publication_row[5]
        )

        published_condition_count = int(
            publication_row[6]
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM stg.PricingExtract
            WHERE LoadBatchId = ?;
            """,
            str(load_batch_id),
        )

        staged_count = int(
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT
                PricingStatus,
                COUNT(*)
            FROM price.PriceRule
            WHERE PriceBookVersionId = ?
            GROUP BY PricingStatus;
            """,
            price_book_version_id,
        )

        status_counts = {
            str(status): int(count)
            for status, count
            in cursor.fetchall()
        }

        found_count = status_counts.get(
            "found",
            0,
        )

        call_for_price_count = (
            status_counts.get(
                "call_for_price",
                0,
            )
        )

        expected_count = len(
            candidates
        )

        if staged_count != expected_count:
            raise RuntimeError(
                "Staging reconciliation failed: "
                f"compiler={expected_count}, "
                f"staging={staged_count}"
            )

        if published_rule_count != expected_count:
            raise RuntimeError(
                "Publication reconciliation failed: "
                f"compiler={expected_count}, "
                f"rules={published_rule_count}"
            )

        if (
            found_count
            + call_for_price_count
            != expected_count
        ):
            raise RuntimeError(
                "Pricing status reconciliation failed."
            )

        connection.commit()

        return PricingPublicationResult(
            load_batch_id=str(
                load_batch_id
            ),
            price_book_id=price_book_id,
            price_book_version_id=(
                price_book_version_id
            ),
            version_code=(
                returned_version_code
            ),
            family_code=(
                returned_family_code
            ),
            currency_code=(
                returned_currency_code
            ),
            staged_count=(
                staged_count
            ),
            published_rule_count=(
                published_rule_count
            ),
            published_condition_count=(
                published_condition_count
            ),
            found_count=(
                found_count
            ),
            call_for_price_count=(
                call_for_price_count
            ),
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
