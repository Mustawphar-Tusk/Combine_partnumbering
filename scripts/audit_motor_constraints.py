"""Post-fix BULK VERIFY of Motor Constraints. For each series, sweep multiple
Alt Sizes and assert the endpoint's MOTOR_HP / MOTOR_RPM / FRAME_SIZE options
are a faithful subset of the workbook allow-lists (no illegal values leak).
Also confirm a full valid walk still completes on each series."""
import json, urllib.request, time, pyodbc

URL="http://127.0.0.1:8080/api/v2/families/FYBROC/configurations/evaluate"
def evaluate(series, sel):
    body=json.dumps({"series":series,"selections":sel}).encode()
    req=urllib.request.Request(URL,data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=60) as r: return json.loads(r.read())
for _ in range(40):
    try: evaluate("1500",{}); break
    except Exception: time.sleep(1)

CONN=("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;"
      "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")
cn=pyodbc.connect(CONN); cur=cn.cursor()
pub=cur.execute("SELECT MetadataPublicationId FROM cfg.MetadataPublication WHERE Status='Active'").fetchone()[0]
fam=cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'").fetchone()[0]
SERIES=["1500","1530","1600","1630","2530","3000","5500"]

def scope_for(series):
    r=cur.execute("SELECT DISTINCT SeriesScope FROM cfg.MotorConstraint WHERE MetadataPublicationId=? AND PumpFamilyId=? "
        "AND (SeriesScope=? OR SeriesScope LIKE ? OR SeriesScope LIKE ? OR SeriesScope LIKE ?)",
        pub,fam,series,f"{series} %",f"% {series}",f"% {series} %").fetchone()
    return r[0] if r else None

def mc_hprpm(scope,size):
    return [str(r[0]) for r in cur.execute("SELECT Dimension2Value FROM cfg.MotorConstraint "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND SeriesScope=? AND Dimension1Field='Alt_Size' "
        "AND Dimension2Field='F_MotorHpRpm' AND LOWER(Dimension1Value)=LOWER(?)", pub,fam,scope,size)]
def mc_frames(scope,size):
    return {str(r[0]).strip().lower() for r in cur.execute("SELECT Dimension2Value FROM cfg.MotorConstraint "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND SeriesScope=? AND Dimension1Field='Alt_Size' "
        "AND Dimension2Field='F_Frame_Size' AND LOWER(Dimension1Value)=LOWER(?)", pub,fam,scope,size)}

def walk_to(series, forced, target):
    sel={}
    for _ in range(150):
        d=evaluate(series,sel); cur_f=d.get("current_field")
        if cur_f is None: break
        if target in d.get("allowable_options",{}) and all(f in sel for f in forced):
            return [str(v).strip().lower() for v in d["allowable_options"][target]]
        o=d["allowable_options"].get(cur_f,[]); std=d.get("standard_defaults",{}).get(cur_f)
        pick=forced.get(cur_f) or (std if std in o else (o[0] if o else None))
        if pick is None: break
        sel[cur_f]=pick
    return [str(v).strip().lower() for v in evaluate(series,sel).get("allowable_options",{}).get(target,[])]

P=[0];F=[0];details=[]
def rec(ok,msg):
    P[0]+=ok;F[0]+=(not ok)
    if not ok: details.append(msg)

print("="*92); print("MOTOR CONSTRAINT BULK VERIFY (post-fix)"); print("="*92)
for series in SERIES:
    scope=scope_for(series)
    if not scope: continue
    sizes=[r[0] for r in cur.execute("SELECT DISTINCT Dimension1Value FROM cfg.MotorConstraint "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND SeriesScope=? AND Dimension1Field='Alt_Size' "
        "AND Dimension2Field='F_MotorHpRpm'", pub,fam,scope)][:4]
    hp_ok=rpm_ok=frame_ok=0; hp_tot=rpm_tot=frame_tot=0
    for size in sizes:
        comps=mc_hprpm(scope,size)
        wb_hp={c.split("-",1)[0].strip().lower() for c in comps if "-" in c}
        # HP
        api_hp=set(walk_to(series,{"ALT_SIZE":size},"MOTOR_HP"))
        leak_hp=api_hp-wb_hp
        hp_tot+=1; ok=(len(leak_hp)==0 and len(api_hp)>0); hp_ok+=ok
        rec(ok, f"{series}/{size} HP leak {sorted(leak_hp)}")
        # RPM given a chosen HP (pick an allowed HP)
        if wb_hp:
            hp_pick=sorted(wb_hp, key=lambda x: float(x))[0]
            wb_rpm={c.split("-",1)[1].strip().lower() for c in comps if c.split("-",1)[0].strip().lower()==hp_pick}
            api_rpm=set(walk_to(series,{"ALT_SIZE":size,"MOTOR_HP":hp_pick},"MOTOR_RPM"))
            leak_rpm=api_rpm-wb_rpm
            rpm_tot+=1; ok=(len(leak_rpm)==0 and len(api_rpm)>0); rpm_ok+=ok
            rec(ok, f"{series}/{size} HP={hp_pick} RPM leak {sorted(leak_rpm)} (wb {sorted(wb_rpm)})")
        # Frame
        wb_fr=mc_frames(scope,size)
        api_fr=set(walk_to(series,{"ALT_SIZE":size},"FRAME_SIZE"))
        leak_fr=api_fr-wb_fr
        frame_tot+=1; ok=(len(leak_fr)==0 and len(api_fr)>0); frame_ok+=ok
        rec(ok, f"{series}/{size} FRAME leak {sorted(leak_fr)[:4]}")
    print(f"  {series} (scope={scope!r}): HP {hp_ok}/{hp_tot}  RPM {rpm_ok}/{rpm_tot}  FRAME {frame_ok}/{frame_tot}")

# valid walks still complete
print("\n  valid-walk completion:")
for series in SERIES:
    sel={};steps=0;stall=None
    for _ in range(160):
        d=evaluate(series,sel);cur_f=d.get("current_field")
        if cur_f is None: break
        o=d["allowable_options"].get(cur_f,[]);std=d.get("standard_defaults",{}).get(cur_f)
        pick=std if std in o else (o[0] if o else None)
        if pick is None: stall=cur_f;break
        sel[cur_f]=pick;steps+=1
    print(f"    {series}: {'COMPLETE' if stall is None else 'STALL '+stall} ({steps})")
    rec(stall is None, f"{series} stalled at {stall}")

print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
for d in details[:15]: print("  FAIL:", d)
cn.close()
