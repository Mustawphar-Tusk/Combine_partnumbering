# M022.7 — Fybroc Excel Component Pricing Bridge

## Approved writeback

- `BASE_PUMP` → `Price Check!Q80`
- `SEAL` → `Price Check!Q81`

The existing workbook chain remains intact:

`Q80/Q81 → D80/D81 (List Each) → F80/F81 (Net Each) → D102/F102 → Formal Quote`

M022.7 does not overwrite `D80`, `D81`, `D102`, `F102`, or Formal Quote formulas.

## Audit names

The `_API_Config` worksheet receives:

- `API_PricingStatus`
- `API_TotalAmount`
- `API_KnownAmount`
- `API_CurrencyCode`
- `API_BasePumpAmount`
- `API_SealAmount`

## Fail-closed behavior

During API finalization, Q80/Q81 are initialized to numeric zero. A component
with status `found` replaces zero with the API amount. Missing/non-found
components therefore cannot fall back to a stale legacy workbook price.

Starting a new API configuration or clearing the API result clears the API
pricing values and Q80/Q81.

## Installation

Keep Excel closed and run:

```powershell
python .\scripts\apply_m0227_excel_pricing_patch.py
python -m pytest .\tests\test_m0227_excel_pricing_bridge_source.py -q
python .\scripts\install_m0227_fybroc_pricing_bridge.py
python .\scripts\verify_m0227_fybroc_pricing_bridge.py
python -m pytest -q
```

The patch and installer create backups under `backups\M0227\`.

## Live proof

For the existing M022.6 proof path, expected API component amounts are:

- BASE_PUMP = 4854
- SEAL = 749
- totalAmount = 5603

After Finalize, verify Q80=4854 and Q81=749. D80/D81 should equal those list
amounts, while F80/F81 remain controlled by the workbook's existing discount
formulas.
