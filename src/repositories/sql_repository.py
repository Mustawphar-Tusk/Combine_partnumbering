import json
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Engine, text

from src.models.configured_product import ConfiguredProductRequest

@dataclass(frozen=True)
class SqlStoredProduct:
    part_number: str
    sku: str

@dataclass(frozen=True)
class SqlPriceMatch:
    unit_price: Decimal

class SqlConfigurationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _selection_json(request: ConfiguredProductRequest) -> str:
        rows = [
            {
                "sequence": item.sequence,
                "fieldCode": item.field_code,
                "optionCode": item.option_code,
                "hexCode": item.hex_code,
            }
            for item in sorted(request.selections, key=lambda row: row.sequence)
        ]
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

    def validate(self, request: ConfiguredProductRequest) -> list[str]:
        with self.engine.connect() as connection:
            found = connection.execute(
                text(
                    '''
                    SELECT TOP (1) 1
                    FROM cfg.PumpFamily pf
                    INNER JOIN cfg.ConfigurationVersion cv
                        ON cv.PumpFamilyId = pf.PumpFamilyId
                    WHERE pf.FamilyCode = :family_code
                      AND pf.IsActive = 1
                      AND cv.IsCurrent = 1
                      AND cv.Status = 'Published'
                    '''
                ),
                {"family_code": request.pump_family_code},
            ).scalar_one_or_none()

        if found is None:
            return ["No active family and published configuration version were found."]

        return []

    def find_price(self, request: ConfiguredProductRequest) -> SqlPriceMatch | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    EXEC price.usp_GetConfigurationPrice
                        @FamilyCode = :family_code,
                        @ConfigurationJson = :configuration_json,
                        @EffectiveDate = NULL
                    '''
                ),
                {
                    "family_code": request.pump_family_code,
                    "configuration_json": self._selection_json(request),
                },
            ).mappings().one()

        if row["PricingStatus"] == "not_found":
            return None

        return SqlPriceMatch(unit_price=Decimal(row["UnitPrice"]))

    def find_product(self, signature: str) -> SqlStoredProduct | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    '''
                    SELECT TOP (1) PartNumber, SKUCode
                    FROM cfg.ConfiguredProduct
                    WHERE ConfigurationSignature = :signature
                    '''
                ),
                {"signature": signature},
            ).mappings().one_or_none()

        if row is None:
            return None

        return SqlStoredProduct(
            part_number=row["PartNumber"],
            sku=row["SKUCode"],
        )

    def create_product(
        self,
        request: ConfiguredProductRequest,
        canonical_json: str,
        signature: str,
    ) -> SqlStoredProduct:
        part_number = f"{request.pump_family_code.upper()}-{signature[:16].upper()}"
        sku = f"SKU-{signature[:16].upper()}"

        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    '''
                    EXEC cfg.usp_GetOrCreateConfiguredProduct
                        @FamilyCode = :family_code,
                        @SeriesCode = :series_code,
                        @ConfigurationJson = :configuration_json,
                        @ConfigurationSignature = :signature,
                        @PartNumber = :part_number,
                        @SKUCode = :sku,
                        @RequestedBy = :requested_by
                    '''
                ),
                {
                    "family_code": request.pump_family_code,
                    "series_code": request.series_code,
                    "configuration_json": self._selection_json(request),
                    "signature": signature,
                    "part_number": part_number,
                    "sku": sku,
                    "requested_by": request.requested_by,
                },
            ).mappings().one()

        return SqlStoredProduct(
            part_number=row["PartNumber"],
            sku=row["SKUCode"],
        )
