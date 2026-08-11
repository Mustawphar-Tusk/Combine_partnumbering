from __future__ import annotations

from decimal import Decimal

import pyodbc

from src.pricing_engine.database import (
    default_connection_string,
)
from src.pricing_engine.models import (
    PricingCondition,
    PricingRule,
)


class SqlPricingRepository:
    def __init__(
        self,
        connection_string: str | None = None,
    ) -> None:
        self._connection_string = (
            connection_string
            or default_connection_string()
        )

    def get_current_rules(
        self,
        *,
        family_code: str,
        price_book_code: str,
        component_code: str,
        series_code: str | None,
    ) -> tuple[PricingRule, ...]:

        sql = """
        SELECT
            r.PriceBookCode,
            r.PriceBookVersionId,
            r.VersionCode,
            r.CurrencyCode,

            r.PriceRuleId,
            r.RuleCode,
            r.ComponentCode,
            r.SeriesCode,
            r.Priority,
            r.Amount,
            r.PricingStatus,

            r.SourceSizeValue,
            r.SourceOptionValue,
            r.SourcePriceValue,
            r.SourceWorksheet,
            r.SourceTable,
            r.SourceCell,

            c.PriceConditionId,
            c.SequenceNo,
            c.FieldCode,
            c.ComparisonOperator,
            c.ComparisonValue

        FROM price.vw_CurrentPricingRules r

        LEFT JOIN price.PriceCondition c
            ON c.PriceRuleId =
               r.PriceRuleId

        WHERE
            r.FamilyCode = ?
            AND r.PriceBookCode = ?
            AND r.ComponentCode = ?
            AND
            (
                r.SeriesCode = ?
                OR r.SeriesCode IS NULL
            )

        ORDER BY
            r.Priority,
            r.PriceRuleId,
            c.SequenceNo;
        """

        connection = pyodbc.connect(
            self._connection_string
        )

        try:
            cursor = connection.cursor()

            cursor.execute(
                sql,
                family_code,
                price_book_code,
                component_code,
                series_code,
            )

            rows = cursor.fetchall()

        finally:
            connection.close()

        grouped: dict[int, dict] = {}

        for row in rows:
            rule_id = int(
                row.PriceRuleId
            )

            if rule_id not in grouped:
                grouped[rule_id] = {
                    "price_book_code":
                        str(row.PriceBookCode),

                    "price_book_version_id":
                        int(
                            row.PriceBookVersionId
                        ),

                    "version_code":
                        str(row.VersionCode),

                    "currency_code":
                        str(row.CurrencyCode),

                    "price_rule_id":
                        rule_id,

                    "rule_code":
                        str(row.RuleCode),

                    "component_code":
                        str(row.ComponentCode),

                    "series_code":
                        (
                            None
                            if row.SeriesCode is None
                            else str(row.SeriesCode)
                        ),

                    "priority":
                        int(row.Priority),

                    "amount":
                        Decimal(
                            str(row.Amount)
                        ),

                    "pricing_status":
                        str(row.PricingStatus),

                    "source_size_value":
                        row.SourceSizeValue,

                    "source_option_value":
                        row.SourceOptionValue,

                    "source_price_value":
                        row.SourcePriceValue,

                    "source_worksheet":
                        row.SourceWorksheet,

                    "source_table":
                        row.SourceTable,

                    "source_cell":
                        row.SourceCell,

                    "conditions": [],
                }

            if (
                row.PriceConditionId
                is not None
            ):
                grouped[
                    rule_id
                ][
                    "conditions"
                ].append(
                    PricingCondition(
                        sequence_no=int(
                            row.SequenceNo
                        ),
                        field_code=str(
                            row.FieldCode
                        ),
                        comparison_operator=str(
                            row.ComparisonOperator
                        ),
                        comparison_value=(
                            None
                            if row.ComparisonValue
                            is None
                            else str(
                                row.ComparisonValue
                            )
                        ),
                    )
                )

        result: list[
            PricingRule
        ] = []

        for state in grouped.values():
            conditions = tuple(
                sorted(
                    state.pop(
                        "conditions"
                    ),
                    key=lambda x:
                        x.sequence_no,
                )
            )

            result.append(
                PricingRule(
                    **state,
                    conditions=conditions,
                )
            )

        return tuple(result)
