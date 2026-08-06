from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pythoncom
    import win32com.client
except ImportError as exc:
    raise RuntimeError(
        "pywin32 is required. Install it with: "
        "python -m pip install pywin32"
    ) from exc


SOURCE_WORKBOOK = Path(
    r"workbooks\Fybroc\Price Estimator-Fybroc.xlsm"
)

OUTPUT_WORKBOOK = Path(
    r"output\M020\Price Estimator-Fybroc_API.xlsm"
)

STATE_SHEET = "_API_Config"

XL_SHEET_VERY_HIDDEN = 2
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3


NAME_MAPPINGS = {
    "API_PartNumber": "$B$2",
    "API_SKU": "$B$3",
    "API_ConfigurationSignature": "$B$4",
    "API_ConfiguredProductRegistryId": "$B$5",
    "API_WasCreated": "$B$6",
    "API_RequestCount": "$B$7",
    "API_RuntimeRevision": "$B$8",
    "API_StateToken": "$B$9",
    "API_Status": "$B$10",
    "API_LastUpdatedUtc": "$B$11",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or update the Fybroc Excel API bridge "
            "without modifying the authoritative source workbook."
        )
    )

    parser.add_argument(
        "--source",
        type=Path,
        default=SOURCE_WORKBOOK,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_WORKBOOK,
    )

    parser.add_argument(
        "--reset-from-source",
        action="store_true",
        help=(
            "Overwrite the output workbook with a fresh "
            "copy of the source before installing the bridge."
        ),
    )

    parser.add_argument(
        "--part-number",
        default="",
    )

    parser.add_argument(
        "--sku",
        default="",
    )

    parser.add_argument(
        "--signature",
        default="",
    )

    parser.add_argument(
        "--registry-id",
        default="",
    )

    parser.add_argument(
        "--was-created",
        default="",
    )

    parser.add_argument(
        "--request-count",
        default="",
    )

    parser.add_argument(
        "--runtime-revision",
        default="",
    )

    parser.add_argument(
        "--state-token",
        default="",
    )

    parser.add_argument(
        "--status",
        default="ready",
    )

    return parser.parse_args()


def normalize_path(path: Path) -> Path:
    return path.expanduser().resolve()


def get_or_create_sheet(
    workbook: Any,
    sheet_name: str,
) -> Any:
    try:
        worksheet = workbook.Worksheets(sheet_name)
    except Exception:
        worksheet = workbook.Worksheets.Add(
            After=workbook.Worksheets(
                workbook.Worksheets.Count
            )
        )
        worksheet.Name = sheet_name

    return worksheet


def replace_workbook_name(
    workbook: Any,
    *,
    name: str,
    refers_to: str,
) -> None:
    try:
        workbook.Names.Item(name).Delete()
    except Exception:
        pass

    workbook.Names.Add(
        Name=name,
        RefersTo=refers_to,
        Visible=False,
    )


def set_text(
    worksheet: Any,
    coordinate: str,
    value: str,
) -> None:
    cell = worksheet.Range(coordinate)
    cell.NumberFormat = "@"
    cell.Value = value


