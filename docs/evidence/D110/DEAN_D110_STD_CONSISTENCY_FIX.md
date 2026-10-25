# D110 — Dean STD-CONSISTENCY fix (sheet-STD never pruned by a constraint)

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (runtime constraint-enforcement fix)
**Type:** CODE fix (src/api/v2_routes.py), Dean-only at runtime; no DB/schema/
loader change. Fybroc frozen (byte-for-byte unchanged).

---

## 1. Symptom (reported)

In the configurator, **CNV206 / 1X1.5X6** reported **Cooling Plan STD** as
incompatible with the standard selection, although the authoritative sheet marks
it STD-compatible.

Reproduced via `/api/v2/families/DEAN/configurations/resolve-state`
(`{"ALT_SIZE": "1x1.5x6"}`): the full STD seed resolved `valid=True` but
`conflicts` reported `CASING_MOUNTING='NONE' conflicts_with ['COOLING_PLAN']`
(and `COOLING_PLAN='NONE'` flagged) — even though both `COOLING_PLAN=NONE` and
`CASING_MOUNTING=NONE` are the authoritative Pump Constraints STD values for that
model.

## 2. Root cause (runtime enforcement, not a parse bug)

The Dean `Codependencies` sheet stacks **multiple sub-blocks in the same two
physical columns** (AT/AU), each introduced by its own in-column header row:

| header row | AT label | AU label | relationship |
|-----------:|----------|----------|--------------|
| r6  | Cooling Plan | Seal Chamber Config | COOLING_PLAN × SEAL_CHAMBER_CONFIG |
| r63 | Cooling Plan | Gland Type          | COOLING_PLAN × GLAND_TYPE |
| r75 | Cooling Plan | Casing Mounting     | COOLING_PLAN × CASING_MOUNTING |

The loader parses these faithfully. The problem is the **r75 sub-block is
source-vocabulary-inconsistent**: under the `Casing Mounting` header, the values
allowed when `COOLING_PLAN=NONE` are cooling-plan **piping accessories** (Steel
Piping, Stainless Steel Tubing/Piping, Valve, Flow Indicator, Valve & Flow
Indicator) — not real casing-mounting values — and there is **no
(COOLING_PLAN=NONE, CASING_MOUNTING=NONE) allow row**.

`_apply_constraints` enforces an allow-list by restricting the target field to the
governed allow-set for the matched context. With `COOLING_PLAN=NONE` in context,
`CASING_MOUNTING` was restricted to that piping set, which excludes `NONE` — so
the authoritative STD value was pruned and surfaced as a false STD-vs-STD
conflict.

