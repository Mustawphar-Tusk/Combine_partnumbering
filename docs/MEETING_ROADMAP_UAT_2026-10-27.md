# Path to UAT — Engineering Meeting Brief
**Meeting date:** today · **Target UAT deployment:** Mon 27 Oct 2026
**Prepared from:** live `PumpConfiguratorDB` snapshot (not stale docs)

> Personal walk-through notes. Numbers below are pulled from the current DB
> publications, so they're accurate to today.

---

## 1. One-line status

Fybroc configuration is complete and enforced; Fybroc pricing is **published for the
horizontal 1500 family + vertical 5500 only** — the other vertical series have no
pricing yet. Dean configuration + pricing is in place for ~32 series, with a known
set of **open engineering questions** (seal code, standard configs, motor/cooling/
barrier numbering) that gate full Dean completion. The architecture, regression gate,
and a reversible price-update mechanism are all in place. The main things between us
and UAT are **data gaps that need engineering answers**, plus **UAT-environment
hardening**.

---

## 2. What's DONE (green)

- **Fybroc config:** all 10 series resolve Part Number + SKU; constraints enforced
  (feasible + motor), progressive hierarchy, Rev0.4 adopted as authority.
- **Fybroc pricing (1500 family + 5500):** base + all adders + seal + coupling +
  testing priced from Rev0.4; VR-1 base-price bug fixed; suction/discharge + casing
  drains pricing bridged; CPQ Conversion2 motor descriptor live.
- **Dean config:** 37 series configured; identifiers + BOM + quote engine working.
- **Dean pricing:** matrix published (9,874 rules) across ~32 series.
- **Platform:** FastAPI + SQL Server; parameterized queries (injection-safe);
  family isolation (Fybroc <-> Dean) proven; 9/9 regression gate green.
- **Price updates:** `price.usp_ApplyPriceAdjustment` — percent updates by
  family / series / all-families, audited + reversible.

---

## 3. Live coverage snapshot (what's actually in the DB today)

**Fybroc pricing — current pub `FYBROC-REV04-MERGE-20260826-V2` (56,355 rules):**

| Series | Orientation | Pricing status |
|---|---|---|
| 1500, 1530, 1550, 1600, 1630, 1650 | Horizontal | priced |
| 2530, 2580, 2630, 3000 | Horizontal | priced |
| 5500 | Vertical | priced (49,637 rules) |
| **5530** | Vertical | **no pricing** |
| **7500** | Vertical | **no pricing** |
| **8500** | Vertical | **no pricing** |

**Dean pricing — current pub `DEAN-MATRIX-20260826-V1` (9,874 rules):** 32 series
priced. Configured-but-UNPRICED Dean series: **M300 (Frame III), RM5140, RMA5140,
RS, RSWA** (config exists, no price rules).

---

## 4. What's LEFT before UAT (grouped by owner)

### A. Needs ENGINEERING input (blocks completion — raise today)

**Fybroc**
1. **Vertical pricing for 5530, 7500, 8500** — provide the pricing datasheets (same
   Rev0.4 shape as 1500/5500) so we can compile + publish. *This is the "pending
   Fybroc pricing for all series" item.*
2. **Series scope decisions** — are 6000 / 7530 active? (config exists in V6 but not
   in the selections source.) Is 2630 legacy or active?

**Dean (from `DEAN_ENGINEERING_QUESTIONS.md`)**
3. **Seal code (A1)** — the real seal code comes from an external Access DB
   (`Seal Numbering.accdb`) we don't have. Seal is currently omitted-but-not-discarded
   from the Dean PN. *Need the DB/export + the seal-vocabulary crosswalk (519 seal
   codependencies are held out until then).*
4. **Standard Configs (A2)** — provide the "Standard Confs" table, or confirm the
   Pump Options STD grid is authoritative.
5. **Motor / cooling / barrier numbering (C1, F1, F2, F3)** — motor main code is inert
   `000` (frame-size only); Cooling Plan + Barrier Plan numbering tables are empty.
   Confirm whether these must encode into the PN or are intentionally frame-only / inert.
6. **Pricing anomalies (D1, D2)** — RTA3146 baseplate has two conflicting prices;
   confirm baseplate keying + "Economy = Formed."
7. **Unpriced Dean series** — pricing for M300, RM5140, RMA5140, RS, RSWA (or confirm
   quote-only / out of scope).
