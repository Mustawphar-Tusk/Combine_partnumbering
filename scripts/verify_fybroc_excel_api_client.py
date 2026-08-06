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

REQUIRED_NAMES = (
    "API_PartNumber",
    "API_SKU",
    "API_ConfigurationSignature",
    "API_ConfiguredProductRegistryId",
    "API_StateToken",
    "API_Status",
)

REQUIRED_PROCEDURES = (
    "Fybroc_StartConfiguration",
    "Fybroc_AdvanceConfiguration",
    "Fybroc_FinalizeConfiguration",
    "Fybroc_ClearApiResult",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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

        for required_sheet in ("API Configurator", "_API_Config", "Price Check"):
            if required_sheet not in sheet_names:
                problems.append(f"Missing worksheet: {required_sheet}")

        workbook_names = {
            workbook.Names(index).Name.split("!")[-1]
            for index in range(1, workbook.Names.Count + 1)
        }

        for required_name in REQUIRED_NAMES:
            if required_name not in workbook_names:
                problems.append(f"Missing workbook name: {required_name}")

        formula = str(workbook.Worksheets("Price Check").Range("F5").Formula)
        if "API_PartNumber" not in formula:
            problems.append("Price Check!F5 does not contain the API override.")

        try:
            component = workbook.VBProject.VBComponents("FybrocApiClient")
            code = component.CodeModule.Lines(
                1,
                component.CodeModule.CountOfLines,
            )

            for procedure in REQUIRED_PROCEDURES:
                if f"Sub {procedure}" not in code:
                    problems.append(f"Missing VBA procedure: {procedure}")
        except Exception:
            problems.append(
                "Could not inspect the FybrocApiClient VBA module. "
                "Confirm Trust access to the VBA project object model is enabled."
            )

        if problems:
            print("M020.4 verification failed:")
            for problem in problems:
                print(f"  - {problem}")
            return 1

        print("=" * 88)
        print("M020.4 FYBROC EXCEL API CLIENT VERIFIED")
        print("=" * 88)
        print(f"Workbook: {workbook_path}")
        print("Required sheets: present")
        print("Required names: present")
        print("Price Check!F5 API override: present")
        print("VBA client procedures: present")
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
