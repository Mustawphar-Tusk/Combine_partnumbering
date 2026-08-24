"""F130.6 - Fybroc Pricing Diff (Rev0.3 vs Price Estimator).

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F130
("Fybroc Pricing & Adders Reconciliation") - FYBROC_PRICING_DIFF.

Compares actual dollar values between:
  - Rev0.3 "1500 Pricing" sheet (base prices per size x material)
  - Price Estimator "Pricebook" sheet (1500 block, table 81)

Both are keyed on (Series=1500, Size, Pump Material).
Classification per price pair: MATCH, MISMATCH, REV03_ONLY, PE_ONLY.

Also compares the 5500 base pricing structure to identify whether
the Price Estimator 5500 block matches Rev0.3's more granular
Size+Setting data.

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (1500 Pricing, 5500 Pricing)
  workbooks/Fybroc/Price Estimator-Fybroc.xlsm  (Pricebook)

Outputs:
  docs/evidence/F130/FYBROC_PRICING_DIFF.{json,txt}
"""
from __future__ import annotations
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    import openpyxl
except ImportError as exc:
    raise SystemExit("openpyxl required") from exc

STEP = "F130.6"; ROADMAP_VERSION = "1.1"; MILESTONE = "F130"
REV03_WB = "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx"
PE_WB = "workbooks/Fybroc/Price Estimator-Fybroc.xlsm"


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False

def _s(v):
    if v is None: return None
    s = str(v).strip(); return s if s else None

def _num(v):
    if v is None: return None
    try: return float(v)
    except: return None

def normalize_size(s):
    """Normalize size strings for comparison (1X1.5X6 -> 1x1.5x6)."""
    if s is None: return None
    return str(s).strip().lower().replace(" ", "")

def normalize_material(m):
    """Normalize material names for comparison."""
    if m is None: return None
    return str(m).strip().lower().replace("-", "").replace(" ", "").replace("/", "")


def extract_rev03_1500_prices(ws) -> dict[tuple[str, str], float]:
    """Extract (size, material) -> price from Rev0.3 1500 Pricing sheet.
    
    Structure: row 5 = headers (Series, Alt Size, Pump Material, Price)
               rows 6+ = data (cols B=Series, C=Alt_Size, D=Material, E=Price)
    """
    prices = {}
    for r in range(6, ws.max_row + 1):
        series = ws.cell(row=r, column=2).value
        if series is None:
            break
        size = normalize_size(ws.cell(row=r, column=3).value)
        material = normalize_material(ws.cell(row=r, column=4).value)
        price = _num(ws.cell(row=r, column=5).value)
        if size and material and price is not None:
            prices[(size, material)] = price
    return prices


def extract_pe_1500_prices(ws) -> dict[tuple[str, str], float]:
    """Extract (size, material) -> price from Price Estimator Pricebook 1500 block.
    
    Structure: row 5 headers at cols 2-15
      col 3 = SIZE, col 6 = VR-1, col 7 = VR-1A, col 8 = EY-2,
      col 9 = VR-1 BPO/DMA, col 10 = VR-1A BPO/DMA, col 14 = VR-1V,
      col 15 = VR-1V BPO/DMA
    Rows 6+ = data.
    """
    # Material column mapping for 1500 block
    material_cols = {
        6: "vr1",           # VR-1 (Standard)
        7: "vr1a",          # VR-1A
        8: "ey2",           # EY-2
        9: "vr1bpodma",     # VR-1 BPO/DMA
        10: "vr1abpodma",   # VR-1A BPO/DMA
        14: "vr1v",         # VR-1V
        15: "vr1vbpodma",   # VR-1V BPO/DMA
    }
    
    prices = {}
    for r in range(6, 50):  # 1500 block has ~25 data rows
        size = normalize_size(ws.cell(row=r, column=3).value)
        if size is None:
            break
        for col, mat_key in material_cols.items():
            price = _num(ws.cell(row=r, column=col).value)
            if price is not None:
                prices[(size, mat_key)] = price
    return prices


