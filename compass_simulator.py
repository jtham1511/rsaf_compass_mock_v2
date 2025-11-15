#!/usr/bin/env python3
import os, sys, time, json, random, math, argparse, datetime, csv

DEFAULT_CONFIG = {
    "session": {"warmup_seconds": 120, "break_seconds": 120},
    "weights": {"control":0.18,"slalom":0.12,"memory":0.12,"task_manager":0.18,"orientation":0.14,"mathematics":0.10,"technical":0.08,"verbal":0.08},
    "durations_seconds": {"control":420,"slalom":360,"memory":420,"task_manager":480,"orientation":480,"mathematics":420,"technical":420,"verbal":360},
    "levels": {"1":{"label":"Basic","speed":0.9,"span":4,"math":"easy"},
               "2":{"label":"Standard","speed":1.0,"span":6,"math":"mix"},
               "3":{"label":"Hard","speed":1.2,"span":7,"math":"hard"}}
}

# --- Simple single-page PDF writer ---
def write_simple_pdf(path, text_lines, title="Session Summary"):
    import io
    b = io.BytesIO()
    b.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    xref = []
    def obj(s): xref.append(b.tell()); b.write(s)
    font = b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
    content = "BT /F1 12 Tf 50 760 Td 14 TL ".encode()
#    content += f"({title.replace('(','\\(').replace(')','\\)')}) Tj T* ".encode()
#   Changed on 31st Oct 2025 to remove title from PDF content
    safe_title = title.replace("(", "\\(").replace(")", "\\)")
    content += f"({safe_title}) Tj T* ".encode()
    
    y = 746
    for ln in text_lines:
        safe = ln.replace("(", "\\(").replace(")", "\\)")
        content += f"({safe}) Tj T* ".encode()
        y -= 14
        if y < 60: break
    content += b"ET"
    stream = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream\n"
    obj(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    obj(b"2 0 obj << /Type /Pages /Kids [4 0 R] /Count 1 >> endobj\n")
    obj(font)
    obj(stream)
    obj(b"4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >> endobj\n")
    xref_pos = b.tell()
    b.write(f"xref\n0 {len(xref)+1}\n".encode())
    b.write(b"0000000000 65535 f \n")
    for pos in xref: b.write(f"{pos:010d} 00000 n \n".encode())
    b.write(b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n" % (len(xref)+1))
    b.write(f"{xref_pos}\n%%EOF".encode())
    with open(path, "wb") as out: out.write(b.getvalue())

# --- Coaching notes ---
COACHING = {
    "control": [
        "Aim for smooth, small corrections; avoid over-correcting the drift.",
        "Glance, correct, re-center; stabilise before the next input.",
        "Warm-up: 2 min breathing + 1 min slow tracking."
    ],
    "slalom": [
        "Commit early: decide L/R instantly; keep cadence.",
        "Hands in default ready position; reduce think time.",
        "Count rhythm quietly to avoid hesitations."
    ],
    "memory": [
        "Chunk letters into small groups; rehearse last span after each item.",
        "If you blank, skip quickly—don’t reconstruct.",
        "Daily 5-min N-back builds working memory."
    ],
    "task_manager": [
        "Prioritise ticker tasks; sweep secondary tasks in a fixed cycle.",
        "Say task name in your head (T1/T2/T3) to load the rule.",
        "When errors spike, back off speed slightly to recover accuracy."
    ],
    "orientation": [
        "Translate: 'nose-up/down' + 'bank-left/right/level' then choose.",
        "Ignore extra data (e.g., heading) unless relevant to the question.",
        "Visualise the attitude indicator before answering."
    ],
    "mathematics": [
        "SDT: Distance = Speed × (Time/60). Round at end.",
        "Anchor conversions: 15m=0.25h, 30m=0.5h, 45m=0.75h.",
        "Group numbers (tens first), then adjust."
    ],
    "technical": [
        "Review lift/drag/thrust/weight; stall = excessive AoA loss of lift.",
        "Fighter basics: G-limits, corner speed, AoA indexer, energy management.",
        "Eliminate wrong options logically before choosing."
    ],
    "verbal": [
        "Find main idea; ignore extra examples.",
        "Pick options directly supported by the passage.",
        "If split, choose the restatement of the core claim."
    ]
}

def now_ts():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def input_with_rt(prompt):
    t0 = time.perf_counter()
    try: ans = input(prompt)
    except EOFError: ans = ""
    rt = time.perf_counter() - t0
    return ans.strip(), rt

def clamp(a, lo, hi): return max(lo, min(hi, a))

def scaled_score(acc, mean_rt, tgt_rt):
    timing = 100.0 * max(0.0, 1.0 - (mean_rt - tgt_rt)/tgt_rt)
    return clamp((acc*0.8) + (timing*0.2), 0, 100)

def print_break(sec):
    print(f"\n=== Break: {sec//60}m {sec%60}s. Press Enter to continue early. ===")
    t0 = time.time()
    try:
        import select
        while True:
            remaining = sec - (time.time()-t0)
            if remaining <= 0: break
            print(f"\rResuming in {int(remaining)}s... (Enter to resume)", end="")
            r,_,_ = select.select([sys.stdin], [], [], 1.0)
            if r: sys.stdin.readline(); break
        print()
    except Exception:
        time.sleep(sec)

def warmup(sec):
    print("\n=== Warm-up ===\nDo light mental math or deep breathing. Press Enter to start.")
    try: input()
    except EOFError: pass

# ---------- Modules ----------
def mod_control(duration, level):
    print("\n[1] CONTROL — enter integer corrections to cancel drift (+/-).")
    end = time.time() + duration
    trials = []
    while time.time() < end:
        drift = random.randint(-9, 9)
        if drift == 0: drift = random.choice([-2,2])
        ans, rt = input_with_rt(f" Drift {drift:+d} -> correction: ")
        try: corr = int(ans)
        except: corr = 0
        err = abs(drift + corr)
        trials.append((err, rt))
    if trials:
        avg_err = sum(e for e,_ in trials)/len(trials)
        acc = max(0.0, 100.0*(1.0 - avg_err/10.0))
        mean_rt = sum(rt for _,rt in trials)/len(trials)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=1.2/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

def mod_slalom(duration, level):
    print("\n[2] SLALOM — type L/R fast and correct.")
    end = time.time() + duration
    trials = []
    while time.time() < end:
        gate = random.choice(["L","R"])
        ans, rt = input_with_rt(f" Gate {gate} >> ")
        ok = 1 if ans.upper()==gate else 0
        trials.append((ok, rt))
    if trials:
        acc = 100.0* (sum(ok for ok,_ in trials)/len(trials))
        mean_rt = sum(rt for _,rt in trials)/len(trials)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=0.9/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

def mod_memory(duration, level):
    print("\n[3] MEMORY — N-back recall. When prompted, type the letter from span-back; else Enter.")
    span = level["span"]
    end = time.time() + duration
    trials = []; stream=[]
    letters = [chr(i) for i in range(65,91)]
    while time.time() < end:
        cur = random.choice(letters)
        print(f" Stream: {cur}")
        target = stream[-span] if len(stream)>=span else None
        ans, rt = input_with_rt(" Recall? ")
        ok = 1 if (target is None and ans=="") or (target is not None and ans.upper()==target) else 0
        trials.append((ok, rt)); stream.append(cur)
    if trials:
        acc = 100.0* (sum(ok for ok,_ in trials)/len(trials))
        mean_rt = sum(rt for _,rt in trials)/len(trials)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=1.5/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

def mod_task_manager(duration, level):
    print("\n[4] TASK MANAGER — rotate through 3 tasks: add / parity / letter match.")
    end = time.time() + duration
    trials=[]; rts=[]; idx=0
    while time.time() < end:
        idx = (idx+1)%3
        if idx==1:
            a,b = random.randint(10,49), random.randint(10,49)
            ans, rt = input_with_rt(f" T1 {a}+{b}=")
            try: ok = 1 if int(ans)==a+b else 0
            except: ok = 0
        elif idx==2:
            x = random.randint(11,199)
            ans, rt = input_with_rt(f" T2 parity {x}? (E/O) ")
            ok = 1 if (x%2==0 and ans.upper()=="E") or (x%2==1 and ans.upper()=="O") else 0
        else:
            l1,l2 = random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ"), random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
            ans, rt = input_with_rt(f" T3 {l1} vs {l2}? (S/D) ")
            ok = 1 if ((l1==l2 and ans.upper()=="S") or (l1!=l2 and ans.upper()=="D")) else 0
        trials.append(ok); rts.append(rt)
    if trials:
        acc = 100.0*(sum(trials)/len(trials)); mean_rt = sum(rts)/len(rts)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=1.8/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

def mod_orientation(duration, level):
    print("\n[5] ORIENTATION — pick the qualitative attitude description.")
    def desc(pitch, bank):
        up = "nose-UP" if pitch>0 else "nose-DOWN"
        roll = "bank-LEFT" if bank<0 else "bank-RIGHT" if bank>0 else "wings-LEVEL"
        return up + ", " + roll
    end = time.time() + duration
    trials=[]; rts=[]
    while time.time() < end:
        pitch = random.choice([-15,-10,-5,5,10,15])
        bank = random.choice([-30,-15,0,15,30])
        heading = random.choice([0,45,90,135,180,225,270,315])
        correct = desc(pitch, bank)
        choices = [correct,"nose-UP, wings-LEVEL","nose-DOWN, bank-LEFT","nose-DOWN, bank-RIGHT"]
        random.shuffle(choices)
        ans, rt = input_with_rt(f" Pitch={pitch} Bank={bank} Hdg={heading}. Pick {choices} -> ")
        ok = 1 if ans.strip()==correct else 0
        trials.append(ok); rts.append(rt)
    if trials:
        acc = 100.0*(sum(trials)/len(trials)); mean_rt = sum(rts)/len(rts)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=2.0/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

def sdt_question(level):
    speed = random.choice([180,240,300,420])  # kt
    tmin = random.choice([15,24,30,36,45,60])
    if level["math"]=="hard":
        wind = random.choice([-30,-20,-10,10,20,30])
        gs = speed + wind
        dist = gs*(tmin/60.0)
        return f"GS {gs} kt for {tmin} min: distance (NM)? ", round(dist,1)
    else:
        dist = speed*(tmin/60.0)
        return f"{speed} kt for {tmin} min: distance (NM)? ", round(dist,1)

def mental_arith():
    a,b,c = random.randint(11,49), random.randint(11,49), random.randint(2,9)
    return f"({a}+{b})*{c} = ? ", (a+b)*c

def mod_math(duration, level):
    print("\n[6] MATHEMATICS — SDT + mental arithmetic (round SDT to 1 dp).")
    end = time.time() + duration
    trials=[]; rts=[]
    while time.time() < end:
        if random.random()<0.6:
            q, a_true = sdt_question(level)
            ans, rt = input_with_rt(q)
            try: ok = 1 if abs(float(ans)-a_true)<=0.1 else 0
            except: ok = 0
        else:
            q, a_true = mental_arith()
            ans, rt = input_with_rt(q)
            try: ok = 1 if int(ans)==a_true else 0
            except: ok = 0
        trials.append(ok); rts.append(rt)
    if trials:
        acc = 100.0*(sum(trials)/len(trials)); mean_rt = sum(rts)/len(rts)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=2.0/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

TECH_Q = [
    ("Which factor increases lift (all else equal)?", ["higher airspeed","lower density","lower angle of attack","smaller wing"], "higher airspeed"),
    ("What primarily opposes thrust?", ["drag","lift","weight","torque"], "drag"),
    ("What is a stall?", ["engine stop","loss of lift from excessive AoA","overspeed","gyro precession"], "loss of lift from excessive AoA"),
    ("What does an altimeter measure?", ["dynamic pressure","static pressure","temperature","airspeed"], "static pressure"),
    ("What does rudder primarily control?", ["pitch","roll","yaw","speed"], "yaw"),
    # Fighter ops
    ("What does 'G-limit' refer to in a fighter aircraft?", ["maximum structural load factor","fuel consumption rate","gun rate of fire","gravity at altitude"], "maximum structural load factor"),
    ("High AoA manoeuvres increase risk of:", ["compressibility","roll coupling","deep stall","P-factor"], "deep stall"),
    ("Which instrument best shows instantaneous turn performance?", ["HSI","AOA indexer","VVI","Airspeed indicator"], "AOA indexer"),
    ("In a sustained turn, which combination helps maintain energy?", ["high AoA, low throttle","low AoA, high throttle","high AoA, high throttle","idle throttle"], "low AoA, high throttle"),
    ("Corner velocity is associated with:", ["best climb rate","min sink rate","max sustained turn rate","best glide speed"], "max sustained turn rate"),
    ("Energy management in BFM balances:", ["lift vs drag","kinetic vs potential energy","roll vs yaw","pitch vs yaw"], "kinetic vs potential energy"),
    ("If density altitude increases significantly, takeoff distance:", ["decreases","stays same","increases","is unaffected"], "increases"),
    ("Which failure could cause uncommanded roll?", ["pitot blockage","aileron hardover","radio failure","transponder off"], "aileron hardover"),
    ("Approaching pre-stall buffet symptom:", ["IAS rapidly increasing","stick forces lightening","engine surging","altimeter freezing"], "stick forces lightening"),
    ("In an ILS, lateral guidance is via:", ["glideslope","localizer","marker beacon","ADF"], "localizer"),
]

def mod_technical(duration, level):
    print("\n[7] TECHNICAL — aviation/physics + fighter basics (type exact option).")
    end = time.time() + duration
    trials=[]; rts=[]
    while time.time() < end:
        q, opts, correct = random.choice(TECH_Q)
        sh = opts[:]; random.shuffle(sh)
        ans, rt = input_with_rt(f" Q: {q} Options: {sh} -> ")
        ok = 1 if ans.strip().lower()==correct.lower() else 0
        trials.append(ok); rts.append(rt)
    if trials:
        acc = 100.0*(sum(trials)/len(trials)); mean_rt = sum(rts)/len(rts)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=2.0/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

VERBAL_PASSAGES = [
    ("Pilots must balance checklists with situational awareness. Blindly following steps can delay critical actions in dynamic scenarios.",
     "Main caution?", ["Over-reliance on checklists can hurt real-time judgement","Checklists should be memorised","Dynamic scenarios are rare","Ignore procedures"],
     "Over-reliance on checklists can hurt real-time judgement"),
    ("Weather briefings summarise hazards, but local conditions can change rapidly near terrain. Pilots should monitor real-time cues.",
     "Best inference?", ["Briefings replace observation","Terrain can cause micro-weather shifts","Forecasts always match reality","Ignore instruments"],
     "Terrain can cause micro-weather shifts"),
]

def mod_verbal(duration, level):
    print("\n[8] VERBAL — main idea / inference.")
    end = time.time() + duration
    trials=[]; rts=[]
    while time.time() < end:
        passage, q, opts, correct = random.choice(VERBAL_PASSAGES)
        print(" Passage:", passage)
        sh = opts[:]; random.shuffle(sh)
        ans, rt = input_with_rt(f" Q: {q} Options: {sh} -> ")
        ok = 1 if ans.strip().lower()==correct.lower() else 0
        trials.append(ok); rts.append(rt)
    if trials:
        acc = 100.0*(sum(trials)/len(trials)); mean_rt = sum(rts)/len(rts)
    else: acc, mean_rt = 0.0, 3.0
    score = scaled_score(acc, mean_rt, tgt_rt=2.0/level["speed"])
    return {"acc":acc,"mean_rt":mean_rt,"score":score,"n":len(trials)}

# --- History & percentiles ---
def load_past_sessions(limit=10):
    os.makedirs("sessions", exist_ok=True)
    files = sorted([f for f in os.listdir("sessions") if f.startswith("session_") and f.endswith(".json")])
    hist = []
    for fp in files[-limit:]:
        try:
            with open(os.path.join("sessions", fp), "r", encoding="utf-8") as jf:
                data = json.load(jf)
            hist.append(data)
        except Exception:
            pass
    return hist

def percentile_rank(value, series):
    if not series: return None
    less = sum(1 for v in series if v < value)
    equal = sum(1 for v in series if v == value)
    return (less + 0.5*equal) / len(series) * 100.0

def percentiles_against_history(current_results, overall_score):
    hist = load_past_sessions(limit=10)
    if not hist: return {"note":"no_history"}
    modules = list(current_results.keys())
    series = {m: [] for m in modules}; series["_overall"] = []
    for h in hist:
        if "results" not in h or "overall" not in h: continue
        series["_overall"].append(float(h.get("overall", 0.0)))
        for m in modules:
            try: series[m].append(float(h["results"][m]["score"]))
            except Exception: pass
    out = {m: percentile_rank(current_results[m]["score"], series[m]) for m in modules}
    out["_overall"] = percentile_rank(overall_score, series["_overall"])
    return out

def run_session(cfg):
    print("=== RSAF COMPASS-Style Mock (Keyboard) ===")
    lvl = input(" Level 1=Basic 2=Standard 3=Hard [2]: ").strip() or "2"
    if lvl not in cfg["levels"]: lvl = "2"
    level = cfg["levels"][lvl]
    print(f" Selected: {level['label']}")
    warmup(cfg["session"]["warmup_seconds"])
    weights = cfg["weights"]; durs = cfg["durations_seconds"]

    results = {}
    results["control"] = mod_control(durs["control"], level)
    print_break(cfg["session"]["break_seconds"])
    results["slalom"] = mod_slalom(durs["slalom"], level)
    results["memory"] = mod_memory(durs["memory"], level)
    print_break(cfg["session"]["break_seconds"])
    results["task_manager"] = mod_task_manager(durs["task_manager"], level)
    results["orientation"] = mod_orientation(durs["orientation"], level)
    print_break(cfg["session"]["break_seconds"])
    results["mathematics"] = mod_math(durs["mathematics"], level)
    results["technical"] = mod_technical(durs["technical"], level)
    results["verbal"] = mod_verbal(durs["verbal"], level)

    total = sum(results[k]["score"]*weights[k] for k in results)
    band = ("Outstanding" if total>=85 else "Strong" if total>=70 else "Borderline" if total>=55 else "Below target")
    print("\n=== SESSION SUMMARY ===")
    for k,v in results.items():
        print(f" {k:12s}  score={v['score']:.1f}  acc={v['acc']:.1f}%  rt={v['mean_rt']:.2f}s  n={v['n']}")
    print(f" >> OVERALL: {total:.1f}  ({band})")

    # Percentiles
    pct = percentiles_against_history(results, total)
    if isinstance(pct, dict) and pct.get("note")=="no_history":
        print(" Percentiles: (no history yet; will compute from your subsequent runs)")
    else:
        print(" Percentiles vs your last 10 sessions:")
        for k in ["control","slalom","memory","task_manager","orientation","mathematics","technical","verbal"]:
            if pct.get(k) is not None:
                print(f"  {k:12s}: {pct[k]:5.1f}th")
        if pct.get("_overall") is not None:
            print(f"  OVERALL      : {pct['_overall']:5.1f}th")

    # Coaching (weakest two)
    sorted_mods = sorted(results.items(), key=lambda kv: kv[1]["score"])
    weak = [sorted_mods[0][0], sorted_mods[1][0]] if len(sorted_mods)>=2 else [sorted_mods[0][0]]
    print("\nCoaching focus (next 7 days):")
    for m in weak:
        print(f" - {m}:")
        for tip in COACHING.get(m, [])[:3]:
            print(f"    • {tip}")

    # Save logs
    os.makedirs("sessions", exist_ok=True)
    ts = now_ts()
    jpath = f"sessions/session_{ts}.json"
    cpath = f"sessions/session_{ts}.csv"
    payload = {"timestamp":ts, "level":level["label"], "results":results, "overall":total, "band":band}
    with open(jpath, "w", encoding="utf-8") as jf: json.dump(payload, jf, indent=2)
    with open(cpath, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf); w.writerow(["module","score","accuracy_pct","mean_rt_sec","trials"])
        for k,v in results.items(): w.writerow([k, f"{v['score']:.1f}", f"{v['acc']:.1f}", f"{v['mean_rt']:.3f}", v["n"]])
        w.writerow(["OVERALL", f"{total:.1f}", "", "", ""])
    print(f"Saved: {jpath} and {cpath}")

    # PDF summary
    pdf_path = f"sessions/session_{ts}_summary.pdf"
    lines = [f"Level: {level['label']}  Band: {band}  Overall: {total:.1f}"]
    for k,v in results.items():
        lines.append(f"{k:12s}  score={v['score']:.1f}  acc={v['acc']:.1f}%  rt={v['mean_rt']:.2f}s  n={v['n']}")
    lines.append(" ")
    if isinstance(pct, dict) and pct.get("note")!="no_history":
        lines.append("Percentiles vs last 10 sessions:")
        for k in ["control","slalom","memory","task_manager","orientation","mathematics","technical","verbal"]:
            if pct.get(k) is not None:
                lines.append(f"{k:12s}: {pct[k]:.1f}th")
        if pct.get("_overall") is not None:
            lines.append(f"OVERALL      : {pct['_overall']:.1f}th")
    lines.append(" ")
    lines.append("Coaching (next 7 days):")
    for m in weak:
        for tip in COACHING.get(m, [])[:2]:
            lines.append(f"- {m}: {tip}")
    write_simple_pdf(pdf_path, lines, title="RSAF COMPASS Mock — Session Summary")
    print(f"PDF saved: {pdf_path}")

def load_cfg(path):
    cfg = DEFAULT_CONFIG.copy()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            ext = json.load(f)
        for k,v in ext.items():
            if isinstance(v, dict) and k in cfg:
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    args = ap.parse_args()
    cfg = load_cfg(args.config)
    run_session(cfg)

if __name__ == "__main__":
    main()
