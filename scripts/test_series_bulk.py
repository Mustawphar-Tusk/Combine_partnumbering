"""Bulk Series Test Harness — One Series at a Time.

Generates hundreds/thousands of random configurations for a single Fybroc series,
calls the API to evaluate and resolve each one, and produces a summary report.

Usage:
    python scripts/test_series_bulk.py 1500          # Test series 1500, 100 configs (default)
    python scripts/test_series_bulk.py 1500 --count 500   # 500 random configs
    python scripts/test_series_bulk.py 5500 --count 1000  # 1000 vertical configs
    python scripts/test_series_bulk.py ALL --count 200    # 200 per series, all series

Output: Console summary + detailed CSV in tests/results/

Requirements: Server must be running on localhost:8000
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

API_BASE = "http://localhost:8000/api/v2"
FAMILY = "FYBROC"

ALL_SERIES = ["1500", "1530", "1600", "1630", "2530", "3000", "5500", "5530", "7500", "8500"]

# Authoritative field hierarchy (same as UI)
FIELD_ORDER = [
    "ALT_SIZE", "PUMP_MATERIAL", "FLANGE_TYPE",
    "SHAFT_MATERIAL", "CASING_DRAINS", "SUCTION_DISCHARGE_TAPS", "SLEEVE",
    "PUMP_ELASTOMERS", "GLAND_HARDWARE", "FLUSH", "FLUSH_MATERIAL",
    "CYCLONE_SEPERATOR", "IMPELLER_BALANCE",
    "CASING_HARDWARE", "BEARING_OPTION", "POWER_FRAME_HARDWARE",
    "WETTED_HARDWARE", "WETTED_HARDWARE_SELECTION",
    "FLUSH_OPTIONS", "VAPOR_SEAL", "STRAINER",
    "SEAL_OPTION", "SEAL_TYPE", "SEAL_MATERIALS", "SEAL_ELASTOMERS", "SEAL_GUARD", "SEAL_MFG",
    "COUPLING_OPTION", "COUPLING_GUARD", "BASEPLATE_OPTION", "BASEPLATEHARDWARE",
    "MOUNTING_PLATE_OPTION",
    "IMPELLER_TRIM", "DYNAMIC_IMPELLER",
    "SETTING", "SETTING/LENGTH", "LENGTH", "TAILPIPE_OPTION", "TAILPIPE_LENGTH",
    "MOTOR_OPTION", "MOTOR_CONTROL", "MOTOR_HP", "MOTOR_RPM",
    "MOTOR_VOLTAGE", "MOTOR_HERTZ", "FRAME_SIZE",
    "MOTOR_ENCLOSURE", "MOTOR_EFFICIENCY", "MOTOR_MFG",
    "PERFORMANCE_TESTING", "HYDROTEST_CERTIFICATE", "VIBRATION_TESTING", "SOUND_LEVEL_TESTING",
    "NAMEPLATE", "CUSTOMER_NAMEPLATE", "PAINT_UPGRADE", "SHAFT_GROUNDING", "C_FACE_ADAPTOR",
]


@dataclass
class TestResult:
    config_num: int
    series: str
    part_number: str = ""
    sku: str = ""
    pricing_total: float = 0.0
    pricing_components: int = 0
    failed_segments: list = field(default_factory=list)
    is_reused: bool = False
    error: str = ""
    selections_count: int = 0
    elapsed_ms: float = 0.0


def evaluate(series: str, selections: dict) -> dict:
    """Call the evaluate endpoint."""
    resp = requests.post(
        f"{API_BASE}/families/{FAMILY}/configurations/evaluate",
        json={"series": series, "selections": selections},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def resolve(series: str, selections: dict) -> dict:
    """Call the resolve endpoint."""
    resp = requests.post(
        f"{API_BASE}/families/{FAMILY}/configured-products/resolve",
        json={
            "series": series,
            "selections": {"SERIES": series, **selections},
            "segment_codes": {},
            "requested_by": "bulk-test-harness",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def build_random_configuration(series: str, max_fields: int = 12) -> dict:
    """Build a random configuration by selecting from initial options only.
    
    Strategy: Call evaluate ONCE to get all available options, then randomly
    pick values for key fields that contribute to Part Number segments.
    This avoids the expensive progressive re-evaluation loop.
    """
    selections = {}

    # Get all available options in ONE call
    data = evaluate(series, {})
    available = data.get("allowable_options", {})

    if not available:
        return selections

    # Fields that directly contribute to Part Number segments (priority)
    SEGMENT_FIELDS = [
        # Primary identity (always pick these)
        "ALT_SIZE", "PUMP_MATERIAL", "FLANGE_TYPE", "IMPELLER_TRIM",
        # Pump options segment
        "SHAFT_MATERIAL", "CASING_DRAINS", "SUCTION_DISCHARGE_TAPS", "SLEEVE",
        "PUMP_ELASTOMERS", "FLUSH", "CASING_HARDWARE", "BEARING_OPTION",
        "POWER_FRAME_HARDWARE", "GLAND_HARDWARE", "CYCLONE_SEPERATOR", "IMPELLER_BALANCE",
        # Vertical pump options
        "WETTED_HARDWARE", "FLUSH_OPTIONS", "VAPOR_SEAL", "STRAINER",
        # Seal segment (all fields for precise combo table matching)
        "SEAL_OPTION", "SEAL_TYPE", "SEAL_MATERIALS", "SEAL_ELASTOMERS", "SEAL_GUARD", "SEAL_MFG",
        # Options segment (coupling/baseplate)
        "COUPLING_OPTION", "BASEPLATE_OPTION",
        # Motor segment (all fields for precise combo table matching)
        "MOTOR_OPTION", "MOTOR_HP", "MOTOR_RPM", "MOTOR_VOLTAGE",
        "MOTOR_HERTZ", "FRAME_SIZE", "MOTOR_ENCLOSURE", "MOTOR_EFFICIENCY", "MOTOR_MFG",
        # Testing segment
        "PERFORMANCE_TESTING", "HYDROTEST_CERTIFICATE", "VIBRATION_TESTING", "SOUND_LEVEL_TESTING",
    ]

    # Pick from segment-contributing fields first, then fill remaining
    fields_to_fill = []
    for f in SEGMENT_FIELDS:
        if f in available:
            fields_to_fill.append(f)
        if len(fields_to_fill) >= max_fields:
            break

    # If we still have room, add other available fields
    if len(fields_to_fill) < max_fields:
        remaining = [f for f in available if f not in fields_to_fill]
        random.shuffle(remaining)
        fields_to_fill.extend(remaining[:max_fields - len(fields_to_fill)])

    for field_code in fields_to_fill:
        options = available.get(field_code, [])
        if options:
            selections[field_code] = random.choice(options)

    return selections


def run_single_test(series: str, config_num: int, max_fields: int = 12) -> TestResult:
    """Run a single random configuration test."""
    result = TestResult(config_num=config_num, series=series)

    try:
        start = time.time()

        # Build random config
        selections = build_random_configuration(series, max_fields=max_fields)
        result.selections_count = len(selections)

        if not selections:
            result.error = "No selections could be made"
            result.elapsed_ms = (time.time() - start) * 1000
            return result

        # Resolve
        resolve_data = resolve(series, selections)
        result.elapsed_ms = (time.time() - start) * 1000

        result.part_number = resolve_data.get("part_number", "")
        result.sku = resolve_data.get("sku", "")
        result.is_reused = resolve_data.get("existing_configuration", False)
        result.pricing_total = resolve_data.get("total_price", 0.0)
        result.pricing_components = len(resolve_data.get("pricing", []))

        segment_debug = resolve_data.get("segment_debug", {})
        result.failed_segments = segment_debug.get("failed_segments", [])

    except requests.exceptions.ConnectionError:
        result.error = "CONNECTION_REFUSED — is server running on localhost:8000?"
    except requests.exceptions.HTTPError as e:
        result.error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        result.error = f"{type(e).__name__}: {str(e)[:200]}"

    return result


def run_series_test(series: str, count: int, output_dir: Path, max_fields: int = 12) -> dict:
    """Run bulk test for a single series and return summary stats."""
    print(f"\n{'='*70}")
    print(f"  TESTING SERIES {series} — {count} random configurations (max {max_fields} fields)")
    print(f"{'='*70}")

    results: list[TestResult] = []
    errors = 0
    fully_resolved = 0
    has_pricing = 0
    failed_segment_counts: dict[str, int] = {}

    for i in range(1, count + 1):
        result = run_single_test(series, i, max_fields=max_fields)
        results.append(result)

        if result.error:
            errors += 1
        elif not result.failed_segments:
            fully_resolved += 1
        
        if result.pricing_total > 0:
            has_pricing += 1

        for seg in result.failed_segments:
            failed_segment_counts[seg] = failed_segment_counts.get(seg, 0) + 1

        # Progress indicator
        if i % 10 == 0 or i == count:
            pct = i / count * 100
            sys.stdout.write(f"\r  Progress: {i}/{count} ({pct:.0f}%) | Resolved: {fully_resolved} | Errors: {errors}")
            sys.stdout.flush()

    print()  # newline after progress

    # Write CSV
    csv_path = output_dir / f"series_{series}_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Config#", "Series", "PartNumber", "SKU", "PricingTotal",
            "PricingComponents", "FailedSegments", "IsReused",
            "SelectionsCount", "ElapsedMs", "Error",
        ])
        for r in results:
            writer.writerow([
                r.config_num, r.series, r.part_number, r.sku,
                f"{r.pricing_total:.2f}", r.pricing_components,
                "|".join(r.failed_segments), r.is_reused,
                r.selections_count, f"{r.elapsed_ms:.0f}", r.error,
            ])

    # Summary
    total_valid = count - errors
    summary = {
        "series": series,
        "total_tests": count,
        "errors": errors,
        "fully_resolved": fully_resolved,
        "fully_resolved_pct": (fully_resolved / total_valid * 100) if total_valid > 0 else 0,
        "has_pricing": has_pricing,
        "has_pricing_pct": (has_pricing / total_valid * 100) if total_valid > 0 else 0,
        "failed_segment_breakdown": failed_segment_counts,
        "avg_elapsed_ms": sum(r.elapsed_ms for r in results) / len(results) if results else 0,
        "csv_path": str(csv_path),
    }

    # Print summary
    print(f"\n  RESULTS FOR SERIES {series}:")
    print(f"  {'─'*50}")
    print(f"  Total configurations tested:  {count}")
    print(f"  Errors (API failures):        {errors}")
    print(f"  Fully resolved (no '?'):      {fully_resolved}/{total_valid} ({summary['fully_resolved_pct']:.1f}%)")
    print(f"  Has pricing:                  {has_pricing}/{total_valid} ({summary['has_pricing_pct']:.1f}%)")
    print(f"  Avg time per config:          {summary['avg_elapsed_ms']:.0f}ms")

    if failed_segment_counts:
        print(f"\n  Unresolved segment breakdown:")
        for seg, cnt in sorted(failed_segment_counts.items(), key=lambda x: -x[1]):
            pct = cnt / total_valid * 100 if total_valid > 0 else 0
            print(f"    {seg:20s}: {cnt:4d} ({pct:.1f}%)")

    print(f"\n  CSV saved: {csv_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Bulk test Fybroc series configurations")
    parser.add_argument("series", help="Series to test (e.g. 1500, 5500, or ALL)")
    parser.add_argument("--count", type=int, default=100, help="Number of random configs to test (default: 100)")
    parser.add_argument("--max-fields", type=int, default=30, help="Max fields to select per config (default: 30)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # Determine which series to test
    if args.series.upper() == "ALL":
        series_list = ALL_SERIES
    else:
        series_list = [args.series]

    # Create output directory
    output_dir = Path("tests/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check server is running
    print("Checking API connectivity...")
    try:
        resp = requests.get(f"{API_BASE}/families/{FAMILY}/configuration-dictionary", timeout=5)
        resp.raise_for_status()
        print(f"  ✅ API is up. Publication loaded.")
    except Exception as e:
        print(f"  ❌ Cannot reach API at {API_BASE}")
        print(f"     Error: {e}")
        print(f"\n  Start the server first:")
        print(f"    .venv\\Scripts\\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload")
        sys.exit(1)

    # Run tests
    all_summaries = []
    start_total = time.time()

    for series in series_list:
        summary = run_series_test(series, args.count, output_dir, max_fields=args.max_fields)
        all_summaries.append(summary)

    elapsed_total = time.time() - start_total

    # Final summary if testing multiple series
    if len(series_list) > 1:
        print(f"\n{'='*70}")
        print(f"  OVERALL SUMMARY — {len(series_list)} series, {args.count} configs each")
        print(f"{'='*70}")
        print(f"\n  {'Series':<8} {'Resolved':>10} {'Pricing':>10} {'Errors':>8} {'Avg ms':>8}")
        print(f"  {'─'*50}")
        for s in all_summaries:
            print(f"  {s['series']:<8} {s['fully_resolved_pct']:>8.1f}% {s['has_pricing_pct']:>8.1f}% {s['errors']:>8} {s['avg_elapsed_ms']:>7.0f}")
        print(f"\n  Total elapsed: {elapsed_total:.1f}s")

    # Save JSON summary
    summary_path = output_dir / "test_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_elapsed_seconds": elapsed_total,
            "configs_per_series": args.count,
            "seed": args.seed,
            "summaries": all_summaries,
        }, f, indent=2, default=str)
    print(f"\n  Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
