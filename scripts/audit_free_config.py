"""U150 free-edit configuration audit (POST /configurations/resolve-state).

Guards the free-edit UX contract for the new endpoint that powers the
configurator UI. Unlike the linear-walk /evaluate (one current field, blanket
prefix pruning), resolve-state exposes a COMPLETE configuration with per-field,
omni-directional allowable options and non-destructive upstream correction.

Asserts, for representative series (1500 horizontal, 5500 vertical):

  1. STD auto-populate: selecting a series (empty selections) seeds a value for
     EVERY configurable field that has a STANDARD default in the workbook, and
     the seeded config is internally consistent (valid=True). (Fields the
     workbook does not default - size, motor HP, impeller trim, length, etc. -
     are intentionally left unset but still offered valid options.)

  2. Allowable integrity: every applicable field's allowable option list is
     non-empty, and each seeded value is contained in its own field's allowable
     set (the STD is never an illegal option).

  3. Non-destructive upstream correction: after choosing downstream values, a
     valid change to an UPSTREAM field keeps the still-valid downstream picks
     untouched (nothing is reset or dropped that did not have to be).

  4. Invalidation is NON-DESTRUCTIVE and REPORTED: a change that makes a prior
     selection incompatible KEEPS that selection (never silently changes it) and
     reports it in `conflicts` with the field(s) it conflicts with and the
     recommended compatible options - so the user corrects it deliberately.

  5. Resolvability: a completed free-edit configuration still resolves to a Part
     Number / SKU with parity_ok (Python assembly == SQL assembly).

Requires the API server on 127.0.0.1:8080. Exit 0 if all pass, 1 otherwise.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"
SERIES = ["1500", "5500"]


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _wait():
    for _ in range(40):
        try:
            post("/configurations/resolve-state", {"series": "1500", "selections": {}})
            return True
        except Exception:
            time.sleep(1)
    return False


def _norm(v):
    return str(v).strip().lower()


def _in(value, options):
    return any(_norm(value) == _norm(o) for o in options)


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    P = [0]
    F = [0]

    def ok(cond, msg):
        cond = bool(cond)
        P[0] += cond
        F[0] += (not cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    for series in SERIES:
        print(f"\n=== {series}: free-edit resolve-state ===")

        # --- (1) STD auto-populate on series select --------------------------
        seed = post("/configurations/resolve-state",
                    {"series": series, "selections": {}})
        ok(seed.get("valid") is True, f"{series}: seed valid=True")
        ordered = seed.get("ordered_fields", [])
        selections = seed.get("selections", {})
        allow = seed.get("allowable_options", {})
        std = seed.get("standard_defaults", {})
        ok(len(ordered) > 0, f"{series}: has applicable fields ({len(ordered)})")

        # Every field that HAS a STD default must be seeded to that STD.
        std_fields = [fc for fc in ordered if fc in std]
        unseeded_std = [fc for fc in std_fields if fc not in selections]
        ok(not unseeded_std,
           f"{series}: every field with a STD is seeded "
           f"({len(std_fields)} std fields, {len(unseeded_std)} unseeded)")
        wrong_std = [fc for fc in std_fields
                     if fc in selections and _norm(selections[fc]) != _norm(std[fc])]
        ok(not wrong_std,
           f"{series}: seeded values equal their STD ({len(wrong_std)} mismatched)")

        # --- (2) Allowable integrity ----------------------------------------
        empty_allow = [fc for fc in ordered if not allow.get(fc)]
        ok(not empty_allow,
           f"{series}: every field has non-empty allowable ({len(empty_allow)} empty)")
        bad_membership = [
            fc for fc, val in selections.items()
            if fc in allow and not _in(val, allow[fc])
        ]
        ok(not bad_membership,
           f"{series}: every seeded value is within its allowable "
           f"({len(bad_membership)} out-of-range)")

        # --- (3) Non-destructive upstream correction ------------------------
        # Choose a couple of downstream values (size + a motor HP), then make a
        # valid upstream correction (PUMP_MATERIAL) and confirm downstream picks
        # that do not depend on it are kept.
        sizes = allow.get("ALT_SIZE", [])
        hps = allow.get("MOTOR_HP", [])
        if sizes and hps:
            chosen = dict(selections)
            chosen["ALT_SIZE"] = sizes[0]
            step = post("/configurations/resolve-state",
                        {"series": series, "selections": chosen,
                         "changed_field": "ALT_SIZE"})
            # Pick an HP valid under this size.
            hp_opts = step["allowable_options"].get("MOTOR_HP", [])
            if hp_opts:
                chosen = dict(step["selections"])
                chosen["MOTOR_HP"] = hp_opts[0]
                step = post("/configurations/resolve-state",
                            {"series": series, "selections": chosen,
                             "changed_field": "MOTOR_HP"})
                kept_hp = step["selections"].get("MOTOR_HP")
                pm_opts = step["allowable_options"].get("PUMP_MATERIAL", [])
                cur_pm = step["selections"].get("PUMP_MATERIAL")
                others = [o for o in pm_opts if _norm(o) != _norm(cur_pm or "")]
                if others:
                    sel2 = dict(step["selections"])
                    sel2["PUMP_MATERIAL"] = others[0]
                    corr = post("/configurations/resolve-state",
                                {"series": series, "selections": sel2,
                                 "changed_field": "PUMP_MATERIAL"})
                    ok(corr["selections"].get("PUMP_MATERIAL") == others[0],
                       f"{series}: upstream PUMP_MATERIAL change applied ({others[0]})")
                    ok(corr["selections"].get("MOTOR_HP") == kept_hp,
                       f"{series}: downstream MOTOR_HP kept across upstream "
                       f"correction (={kept_hp})")
                    ok("MOTOR_HP" not in corr.get("reset_fields", {})
                       and "MOTOR_HP" not in corr.get("dropped_fields", []),
                       f"{series}: MOTOR_HP not needlessly reset/dropped "
                       f"(non-destructive)")
                else:
                    ok(True, f"{series}: PUMP_MATERIAL single-option, "
                             f"non-destructive check skipped")
            else:
                ok(False, f"{series}: no MOTOR_HP options under size {sizes[0]}")
        else:
            ok(True, f"{series}: no ALT_SIZE/MOTOR_HP fields, "
                     f"non-destructive check skipped")

        # --- (4) Invalidation is KEPT and REPORTED (non-destructive) --------
        # Find a size A + HP where that HP is invalid under some other size B,
        # then change A->B and assert the endpoint does NOT silently change the
        # HP: the value is KEPT and reported in `conflicts` with the field(s) it
        # conflicts with and recommended compatible options.
        size_hp = {}
        for s in sizes:
            t = post("/configurations/resolve-state",
                     {"series": series, "selections": {**selections, "ALT_SIZE": s}})
            size_hp[s] = t["allowable_options"].get("MOTOR_HP", [])
        pair = None
        for a in sizes:
            for b in sizes:
                if a == b:
                    continue
                extra = [hp for hp in size_hp[a]
                         if not _in(hp, size_hp[b])]
                if extra:
                    pair = (a, b, extra[0])
                    break
            if pair:
                break

        if pair:
            a, b, hp = pair
            picked = post("/configurations/resolve-state",
                          {"series": series,
                           "selections": {**selections, "ALT_SIZE": a, "MOTOR_HP": hp},
                           "changed_field": "MOTOR_HP"})
            ok(picked["selections"].get("MOTOR_HP") == hp,
               f"{series}: picked MOTOR_HP={hp} valid under size {a}")
            sel_b = dict(picked["selections"])
            sel_b["ALT_SIZE"] = b
            inval = post("/configurations/resolve-state",
                         {"series": series, "selections": sel_b,
                          "changed_field": "ALT_SIZE"})
            # Non-destructive: the incompatible MOTOR_HP is KEPT, not changed.
            ok(inval["selections"].get("MOTOR_HP") == hp,
               f"{series}: incompatible MOTOR_HP KEPT (not silently changed) "
               f"(={inval['selections'].get('MOTOR_HP')})")
            ok("MOTOR_HP" not in inval.get("reset_fields", {})
               and "MOTOR_HP" not in inval.get("dropped_fields", []),
               f"{series}: MOTOR_HP not silently reset/dropped")
            # Reported as a conflict with recommendations.
            conf = {c["field"]: c for c in inval.get("conflicts", [])}
            ok("MOTOR_HP" in conf,
               f"{series}: MOTOR_HP reported in conflicts")
            mh = conf.get("MOTOR_HP", {})
            ok(bool(mh.get("recommended")) and all(
                _in(r, size_hp[b]) for r in mh.get("recommended", [])),
               f"{series}: MOTOR_HP conflict recommends valid options under "
               f"size {b} ({mh.get('recommended')})")
        else:
            # No size differentiates HP for this series - skip honestly.
            ok(True, f"{series}: no size invalidates a motor HP "
                     f"(no differentiating constraint) - invalidation check skipped")

        # --- (5) Resolvability ----------------------------------------------
        # Complete the seeded config by picking the first allowable for any
        # unset field, settle once, then resolve to a PN/SKU.
        st = post("/configurations/resolve-state",
                  {"series": series, "selections": {}})
        sel = dict(st["selections"])
        for fc, opts in st["allowable_options"].items():
            if fc not in sel and opts:
                sel[fc] = opts[0]
        st2 = post("/configurations/resolve-state",
                   {"series": series, "selections": sel})
        sel = dict(st2["selections"])
        for fc, opts in st2["allowable_options"].items():
            if fc not in sel and opts:
                sel[fc] = opts[0]
        payload = {"series": series, "selections": {"SERIES": series, **sel},
                   "segment_codes": {}, "requested_by": "audit_free_config"}
        try:
            r = post("/configured-products/resolve", payload)
            pn = r.get("part_number")
            ok(bool(pn) and "?" not in pn,
               f"{series}: free config resolves to a PN ({pn})")
            ok(r.get("parity_ok") is True,
               f"{series}: resolved PN parity_ok (python==sql)")
        except urllib.error.HTTPError as e:
            ok(False, f"{series}: resolve HTTP {e.code} {e.read().decode()[:120]}")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
