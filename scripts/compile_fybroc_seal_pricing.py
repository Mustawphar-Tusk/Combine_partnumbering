from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.compiler.fybroc_seal_pricing_compiler import (
    compile_fybroc_seal_pricing,
)
from src.compiler.pricing_metadata_compiler import (
    save_report,
)


price_workbook = (
    ROOT
    / "workbooks"
    / "Fybroc"
    / "Price Estimator-Fybroc.xlsm"
)

nomenclature_workbook = (
    ROOT
    / "workbooks"
    / "Fybroc"
    / "Fybroc Nomenclature_V5.xlsm"
)

base_pump_compilation = (
    ROOT
    / "exports"
    / "fybroc_base_pump_pricing.json"
)

profile = (
    ROOT
    / "config"
    / "pricing_profiles"
    / "fybroc_seal.json"
)

output = (
    ROOT
    / "exports"
    / "fybroc_seal_pricing.json"
)


report = compile_fybroc_seal_pricing(
    price_workbook,
    nomenclature_workbook,
    base_pump_compilation,
    profile,
)

save_report(
    report,
    output,
)


status_counts = Counter(
    candidate.pricing_status
    for candidate
    in report.candidates
)

series_counts = Counter(
    candidate.series_code
    for candidate
    in report.candidates
)

option_counts = Counter(
    next(
        condition.comparison_value
        for condition
        in candidate.conditions
        if (
            condition.field_code
            == "SEAL_OPTION"
        )
    )
    for candidate
    in report.candidates
)

elastomer_counts = Counter(
    next(
        condition.comparison_value
        for condition
        in candidate.conditions
        if (
            condition.field_code
            == "SEAL_ELASTOMERS"
        )
    )
    for candidate
    in report.candidates
)


print("=" * 80)
print(
    "M022.4B FYBROC COMPLETE SEAL COMPONENT COMPILER"
)
print("=" * 80)
print(
    f"Candidates       : "
    f"{report.candidate_count}"
)
print(
    f"Issues           : "
    f"{report.issue_count}"
)
print(
    f"Found            : "
    f"{status_counts.get('found', 0)}"
)
print(
    f"Call for price   : "
    f"{status_counts.get('call_for_price', 0)}"
)
print(
    f"Output           : "
    f"{output}"
)

print()
print("By runtime series:")
for key in sorted(
    series_counts
):
    print(
        f"  {key:<40} "
        f"{series_counts[key]}"
    )

print()
print("By seal option:")
for key in sorted(
    option_counts
):
    print(
        f"  {key:<40} "
        f"{option_counts[key]}"
    )

print()
print("By seal elastomer:")
for key in sorted(
    elastomer_counts
):
    print(
        f"  {key:<40} "
        f"{elastomer_counts[key]}"
    )

if report.issues:
    print()
    print("Issues:")

    for issue in report.issues:
        print(
            f"  {issue.severity}: "
            f"{issue.issue_code}: "
            f"{issue.message}"
        )
