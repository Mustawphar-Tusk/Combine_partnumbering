import hashlib
import json

from src.models.configured_product import ConfiguredProductRequest

def canonicalize(request: ConfiguredProductRequest) -> str:
    payload = {
        "pumpFamilyCode": request.pump_family_code.upper(),
        "seriesCode": request.series_code,
        "selections": [
            {
                "sequence": item.sequence,
                "fieldCode": item.field_code.upper(),
                "optionCode": item.option_code.upper(),
                "hexCode": item.hex_code,
            }
            for item in sorted(request.selections, key=lambda row: row.sequence)
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

def create_signature(canonical_json: str) -> str:
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
