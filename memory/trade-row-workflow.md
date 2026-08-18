---
name: trade-row-workflow
description: "Active daily workflow — Noman annotates charts, Claude reads the PNGs and appends structured rows to trade-rows.csv"
metadata: 
  node_type: memory
  type: project
  originSessionId: bd2c3ab9-998c-4817-b386-dc5487fb56b5
  modified: 2026-08-18T14:32:41.972Z
---

Agreed 2026-08-18 (explicit "build"). **This is a standing job.** When Noman says
"new chart", points at a PNG, or mentions he traded: read the chart image(s), draft a
row, confirm anything ambiguous, append to `trade-rows.csv` in the project folder
(header already written).

**He trades and annotates exactly as he always has — the workflow never restricts what
he trades.** Claude does all transcription; he never fills a form.

**Chart locations:** annotated PNGs land in `F:\Forex\Backtest\` (filenames like
`08-17-2026-Monday-H1-NASUSD-06-03-AM.png`); copies under `F:\Forex\Target\<INST>\<date>\`.
His handwriting is readable — quote annotations back when uncertain. Journal is
`2026 TradeJournal.docx` in the project folder (extract word/document.xml via unzip;
he re-saves it often, re-extract fresh each time).

**Row schema** (closed vocabulary — his own chart language, extensible only when he
confirms a new value; never invent):
- signal_day: bull BO / bear BO / inside / range
- d, h4, h1, m15: bull BO / bear BO / range / creeper / pullback / inside
- white_space: above / below / none
- creeper: yes / no
- claim: claimed high / claimed low / gave up high / gave up low / re-claimed high / re-claimed low / none
- hoy_loy: in play / not
- trigger: pin bar / engulfing / color change / exhaustive candle / BO / double top / none
- sl_bar_tf: M5 / M15 / H1 — his stop rule is **1-bar SL**, usually M5, sometimes M15,
  rarely H1 (~95% compliance). Read the stop price off the annotated SL bar.
- taken: yes / no — **`no` rows are the control group; they matter as much as trades**
- mfe_r: how far it went his way before close — ask if not annotated
- Ask only for what the chart doesn't show (usually MFE, sometimes stop).

**Why:** his journal used 142 setup names (115 once) — uncountable. His chart
vocabulary (creeper, white space, claims, HOY, 9–10 window, exhaustive candle) is
stable and is the real lens; almost none of it reached the journal (2–10 mentions in
726 trades). Goal: ~100 rows ≈ first real test of his own concepts vs the 32.9%
baseline ([[trading-baseline-2025-2026]]). Design counters his known failure modes:
practices die at 4–6 weeks, so 100 rows is the finish line; sl_bar_tf may explain the
tapped-then-go pattern (his limit-at-SL log ran 9/16 in July 2026).

Scoreboard he watches: e.g. Tuesday after an all-loss Monday = 15.6% historically; he
wants to beat cells like that by process, not abstention — he has refused day-skipping
rules ([[nomans-trading-goals-and-boundaries]]). He trades demo/challenge accounts;
account rarely tagged in journal — worth asking which account a trade was on.

Repo: https://github.com/nomss/trade-row-lab (public, remote "origin", branch master).
After appending rows: copy memory files into memory/, git add -A, commit, push.
