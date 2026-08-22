"""BlindLab phone trainer - batch generator.
Reads *_M5.npz + deck_days.json, cuts disguised frozen rounds, writes trainer.html
(sealed: continuations stay in keys/, never in the page)."""
import numpy as np, json, random, os, datetime, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SYMS = "NASUSD,U30USD,SPXUSD,XAUUSD,USOUSD,EURUSD,GBPUSD,USDCAD,USDJPY,AUDUSD".split(',')
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 10
DECK_PROB = 0.7
CTX_DAYS = 10
FUT_HOURS = 30
FREEZE_H, FREEZE_M = 16, 30            # server = 9:30 AM EST
ANCHOR = datetime.datetime(2023, 6, 5).timestamp()
WEEK = 7 * 86400

data = {}
for s in SYMS:
    z = np.load(os.path.join(HERE, s + "_M5.npz"))
    data[s] = (z['time'], z['o'], z['h'], z['l'], z['c'])

deck_path = os.path.join(HERE, "deck_days.json")
deck = json.load(open(deck_path)) if os.path.exists(deck_path) else []

def day_bounds(sym, day_epoch):
    t = data[sym][0]
    freeze = day_epoch + FREEZE_H * 3600 + FREEZE_M * 60
    ctx_from = freeze - CTX_DAYS * 86400
    fut_to = freeze + FUT_HOURS * 3600
    if ctx_from < t[0] or fut_to > t[-1]:
        return None
    c0, c1 = np.searchsorted(t, ctx_from), np.searchsorted(t, freeze, 'right')
    f1 = np.searchsorted(t, fut_to, 'right')
    if c1 - c0 < 800 or f1 - c1 < 12:
        return None
    return (int(c0), int(c1)), (int(c1), int(f1))

state_path = os.path.join(HERE, "state.json")
state = json.load(open(state_path)) if os.path.exists(state_path) else {"next_id": 1, "used": []}
rng = random.Random()