**This is widespread, not CNV206-specific.** The new audit (below) failed **0/7**
of a diverse sample pre-fix, implicating several tables:
`CASING_MOUNTING ↔ COOLING_PLAN`, `BEARING_LUBRICATION ↔ OILER_OPTIONS`, and
`BEARING_LUBRICATION ↔ BEARING_SEAL`. A second, distinct mechanism also pruned a
STD value: the **Dean numbering-combination allow-list** (buildable wet-end/
power-frame combinations) narrowed `CASING_MOUNTING` to its reachable set and
dropped `Yoke Foot` (RM5140's STD) when no enumerated combination covered it.

## 3. Fix — Dean sheet-STD is never pruned by a constraint (Dean-only)

Principle: a field's **authoritative STD value (from the Pump Constraints matrix)
is, by definition, part of a complete valid shippable configuration**, so the
constraint filter must never remove a field's own STD value. A codependency
allow-list (or a numbering-combination gap) that would exclude a sheet-STD value
is a **source mismatch**, not a real restriction, and must not win over the
authoritative STD.

Implementation (`src/api/v2_routes.py`, `_apply_constraints`):

- New `std_defaults` parameter ({field → STD value}, size-scoped). A normalized
  `_std_norm` map is built once.
- **Feasible-constraint allow/deny block:** a value is kept if it equals the
  target field's STD; otherwise it is filtered exactly as before.
- **Dean numbering-combination allow-list block:** the field's STD value is kept
  even if no currently-matching enumerated combination covers it (that block
  already fails open per-field; this makes STD explicitly safe).
- Threaded into both callers — `/configurations/evaluate` and the resolve-state
  `_allowable_for`.

**Non-STD values are filtered exactly as before** — genuine constraints are not
weakened (confirmed: codependency fail-closed still prunes 3 disallowed
CASING_GASKET values for CASING_MATERIAL=none).

### 3a. Dean-only scoping (a Fybroc regression caught and fixed)

The first implementation protected STD for **all** families. The Fybroc gate then
failed: `audit_feasible_constraints` 43/1 — `CT20 MotorControl × ShaftGrounding`
expected `SHAFT_GROUNDING='not included'` ABSENT but it was present. Unlike the
Dean Pump Constraints matrix, a **Fybroc** field default can legitimately be
pruned by a genuine Fybroc constraint in context — so "STD is always valid" is not
a safe universal invariant.

Resolution: the STD protection is **Dean-only**. Both call sites pass
`std_defaults = standard_defaults if family_upper == "DEAN" else None`; Fybroc
passes `None` → byte-for-byte legacy behavior. Re-running the gate restored
`audit_feasible_constraints` to 44/0 and the full gate to ALL CORRECTIONS INTACT.

## 4. New audit

`scripts/audit_dean_std_consistency.py` (DB-derived expectations; `--all` for the
exhaustive sweep). For each Dean (series, size) it seeds the full STD set via
resolve-state and fails if any STD field is reported in `conflicts`, if a STD
value is pruned from its own allowable list, or if the resolve is not valid. Exits
non-zero on any wrongly-incompatible STD.

- **Pre-fix:** 0/7 sample (surfaced the multi-table scope).
- **Post-fix sample:** 7/7.
- **Post-fix exhaustive (`--all`): 206 passed, 0 failed — every Dean model.**

## 5. Verification

| Check | Result |
|-------|--------|
| `audit_dean_std_consistency.py --all` | **206 / 206** (0 failed) |
| CNV206/1x1.5x6 (reported case) | `conflicts: []`; COOLING_PLAN=NONE + CASING_MOUNTING=NONE both kept |
| RM5140/1.5x3x10 (combination-block case) | `conflicts: []`; Yoke Foot (STD) kept |
| `audit_dean_config.py` | **28 / 0** |
| `audit_dean_codependencies.py` | **13 / 0** (fail-closed intact; non-STD still pruned; FYBROC FeasibleConstraint 4487 unchanged) |
| `run_all_fybroc_audits.py` | **ALL CORRECTIONS INTACT (9/9)** |

**Isolation (DB watermarks, code-only change, no DB write):** non-DEAN
`FeasibleConstraint` 4487, `ConstraintFieldMap` 28, `SeriesFieldOption` 3638 —
unchanged.

## 6. Gaps / notes (disclosed)

- The underlying Dean `Codependencies` sub-blocks whose vocabulary does not line
  up with the Pump Constraints offered values (e.g. a "Casing Mounting" sub-block
  enumerating cooling-plan piping accessories) remain in the source. The STD
  guard neutralizes their effect on the STD configuration; a full source
  reconciliation of those blocks is a separate pending-engineering item (same
  class as the deferred seal-vocabulary A1). Non-STD enforcement from those tables
  is unchanged.
- The exhaustive `--all` audit is slow (resolve-state ≈ 30 s/call); it completed
  for all 206 models in this run.

## 7. Exit-gate decision

> Every Dean (series, size) whose sheet STD set is self-consistent resolves valid
> with all its STD values seeded and none reported incompatible; Fybroc untouched;
> genuine constraints not weakened.

**PASS.** The reported CNV206 case is fixed, and the STD-consistency audit passes
**206/206** across every Dean model. Non-STD constraint enforcement is intact
(Dean fail-closed 13/0; Dean config 28/0) and Fybroc is frozen (gate 9/9, watermarks
4487/28/3638 unchanged).

## 8. Reproduction commands

```powershell
# API on 127.0.0.1:8080
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="<secret>"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080

# the new STD-consistency audit (sample, or --all for every model)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_std_consistency.py --all

# Dean regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py

# Fybroc gate (needs 8080 free; starts its own temp API)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression. **Do not start
D150 without explicit go-ahead.**
