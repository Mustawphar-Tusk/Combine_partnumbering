# M020.4 — Fybroc Excel Closed API Client

This patch installs a closed, signed-token VBA client into:

`output\M020\Price Estimator-Fybroc_API.xlsm`

The authoritative source workbook remains unchanged.

## Security model

The workbook never sends arbitrary engineering field/value pairs. It calls the
API using only:

- the signed `stateToken`;
- the signed `optionToken`;
- the completed signed state during finalization.

`CONFIGURATION_TOKEN_SECRET` remains server-side.

## Merge

Extract the package into the project root so these folders merge:

- `vba`
- `scripts`
- `docs`

## Install

Close every Excel window first.

```powershell
python -m pip install pywin32
python -m scripts.install_fybroc_vba_client
python -m scripts.verify_fybroc_excel_api_client
```

If Excel blocks VBA injection, enable:

`File > Options > Trust Center > Trust Center Settings > Macro Settings >
Trust access to the VBA project object model`

Close Excel and rerun the installer.

## Run

Start the local API:

```powershell
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Open:

`output\M020\Price Estimator-Fybroc_API.xlsm`

Enable macros, then use the `API Configurator` sheet:

1. Start Configuration
2. Select an allowable value from the dropdown
3. Advance Selection
4. Repeat until complete
5. Finalize Part / SKU

After finalization:

- `API_PartNumber` is written to the hidden integration state;
- `Price Check!F5` displays that part number through the installed override;
- the SKU and persistence metadata are retained;
- repeated finalization reuses the same configured-product registry record.

The VBA client calculates only `Price Check!F5`; it does not run a full
workbook calculation rebuild.
