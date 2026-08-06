from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.metadata_extractor import extract_from_discovery, save_csv_exports, save_metadata_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract workbook metadata using streaming XML.")
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args()

    discovery = PROJECT_ROOT / "exports" / "workbook_discovery.json"
    if not discovery.exists():
        raise SystemExit("Run `python -m scripts.discover_workbooks` first.")

    report = extract_from_discovery(PROJECT_ROOT, discovery, args.sample_limit)
    output = PROJECT_ROOT / "exports" / "workbook_metadata.json"
    save_metadata_report(report, output)
    save_csv_exports(report, PROJECT_ROOT / "exports")

    print(f"Workbooks processed: {report.workbook_count}")
    print(f"Worksheets processed: {report.worksheet_count}")
    print(f"Defined names found: {report.defined_name_count}")
    print(f"JSON report: {output}")

    warnings = [m for w in report.workbooks for m in w.extraction_messages]
    if warnings:
        print(f"Warnings: {len(warnings)}")
        for message in warnings[:20]:
            print(f"  - {message}")


if __name__ == "__main__":
    main()