def main() -> int:
    args = parse_arguments()

    source = normalize_path(args.source)
    output = normalize_path(args.output)

    if not source.exists():
        raise FileNotFoundError(
            f"Source workbook not found: {source}"
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if args.reset_from_source or not output.exists():
        shutil.copy2(source, output)
        print(f"Copied source workbook to: {output}")
    else:
        print(f"Updating existing workbook: {output}")

    pythoncom.CoInitialize()

    excel = None
    workbook = None

    try:
        excel = win32com.client.DispatchEx(
            "Excel.Application"
        )

        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False
        excel.AutomationSecurity = (
            MSO_AUTOMATION_SECURITY_FORCE_DISABLE
        )

        workbook = excel.Workbooks.Open(
            str(output),
            UpdateLinks=0,
            ReadOnly=False,
            IgnoreReadOnlyRecommended=True,
        )

        state_sheet = get_or_create_sheet(
            workbook,
            STATE_SHEET,
        )

        state_sheet.Visible = -1

        state_sheet.Range("A1").Value = (
            "Pump Configurator API Integration"
        )
        state_sheet.Range("A2").Value = "Part Number"
        state_sheet.Range("A3").Value = "SKU"
        state_sheet.Range("A4").Value = (
            "Configuration Signature"
        )
        state_sheet.Range("A5").Value = (
            "Configured Product Registry ID"
        )
        state_sheet.Range("A6").Value = "Was Created"
        state_sheet.Range("A7").Value = "Request Count"
        state_sheet.Range("A8").Value = (
            "Runtime Revision"
        )
        state_sheet.Range("A9").Value = "State Token"
        state_sheet.Range("A10").Value = "Status"
        state_sheet.Range("A11").Value = (
            "Last Updated UTC"
        )
        state_sheet.Range("A20").Value = (
            "Original Price Check F5 Formula"
        )

        state_sheet.Range("B2").Value = (
            args.part_number
        )
        state_sheet.Range("B3").Value = args.sku
        state_sheet.Range("B4").Value = (
            args.signature
        )
        state_sheet.Range("B5").Value = (
            args.registry_id
        )
        state_sheet.Range("B6").Value = (
            args.was_created
        )
        state_sheet.Range("B7").Value = (
            args.request_count
        )
        state_sheet.Range("B8").Value = (
            args.runtime_revision
        )
        set_text(
            state_sheet,
            "B9",
            args.state_token,
        )
        state_sheet.Range("B10").Value = (
            args.status
        )
        state_sheet.Range("B11").Value = (
            datetime.now(timezone.utc).isoformat()
        )

        state_sheet.Columns("A").ColumnWidth = 36
        state_sheet.Columns("B").ColumnWidth = 90

        for name, cell_reference in NAME_MAPPINGS.items():
            replace_workbook_name(
                workbook,
                name=name,
                refers_to=(
                    f"='{STATE_SHEET}'!"
                    f"{cell_reference}"
                ),
            )

        price_check = workbook.Worksheets(
            "Price Check"
        )

        pump_part_cell = price_check.Range("F5")
        current_formula = str(
            pump_part_cell.Formula
        )

        existing_original_formula = str(
            state_sheet.Range("B20").Value or ""
        )

        api_wrapper_prefix = (
            '=IF(API_PartNumber<>"",'
            "API_PartNumber,"
        )

        if current_formula.startswith(
            api_wrapper_prefix
        ):
            if not existing_original_formula:
                raise RuntimeError(
                    "Price Check!F5 already contains "
                    "the API wrapper, but the preserved "
                    "original formula is missing."
                )

            original_formula = (
                existing_original_formula
            )
        else:
            original_formula = current_formula

            if not original_formula.startswith("="):
                raise RuntimeError(
                    "Price Check!F5 does not contain "
                    "the expected Excel formula."
                )

            set_text(
                state_sheet,
                "B20",
                original_formula,
            )

        wrapped_formula = (
            api_wrapper_prefix
            + original_formula[1:]
            + ")"
        )

        pump_part_cell.Formula = wrapped_formula

        pump_part_cell.Calculate()

        state_sheet.Visible = (
            XL_SHEET_VERY_HIDDEN
        )

        workbook.Save()

        print()
        print("=" * 90)
        print("M020 FYBROC EXCEL API BRIDGE INSTALLED")
        print("=" * 90)
        print(f"Workbook: {output}")
        print(f"State sheet: {STATE_SHEET}")
        print(
            "State sheet visibility: VeryHidden"
        )
        print(
            "Price Check!F5 formula:"
        )
        print(f"  {pump_part_cell.Formula}")
        print(
            "API Part Number:"
            f" {state_sheet.Range('B2').Value}"
        )
        print(
            "API SKU:"
            f" {state_sheet.Range('B3').Value}"
        )
        print()
        print(
            "The authoritative source workbook "
            "was not modified."
        )

        return 0

    finally:
        if workbook is not None:
            try:
                workbook.Close(
                    SaveChanges=False
                )
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
