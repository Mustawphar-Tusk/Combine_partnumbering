from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: expected block was not found")
    return text.replace(old, new, 1)


def patch_compiler() -> None:
    path = ROOT / "src" / "compiler" / "pricing_metadata_compiler.py"
    text = path.read_text(encoding="utf-8-sig")

    if "class PriceCandidateCondition:" not in text:
        text = replace_once(
            text,
            "@dataclass(frozen=True)\nclass PriceCandidate:\n",
            """@dataclass(frozen=True)\nclass PriceCandidateCondition:\n    sequence_no: int\n    field_code: str\n    comparison_operator: str\n    comparison_value: str | None\n    source_value: str | None = None\n\n\n@dataclass(frozen=True)\nclass PriceCandidate:\n""",
            "compiler condition dataclass",
        )

    start = text.index("class PriceCandidate:")
    end = text.index("\n\n@dataclass", start)
    block = text[start:end]
    if "conditions:" not in block:
        before, after = text[:start], text[start:]
        after = replace_once(
            after,
            "    source_cell: str\n",
            """    source_cell: str\n    conditions: tuple[\n        PriceCandidateCondition,\n        ...\n    ] = ()\n""",
            "compiler candidate conditions field",
        )
        text = before + after

    candidate_area = text[text.find("candidates.append("):]
    if "PriceCandidateCondition(" not in candidate_area:
        text = replace_once(
            text,
            """                            table_name=table_name,\n                            source_cell=source_cell,\n                        )\n""",
            """                            table_name=table_name,\n                            source_cell=source_cell,\n                            conditions=(\n                                PriceCandidateCondition(\n                                    sequence_no=1,\n                                    field_code=\"SIZE\",\n                                    comparison_operator=\"EQ\",\n                                    comparison_value=canonical_size,\n                                    source_value=source_size,\n                                ),\n                                PriceCandidateCondition(\n                                    sequence_no=2,\n                                    field_code=\"PUMP_MATERIAL\",\n                                    comparison_operator=\"EQ\",\n                                    comparison_value=canonical_material,\n                                    source_value=source_material,\n                                ),\n                            ),\n                        )\n""",
            "compiler BASE_PUMP condition construction",
        )

    path.write_text(text, encoding="utf-8")
    print(f"Patched: {path}")


def publisher_helpers() -> str:
    return r'''
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


'''