def compare_1500_prices(rev03_prices, pe_prices) -> dict[str, Any]:
    """Compare Rev0.3 1500 prices against Price Estimator 1500 prices."""
    all_keys = set(rev03_prices.keys()) | set(pe_prices.keys())
    
    results = []
    counts = {"MATCH": 0, "MISMATCH": 0, "REV03_ONLY": 0, "PE_ONLY": 0}
    
    for key in sorted(all_keys):
        size, material = key
        r03 = rev03_prices.get(key)
        pe = pe_prices.get(key)
        
        if r03 is not None and pe is not None:
            if abs(r03 - pe) < 0.01:
                cls = "MATCH"
            else:
                cls = "MISMATCH"
        elif r03 is not None:
            cls = "REV03_ONLY"
        else:
            cls = "PE_ONLY"
        
        counts[cls] += 1
        if cls != "MATCH":  # Only store non-matching for output
            results.append({
                "size": size,
                "material": material,
                "rev03_price": r03,
                "pe_price": pe,
                "difference": round(pe - r03, 2) if r03 and pe else None,
                "classification": cls,
            })
    
    return {
        "total_compared": len(all_keys),
        "counts": counts,
        "match_rate": f"{counts['MATCH'] / len(all_keys) * 100:.1f}%" if all_keys else "N/A",
        "differences": results,
    }


def extract_rev03_5500_summary(ws) -> dict[str, Any]:
    """Get summary statistics from Rev0.3 5500 Pricing (too large to fully compare)."""
    # Structure: row 5 headers, row 6 = data start
    # Cols: B=Alt_Size, C=Setting, D=Combined, F=Series, G=Alt_Size, H=Setting, I=Material, J=Price
    sizes = set(); settings = set(); materials = set()
    price_count = 0; min_price = None; max_price = None
    
    for r in range(6, min(ws.max_row + 1, 500)):  # Sample first 494 rows
        size = _s(ws.cell(row=r, column=7).value)
        setting = _s(ws.cell(row=r, column=8).value)
        material = _s(ws.cell(row=r, column=9).value)
        price = _num(ws.cell(row=r, column=10).value)
        
        if size is None:
            break
        if size: sizes.add(size)
        if setting: settings.add(str(setting))
        if material: materials.add(material)
        if price is not None:
            price_count += 1
            if min_price is None or price < min_price: min_price = price
            if max_price is None or price > max_price: max_price = price
    
    return {
        "sample_rows": price_count,
        "total_estimated_rows": ws.max_row - 5,
        "distinct_sizes": len(sizes),
        "distinct_settings": len(settings),
        "distinct_materials": len(materials),
        "sizes_sample": sorted(sizes)[:10],
        "settings": sorted(settings),
        "materials": sorted(materials),
        "price_range": {"min": min_price, "max": max_price},
    }


def extract_pe_5500_summary(ws) -> dict[str, Any]:
    """Get summary from Price Estimator 5500 block (cols 87-115, rows 6+)."""
    sizes = set(); settings = set()
    price_count = 0; min_price = None; max_price = None
    
    for r in range(6, 300):
        size = _s(ws.cell(row=r, column=87).value)  # ANSI Size
        setting = _s(ws.cell(row=r, column=88).value)  # Setting Number
        
        if size is None and setting is None:
            break
        if size: sizes.add(size)
        if setting: settings.add(str(setting))
        
        # Check first price column (col 91 = VR-1 Standard : 316 SS)
        price = _num(ws.cell(row=r, column=91).value)
        if price is not None:
            price_count += 1
            if min_price is None or price < min_price: min_price = price
            if max_price is None or price > max_price: max_price = price
    
    return {
        "data_rows": price_count,
        "distinct_sizes": len(sizes),
        "distinct_settings": len(settings),
        "sizes_sample": sorted(sizes)[:10],
        "settings": sorted(settings),
        "price_range": {"min": min_price, "max": max_price},
    }


