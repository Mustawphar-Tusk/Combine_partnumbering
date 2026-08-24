# D140 — Dean Excel Oracle

**Date:** 2026-08-24  
**Milestone:** D140  

---

## Oracle Infrastructure

The Excel Oracle harness built for Fybroc (F160) is **family-agnostic** and supports Dean workbooks.

| Component | Status |
|-----------|--------|
| win32com Excel COM | ✅ Operational (v16.0) |
| Disposable copy mechanism | ✅ Working |
| Cell write + CalculateFull | ✅ Working |
| Dean Data Sheet Rev 2.xlsm | Available as oracle source |

## Dean Oracle Cell Map (Smart Number sheet)

| Field | Cell | Notes |
|-------|------|-------|
| Part Number output | (5, 2) | B5 = generated Part Number |
| Description | (8, 2) | B8 = human-readable description |
| Brand code | (12, 2) | Always 'D' |
| A# segment | (12, 3) | e.g., '610' |
| Wet End code | (12, 4) | e.g., '00CA' |
| Trim code | (12, 8) | e.g., 'AB' |

## Exit Gate

Dean Oracle harness can be instantiated from the same infrastructure as Fybroc.
Full validation requires Dean-specific test cases to be defined after D110 configuration 
model is loaded into SQL.
