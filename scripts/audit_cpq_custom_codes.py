"""CPQ A4 audit - governed per-grouping custom-code mirror. Self-cleaning, FULL.

Verifies against a running dev-mock API (default http://127.0.0.1:8080; --base):
  1. Reuse determinism: same spec -> same code; different spec -> different,
     strictly-incrementing code (next-after-max).
  2. Per-grouping independence: the same spec in two groupings mints from each
     grouping's own sequence.
  3. Width / radix: every minted code is fixed-width base-36 (0-9A-Z) == the
     grouping's authoritative ExpectedWidth.
  4. Next-after-max: a minted code decodes to realMax+1 (strictly above every
     real code) for a grouping with room; a full grouping (e.g. BASEPLATE 'ZZ')
     fails closed (409), never collides.
  5. NO real-custom collision anywhere (DB invariant; fails closed).
  6. Authoritative PN byte-UNCHANGED: a Dean resolve PN before == after minting.
Cleans up every cfg.CustomSegmentCode row it created.

Usage: uv run python scripts/audit_cpq_custom_codes.py [--base URL]
"""
import json, sys, urllib.error, urllib.request, uuid, hashlib
import pyodbc

_base = "http://127.0.0.1:8080"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        _base = sys.argv[i + 1]
BASE = _base.rstrip("/") + "/api/v2"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")
RUN = uuid.uuid4().hex[:8]
DIGITS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def call(method, path, *, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw.strip() else None)


def b36(code):
    n = 0
    for ch in code:
        n = n * 36 + "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ".index(ch)
    return n


results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def real_max(seg):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        mx = cur.execute("SELECT MAX(SegmentValue) FROM stg.SegmentCombinationImport "
                         "WHERE FamilyCode='DEAN' AND SegmentCode=?", seg).fetchval()
        return mx
    finally:
        c.close()


def mint(seg, spec):
    return call("POST", "/families/DEAN/custom-segment-codes",
                body={"segment_code": seg, "spec_text": spec})


def main():
    # Authoritative Dean PN BEFORE (byte-unchanged check).
    _, se = call("POST", "/families/DEAN/configurations/resolve-state",
                 body={"series": "RA3146", "selections": {}})
    sel = se.get("selections", {})
    _, r_before = call("POST", "/families/DEAN/configured-products/resolve",
                       body={"series": "RA3146", "selections": {"SERIES": "RA3146", **sel}})
    pn_before = r_before.get("part_number")

    spec_a = f"Hastelloy C wet end {RUN}"
    spec_b = f"Titanium wet end {RUN}"

    wmax = real_max("WET_END_OPTIONS")
    st1, m1 = mint("WET_END_OPTIONS", spec_a)
    ok("mint 201/200", st1 == 200, f"status={st1}")
    code_a = m1.get("custom_code")
    ok("minted code is width-4 base-36", code_a and len(code_a) == 4 and set(code_a) <= DIGITS, code_a)
    ok("minted = realMax+1 (next-after-max)", b36(code_a) == b36(wmax) + 1,
       f"{code_a}({b36(code_a)}) vs realMax {wmax}({b36(wmax)})+1")
    ok("first mint not existing", m1.get("was_existing") is False)

    _, m1b = mint("WET_END_OPTIONS", spec_a)
    ok("reuse same spec -> same code", m1b.get("custom_code") == code_a and m1b.get("was_existing") is True,
       f"{m1b.get('custom_code')}")

    _, m2 = mint("WET_END_OPTIONS", spec_b)
    code_b = m2.get("custom_code")
    ok("different spec -> strictly incrementing code", b36(code_b) == b36(code_a) + 1,
       f"{code_a} -> {code_b}")

    # Per-grouping independence: same spec in IMPELLER mints from ITS sequence.
    imax = real_max("IMPELLER_OPTIONS")
    _, mi = mint("IMPELLER_OPTIONS", spec_a)
    code_i = mi.get("custom_code")
    ok("per-grouping independence (IMPELLER own sequence)",
       code_i and len(code_i) == 2 and b36(code_i) == b36(imax) + 1,
       f"IMPELLER {code_i}({b36(code_i) if code_i else '?'}) vs realMax {imax}+1")

    # Full grouping fails closed (BASEPLATE real max 'ZZ').
    st_full, full = mint("BASEPLATE_OPTIONS", spec_a)
    ok("full grouping fails closed (409)", st_full == 409, f"status={st_full}")

    # Authoritative PN byte-UNCHANGED after minting.
    _, r_after = call("POST", "/families/DEAN/configured-products/resolve",
                      body={"series": "RA3146", "selections": {"SERIES": "RA3146", **sel}})
    ok("authoritative PN byte-unchanged", r_after.get("part_number") == pn_before,
       f"{pn_before} == {r_after.get('part_number')}")

    # Library lists the minted codes.
    _, lib = call("GET", "/families/DEAN/custom-segment-codes?segment_code=WET_END_OPTIONS")
    libcodes = {x["custom_code"] for x in lib.get("custom_codes", [])}
    ok("library lists minted WET_END codes", {code_a, code_b} <= libcodes, str(sorted(libcodes))[:80])

    # DB invariant: no SegmentValue collision between real and custom per (family, grouping).
    collisions = collision_count()
    ok("NO real-custom collision anywhere", collisions == 0, f"collisions={collisions}")

    cleanup()
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ A4 CUSTOM-CODE AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def collision_count():
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        return c.cursor().execute(
            "SELECT COUNT(*) FROM cfg.CustomSegmentCode csc "
            "JOIN stg.SegmentCombinationImport sci "
            "  ON sci.FamilyCode = csc.FamilyCode AND sci.SegmentCode = csc.SegmentCode "
            " AND sci.SegmentValue = csc.SegmentValue").fetchval()
    finally:
        c.close()


def cleanup():
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        c.cursor().execute("DELETE FROM cfg.CustomSegmentCode WHERE SpecText LIKE ?", f"%{RUN}%")
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
