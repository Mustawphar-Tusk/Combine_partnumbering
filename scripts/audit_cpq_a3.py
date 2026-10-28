"""CPQ Adjustment A3 audit - C/F forces review + explicit unresolved list. Self-cleaning.

  1. A quote with a Dean (partial/call_for_price) line reports requires_review=True
     and lists the C/F line as an unresolved 'pricing' item (never priced/$0).
  2. A customization request appears as an unresolved 'customization' item.
  3. A fully-'found' Fybroc-only quote with no customs reports requires_review=False.
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
COMPANY = f"A3 Co {RUN}"


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


def std_sel(family, series):
    _, r = call("POST", f"/families/{family}/configurations/resolve-state",
                body={"series": series, "selections": {}})
    return r.get("selections", {})


def make_quote(family, series):
    _, q = call("POST", f"/families/{family}/quotes",
                body={"site_code": "TEL" if family == "FYBROC" else "IND",
                      "customer_name": COMPANY, "created_by": RUN})
    qid = q["quote_header_id"]
    sel = std_sel(family, series)
    _, line = call("POST", f"/families/{family}/quotes/{qid}/lines",
                   body={"series": series, "selections": {"SERIES": series, **sel},
                         "quantity": 1, "requested_by": RUN})
    return qid, line


def main():
    # Dean quote -> at least a partial (C/F) line.
    dq, dline = make_quote("DEAN", "RA3146")
    lid = dline.get("quote_line_id")
    _, unr = call("GET", f"/families/DEAN/quotes/{dq}/unresolved")
    ok("dean quote requires review", unr and unr.get("requires_review") is True,
       f"count={unr.get('unresolved_count')}")
    pricing_items = [i for i in unr["items"] if i["kind"] == "pricing"]
    ok("C/F line listed as unresolved pricing item", len(pricing_items) >= 1,
       f"{[ (i['pricing_status']) for i in pricing_items]}")
    ok("C/F line not treated as found", all(i["pricing_status"] != "found" for i in pricing_items))

    # Add a customization -> appears as unresolved 'customization'.
    call("POST", f"/families/DEAN/quotes/{dq}/lines/{lid}/customizations",
         body={"grouping": "WET_END", "requested_change": "Custom casing coating"})
    _, unr2 = call("GET", f"/families/DEAN/quotes/{dq}/unresolved")
    cust_items = [i for i in unr2["items"] if i["kind"] == "customization"]
    ok("customization listed as unresolved item", len(cust_items) == 1,
       f"n={len(cust_items)}")
    ok("unresolved count grew by the customization",
       unr2["unresolved_count"] == unr["unresolved_count"] + 1,
       f"{unr['unresolved_count']} -> {unr2['unresolved_count']}")

    # Fybroc found line, no customs -> depends on pricing; assert the shape is honest:
    # requires_review reflects whether any line is non-found.
    fq, fline = make_quote("FYBROC", "1500")
    _, funr = call("GET", f"/families/FYBROC/quotes/{fq}/unresolved")
    fstatus = fline.get("pricing_status")
    if fstatus == "found":
        ok("fully-found Fybroc quote requires_review=False", funr.get("requires_review") is False,
           f"status={fstatus} count={funr.get('unresolved_count')}")
    else:
        ok("non-found Fybroc quote requires_review=True", funr.get("requires_review") is True,
           f"status={fstatus} (line not fully found; honest)")

    cleanup([dq, fq])
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ A3 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(qids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
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
