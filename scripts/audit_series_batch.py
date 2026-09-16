"""Exhaustive free-edit batch audit for ANY Fybroc series.

Usage:
    python scripts/audit_series_batch.py [SERIES]   (default 1500)

Drives the exact two calls the configurator UI makes, for EVERY option of EVERY
field of the given series:
  1. POST /configurations/resolve-state (set the option from the STD seed)
  2. POST /configured-products/resolve   (resolve + price the settled config)

Also runs a cumulative pass (carrying each pick forward) to catch failures that
only appear in combination, and prints a per-component C/F (Contact Factory)
pricing-gap summary. If this audit is green, any UI "error to fetch" for the
series is client-side, not server-side.

Requires the API on 127.0.0.1:8080. Exit 0 if no errors, non-zero otherwise.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"


def post(path, p, timeout=300):
    # Generous timeout: the 5500 (vertical) resolve/pricing path can take several
    # seconds per call, and under a back-to-back batch the single dev API worker
    # serializes requests - a short client timeout would report a spurious error
    # for a call the server is still (correctly) processing.
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


def _wait(series):
    for _ in range(60):
        st, _, _ = post("/configurations/resolve-state",
                        {"series": series, "selections": {}})
        if st == 200:
            return True
        time.sleep(1)
    return False


def _sample_options(opts, cap):
    """For very large option lists (e.g. LENGTH has 183 options), test a
    representative subset so the exhaustive matrix stays bounded: keep the
    first, last, and an evenly-spaced sample in between, up to `cap`. Fields
    at or under the cap are tested in full. Returns (subset, sampled?)."""
    n = len(opts)
    if cap <= 0 or n <= cap:
        return opts, False
    idxs = sorted(set([0, n - 1] +
                      [round(i * (n - 1) / (cap - 1)) for i in range(cap)]))
    return [opts[i] for i in idxs], True


def run_series(series, cap=40):
    st, seed, err = post("/configurations/resolve-state",
                         {"series": series, "selections": {}})
    if st != 200 or not seed:
        print(f"FAIL: {series} STD seed failed ({st}) {err}")
        return 1
    if not seed.get("valid"):
        print(f"FAIL: {series} seed valid=False errors={seed.get('errors')}")
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
    sampled_fields = []

    # PASS 1 - every option in isolation from the STD seed (large fields sampled).
    for fc in ordered:
        opts_all = allow.get(fc, [])
        opts, was_sampled = _sample_options(opts_all, cap)
        if was_sampled:
            sampled_fields.append((fc, len(opts_all), len(opts)))
        for val in opts:
            n_state += 1
            sel = dict(base)
            sel[fc] = val
            st, data, err = post(
                "/configurations/resolve-state",
                {"series": series, "selections": sel, "changed_field": fc})
            if st != 200:
                state_errors.append((fc, val, st, err)); continue
            if not data.get("valid"):
                invalid.append((fc, val, data.get("errors"))); continue

            rsel = dict(data["selections"])
            codes = {k: v for k, v in data.get("resolved_codes", {}).items() if v}
            n_resolve += 1
            st2, r2, err2 = post(
                "/configured-products/resolve",
                {"series": series, "selections": {"SERIES": series, **rsel},
                 "segment_codes": codes, "requested_by": "audit_series_batch"})
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
            {"series": series, "selections": cum, "changed_field": fc})
        if st != 200:
            cum_errors.append((fc, opts[0], st, err)); continue
        if not data.get("valid"):
            cum_errors.append((fc, opts[0], "invalid", data.get("errors"))); continue
        cum = dict(data["selections"])

    print("=" * 74)
    print(f"{series} EXHAUSTIVE BATCH AUDIT")
    print("=" * 74)
    print(f"fields={len(ordered)}  resolve-state calls={n_state}  "
          f"resolve calls={n_resolve}  (option cap={cap})")
    if sampled_fields:
        print("large fields sampled (tested subset, not every option):")
        for fc, total, took in sampled_fields:
            print(f"   {fc}: {took} of {total} options")

    def _dump(title, rows):
        print(f"\n{title}: {len(rows)}")
        for r in rows[:60]:
            print("   ", r)

    _dump("resolve-state ERRORS (non-200)", state_errors)
    _dump("invalid=True states", invalid)
    _dump("resolve (pricing) ERRORS (non-200)", resolve_errors)
    _dump("cumulative-pass ERRORS", cum_errors)

    comp_cf = {}
    for _fc, per_opt in cf_by_field.items():
        for _opt, comps in per_opt.items():
            for c in comps:
                comp_cf[c] = comp_cf.get(c, 0) + 1
    print(f"\nComponent C/F frequency across {series} option tests (informational):")
    for comp, n in sorted(comp_cf.items(), key=lambda kv: -kv[1]):
        print(f"   {comp:<28} C/F in {n} tested configs")

    total_err = (len(state_errors) + len(invalid)
                 + len(resolve_errors) + len(cum_errors))
    print("\n" + "=" * 74)
    print(f"RESULT ({series}): {total_err} ERRORS")
    print("=" * 74)
    return 0 if total_err == 0 else 2


def main():
    series = sys.argv[1] if len(sys.argv) > 1 else "1500"
    # Optional 2nd arg = per-field option cap (0 = no cap, test every option).
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    if not _wait(series):
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1
    return run_series(series, cap=cap)


if __name__ == "__main__":
    sys.exit(main())
