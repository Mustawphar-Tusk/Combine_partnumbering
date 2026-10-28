"""CPQ Adjustment A2 audit - per-grouping customization requests. Self-cleaning.

Verifies against a running dev-mock API (default http://127.0.0.1:8080; --base):
  1. Add multiple customization requests to a draft line (>1 per grouping allowed).
  2. List by line and by quote returns them.
  3. Edit a request; remove a request (count drops); draft-only.
  4. Each request retains grouping/field/current value/requested change/notes.
Cleans up the quote + lines + customizations it created.
"""
import json, sys, urllib.error, urllib.request, uuid
import pyodbc

_base = "http://127.0.0.1:8080"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        _base = sys.argv[i + 1]
BASE = _base.rstrip("/") + "/api/v2"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")
RUN = uuid.uuid4().hex[:10]
COMPANY = f"A2 Co {RUN}"
FAMILY, SERIES = "FYBROC", "1500"


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


results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def main():
    _, st = call("POST", f"/families/{FAMILY}/configurations/resolve-state",
                 body={"series": SERIES, "selections": {}})
    sel = st.get("selections", {})
    _, q = call("POST", f"/families/{FAMILY}/quotes",
                body={"site_code": "TEL", "customer_name": COMPANY, "created_by": RUN})
    qid = q.get("quote_header_id")
    _, line = call("POST", f"/families/{FAMILY}/quotes/{qid}/lines",
                   body={"series": SERIES, "selections": {"SERIES": SERIES, **sel},
                         "quantity": 1, "requested_by": RUN})
    lid = line.get("quote_line_id")
    ok("draft line created", lid is not None, f"line={lid}")

    base = f"/families/{FAMILY}/quotes/{qid}/lines/{lid}/customizations"
    # Two requests in the SAME grouping (WET_END) + one in MOTOR.
    st1, c1 = call("POST", base, body={"grouping": "WET_END", "field_code": "CASING_MATERIAL",
                   "current_value": "VR-1", "requested_change": "Hastelloy C casing", "notes": "spec 44-2"})
    st2, c2 = call("POST", base, body={"grouping": "WET_END", "field_code": "IMPELLER_MATERIAL",
                   "current_value": "VR-1", "requested_change": "Titanium impeller"})
    st3, c3 = call("POST", base, body={"grouping": "MOTOR", "requested_change": "575V premium efficiency"})
    ok("add req 1 (201)", st1 == 201, f"status={st1}")
    ok("add req 2 same grouping (201)", st2 == 201, f"status={st2}")
    ok("add req 3 other grouping (201)", st3 == 201, f"status={st3}")
    ok("req retains grouping/field/current/change/notes",
       c1 and c1.get("grouping") == "WET_END" and c1.get("field_code") == "CASING_MATERIAL"
       and c1.get("current_value") == "VR-1" and "Hastelloy" in (c1.get("requested_change") or "")
       and c1.get("notes") == "spec 44-2", str(c1))

    # List by line: 3.
    _, byline = call("GET", base)
    ok("list by line == 3 (multiple per grouping)", byline and len(byline["customizations"]) == 3,
       f"n={len(byline['customizations']) if byline else '?'}")
    we = [c for c in byline["customizations"] if c["grouping"] == "WET_END"]
    ok("two requests in WET_END grouping", len(we) == 2, f"n={len(we)}")

    # List by quote.
    _, byquote = call("GET", f"/families/{FAMILY}/quotes/{qid}/customizations")
    ok("list by quote == 3", byquote and len(byquote["customizations"]) == 3,
       f"n={len(byquote['customizations']) if byquote else '?'}")

    # Edit req 2.
    cid2 = c2["customization_id"]
    st_e, e2 = call("PUT", f"/families/{FAMILY}/quotes/{qid}/customizations/{cid2}",
                    body={"grouping": "WET_END", "field_code": "IMPELLER_MATERIAL",
                          "current_value": "VR-1", "requested_change": "Titanium impeller (balanced)"})
    ok("edit req 2 (200)", st_e == 200 and "balanced" in (e2.get("requested_change") or ""),
       f"status={st_e}")

    # Remove req 3 -> 2 remain.
    cid3 = c3["customization_id"]
    st_r, r3 = call("DELETE", f"/families/{FAMILY}/quotes/{qid}/customizations/{cid3}")
    ok("remove req 3 (200)", st_r == 200, f"status={st_r}")
    _, after = call("GET", base)
    ok("2 remain after remove", after and len(after["customizations"]) == 2,
       f"n={len(after['customizations']) if after else '?'}")

    cleanup([qid], [lid])
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ A2 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(qids, lids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        for lid in lids:
            if lid is not None:
                cur.execute("DELETE FROM quote.QuoteLineCustomization WHERE QuoteLineId = ?", lid)
        for qid in qids:
            if qid is None:
                continue
            cur.execute("DELETE FROM quote.QuoteLineCustomization WHERE QuoteLineId IN "
                        "(SELECT QuoteLineId FROM quote.QuoteLine WHERE QuoteHeaderId = ?)", qid)
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
