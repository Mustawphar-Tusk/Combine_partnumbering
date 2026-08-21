"""F110.9 - Fybroc Nomenclature V6 Motor Assembly Compiler.

Sheet: ' Motor Assy' (note leading space)
11 fields, 702 combinations, hex-code col O(15), ID col P(16).
Data rows 3-728.

Fields:
  D: Motor Option
  E: Motor Class
  F: Motor Orientation
  G: Motor Horsepower
  H: Motor RPM
  I: Motor Voltage
  J: Motor Hertz
  K: Motor Frame
  L: Motor Enclosure
  M: Motor Efficiency
  N: Motor Manufacturer

Additional display cols (not in lookup):
  Q(17): Speed Control options
  U(21): Motor Hertz display
  V(22): Motor Voltage display
  Z(26): Motor Frame display
  AA(27): Motor HP display
  AB(28): Motor RPM display

Inputs:  workbooks/Fybroc/Nomenclature_V6.xlsm
Outputs: docs/evidence/F110/FYBROC_V6_MOTOR_ASSY.{json,txt}
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

STEP="F110.9"; ROADMAP_VERSION="1.0"; MILESTONE="F110"
WORKBOOK_REL="workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET=" Motor Assy"
DISPLAY_HEADER_ROW=2; DISPLAY_DATA_START=3; DISPLAY_DATA_END=8
DATA_START_ROW=27; DATA_END_ROW=728
COL_KEY=3
COL_MOTOR_OPT=4; COL_MOTOR_CLASS=5; COL_MOTOR_ORI=6
COL_MOTOR_HP=7; COL_MOTOR_RPM=8; COL_MOTOR_VOLT=9
COL_MOTOR_HERTZ=10; COL_MOTOR_FRAME=11; COL_MOTOR_ENC=12
COL_MOTOR_EFF=13; COL_MOTOR_MFR=14
COL_HEX=15; COL_ID=16  # hex in col O(15), ID in col P(16)

FIELD_COLS=[
    (COL_MOTOR_OPT,"Motor Option"),(COL_MOTOR_CLASS,"Motor Class"),
    (COL_MOTOR_ORI,"Motor Orientation"),(COL_MOTOR_HP,"Motor Horsepower"),
    (COL_MOTOR_RPM,"Motor RPM"),(COL_MOTOR_VOLT,"Motor Voltage"),
    (COL_MOTOR_HERTZ,"Motor Hertz"),(COL_MOTOR_FRAME,"Motor Frame"),
    (COL_MOTOR_ENC,"Motor Enclosure"),(COL_MOTOR_EFF,"Motor Efficiency"),
    (COL_MOTOR_MFR,"Motor Manufacturer"),
]

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
    for c in range(COL_MOTOR_OPT,COL_MOTOR_MFR+1):
        v=_s(ws.cell(row=DISPLAY_HEADER_ROW,column=c).value)
        if v: fields[c]=v
    options={name:[] for name in fields.values()}
    for r in range(DISPLAY_DATA_START,DISPLAY_DATA_END+1):
        for col,fname in fields.items():
            v=_s(ws.cell(row=r,column=col).value)
            if v and v!="-": options[fname].append(v)

    # Find data start (Motor Assy has no col C key; data starts row 3 with hex in col AD)
    data_start = DATA_START_ROW

    fv={name:set() for _,name in FIELD_COLS}
    hexcodes=set(); rows=[]; total=0; BASE=COL_KEY
    for row_tuple in ws.iter_rows(min_row=data_start,max_row=DATA_END_ROW,
                                   min_col=COL_KEY,max_col=COL_ID,values_only=True):
        hx=_s(row_tuple[COL_HEX-BASE])
        if hx is None or hx in ("Hex","Hex-Code"): break
        total+=1; hexcodes.add(hx)
        rd={}
        for col,name in FIELD_COLS:
            v=_s(row_tuple[col-BASE]); rd[name]=v
            if v: fv[name].add(v)
        if total<=30:
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
            "sample_rows":rows
        },
        "lookup_key_col":"C","hex_code_col":"O (3-char)",
        "part_number_role":"Motor Assembly segment in part number (3-char hex). VLOOKUP(concat_key,col_C,col_O)."
    }

def write_outputs(evidence_dir,result):
    payload={"artifact":"FYBROC_V6_MOTOR_ASSY",**result}
    (evidence_dir/"FYBROC_V6_MOTOR_ASSY.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    cm=result["combination_matrix"]; line="="*120
    out=[f"{line}\r\nF110.9 - FYBROC V6 MOTOR ASSY\r\n{line}\r\n\r\n"]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")
    out.append(f"Fields             : {len(result['fields'])}\r\nTotal combinations : {cm['total_combinations']}\r\nDistinct hex-codes : {cm['distinct_hex_codes']}\r\nHex range          : {cm['hex_code_range']['first']} -> {cm['hex_code_range']['last']}\r\n\r\n")
    out.append(f"{line}\r\nFIELD OPTIONS\r\n{line}\r\n\r\n")
    for f,opts in result["field_options"].items():
        out.append(f"  {f}:\r\n")
        for o in opts: out.append(f"    - {o}\r\n")
        out.append("\r\n")
    out.append(f"{line}\r\nDISTINCT VALUES PER FIELD\r\n{line}\r\n\r\n")
    for f,vals in cm["distinct_values_per_field"].items():
        out.append(f"  {f} ({len(vals)}): {vals}\r\n")
    out.append(f"\r\n{line}\r\nSAMPLE ROWS (first 30)\r\n{line}\r\n\r\n")
    for r in cm["sample_rows"]:
        out.append(f"  ID={r['id']:>4}  hex={r['hex_code']}  "+"  ".join(f"{n}={r.get(n,'—')}" for _,n in FIELD_COLS[:5])+"\r\n")
    (evidence_dir/"FYBROC_V6_MOTOR_ASSY.txt").write_text("".join(out),encoding="utf-8")

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