def patch_publisher() -> None:
    path = ROOT / "src" / "pricing_engine" / "publisher.py"
    text = path.read_text(encoding="utf-8-sig")

    if "import hashlib" not in text:
        text = replace_once(text, "import json\n", "import hashlib\nimport json\n", "publisher hashlib import")

    if "def _normalized_conditions(" not in text:
        marker = "def _default_connection_string("
        pos = text.find(marker)
        if pos < 0:
            raise RuntimeError("publisher helper insertion anchor was not found")
        text = text[:pos] + publisher_helpers() + text[pos:]

    old_key = """        key = (\n            str(row.get(\"component_code\") or \"\"),\n            str(row.get(\"series_code\") or \"\"),\n            str(row.get(\"size_value\") or \"\"),\n            str(row.get(\"option_field_code\") or \"\"),\n            str(row.get(\"option_value\") or \"\"),\n        )\n"""
    if old_key in text:
        new_key = """        normalized_conditions = _normalized_conditions(row)\n\n        key = (\n            str(row.get(\"component_code\") or \"\"),\n            str(row.get(\"series_code\") or \"\"),\n            tuple(\n                (\n                    condition[\"field_code\"],\n                    condition[\"comparison_operator\"],\n                    condition[\"comparison_value\"],\n                )\n                for condition in normalized_conditions\n            ),\n        )\n"""
        text = text.replace(old_key, new_key, 1)

    insert_start = text.find("INSERT INTO stg.PricingExtract")
    insert_end = text.find('"""', insert_start)
    insert_block = text[insert_start:insert_end]
    if "ConditionsJson" not in insert_block:
        text = replace_once(
            text,
            """            OptionFieldCode,\n            OptionValue,\n            SourceOptionValue,\n\n            Amount,\n""",
            """            OptionFieldCode,\n            OptionValue,\n            SourceOptionValue,\n            ConditionsJson,\n\n            Amount,\n""",
            "publisher ConditionsJson insert column",
        )
        text = replace_once(
            text,
            """        VALUES\n        (\n            ?, ?, ?, ?, ?,\n            ?, ?,\n            ?, ?, ?,\n            ?, ?, ?,\n            ?,\n            ?, ?, ?, ?\n        );\n""",
            """        VALUES\n        (\n            ?, ?, ?, ?, ?,\n            ?, ?,\n            ?, ?, ?,\n            ?,\n            ?, ?, ?,\n            ?,\n            ?, ?, ?, ?\n        );\n""",
            "publisher ConditionsJson placeholders",
        )

    loop_area = text[text.find("for candidate in candidates:"):text.find("cursor.fast_executemany")]
    if "conditions_json =" not in loop_area:
        text = replace_once(
            text,
            """            source_price_value = (\n                None\n                if raw_source_price is None\n                else str(raw_source_price)\n            )\n\n            rows.append(\n""",
            """            source_price_value = (\n                None\n                if raw_source_price is None\n                else str(raw_source_price)\n            )\n\n            conditions_json = _canonical_conditions_json(candidate)\n\n            (\n                transport_size_value,\n                transport_source_size_value,\n                transport_option_field_code,\n                transport_option_value,\n                transport_source_option_value,\n            ) = _legacy_transport_values(\n                candidate,\n                conditions_json,\n            )\n\n            rows.append(\n""",
            "publisher condition payload preparation",
        )

    old_rows = """                    candidate.get(\"size_value\"),\n                    candidate.get(\"source_size_value\"),\n\n                    candidate.get(\"option_field_code\"),\n                    candidate.get(\"option_value\"),\n                    candidate.get(\"source_option_value\"),\n\n                    candidate.get(\"amount\"),\n"""
    if old_rows in text:
        text = text.replace(
            old_rows,
            """                    transport_size_value,\n                    transport_source_size_value,\n\n                    transport_option_field_code,\n                    transport_option_value,\n                    transport_source_option_value,\n                    conditions_json,\n\n                    candidate.get(\"amount\"),\n""",
            1,
        )

    path.write_text(text, encoding="utf-8")
    print(f"Patched: {path}")


