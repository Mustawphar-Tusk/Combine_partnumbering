from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.pricing_engine.compilation_merge import (
    merge_compiled_pricing,
    save_combined_compilation,
)


inputs = (
    ROOT
    / "exports"
    / "fybroc_base_pump_pricing.json",
    ROOT
    / "exports"
    / "fybroc_seal_pricing.json",
)

output = (
    ROOT
    / "exports"
    / "fybroc_configuration_pricing.json"
)


data = merge_compiled_pricing(
    inputs
)

save_combined_compilation(
    data,
    output,
)


print("=" * 80)
print(
    "M022.5 FYBROC COMBINED PRICING COMPILATION"
)
print("=" * 80)

print(
    f"Candidates         : "
    f"{data['candidate_count']}"
)
print(
    f"Conditions         : "
    f"{data['condition_count']}"
)
print(
    f"Issues             : "
    f"{data['issue_count']}"
)
print(
    f"Family             : "
    f"{data['family_code']}"
)
print(
    f"Currency           : "
    f"{data['currency_code']}"
)
print(
    f"Source workbook    : "
    f"{data['source_workbook']}"
)

print()
print("By component:")
for (
    component,
    count,
) in data[
    "component_counts"
].items():
    print(
        f"  {component:<20} "
        f"{count}"
    )

print()
print("By status:")
for (
    status,
    count,
) in data[
    "status_counts"
].items():
    print(
        f"  {status:<20} "
        f"{count}"
    )

print()
print(
    f"Output             : "
    f"{output}"
)
