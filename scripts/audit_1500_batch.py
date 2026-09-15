"""Exhaustive 1500 batch audit: every field, every selectable option.

Drives the exact two calls the configurator UI makes for the 1500 series and
proves none of them error, for EVERY option of EVERY field:
  1. POST /configurations/resolve-state (set the option from the STD seed)
  2. POST /configured-products/resolve   (resolve + price the settled config)

Also runs a cumulative pass (carrying each pick forward) to catch failures that
only appear in combination. Reports, per field, how many of its options leave a
component at C/F (Contact Factory) so pricing gaps are visible. This exists to
detect the "error to fetch" failures the UI has surfaced - if this audit is
green, the failure is client-side, not server-side.

Requires the API on 127.0.0.1:8080. Exit 0 if no errors, non-zero otherwise.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"
SERIES = "1500"


def post(path, p, timeout=120):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(p).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode()[:600]
    except Exception as e:
        return -1, None, f"{type(e).__name__}: {e}"


def _wait():
    for _ in range(60):
        st, _, _ = post("/configurations/resolve-state",
                        {"series": SERIES, "selections": {}})
        if st == 200:
            return True
        time.sleep(1)
    return False


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    st, seed, err = post("/configurations/resolve-state",
                         {"series": SERIES, "selections": {}})
    if st != 200 or not seed:
        print(f"FAIL: 1500 STD seed failed ({st}) {err}")
        return 1

    base = dict(seed["selections"])
    allow = seed["allowable_options"]
    ordered = seed["ordered_fields"]

    state_errors = []    # (field, value, status, err)
    invalid = []         # (field, value, errors)
    resolve_errors = []  # (field, value, status, err)
    cf_by_field = {}     # field -> {option: [C/F components]}

    n_state = 0
    n_resolve = 0

    # PASS 1 - every option in isolation from the STD seed.
    for fc in ordered:
        for val in allow.get(fc, []):
            n_state += 1
            sel = dict(base)
            sel[fc] = val
            st, data, err = post(
                "/configurations/resolve-state",
                {"series": SERIES, "selections": sel, "changed_field": fc})
            if st != 200:
                state_errors.append((fc, val, st, err)); continue
            if not data.get("valid"):
                invalid.append((fc, val, data.get("errors"))); continue

            rsel = dict(data["selections"])
            codes = {k: v for k, v in data.get("resolved_codes", {}).items() if v}
            n_resolve += 1
            st2, r2, err2 = post(
                "/configured-products/resolve",
                {"series": SERIES, "selections": {"SERIES": SERIES, **rsel},
                 "segment_codes": codes, "requested_by": "audit_1500_batch"})
            if st2 != 200 or r2 is None:
                resolve_errors.append((fc, val, st2, err2)); continue
            cfs = [c["component"] for c in r2.get("component_pricing", [])
                   if c.get("status") == "C/F"]
            if cfs:
                cf_by_field.setdefault(fc, {})[val] = cfs

    # PASS 2 - cumulative (carry each pick forward).
    cum = dict(base)
    cum_errors = []
    for fc in ordered:
        opts = allow.get(fc, [])
        if not opts:
            continue
        cum[fc] = opts[0]
        st, data, err = post(
            "/configurations/resolve-state",
            {"series": SERIES, "selections": cum, "changed_field": fc})
        if st != 200:
            cum_errors.append((fc, opts[0], st, err)); continue
        if not data.get("valid"):
            cum_errors.append((fc, opts[0], "invalid", data.get("errors"))); continue
        cum = dict(data["selections"])

    print("=" * 74)
    print("1500 EXHAUSTIVE BATCH AUDIT")
    print("=" * 74)
    print(f"fields={len(ordered)}  resolve-state calls={n_state}  "
          f"resolve calls={n_resolve}")

    def _dump(title, rows):
        print(f"\n{title}: {len(rows)}")
        for r in rows[:60]:
            print("   ", r)

    _dump("resolve-state ERRORS (non-200)", state_errors)
    _dump("invalid=True states", invalid)
    _dump("resolve (pricing) ERRORS (non-200)", resolve_errors)
    _dump("cumulative-pass ERRORS", cum_errors)

    # Pricing-gap summary (informational, not a failure): which components are
    # C/F and how many option choices leave them C/F.
    comp_cf = {}
    for fc, per_opt in cf_by_field.items():
        for _opt, comps in per_opt.items():
            for c in comps:
                comp_cf[c] = comp_cf.get(c, 0) + 1
    print("\nComponent C/F frequency across 1500 option tests (informational):")
    for comp, n in sorted(comp_cf.items(), key=lambda kv: -kv[1]):
        print(f"   {comp:<28} C/F in {n} tested configs")

    total_err = (len(state_errors) + len(invalid)
                 + len(resolve_errors) + len(cum_errors))
    print("\n" + "=" * 74)
    print(f"RESULT: {total_err} ERRORS")
    print("=" * 74)
    return 0 if total_err == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