def patch_sql17() -> None:
    path = ROOT / "sql" / "17_Create_Pricing_Publication.sql"
    text = path.read_text(encoding="utf-8-sig")

    if "ConditionsJson        nvarchar(max) NULL" not in text:
        text = replace_once(
            text,
            """        OptionFieldCode       varchar(100) NULL,\n        OptionValue           nvarchar(1000) NULL,\n        SourceOptionValue     nvarchar(1000) NULL,\n\n        Amount                decimal(19,4) NULL,\n""",
            """        OptionFieldCode       varchar(100) NULL,\n        OptionValue           nvarchar(1000) NULL,\n        SourceOptionValue     nvarchar(1000) NULL,\n        ConditionsJson        nvarchar(max) NULL,\n\n        Amount                decimal(19,4) NULL,\n""",
            "SQL17 create-table ConditionsJson",
        )

    if "CK_PricingExtract_ConditionsJson" not in text:
        marker = """/* ================================================================\n   2. EXTEND price.PriceRule\n   ================================================================ */\n"""
        addition = """IF COL_LENGTH(\n    'stg.PricingExtract',\n    'ConditionsJson'\n) IS NULL\nBEGIN\n    ALTER TABLE stg.PricingExtract\n        ADD ConditionsJson nvarchar(max) NULL;\nEND;\nGO\n\n\nIF NOT EXISTS\n(\n    SELECT 1\n    FROM sys.check_constraints\n    WHERE\n        parent_object_id = OBJECT_ID('stg.PricingExtract')\n        AND name = 'CK_PricingExtract_ConditionsJson'\n)\nBEGIN\n    ALTER TABLE stg.PricingExtract\n        ADD CONSTRAINT CK_PricingExtract_ConditionsJson\n        CHECK\n        (\n            ConditionsJson IS NULL\n            OR ISJSON(ConditionsJson) = 1\n        );\nEND;\nGO\n\n\n"""
        text = replace_once(text, marker, addition + marker, "SQL17 additive ConditionsJson migration")

    if "ConditionsJson       nvarchar(max) NULL" not in text:
        text = replace_once(
            text,
            """        OptionFieldCode      varchar(100) NULL,\n        OptionValue          nvarchar(1000) NULL,\n        SourceOptionValue    nvarchar(1000) NULL,\n        Amount               decimal(19,4) NULL,\n""",
            """        OptionFieldCode      varchar(100) NULL,\n        OptionValue          nvarchar(1000) NULL,\n        SourceOptionValue    nvarchar(1000) NULL,\n        ConditionsJson       nvarchar(max) NULL,\n        Amount               decimal(19,4) NULL,\n""",
            "SQL17 #PricingSource ConditionsJson",
        )

    # #PricingSource insert list and SELECT flow.
    source_region = text[text.find("INSERT INTO #PricingSource"):text.find("/* ------------------------------------------------------------\n       Create runtime price rules")]
    if "ConditionsJson" not in source_region:
        text = replace_once(
            text,
            """        OptionFieldCode,\n        OptionValue,\n        SourceOptionValue,\n        Amount,\n""",
            """        OptionFieldCode,\n        OptionValue,\n        SourceOptionValue,\n        ConditionsJson,\n        Amount,\n""",
            "SQL17 #PricingSource insert ConditionsJson",
        )
        text = replace_once(
            text,
            """        pe.OptionFieldCode,\n        pe.OptionValue,\n        pe.SourceOptionValue,\n        pe.Amount,\n""",
            """        pe.OptionFieldCode,\n        pe.OptionValue,\n        pe.SourceOptionValue,\n        pe.ConditionsJson,\n        pe.Amount,\n""",
            "SQL17 #PricingSource select ConditionsJson",
        )

    start_marker = """    /* ------------------------------------------------------------\n       Add canonical configuration conditions\n       ------------------------------------------------------------ */\n"""
    end_marker = "    COMMIT TRANSACTION;\n"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("SQL17 condition publication markers were not found")

    if "OPENJSON(src.ConditionsJson)" not in text[start:end]:
        new_block = r'''    /* ------------------------------------------------------------
       Add canonical configuration conditions

       M022:
       ConditionsJson is authoritative for new publications.
       NULL ConditionsJson falls back to the M021 fixed transport.
       ------------------------------------------------------------ */

    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        c.SequenceNo,
        c.FieldCode,
        c.ComparisonOperator,
        c.ComparisonValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    CROSS APPLY OPENJSON(src.ConditionsJson)
    WITH
    (
        SequenceNo         int            '$.sequence_no',
        FieldCode          varchar(100)   '$.field_code',
        ComparisonOperator varchar(30)    '$.comparison_operator',
        ComparisonValue    nvarchar(1000) '$.comparison_value'
    ) c
    WHERE src.ConditionsJson IS NOT NULL;


    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        1,
        'SIZE',
        'EQ',
        src.SizeValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    WHERE
        src.ConditionsJson IS NULL
        AND src.SizeValue IS NOT NULL;


    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        2,
        src.OptionFieldCode,
        'EQ',
        src.OptionValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    WHERE
        src.ConditionsJson IS NULL
        AND src.OptionFieldCode IS NOT NULL
        AND src.OptionValue IS NOT NULL;


'''
        text = text[:start] + new_block + text[end:]

    path.write_text(text, encoding="utf-8")
    print(f"Patched: {path}")


def create_sql20() -> None:
    path = ROOT / "sql" / "20_Add_Generic_Pricing_Conditions.sql"
    path.write_text(
        """SET ANSI_NULLS ON;\nGO\nSET QUOTED_IDENTIFIER ON;\nGO\nSET NOCOUNT ON;\nSET XACT_ABORT ON;\nGO\n\nIF COL_LENGTH(\n    'stg.PricingExtract',\n    'ConditionsJson'\n) IS NULL\nBEGIN\n    ALTER TABLE stg.PricingExtract\n        ADD ConditionsJson nvarchar(max) NULL;\nEND;\nGO\n\nIF NOT EXISTS\n(\n    SELECT 1\n    FROM sys.check_constraints\n    WHERE\n        parent_object_id = OBJECT_ID('stg.PricingExtract')\n        AND name = 'CK_PricingExtract_ConditionsJson'\n)\nBEGIN\n    ALTER TABLE stg.PricingExtract\n        ADD CONSTRAINT CK_PricingExtract_ConditionsJson\n        CHECK\n        (\n            ConditionsJson IS NULL\n            OR ISJSON(ConditionsJson) = 1\n        );\nEND;\nGO\n\nPRINT 'M022.3 generic pricing condition staging deployed.';\nGO\n""",
        encoding="utf-8",
    )
    print(f"Created: {path}")


