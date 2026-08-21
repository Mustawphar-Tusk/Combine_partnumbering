"""F110.10 - Fybroc Nomenclature V6 Testing Compiler.

Sheet: Testing
4 fields, ~228 combinations, hex-code col L(12), ID col M(13).
Data rows ~11-70.

Fields:
  H: Performance Testing
  I: Hydrotest
  J: Vibration
  K: Sound Level

Inputs:  workbooks/Fybroc/Nomenclature_V6.xlsm
Outputs: docs/evidence/F110/FYBROC_V6_TESTING.{json,txt}
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

STEP="F110.10"; ROADMAP_VERSION="1.0"; MILESTONE="F110"
WORKBOOK_REL="workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET="Testing"
DISPLAY_HEADER_ROW=2; DISPLAY_DATA_START=3; DISPLAY_DATA_END=8
DATA_END_ROW=70
COL_KEY=7; COL_PERF=8; COL_HYDRO=9; COL_VIB=10; COL_SOUND=11
COL_HEX=12; COL_ID=13
DATA_START_ROW=10  # row 9 is header, data starts row 10

FIELD_COLS=[(COL_PERF,"Performance Testing"),(COL_HYDRO,"Hydrotest"),
            (COL_VIB,"Vibration"),(COL_SOUND,"Sound Level")]

def git_info(repo_root):
    try:
        c=subprocess.run(["git","rev-parse","HEAD"],cwd=repo_root,capture_output=True,text=True,check=True).stdout.strip()
        s=subprocess.run(["git","status","--porcelain"],cwd=repo_root,capture_output=True,text=True,check=True).stdout
        return c,(s.strip()=="")
    except: return "unknown",False

def _s(v):
    if v is None: return None
    s=str(v).strip(); return s if s else None

def build_model(repo_root):
    commit,clean=git_info(repo_root)
    wb=openpyxl.load_workbook(str(repo_root/WORKBOOK_REL),read_only=True,data_only=True)
    ws=wb[SHEET]

    # Display options
    fields={}
    for c in range(COL_PERF,COL_SOUND+1):
        v=_s(ws.cell(row=DISPLAY_HEADER_ROW,column=c).value)
        if v: fields[c]=v
    options={name:[] for name in fields.values()}
    for r in range(DISPLAY_DATA_START,DISPLAY_DATA_END+1):
        for col,fname in fields.items():
            v=_s(ws.cell(row=r,column=col).value)
            if v: options[fname].append(v)

    # Data start fixed at row 10
    data_start = DATA_START_ROW

    fv={name:set() for _,name in FIELD_COLS}
    hexcodes=set(); rows=[]; total=0; BASE=COL_KEY
    for row_tuple in ws.iter_rows(min_row=data_start,max_row=DATA_END_ROW,
                                   min_col=COL_KEY,max_col=COL_ID,values_only=True):
        hx=_s(row_tuple[COL_HEX-BASE])
        if hx is None or hx in ("Hex-Code","Base-36 Code"): break
        total+=1; hexcodes.add(hx)
        rd={}
        for col,name in FIELD_COLS:
            v=_s(row_tuple[col-BASE]); rd[name]=v
            if v: fv[name].add(v)
        rows.append({"id":row_tuple[COL_ID-BASE],"hex_code":hx,**rd})

    wb.close()
    sh=sorted(hexcodes)
    return {
        "step":STEP,"roadmap_version":ROADMAP_VERSION,"milestone":MILESTONE,
        "source_workbook":WORKBOOK_REL,"sheet":SHEET,
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "git_commit":commit,"git_working_tree_clean":clean,
        "fields":[n for _,n in FIELD_COLS],
        "field_options":options,
        "combination_matrix":{
            "total_combinations":total,"distinct_hex_codes":len(hexcodes),
            "hex_code_range":{"first":sh[0] if sh else None,"last":sh[-1] if sh else None},
            "distinct_values_per_field":{n:sorted(v) for n,v in fv.items()},
            "all_rows":rows
        },
        "lookup_key_col":"G","hex_code_col":"L (2-char)",
        "part_number_role":"Testing segment in part number (2-char hex). VLOOKUP(concat_key,col_G,col_L)."
    }

def write_outputs(evidence_dir,result):
    payload={"artifact":"FYBROC_V6_TESTING",**result}
    (evidence_dir/"FYBROC_V6_TESTING.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    cm=result["combination_matrix"]; line="="*120
    out=[f"{line}\r\nF110.10 - FYBROC V6 TESTING\r\n{line}\r\n\r\n"]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")
    out.append(f"Fields             : {len(result['fields'])}\r\nTotal combinations : {cm['total_combinations']}\r\nDistinct hex-codes : {cm['distinct_hex_codes']}\r\nHex range          : {cm['hex_code_range']['first']} -> {cm['hex_code_range']['last']}\r\n\r\n")
    out.append(f"{line}\r\nFIELD OPTIONS\r\n{line}\r\n\r\n")
    for f,opts in result["field_options"].items():
        out.append(f"  {f}:\r\n")
        for o in opts: out.append(f"    - {o}\r\n")
        out.append("\r\n")
    out.append(f"{line}\r\nALL COMBINATIONS\r\n{line}\r\n\r\n")
    for r in cm["all_rows"]:
        out.append(f"  ID={r['id']:>3}  hex={r['hex_code']}  perf={r.get('Performance Testing','—')}  hydro={r.get('Hydrotest','—')}  vib={r.get('Vibration','—')}  sound={r.get('Sound Level','—')}\r\n")
    (evidence_dir/"FYBROC_V6_TESTING.txt").write_text("".join(out),encoding="utf-8")

def main():
    p=argparse.ArgumentParser(); root=Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root",type=Path,default=root); p.add_argument("--evidence-dir",type=Path,default=None)
    a=p.parse_args(); repo_root=a.repo_root.resolve()
    ev=(a.evidence_dir or (repo_root/"docs"/"evidence"/"F110")).resolve(); ev.mkdir(parents=True,exist_ok=True)
    result=build_model(repo_root); write_outputs(ev,result)
    cm=result["combination_matrix"]
    print(json.dumps({"step":STEP,"output_dir":str(ev),"fields":result["fields"],
        "total_combinations":cm["total_combinations"],"hex_code_range":cm["hex_code_range"]},indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
