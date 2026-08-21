"""F110.7 - Fybroc Nomenclature V6 Setting-Length Vertical Compiler.

Sheet: Setting-Length-Vertical
Two distinct lookup tables on one sheet:

TABLE 1 - Setting/Length (cols C-K, rows 4-684):
  Lookup key: col C (concatenated Setting_Length + Dimension)
  Col D: Setting Length (Setting or Length)
  Col E: Setting-L Dimension (e.g. S-01, S-07, custom length value)
  Col F: Index (sequential)
  Col G: Code (2-digit, e.g. 01, 07)
  Display cols I-K show the option lists

TABLE 2 - Tailpipe (cols O-S, rows 4-end):
  Lookup key: col O (concatenated Tailpipe_Option + Tailpipe_Length)
  Col P: Tailpipe Option
  Col Q: Tailpipe Length
  Col R: Index
  Col S: Code (2-digit)

Note from row 1: CPQ selects setting or length option. Setting-L
dimension shows setting options or length options depending on
Setting/Length selection.

Inputs:  workbooks/Fybroc/Nomenclature_V6.xlsm
Outputs: docs/evidence/F110/FYBROC_V6_SETTING_LENGTH_VERTICAL.{json,txt}
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

STEP = "F110.7"; ROADMAP_VERSION = "1.0"; MILESTONE = "F110"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET = "Setting-Length-Vertical"
DATA_START = 5; DATA_END = 684
COL_SL_KEY=3; COL_SL_TYPE=4; COL_SL_DIM=5; COL_SL_IDX=6; COL_SL_CODE=7
COL_TP_KEY=15; COL_TP_OPT=16; COL_TP_LEN=17; COL_TP_IDX=18; COL_TP_CODE=19

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

    sl_rows=[]; tp_rows=[]
    sl_types=set(); sl_dims=set(); tp_opts=set(); tp_lens=set()

    for row_tuple in ws.iter_rows(min_row=DATA_START,max_row=DATA_END,
                                   min_col=COL_SL_KEY,max_col=COL_TP_CODE,values_only=True):
        base=COL_SL_KEY-1
        sl_code=_s(row_tuple[COL_SL_CODE-1-base+1-1])  # col G index
        sl_type=_s(row_tuple[COL_SL_TYPE-COL_SL_KEY])
        sl_dim =_s(row_tuple[COL_SL_DIM-COL_SL_KEY])
        sl_idx =row_tuple[COL_SL_IDX-COL_SL_KEY]
        sl_code=_s(row_tuple[COL_SL_CODE-COL_SL_KEY])
        if sl_type or sl_dim:
            if sl_type: sl_types.add(sl_type)
            if sl_dim:  sl_dims.add(sl_dim)
            sl_rows.append({"setting_length":sl_type,"dimension":sl_dim,"index":sl_idx,"code":sl_code})

        tp_opt =_s(row_tuple[COL_TP_OPT-COL_SL_KEY])
        tp_len =_s(row_tuple[COL_TP_LEN-COL_SL_KEY])
        tp_idx =row_tuple[COL_TP_IDX-COL_SL_KEY]
        tp_code=_s(row_tuple[COL_TP_CODE-COL_SL_KEY])
        if tp_opt or tp_len:
            if tp_opt: tp_opts.add(tp_opt)
            if tp_len: tp_lens.add(str(tp_len))
            tp_rows.append({"tailpipe_option":tp_opt,"tailpipe_length":_s(str(tp_len)) if tp_len else None,"index":tp_idx,"code":tp_code})

    wb.close()
    return {
        "step":STEP,"roadmap_version":ROADMAP_VERSION,"milestone":MILESTONE,
        "source_workbook":WORKBOOK_REL,"sheet":SHEET,
        "generated_utc":datetime.now(timezone.utc).isoformat(),
        "git_commit":commit,"git_working_tree_clean":clean,
        "setting_length_table":{
            "row_count":len(sl_rows),
            "setting_length_types":sorted(sl_types),
            "dimension_values":sorted(sl_dims),
            "lookup_key_col":"C","code_col":"G",
            "rows":sl_rows
        },
        "tailpipe_table":{
            "row_count":len(tp_rows),
            "tailpipe_options":sorted(tp_opts),
            "tailpipe_lengths":sorted(tp_lens),
            "lookup_key_col":"O","code_col":"S",
            "rows":tp_rows
        },
        "part_number_role":"Setting/Length code (2-digit) = Setting-Length segment. Tailpipe code (2-digit) = Vertical Options segment."
    }

def write_outputs(evidence_dir,result):
    payload={"artifact":"FYBROC_V6_SETTING_LENGTH_VERTICAL",**result}
    (evidence_dir/"FYBROC_V6_SETTING_LENGTH_VERTICAL.json").write_text(json.dumps(payload,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    sl=result["setting_length_table"]; tp=result["tailpipe_table"]
    line="="*120
    out=[f"{line}\r\nF110.7 - FYBROC V6 SETTING-LENGTH VERTICAL\r\n{line}\r\n\r\n"]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")
    out.append(f"Setting/Length table rows : {sl['row_count']}\r\n")
    out.append(f"Setting/Length types      : {sl['setting_length_types']}\r\n")
    out.append(f"Dimension values          : {len(sl['dimension_values'])} values\r\n\r\n")
    out.append(f"Tailpipe table rows       : {tp['row_count']}\r\n")
    out.append(f"Tailpipe options          : {tp['tailpipe_options']}\r\n")
    out.append(f"Tailpipe lengths          : {tp['tailpipe_lengths']}\r\n\r\n")
    out.append(f"{line}\r\nSETTING/LENGTH ROWS (first 20)\r\n{line}\r\n\r\n")
    for r in sl["rows"][:20]:
        out.append(f"  type={r['setting_length']:<10} dim={r['dimension']:<8} idx={str(r['index']):<4} code={r['code']}\r\n")
    out.append(f"\r\n{line}\r\nTAILPIPE ROWS\r\n{line}\r\n\r\n")
    for r in tp["rows"]:
        out.append(f"  opt={r['tailpipe_option']:<25} len={str(r['tailpipe_length']):<6} idx={str(r['index']):<4} code={r['code']}\r\n")
    (evidence_dir/"FYBROC_V6_SETTING_LENGTH_VERTICAL.txt").write_text("".join(out),encoding="utf-8")

def main():
    p=argparse.ArgumentParser(); root=Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root",type=Path,default=root)
    p.add_argument("--evidence-dir",type=Path,default=None)
    a=p.parse_args()
    repo_root=a.repo_root.resolve()
    ev=(a.evidence_dir or (repo_root/"docs"/"evidence"/"F110")).resolve()
    ev.mkdir(parents=True,exist_ok=True)
    result=build_model(repo_root)
    write_outputs(ev,result)
    sl=result["setting_length_table"]; tp=result["tailpipe_table"]
    print(json.dumps({"step":STEP,"output_dir":str(ev),
        "setting_length_rows":sl["row_count"],"setting_length_types":sl["setting_length_types"],
        "tailpipe_rows":tp["row_count"],"tailpipe_options":tp["tailpipe_options"]},indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
