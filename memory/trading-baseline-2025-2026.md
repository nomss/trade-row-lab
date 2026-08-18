---
name: trading-baseline-2025-2026
description: "Validated win-rate findings from Noman's 2025+2026 trade journals (726 trades) — baseline, working filters, and dead ends"
metadata: 
  node_type: memory
  type: project
  originSessionId: bd2c3ab9-998c-4817-b386-dc5487fb56b5
  modified: 2026-08-16T09:53:16.657Z
---

Derived 2026-08-16 by parsing `2025 TradeJournal.docx` (full year, 470 trades) and
`2026 TradeJournal.docx` (256 trades through 08-14). The three other 2025 docx files
are strict subsets — snapshots, not extra data. Don't double-count them.

**Baseline: 32.9% win rate over 726 trades.** Stable across both years
(33.2% / 32.4%). It is his constant, not a slump.

**What works — all abstention, all cross-year replicated:**
- Not the first trade of the day: 38.4% vs 27.9% for first trades (380 trades, 28%/27%)
- U30USD / USDCAD / USDJPY: 46.3% (n=136, z=+3.33) — strongest single signal
- Monday 42.6% vs Tuesday 24.6%; Tuesday's *first* trade is 17.1% (13W/63L)
- Stacked filters tested out-of-sample on 2026: **32.4% → 41.2%**

**Biggest single effect — trades with no written thesis win 19.3%** (shortest-quartile
notes, avg 13 chars) vs 39.8% for medium notes. Threshold not dose: his longest notes
do *worse* (33.9%). Bias runs the wrong way (losses attract writing), which strengthens it.
Matches his own #1 self-diagnosis, "poor setup," logged 61 times.

**Dead ends — don't re-run these:** direction (BUY 32.0% / SELL 33.5%), entry hour,
reversal vs continuation language (reversal is *better*, 39.3%), setup grade (filled on
10 trades), setup name field (13 trades). Pin bar survives controls but only ~5 points
over length-matched trades.

**Exits, for when he's ready:** avg win fell 1.70R (2025) → 1.05R (2026) at a flat win
rate; that decline is the whole difference between roughly breakeven and clearly losing.
Only 30% of trades have both risk and profit recorded, so R figures are a thin sample.
See [[nomans-trading-goals-and-boundaries]].