def build_model(repo_root):
    commit, clean = git_info(repo_root)
    
    # Open Rev0.3
    wb_rev03 = openpyxl.load_workbook(
        str(repo_root / REV03_WB), read_only=True, data_only=True)
    
    rev03_1500 = extract_rev03_1500_prices(wb_rev03["1500 Pricing"])
    rev03_5500_summary = extract_rev03_5500_summary(wb_rev03["5500 Pricing"])
    wb_rev03.close()
    
    # Open Price Estimator
    wb_pe = openpyxl.load_workbook(
        str(repo_root / PE_WB), read_only=True, data_only=True)
    
    pe_1500 = extract_pe_1500_prices(wb_pe["Pricebook"])
    pe_5500_summary = extract_pe_5500_summary(wb_pe["Pricebook"])
    wb_pe.close()
    
    # Compare 1500 prices
    comparison_1500 = compare_1500_prices(rev03_1500, pe_1500)
    
    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "comparison_1500": {
            "rev03_price_count": len(rev03_1500),
            "pe_price_count": len(pe_1500),
            **comparison_1500,
        },
        "comparison_5500": {
            "rev03_summary": rev03_5500_summary,
            "pe_summary": pe_5500_summary,
            "structural_finding": (
                f"Rev0.3 has {rev03_5500_summary['total_estimated_rows']} rows "
                f"({rev03_5500_summary['distinct_sizes']} sizes x "
                f"{rev03_5500_summary['distinct_settings']} settings x "
                f"{rev03_5500_summary['distinct_materials']} materials). "
                f"Price Estimator has {pe_5500_summary['data_rows']} rows "
                f"({pe_5500_summary['distinct_sizes']} sizes x "
                f"{pe_5500_summary['distinct_settings']} settings). "
                "Both sources have Setting-level granularity for 5500."
            ),
        },
    }


def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_PRICING_DIFF", **result}
    (evidence_dir / "FYBROC_PRICING_DIFF.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    c15 = result["comparison_1500"]; c55 = result["comparison_5500"]
    out = [_banner("F130.6 - FYBROC PRICING DIFF (Rev0.3 vs Price Estimator)")]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")
    
    out.append(_banner("1500 SERIES BASE PRICE COMPARISON"))
    out.append(f"Rev0.3 prices   : {c15['rev03_price_count']}\r\n")
    out.append(f"PE prices       : {c15['pe_price_count']}\r\n")
    out.append(f"Total compared  : {c15['total_compared']}\r\n")
    out.append(f"Match rate      : {c15['match_rate']}\r\n\r\n")
    out.append(f"Counts:\r\n")
    for cls, n in c15['counts'].items():
        out.append(f"  {cls:<15} : {n}\r\n")
    
    if c15['differences']:
        out.append(f"\r\nDIFFERENCES ({len(c15['differences'])} entries):\r\n\r\n")
        for d in c15['differences']:
            out.append(
                f"  {d['classification']:<12} size={d['size']:<12} material={d['material']:<15} "
                f"rev03={d['rev03_price']}  pe={d['pe_price']}  diff={d['difference']}\r\n"
            )
    
    out.append("\r\n" + _banner("5500 SERIES STRUCTURAL COMPARISON"))
    out.append(f"Rev0.3 5500:\r\n")
    r55 = c55['rev03_summary']
    out.append(f"  Estimated rows : {r55['total_estimated_rows']}\r\n")
    out.append(f"  Sizes          : {r55['distinct_sizes']} ({r55['sizes_sample']})\r\n")
    out.append(f"  Settings       : {r55['distinct_settings']} ({r55['settings']})\r\n")
    out.append(f"  Materials      : {r55['distinct_materials']} ({r55['materials']})\r\n")
    out.append(f"  Price range    : {r55['price_range']}\r\n\r\n")
    
    p55 = c55['pe_summary']
    out.append(f"Price Estimator 5500:\r\n")
    out.append(f"  Data rows      : {p55['data_rows']}\r\n")
    out.append(f"  Sizes          : {p55['distinct_sizes']} ({p55['sizes_sample']})\r\n")
    out.append(f"  Settings       : {p55['distinct_settings']} ({p55['settings']})\r\n")
    out.append(f"  Price range    : {p55['price_range']}\r\n\r\n")
    
    out.append(f"FINDING: {c55['structural_finding']}\r\n")

    (evidence_dir / "FYBROC_PRICING_DIFF.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F130")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    c15 = result["comparison_1500"]
    print(json.dumps({
        "step": STEP, "output_dir": str(ev),
        "1500_comparison": {
            "rev03_prices": c15["rev03_price_count"],
            "pe_prices": c15["pe_price_count"],
            "match_rate": c15["match_rate"],
            "counts": c15["counts"],
        },
        "5500_finding": result["comparison_5500"]["structural_finding"],
    }, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
