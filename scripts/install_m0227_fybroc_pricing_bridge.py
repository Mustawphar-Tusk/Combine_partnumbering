from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pythoncom
import win32com.client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = PROJECT_ROOT / "output" / "M020" / "Price Estimator-Fybroc_API.xlsm"
VBA_PATH = PROJECT_ROOT / "vba" / "FybrocApiClient.bas"
BACKUP_DIR = PROJECT_ROOT / "backups" / "M0227"

API_FIELDS = (
    ("API_PricingStatus", "A12", "B12", "Pricing Status"),
    ("API_TotalAmount", "A13", "B13", "Total Amount"),
    ("API_KnownAmount", "A14", "B14", "Known Amount"),
    ("API_CurrencyCode", "A15", "B15", "Currency Code"),
    ("API_BasePumpAmount", "A16", "B16", "Base Pump Amount"),
    ("API_SealAmount", "A17", "B17", "Seal Amount"),
)


def add_or_replace_name(workbook, name: str, refers_to: str) -> None:
    try:
        workbook.Names(name).Delete()
    except Exception:
        pass
    workbook.Names.Add(Name=name, RefersTo=refers_to, Visible=False)


def replace_vba_module(workbook, module_path: Path) -> None:
    project = workbook.VBProject
    existing = None
    for component in project.VBComponents:
        if component.Name == "FybrocApiClient":
            existing = component
            break
    if existing is not None:
        project.VBComponents.Remove(existing)
    imported = project.VBComponents.Import(str(module_path.resolve()))
    if imported.Name != "FybrocApiClient":
        imported.Name = "FybrocApiClient"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    args = parser.parse_args()
    workbook_path = args.workbook.resolve()

    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")
    if not VBA_PATH.exists():
        raise FileNotFoundError(f"VBA source not found: {VBA_PATH}")

    vba_text = VBA_PATH.read_text(encoding="utf-8", errors="replace")
    if "M022.7 - Fybroc API component pricing bridge." not in vba_text:
        raise RuntimeError(
            "FybrocApiClient.bas is not patched for M022.7. "
            "Run scripts/apply_m0227_excel_pricing_patch.py first."
        )

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{workbook_path.stem}_before_m0227_{stamp}{workbook_path.suffix}"
    shutil.copy2(workbook_path, backup_path)

    pythoncom.CoInitialize()
    excel = None
    workbook = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False

        workbook = excel.Workbooks.Open(str(workbook_path), UpdateLinks=0, ReadOnly=False)

        try:
            bridge_sheet = workbook.Worksheets("_API_Config")
        except Exception as exc:
            raise RuntimeError(
                "The workbook does not contain _API_Config. "
                "Run the M020 Excel API bridge preparation first."
            ) from exc

        price_sheet = workbook.Worksheets("Price Check")
        d80_formula = str(price_sheet.Range("D80").Formula)
        d81_formula = str(price_sheet.Range("D81").Formula)

        if 'IF(Q80<>"", Q80' not in d80_formula:
            raise RuntimeError("Price Check!D80 no longer exposes the expected Q80 override.")
        if 'IF(Q81<>"", Q81' not in d81_formula:
            raise RuntimeError("Price Check!D81 no longer exposes the expected Q81 override.")

        for name, label_cell, value_cell, label in API_FIELDS:
            bridge_sheet.Range(label_cell).Value = label
            add_or_replace_name(
                workbook,
                name,
                f"='_API_Config'!${value_cell[0]}${value_cell[1:]}",
            )

        if bridge_sheet.Range("B20").Value in (None, ""):
            raise RuntimeError(
                "_API_Config!B20 does not contain the preserved original Price Check!F5 formula."
            )

        replace_vba_module(workbook, VBA_PATH)
        workbook.Save()

        print("=" * 88)
        print("M022.7 FYBROC EXCEL PRICING BRIDGE INSTALLED")
        print("=" * 88)
        print(f"Workbook : {workbook_path}")
        print(f"Backup   : {backup_path}")
        print("Writeback: BASE_PUMP -> Price Check!Q80")
        print("Writeback: SEAL      -> Price Check!Q81")
        print("Preserved: D/F subtotals and Formal Quote formulas")
        return 0
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.EnableEvents = True
            except Exception:
                pass
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    sys.exit(main())
