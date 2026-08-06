from pathlib import Path
from src.compiler.manifest_loader import load_all_manifests
from src.compiler.workbook_discovery import discover_all, save_report

project_root = Path.cwd()
manifests = load_all_manifests(project_root / "config" / "workbook_manifests")
report = discover_all(project_root, manifests)
output = project_root / "exports" / "workbook_discovery.json"
save_report(report, output)

print(f"Families discovered: {report.family_count}")
print(f"Workbooks discovered: {report.workbook_count}")
print(f"Report written to: {output}")

errors = [r for r in report.records if r.discovery_status in {"missing", "error"}]
for r in report.records:
    print(f"[{r.discovery_status.upper()}] {r.family_code} | {r.role} | {r.file_name or '<missing>'}")

if errors:
    raise SystemExit(f"Discovery completed with {len(errors)} error/missing record(s).")