def create_tests() -> None:
    path = ROOT / "tests" / "test_m022_generic_pricing_conditions.py"
    path.write_text(
        r'''from pathlib import Path

from src.compiler.pricing_metadata_compiler import compile_base_pump_pricing
from src.pricing_engine.publisher import (
    _canonical_conditions_json,
    _legacy_transport_values,
    _normalized_conditions,
)

ROOT = Path(__file__).resolve().parents[1]


def test_m022_base_pump_emits_two_generic_conditions():
    report = compile_base_pump_pricing(
        ROOT / "workbooks" / "Fybroc" / "Price Estimator-Fybroc.xlsm",
        ROOT / "config" / "pricing_profiles" / "fybroc_base_pump.json",
    )
    assert report.issue_count == 0
    assert report.candidate_count == 436
    assert all(len(c.conditions) == 2 for c in report.candidates)
    first = report.candidates[0]
    assert first.conditions[0].field_code == "SIZE"
    assert first.conditions[0].comparison_value == first.size_value
    assert first.conditions[1].field_code == "PUMP_MATERIAL"
    assert first.conditions[1].comparison_value == first.option_value


def test_m022_publisher_preserves_base_pump_legacy_transport():
    candidate = {
        "size_value": "1x1.5x6",
        "source_size_value": "1x1.5x6 (6AA)",
        "option_field_code": "PUMP_MATERIAL",
        "option_value": "VR-1*",
        "source_option_value": "VR-1 (Standard)",
        "conditions": [
            {"sequence_no": 1, "field_code": "SIZE", "comparison_operator": "EQ", "comparison_value": "1x1.5x6"},
            {"sequence_no": 2, "field_code": "PUMP_MATERIAL", "comparison_operator": "EQ", "comparison_value": "VR-1*"},
        ],
    }
    payload = _canonical_conditions_json(candidate)
    assert len(_normalized_conditions(candidate)) == 2
    assert _legacy_transport_values(candidate, payload) == (
        "1x1.5x6",
        "1x1.5x6 (6AA)",
        "PUMP_MATERIAL",
        "VR-1*",
        "VR-1 (Standard)",
    )


def test_m022_multi_condition_uses_deterministic_proxy_key():
    candidate = {
        "size_value": "1x1.5x6",
        "source_size_value": "1x1.5x6 (6AA)",
        "option_field_code": None,
        "option_value": None,
        "source_option_value": None,
        "conditions": [
            {"sequence_no": 1, "field_code": "SIZE", "comparison_operator": "EQ", "comparison_value": "1x1.5x6"},
            {"sequence_no": 2, "field_code": "SEAL_OPTION", "comparison_operator": "EQ", "comparison_value": "Mechanical Seal Included*"},
            {"sequence_no": 3, "field_code": "SEAL_TYPE", "comparison_operator": "EQ", "comparison_value": "8B2 Single Outside*"},
            {"sequence_no": 4, "field_code": "SEAL_MATERIALS", "comparison_operator": "EQ", "comparison_value": "Carbon vs. Ceramic*"},
            {"sequence_no": 5, "field_code": "SEAL_ELASTOMERS", "comparison_operator": "EQ", "comparison_value": "FKM*"},
        ],
    }
    payload = _canonical_conditions_json(candidate)
    transport = _legacy_transport_values(candidate, payload)
    assert transport[0] == "1x1.5x6"
    assert transport[2] == "__CONDITION_SET__"
    assert len(transport[3]) == 64
''',
        encoding="utf-8",
    )
    print(f"Created: {path}")


def main() -> None:
    patch_compiler()
    patch_publisher()
    patch_sql17()
    create_sql20()
    create_tests()
    print("M022.3 generic multi-condition pricing patch applied.")
    print("No price-book publication was created; current V2 is untouched.")


if __name__ == "__main__":
    main()
