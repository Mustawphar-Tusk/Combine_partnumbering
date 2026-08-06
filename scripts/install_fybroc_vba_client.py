from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
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


DEFAULT_WORKBOOK = Path(
    r"output\M020\Price Estimator-Fybroc_API.xlsm"
)
DEFAULT_MODULE = Path(
    r"vba\FybrocApiClient.bas"
)

UI_SHEET = "API Configurator"
STATE_SHEET = "_API_Config"
MODULE_NAME = "FybrocApiClient"

MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3
XL_SHEET_VERY_HIDDEN = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install the closed Fybroc VBA API client into "
            "the non-destructive M020 workbook copy."
        )
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=DEFAULT_WORKBOOK,
    )
    parser.add_argument(
        "--module",
        type=Path,
        default=DEFAULT_MODULE,
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
    )
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def get_or_create_sheet(workbook: Any, name: str) -> Any:
    try:
        return workbook.Worksheets(name)
    except Exception:
        worksheet = workbook.Worksheets.Add(
            After=workbook.Worksheets(workbook.Worksheets.Count)
        )
        worksheet.Name = name
        return worksheet


def remove_existing_module(vbproject: Any, module_name: str) -> None:
    for index in range(vbproject.VBComponents.Count, 0, -1):
        component = vbproject.VBComponents.Item(index)
        if component.Name.lower() == module_name.lower():
            vbproject.VBComponents.Remove(component)


def add_button(
    worksheet: Any,
    *,
    name: str,
    caption: str,
    macro_name: str,
    left: float,
    top: float,
    width: float = 145,
    height: float = 30,
) -> None:
    try:
        worksheet.Buttons(name).Delete()
    except Exception:
        pass

    button = worksheet.Buttons().Add(left, top, width, height)
    button.Name = name
    button.Caption = caption
    button.OnAction = macro_name


def format_ui(worksheet: Any) -> None:
    worksheet.Cells.Clear()

    worksheet.Range("A1").Value = "FYBROC CLOSED CONFIGURATION"
    worksheet.Range("A1:E1").Merge()
    worksheet.Range("A1").Font.Bold = True
    worksheet.Range("A1").Font.Size = 16

    labels = {
        "A3": "API Base URL",
        "A4": "Family",
        "A6": "Current Field",
        "A7": "Selection Count",
        "A8": "Status",
        "A10": "Allowable Option",
        "A12": "Part Number",
        "A13": "SKU",
        "A14": "Registry ID",
        "A17": "Workflow",
        "A18": "1. Start a configuration.",
        "A19": "2. Choose only from the API-projected dropdown.",
        "A20": "3. Advance until the state is complete.",
        "A21": "4. Finalize to generate/reuse the Part Number and SKU.",
    }

    for coordinate, value in labels.items():
        worksheet.Range(coordinate).Value = value

    worksheet.Range("B3").Value = "http://127.0.0.1:8000"
    worksheet.Range("B4").Value = "FYBROC"
    worksheet.Range("B7").Value = 0
    worksheet.Range("B8").Value = "Ready"

    worksheet.Range("A3:A14").Font.Bold = True
    worksheet.Range("A17").Font.Bold = True
    worksheet.Range("B3:B14").Interior.ColorIndex = 36
    worksheet.Range("B10").Interior.ColorIndex = 35
    worksheet.Range("B12:B14").Interior.ColorIndex = 34

    worksheet.Columns("A").ColumnWidth = 25
    worksheet.Columns("B").ColumnWidth = 58
    worksheet.Columns("C").ColumnWidth = 3
    worksheet.Columns("D").ColumnWidth = 22
    worksheet.Columns("E").ColumnWidth = 22
    worksheet.Columns("H:I").Hidden = True

    worksheet.Range("A1:E21").VerticalAlignment = -4108
    worksheet.Range("A1:E21").WrapText = True

    add_button(
        worksheet,
        name="btnFybStart",
        caption="Start Configuration",
        macro_name="Fybroc_StartConfiguration",
        left=worksheet.Range("D3").Left,
        top=worksheet.Range("D3").Top,
    )
    add_button(
        worksheet,
        name="btnFybAdvance",
        caption="Advance Selection",
        macro_name="Fybroc_AdvanceConfiguration",
        left=worksheet.Range("D5").Left,
        top=worksheet.Range("D5").Top,
    )
    add_button(
        worksheet,
        name="btnFybFinalize",
        caption="Finalize Part / SKU",
        macro_name="Fybroc_FinalizeConfiguration",
        left=worksheet.Range("D7").Left,
        top=worksheet.Range("D7").Top,
    )
    add_button(
        worksheet,
        name="btnFybClear",
        caption="Clear API Result",
        macro_name="Fybroc_ClearApiResult",
        left=worksheet.Range("D9").Left,
        top=worksheet.Range("D9").Top,
    )

    worksheet.Activate()
    worksheet.Range("B3").Select()


def main() -> int:
    args = parse_args()
    workbook_path = resolve(args.workbook)
    module_path = resolve(args.module)

    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Workbook not found: {workbook_path}"
        )

    if not module_path.exists():
        raise FileNotFoundError(
            f"VBA module not found: {module_path}"
        )

    if not args.no_backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = workbook_path.with_name(
            f"{workbook_path.stem}_before_vba_{timestamp}{workbook_path.suffix}"
        )
        shutil.copy2(workbook_path, backup)
        print(f"Backup: {backup}")

    pythoncom.CoInitialize()
    excel = None
    workbook = None

    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False
        excel.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE

        workbook = excel.Workbooks.Open(
            str(workbook_path),
            UpdateLinks=0,
            ReadOnly=False,
            IgnoreReadOnlyRecommended=True,
        )

        ui_sheet = get_or_create_sheet(workbook, UI_SHEET)
        state_sheet = get_or_create_sheet(workbook, STATE_SHEET)

        state_sheet.Visible = -1

        try:
            vbproject = workbook.VBProject
            _ = vbproject.VBComponents.Count
        except Exception as exc:
            raise RuntimeError(
                "Excel blocked programmatic VBA access. In Excel, open "
                "File > Options > Trust Center > Trust Center Settings > "
                "Macro Settings, enable 'Trust access to the VBA project "
                "object model', close Excel, and rerun the installer."
            ) from exc

        remove_existing_module(vbproject, MODULE_NAME)
        imported_component = vbproject.VBComponents.Import(str(module_path))

        if imported_component.Name.lower() != MODULE_NAME.lower():
            imported_component.Name = MODULE_NAME

        format_ui(ui_sheet)

        state_sheet.Visible = XL_SHEET_VERY_HIDDEN
        workbook.Save()

        print()
        print("=" * 88)
        print("M020.4 FYBROC VBA API CLIENT INSTALLED")
        print("=" * 88)
        print(f"Workbook: {workbook_path}")
        print(f"VBA module: {MODULE_NAME}")
        print(f"UI sheet: {UI_SHEET}")
        print(f"State sheet: {STATE_SHEET} (VeryHidden)")
        print("Buttons: Start, Advance, Finalize, Clear")
        print()
        print("The workbook now submits only signed state and option tokens.")
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
