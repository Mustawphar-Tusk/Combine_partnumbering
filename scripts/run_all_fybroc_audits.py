"""Consolidated Fybroc correction-regression runner.

Runs every audit that guards a completed correction, in one command, and reports
a single PASS/FAIL summary. This is the alignment gate: run it at every milestone
boundary (and before declaring anything done) to prove that new work has NOT
regressed any prior correction. Exit code is non-zero if ANY audit fails.

Audits:
  1. audit_selections_vs_db.py   - DB-only. Selections X/STD applicability vs DB,
                                    V6 flange authority, STD defaults.
  2. audit_feasible_constraints.py - API. Feasible-constraint fail-closed
                                    (NOT-ALLOWED / ALLOW-LIST) + valid walks.
  3. audit_motor_constraints.py  - API. All 4 Motor Constraint relationships.

The API-dependent audits need the FastAPI server on 127.0.0.1:8080. This runner
detects whether it is already up; if not, it starts a temporary local instance
for the duration of the run and shuts it down afterward.

Usage:
    python scripts/run_all_fybroc_audits.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
API_HEALTH = "http://127.0.0.1:8080/docs"

DB_ONLY_AUDITS = ["audit_selections_vs_db.py"]
API_AUDITS = ["audit_feasible_constraints.py", "audit_motor_constraints.py",
              "audit_identifier_parity.py", "audit_bom_engine.py",
              "audit_quote_engine.py"]


def _api_up() -> bool:
    try:
        with urllib.request.urlopen(API_HEALTH, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def _run(script: str) -> bool:
    print("\n" + "=" * 92)
    print(f"RUNNING: {script}")
    print("=" * 92)
    proc = subprocess.run([PY, str(ROOT / "scripts" / script)], cwd=str(ROOT))
    ok = proc.returncode == 0
    print(f"--> {script}: {'PASS' if ok else 'FAIL'} (exit {proc.returncode})")
    return ok


def main() -> int:
    results: dict[str, bool] = {}

    # 1. DB-only audits (no server needed)
    for s in DB_ONLY_AUDITS:
        results[s] = _run(s)

    # 2. API-dependent audits: ensure a server is available
    started = None
    if _api_up():
        print("\n[info] Reusing already-running API on 127.0.0.1:8080")
    else:
        print("\n[info] Starting a temporary local API for the audit run...")
        env = dict(os.environ)
        env.setdefault("CONFIGURATION_TOKEN_SECRET",
                       "local-dev-configuration-token-secret-0123456789")
        env["PYTHONPATH"] = "."
        started = subprocess.Popen(
            [PY, "-m", "uvicorn", "src.api.app:app",
             "--host", "127.0.0.1", "--port", "8080"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            if _api_up():
                break
            time.sleep(1)
        if not _api_up():
            print("[error] temporary API failed to start; API audits will fail")

    try:
        for s in API_AUDITS:
            results[s] = _run(s)
    finally:
        if started is not None:
            started.terminate()
            try:
                started.wait(timeout=10)
            except Exception:
                started.kill()
            print("\n[info] temporary API shut down")

    # Summary
    print("\n" + "=" * 92)
    print("FYBROC CORRECTION-REGRESSION SUMMARY")
    print("=" * 92)
    for s, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {s}")
    all_ok = all(results.values())
    print("=" * 92)
    print("RESULT: ALL CORRECTIONS INTACT" if all_ok else "RESULT: REGRESSION DETECTED — a prior correction broke")
    print("=" * 92)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
