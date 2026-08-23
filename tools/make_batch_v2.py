"""BlindLab v2 - ladder batch generator. ADMISSIONS CLOSED 2026-08-23:
requeue-only tranches drain the admitted days to rung 30 (11:55).
One frozen frame per round. No disguise of price (real values), pair hidden,
dates week-shifted to anchor (weekday+clock preserved, shown in EST).
Ladder: rung 1 = 9:30 AM EST, +5 min per rung, last 11:55.
Skip requeues day at next rung after >=100 rounds OR >=14 days (first).
50 rounds/batch: 42 fresh + 8 consistency re-deals (dups of rounds 1-15).
Sealed keys hold sym/day/rung only; outcomes computed from npz at reveal.
"""
import numpy as np, json, random, os, datetime, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = "NASUSD,U30USD,SPXUSD,XAUUSD,USOUSD,EURUSD,GBPUSD,USDCAD,USDJPY,AUDUSD".split(',')
BATCH_FRESH, BATCH_REDEAL = 42, 8
REQUEUE_CAP = BATCH_FRESH               # admissions closed - requeue-only
DECK_PROB = 0.7
CTX_DAYS = 10
EST_OFF = 7 * 3600                      # server = EST+7
ANCHOR = datetime.datetime(2023, 6, 5).timestamp()
WEEK = 7 * 86400
RUNG1_H, RUNG1_M = 16, 30               # server clock at rung 1
MAX_RUNG = 30                           # 16:30 .. 18:55 server = 9:30 .. 11:55 EST
TODAY = datetime.date.today()

data = {}
for s in SYMS:
    z = np.load(os.path.join(HERE, s + "_M5.npz"))
    data[s] = (z['time'], z['o'], z['h'], z['l'], z['c'])

deck = json.load(open(os.path.join(HERE, "deck_days.json")))
seed = json.load(open(os.path.join(HERE, "ladder_seed.json")))

# ---- ladder state ------------------------------------------------------
lad_path = os.path.join(HERE, "ladder_state.json")
if os.path.exists(lad_path):
    lad = json.load(open(lad_path))
else:
    lad = {"round_seq": 50, "next_num": 1, "days": {}, "dealt": []}
    for tag, v in seed["rung1_done"].items():
        lad["days"][tag] = {"rung_next": 2, "last_skip_seq": 50 if v["source"] == "phone-v1" else 0,
                            "last_skip_date": "2026-08-18", "status": "open"}
    for tag in seed["excluded_contaminated"]:
        lad["days"][tag] = {"rung_next": 0, "status": "excluded"}
v1_state = json.load(open(os.path.join(HERE, "state.json")))
blocked = set(lad["days"]) | set(v1_state["used"])
import glob as _g
dealt_pairs = set()
for _p in _g.glob(os.path.join(HERE, "keys", "L*.json")):
    _k = json.load(open(_p))
    blocked.add(f"{_k['sym']}|{_k['day']}")
    dealt_pairs.add((f"{_k['sym']}|{_k['day']}", _k.get("rung", 1)))

def day_bounds(sym, day_epoch, rung):
    t = data[sym][0]
    freeze = day_epoch + RUNG1_H * 3600 + RUNG1_M * 60 + (rung - 1) * 300
    ctx_from = freeze - CTX_DAYS * 86400
    if ctx_from < t[0] or freeze + 6 * 3600 > t[-1]:
        return None
    c0, c1 = np.searchsorted(t, ctx_from), np.searchsorted(t, freeze, 'left')
    # bar OPEN times: last bar must OPEN at freeze-300 (i.e. close exactly at freeze)
    if c1 - c0 < 800 or int(t[c1 - 1]) != freeze - 300:
        return None
    return int(c0), int(c1), freeze

