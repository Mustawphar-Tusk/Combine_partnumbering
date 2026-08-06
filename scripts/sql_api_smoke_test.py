from __future__ import annotations

import json
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"


def get_json(path: str) -> dict:
    with urlopen(f"{BASE_URL}{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


health = get_json("/health")
print("HEALTH")
print(json.dumps(health, indent=2))

payload = {
    "pump_family_code": "DEAN",
    "series_code": None,
    "currency_code": "USD",
    "quantity": 2,
    "requested_by": "SQL smoke test",
    "selections": [
        {
            "sequence": 1,
            "field_code": "SERIES",
            "option_code": "DEMO",
            "hex_code": "01"
        }
    ]
}

first = post_json("/api/v1/configured-products/get-or-create", payload)
second = post_json("/api/v1/configured-products/get-or-create", payload)

print("FIRST REQUEST")
print(json.dumps(first, indent=2))
print("SECOND REQUEST")
print(json.dumps(second, indent=2))

assert first["valid"] is True
assert first["price"]["unit_price"] == "0"
assert first["price"]["status"] == "not_found"
assert first["existing_configuration"] is False

assert second["valid"] is True
assert second["existing_configuration"] is True
assert second["part_number"] == first["part_number"]
assert second["sku"] == first["sku"]

print("SQL API smoke test passed.")
