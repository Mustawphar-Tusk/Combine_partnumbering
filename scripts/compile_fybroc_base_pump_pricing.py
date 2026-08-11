from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

# Make repository-root packages such as "src" importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from src.compiler.pricing_metadata_compiler import (
    compile_base_pump_pricing,
    save_report,
)


workbook = (
    ROOT
    / "workbooks"
    / "Fybroc"
    / "Price Estimator-Fybroc.xlsm"
)

profile = (
    ROOT
    / "config"
    / "pricing_profiles"
    / "fybroc_base_pump.json"
)

output = (
    ROOT
    / "exports"
    / "fybroc_base_pump_pricing.json"
)


report = compile_base_pump_pricing(
    workbook,
    profile,
)

save_report(
    report,
    output,
)


print("=" * 80)
print("M021.1 FYBROC BASE PUMP PRICING COMPILER")
print("=" * 80)
print(f"Candidates : {report.candidate_count}")
print(f"Issues     : {report.issue_count}")
print(f"Output     : {output}")

for issue in report.issues:
    print(
        f"{issue.severity}: "
        f"{issue.issue_code}: "
        f"{issue.message}"
    )