8. **2 models with no A#/D# identity (E1)** — real/current? If so, their A-numbers.

### B. Dev work (ours — proceeds in parallel)

9. **D150 — Exhaustive Dean regression** (not yet started; the gated next Dean step).
10. **Publish Fybroc vertical pricing** once datasheets arrive (compile -> merge ->
    publish -> audit). Mechanism already proven.
11. **Reconcile the ~5 unpriced Dean series** once pricing provided.
12. **UAT-readiness hardening (T105, 6 items):** fail-closed auth-bypass guard, schema
    migration tool, run the audit gate in CI, secrets -> Key Vault, promotion/rollback
    runbook, price-adjustment reapply policy.
13. **UAT environment (T110):** stand up a persistent TEST env (currently a
    Vercel/Render/ngrok preview that only runs during a coordinated window). For
    reliable UAT, move the DB to Azure SQL to remove the local-PC + ngrok dependency.

### C. UAT execution (the deployment itself)

14. T120 Telford (Fybroc) acceptance · T130 Indianapolis (Dean) acceptance ·
    T140 cross-family · T150 defect-correction cycle.

---

## 5. Proposed schedule to 27 Oct

Working back from the UAT date. The long pole is **engineering data answers**, not
dev throughput — the earlier Section 4A is resolved, the safer this date is.

| Window | Focus | Depends on |
|---|---|---|
| This week (meeting) | Lock Section 4A answers; get Fybroc vertical pricing sheets + Dean seal/standard/numbering decisions | **Engineering** |
| Weeks 1–2 | Publish Fybroc 5530/7500/8500 pricing; price the 5 unpriced Dean series; begin D150 | 4A #1, #7 |
| Weeks 2–4 | D150 exhaustive Dean regression; Dean seal/motor/cooling reconciliation as answers land | 4A #3–6 |
| Weeks 3–5 | T105 hardening (auth guard, migrations, CI gate, secrets, runbook) | dev |
| Weeks 4–6 | T110 persistent UAT env (Azure SQL); deploy build; smoke-test | infra |
| ~1 week before 27 Oct | Freeze; full regression green; UAT entry sign-off | all above |
| **27 Oct** | **UAT deployment** (T120/T130 begin) | all above |

---

## 6. Effort estimate (dev hours to UAT-ready)

Rough order-of-magnitude for the **dev** work only (excludes engineering's time to
produce data, and excludes the UAT test cycle itself). Ranges reflect how much
hinges on the Section 4A answers.

| Work item | Est. hours |
|---|---|
| Publish Fybroc vertical pricing (5530/7500/8500) once sheets arrive | 12–20 |
| Price + reconcile the 5 unpriced Dean series | 8–16 |
| D150 exhaustive Dean regression (build + run + fix) | 24–40 |
| Dean seal / motor / cooling / barrier reconciliation (post-answers) | 20–40 |
| T105 UAT hardening (6 items) | 24–40 |
| T110 persistent UAT env + Azure SQL migration | 20–32 |
| Integration, full-regression, freeze, UAT sign-off prep | 12–20 |
| **Total (dev)** | **~ 120–210 hours** |

**Read:** at ~20–30 focused dev hours/week, that's roughly **5–8 weeks of dev** —
which fits inside the window to 27 Oct **only if** engineering's Section 4A answers
(especially Fybroc vertical pricing and the Dean seal/numbering decisions) land in the
next 1–2 weeks. If those slip, the Dean-completeness and vertical-pricing items become
the schedule risk, and we should agree a reduced-scope UAT (e.g. Fybroc horizontal +
Dean priced-series first).

---

## 7. Decisions I need from engineering TODAY

1. Deliver (or commit a date for) **Fybroc vertical pricing** for 5530 / 7500 / 8500.
2. **Dean seal:** provide `Seal Numbering.accdb` + crosswalk, or confirm seal stays
   quote-only (omitted from PN) for UAT.
3. **Dean standard configs:** provide the table or confirm Pump Options STD is authority.
4. **Dean motor/cooling/barrier numbering:** encode in PN, or intentionally inert for UAT?
5. **Scope call:** are 6000/7530 (Fybroc) and M300/RM5140/RMA5140/RS/RSWA (Dean) in or
   out of UAT scope?
6. Confirm the **Dean baseplate pricing** anomalies (D1/D2).
7. Agree the **UAT scope line**: full dual-family vs a phased UAT if data answers slip.