def est_label(rung):
    m = 9 * 60 + 30 + (rung - 1) * 5
    h12 = (m // 60 - 1) % 12 + 1
    return f"{h12}:{m % 60:02d} AM EST" if m // 60 < 12 else f"{h12}:{m % 60:02d} PM EST"

rng = random.Random(20260822 + lad['next_num'])   # varies per run - no repeated shuffles

# ---- requeue-eligible days (>=100 rounds AND >=14 days, whichever later) ----
elig = []
for tag, v in lad["days"].items():
    if v.get("status") != "open" or v.get("rung_next", 0) < 2 or v["rung_next"] > MAX_RUNG:
        continue
    d0 = datetime.date.fromisoformat(v["last_skip_date"].replace(".", "-"))
    if (TODAY - d0).days >= 14 or lad["round_seq"] - v["last_skip_seq"] >= 100:
        elig.append(tag)
rng.shuffle(elig)

rounds, keys = [], []
def deal(sym, day_s, rung, from_deck, redeal_of=None):
    day = datetime.datetime.strptime(day_s, "%Y.%m.%d")
    day_epoch = int(day.timestamp() // 86400 * 86400)
    b = day_bounds(sym, day_epoch, rung)
    if b is None:
        return False
    c0, c1, freeze = b
    t, o, h, l, c = data[sym]
    shift = int((freeze - ANCHOR) // WEEK) * WEEK + EST_OFF
    ref = float(o[c1 - 1])
    dig = 5 if ref < 50 else (3 if ref < 500 else 2)
    rid = f"L{lad['next_num']:03d}"
    lad['next_num'] += 1
    bars = [[int(t[i]) - shift, round(float(o[i]), dig), round(float(h[i]), dig),
             round(float(l[i]), dig), round(float(c[i]), dig)] for i in range(c0, c1)]
    rounds.append({"id": rid, "f": est_label(rung), "bars": bars})
    keys.append({"id": rid, "sym": sym, "day": day_s, "rung": rung, "freeze_server": freeze,
                 "shift": shift, "deck": from_deck, "redeal_of": redeal_of})
    return True

# requeued days first (none expected before 2026-09-01)
n_requeue = 0
for tag in elig:
    if len(rounds) >= min(BATCH_FRESH, REQUEUE_CAP):
        break
    if (tag, lad["days"][tag]["rung_next"]) in dealt_pairs:
        continue                        # this exact frame already staged/dealt
    sym, day_s = tag.split("|")
    if sym in data and deal(sym, day_s, lad["days"][tag]["rung_next"], True):
        dealt_pairs.add((tag, lad["days"][tag]["rung_next"]))
        n_requeue += 1

if not rounds:
    print("LADDER DRAINED - no eligible days; campaign complete, run the final reveal")
    raise SystemExit(0)
n_redeal = max(2, round(len(rounds) * 0.16)) if len(rounds) >= 12 else min(2, len(rounds))
if len(rounds) < BATCH_FRESH:
    print(f"short tranche: only {len(rounds)} eligible requeues")
# consistency re-deals: dup frames from the front into the back half
srcs = rng.sample(range(min(15, len(rounds))), min(n_redeal, len(rounds)))
lo = max(1, min(30, len(rounds) - n_redeal))
slots = sorted(rng.sample(range(lo, len(rounds) + len(srcs)), len(srcs)))
for slot, si in zip(slots, srcs):
    src = rounds[si]
    rid = f"L{lad['next_num']:03d}"
    lad['next_num'] += 1
    rounds.insert(slot, {"id": rid, "f": src["f"], "d": src["id"]})
    sk = next(k for k in keys if k["id"] == src["id"])
    keys.append({"id": rid, "sym": sk["sym"], "day": sk["day"], "rung": sk["rung"],
                 "freeze_server": sk["freeze_server"], "shift": sk["shift"],
                 "deck": sk["deck"], "redeal_of": src["id"]})

for i, r in enumerate(rounds):
    lad["dealt"].append({"id": r["id"], "seq": lad["round_seq"] + i + 1, "date": str(TODAY)})
lad["round_seq"] += len(rounds)

os.makedirs(os.path.join(HERE, "keys"), exist_ok=True)
for k in keys:
    json.dump(k, open(os.path.join(HERE, "keys", k["id"] + ".json"), "w"))
json.dump(lad, open(lad_path, "w"), indent=1)
print(f"batch: {len(rounds)} rounds = {n_requeue} requeued + {len(srcs)} re-deals (admissions closed)")
print("ids", rounds[0]["id"], "..", f"L{lad['next_num']-1:03d}")

tr = f"{lad.get('tranche_next', 3):03d}"
lad['tranche_next'] = lad.get('tranche_next', 3) + 1
json.dump(lad, open(lad_path, "w"), indent=1)
os.makedirs(os.path.join(HERE, "public", "t"), exist_ok=True)
tpath = os.path.join(HERE, "public", "t", tr + ".json")
json.dump(rounds, open(tpath, "w"), separators=(',', ':'))
man_path = os.path.join(HERE, "public", "t", "index.json")
man = json.load(open(man_path)) if os.path.exists(man_path) else {"tranches": []}
man["tranches"].append({"t": tr, "ids": [r["id"] for r in rounds]})
json.dump(man, open(man_path, "w"))
LWC = open(os.path.join(HERE, "lwc.js"), encoding="utf-8").read()
TPL = open(os.path.join(HERE, "trainer_v2_template.html"), encoding="utf-8").read()
page = TPL.replace("__LWC__", LWC)
out = os.path.join(HERE, "public", "index.html")
open(out, "w", encoding="utf-8").write(page)
print(f"tranche {tr}: t/{tr}.json {os.path.getsize(tpath)//1024} KB; index.html {os.path.getsize(out)//1024} KB")