rounds, keys = [], []
attempts = 0
while len(rounds) < BATCH and attempts < 5000:
    attempts += 1
    from_deck = bool(deck) and rng.random() < DECK_PROB
    if from_deck:
        sym, day_s = rng.choice(deck)
        if sym not in data:
            continue
        day = datetime.datetime.strptime(day_s, "%Y.%m.%d")
        day_epoch = int(day.timestamp() // 86400 * 86400)
    else:
        sym = rng.choice(SYMS)
        t = data[sym][0]
        ts = int(rng.choice(t[3000:-3000]))
        d = datetime.datetime.utcfromtimestamp(ts)
        if d.weekday() > 4:
            continue
        day_epoch = ts // 86400 * 86400
        day = datetime.datetime.utcfromtimestamp(day_epoch)
    tag = f"{sym}|{day:%Y.%m.%d}"
    if tag in state["used"]:
        continue
    b = day_bounds(sym, day_epoch)
    if b is None:
        continue
    (c0, c1), (f0, f1) = b
    t, o, h, l, c = data[sym]
    factor = round(10 ** (rng.uniform(-0.45, 0.40)), 4)
    freeze = day_epoch + FREEZE_H * 3600 + FREEZE_M * 60
    shift = int((freeze - ANCHOR) // WEEK) * WEEK
    ref = float(o[c1 - 1]) * factor
    dig = 5 if ref < 50 else (3 if ref < 500 else 2)
    def bars(i0, i1):
        return [[int(t[i]) - shift, round(float(o[i]) * factor, dig), round(float(h[i]) * factor, dig),
                 round(float(l[i]) * factor, dig), round(float(c[i]) * factor, dig)] for i in range(i0, i1)]
    rid = f"P{state['next_id']:03d}"
    state['next_id'] += 1
    state['used'].append(tag)
    rounds.append({"id": rid, "bars": bars(c0, c1)})
    keys.append({"id": rid, "sym": sym, "day": f"{day:%Y.%m.%d}", "factor": factor,
                 "shift": shift, "deck": from_deck, "continuation": bars(f0, f1)})

os.makedirs(os.path.join(HERE, "keys"), exist_ok=True)
for k in keys:
    json.dump(k, open(os.path.join(HERE, "keys", k["id"] + ".json"), "w"))
json.dump(state, open(state_path, "w"))
deck_n = sum(1 for k in keys if k["deck"])
print(f"batch: {len(rounds)} rounds ({deck_n} deck / {len(rounds)-deck_n} random)  ids {rounds[0]['id']}..{rounds[-1]['id']}")

LWC = open(os.environ.get("LWC_PATH", os.path.join(HERE, "lwc.js")), encoding="utf-8").read()

page = """<title>BlindLab Trainer</title>
<style>
:root{--bg:#F5F7F6;--card:#FFF;--ink:#17211D;--mut:#5C6B64;--line:#D8E0DB;--up:#0E8A6D;--dn:#C6473E}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#101614;--card:#161D1A;--ink:#E7EDE9;--mut:#93A29A;--line:#263029;--up:#3FBF9B;--dn:#E06B5F}}
:root[data-theme="dark"]{--bg:#101614;--card:#161D1A;--ink:#E7EDE9;--mut:#93A29A;--line:#263029;--up:#3FBF9B;--dn:#E06B5F}
*{box-sizing:border-box}body{background:var(--bg);color:var(--ink);font:15px/1.45 system-ui;margin:0;padding:10px;display:flex;justify-content:center}
.app{width:100%;max-width:440px}
.top{display:flex;justify-content:space-between;align-items:center;padding:4px 2px 8px;font-size:13px}
.top b{font-size:15px}.mut{color:var(--mut)}
#chart{border:1px solid var(--line);border-radius:10px;overflow:hidden;background:var(--card);height:46vh;min-height:300px}
.row{display:flex;gap:8px;margin-top:8px}
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:10px}
button{height:46px;font-size:14px;border:1.5px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;font-family:inherit}
button.on{border-color:var(--up);background:var(--up);color:#fff}
button.side.on.sell{border-color:var(--dn);background:var(--dn)}
button.skipb{color:var(--mut)}
button.commit{background:var(--up);color:#fff;border:none;font-weight:600;height:50px;flex:1}
select{height:46px;border:1.5px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;flex:1;font-size:14px;padding:0 8px}
.done{text-align:center;padding:30px 10px}
.attr{text-align:center;font-size:11px;color:var(--mut);padding:10px 0 4px}
.attr a{color:var(--mut)}
</style>
<div class="app">
<div class="top"><b id="prog"></b><span class="mut">&#128274; sealed &middot; M5+SMA20 &middot; entry = market @freeze</span></div>
<div id="chart"></div>
<div class="grid">
<button id="b_sma">SMA 20</button><button id="b_low">Buy low</button><button id="b_ts">T&amp;S</button>
</div>
<div class="row">
<button id="b_buy" class="side" style="flex:1">BUY</button>
<button id="b_sell" class="side" style="flex:1">SELL</button>
<button id="b_skip" class="skipb" style="flex:1">Skip</button>
</div>
<div class="row">
<select id="guess"><option value="">instrument guess...</option>
<option>NASUSD</option><option>U30USD</option><option>SPXUSD</option><option>GOLD</option><option>OIL</option>
<option>EURUSD</option><option>GBPUSD</option><option>USDCAD</option><option>USDJPY</option><option>AUDUSD</option></select>
</div>
<div class="row"><button class="commit" id="commit">Commit &rarr; next</button></div>
<div class="done" id="done" style="display:none">
<p style="font-size:17px;font-weight:600">Batch complete</p>
<p class="mut" id="donesub"></p>
<div class="row"><button class="commit" id="copy">Copy calls</button></div>
<p class="mut" style="font-size:12px">Paste the blob to Claude. Sealed until the reveal.</p>
</div>
<div class="attr">chart by <a href="https://www.tradingview.com/">TradingView</a> lightweight-charts</div>
</div>
<script>__LWC__</script>
<script>
const ROUNDS=__ROUNDS__;
const LS='blindlab_calls_v1';
let calls=JSON.parse(localStorage.getItem(LS)||'{}');
let idx=ROUNDS.findIndex(r=>!calls[r.id]); if(idx<0) idx=ROUNDS.length;
let setup=null, side=null;
const el=id=>document.getElementById(id);
const chartEl=el('chart');
const chart=LightweightCharts.createChart(chartEl,{
  layout:{background:{color:'transparent'},textColor:getComputedStyle(document.body).color,fontSize:11},
  rightPriceScale:{visible:false},leftPriceScale:{visible:false},
  timeScale:{timeVisible:true,secondsVisible:false,borderVisible:false},
  grid:{vertLines:{visible:false},horzLines:{visible:false}},
  handleScroll:true,handleScale:true,crosshair:{mode:0}});
const cs=chart.addCandlestickSeries({upColor:'#1D9E75',downColor:'#D85A30',wickUpColor:'#0F6E56',wickDownColor:'#993C1D',borderVisible:false,priceLineVisible:false,lastValueVisible:false});
const sma=chart.addLineSeries({color:'#BA7517',lineWidth:2,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
let lines=[];
function show(){
  if(idx>=ROUNDS.length){document.querySelectorAll('.grid').forEach(x=>x.style.display='none');
    document.querySelectorAll('.row').forEach(x=>x.style.display='none');
    el('chart').style.display='none';el('done').style.display='block';
    el('done').querySelector('.row').style.display='flex';
    el('donesub').textContent=Object.keys(calls).length+' calls saved on this phone';
    el('prog').textContent='done';return;}
  const r=ROUNDS[idx];
  el('prog').textContent='Round '+(idx+1)+' / '+ROUNDS.length;
  const bars=r.bars.map(b=>({time:b[0],open:b[1],high:b[2],low:b[3],close:b[4]}));
  cs.setData(bars);
  const cl=r.bars.map(b=>b[4]);const sm=[];let s=0;
  for(let i=0;i<cl.length;i++){s+=cl[i];if(i>=20)s-=cl[i-20];if(i>=19)sm.push({time:r.bars[i][0],value:s/20});}
  sma.setData(sm);
  chart.timeScale().setVisibleLogicalRange({from:bars.length-90,to:bars.length+4});
  setup=null;side=null;el('guess').value='';
  document.querySelectorAll('button').forEach(b=>b.classList.remove('on','sell'));
  lines.forEach(l=>cs.removePriceLine(l));lines=[];
}
function pick(btn,val){setup=val;['b_sma','b_low','b_ts'].forEach(i=>el(i).classList.remove('on'));btn.classList.add('on');}
el('b_sma').onclick=()=>pick(el('b_sma'),'SMA20');
el('b_low').onclick=()=>pick(el('b_low'),'BuyLow');
el('b_ts').onclick=()=>pick(el('b_ts'),'T&S');
function drawTrade(){
  lines.forEach(l=>cs.removePriceLine(l));lines=[];
  if(!side||side==='SKIP')return;
  const r=ROUNDS[idx],n=r.bars.length;
  const entry=r.bars[n-1][4];
  const sl=side==='BUY'?Math.min(r.bars[n-1][3],r.bars[n-2][3]):Math.max(r.bars[n-1][2],r.bars[n-2][2]);
  const tp=side==='BUY'?entry+(entry-sl):entry-(sl-entry);
  lines.push(cs.createPriceLine({price:entry,color:'#888',lineWidth:1,lineStyle:0,title:'entry'}));
  lines.push(cs.createPriceLine({price:sl,color:'#D85A30',lineWidth:1,lineStyle:2,title:'SL'}));
  lines.push(cs.createPriceLine({price:tp,color:'#1D9E75',lineWidth:1,lineStyle:2,title:'TP'}));
}
el('b_buy').onclick=()=>{side='BUY';el('b_buy').classList.add('on');el('b_sell').classList.remove('on','sell');el('b_skip').classList.remove('on');drawTrade();};
el('b_sell').onclick=()=>{side='SELL';el('b_sell').classList.add('on','sell');el('b_buy').classList.remove('on');el('b_skip').classList.remove('on');drawTrade();};
el('b_skip').onclick=()=>{side='SKIP';el('b_skip').classList.add('on');el('b_buy').classList.remove('on');el('b_sell').classList.remove('on','sell');lines.forEach(l=>cs.removePriceLine(l));lines=[];};
el('commit').onclick=()=>{
  const g=el('guess').value;
  if(!side){alert('Pick BUY / SELL or Skip');return;}
  if(side!=='SKIP'&&!setup){alert('Which setup?');return;}
  if(!g){alert('Instrument guess first');return;}
  const r=ROUNDS[idx];
  calls[r.id]={call:side==='SKIP'?'skip':setup+'/'+side,guess:g,t:new Date().toISOString().slice(0,16)};
  localStorage.setItem(LS,JSON.stringify(calls));
  idx++;show();
};
el('copy').onclick=()=>{navigator.clipboard.writeText('BLINDLAB '+JSON.stringify(calls)).then(()=>{el('copy').textContent='Copied';});};
new ResizeObserver(()=>chart.applyOptions({width:chartEl.clientWidth,height:chartEl.clientHeight})).observe(chartEl);
show();
</script>
"""
page = page.replace("__LWC__", LWC).replace("__ROUNDS__", json.dumps(rounds, separators=(',', ':')))
out = os.path.join(HERE, "trainer.html")
open(out, "w", encoding="utf-8").write(page)
print(f"trainer.html: {os.path.getsize(out)//1024} KB, {len(rounds)} rounds embedded, continuations sealed in keys/")
