from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pythoncom
    import win32com.client
except ImportError as exc:
    raise RuntimeError(
        "pywin32 is required. Install it with: "
        "python -m pip install pywin32"
    ) from exc


DEFAULT_WORKBOOK = Path(
    r"output\M020\Price Estimator-Fybroc_API.xlsm"
)

REQUIRED_SHEETS = (
    "API Configurator",
    "_API_Config",
    "Price Check",
)

M020_REQUIRED_NAMES = (
    "API_PartNumber",
    "API_SKU",
    "API_ConfigurationSignature",
    "API_ConfiguredProductRegistryId",
    "API_StateToken",
    "API_Status",
)

M0227_REQUIRED_NAMES = (
    "API_PricingStatus",
    "API_TotalAmount",
    "API_KnownAmount",
    "API_CurrencyCode",
    "API_BasePumpAmount",
    "API_SealAmount",
)

REQUIRED_VBA_PROCEDURES = (
    "Fybroc_StartConfiguration",
    "Fybroc_AdvanceConfiguration",
    "Fybroc_FinalizeConfiguration",
    "Fybroc_ClearApiResult",
    "WritePricingResponse",
    "ClearApiPricingBridge",
    "CalculateApiBridge",
)

REQUIRED_VBA_SNIPPETS = (
    'WriteNamedValue "API_TotalAmount"',
    'WriteNamedValue "API_BasePumpAmount"',
    'WriteNamedValue "API_SealAmount"',
    'priceSheet.Range("Q80").Value2 = amountValue',
    'priceSheet.Range("Q81").Value2 = amountValue',
    '.Range("Q80:Q81").ClearContents',
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only verification of the installed "
            "M022.7 Fybroc pricing bridge."
        )
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_WORKBOOK,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workbook_path = args.workbook.expanduser().resolve()

    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)

    pythoncom.CoInitialize()
    excel = None
    workbook = None

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False
        excel.AutomationSecurity = 3

        workbook = excel.Workbooks.Open(
            str(workbook_path),
            UpdateLinks=0,
            ReadOnly=True,
            IgnoreReadOnlyRecommended=True,
        )

        problems: list[str] = []

        sheet_names = {
            workbook.Worksheets(index).Name
            for index in range(1, workbook.Worksheets.Count + 1)
        }

        for sheet_name in REQUIRED_SHEETS:
            if sheet_name not in sheet_names:
                problems.append(f"Missing worksheet: {sheet_name}")

        workbook_names = {
            workbook.Names(index).Name.split("!")[-1]
            for index in range(1, workbook.Names.Count + 1)
        }

        for required_name in M020_REQUIRED_NAMES + M0227_REQUIRED_NAMES:
            if required_name not in workbook_names:
                problems.append(
                    f"Missing workbook name: {required_name}"
                )

        price_sheet = workbook.Worksheets("Price Check")

        f5_formula = str(price_sheet.Range("F5").Formula)
        d80_formula = str(price_sheet.Range("D80").Formula)
        d81_formula = str(price_sheet.Range("D81").Formula)

        if "API_PartNumber" not in f5_formula:
            problems.append(
                "Price Check!F5 does not contain the API part-number override."
            )

        if 'IF(Q80<>"", Q80' not in d80_formula:
            problems.append(
                "Price Check!D80 no longer exposes the expected Q80 override."
            )

        if 'IF(Q81<>"", Q81' not in d81_formula:
            problems.append(
                "Price Check!D81 no longer exposes the expected Q81 override."
            )

        try:
            api_config = workbook.Worksheets("_API_Config")
            if api_config.Range("B20").Value in (None, ""):
                problems.append(
                    "_API_Config!B20 does not contain the preserved original "
                    "Price Check!F5 formula."
                )
        except Exception as exc:
            problems.append(
                f"Could not inspect _API_Config!B20: {exc}"
            )

        try:
            component = workbook.VBProject.VBComponents("FybrocApiClient")
            code_module = component.CodeModule
            code = code_module.Lines(
                1,
                code_module.CountOfLines,
            )

            for procedure in REQUIRED_VBA_PROCEDURES:
                if (
                    f"Sub {procedure}" not in code
                    and f"Function {procedure}" not in code
                ):
                    problems.append(
                        f"Missing VBA procedure: {procedure}"
                    )

            for snippet in REQUIRED_VBA_SNIPPETS:
                if snippet not in code:
                    problems.append(
                        f"Missing VBA pricing bridge snippet: {snippet}"
                    )

        except Exception:
            problems.append(
                "Could not inspect the FybrocApiClient VBA module. "
                "Confirm Trust access to the VBA project object model is enabled."
            )

        if problems:
            print("M022.7 read-only verification FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        print("=" * 88)
        print("M022.7 FYBROC EXCEL PRICING BRIDGE VERIFIED")
        print("=" * 88)
        print(f"Workbook: {workbook_path}")
        print("Required M020 sheets/names          : present")
        print("M022.7 pricing named ranges         : present")
        print("Price Check!F5 API override         : present")
        print("Price Check!D80 -> Q80 override      : present")
        print("Price Check!D81 -> Q81 override      : present")
        print("_API_Config!B20 preserved F5 formula : present")
        print("FybrocApiClient M022.7 procedures    : present")
        print("BASE_PUMP -> Q80 VBA writeback       : present")
        print("SEAL -> Q81 VBA writeback            : present")
        print("Q80:Q81 stale-price clearing         : present")
        print()
        print("READ-ONLY VERIFICATION PASSED")
        return 0

    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                pass

        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass

        pythoncom.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
