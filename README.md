# ChainTracer India

A crypto fraud investigation dashboard for cyber-cell police officers. An officer enters a
victim-reported TRON (USDT-TRC20) wallet address; the app fetches its transaction history from
the public Tronscan API, follows the largest outgoing transfer at each hop (up to 4 hops),
checks the trail against a small sample exchange/scam/mixer wallet list, scores the case with a
fixed weighted formula, and lets the officer generate a PDF summary.

**This is an investigative aid, not an enforcement tool.** It never contacts a real exchange,
sends a real email/SMS, or freezes funds — every such action in the UI is clearly simulated.

---

## What's real vs. sample here

- **Real:** the Tronscan API calls, the hop-following logic, the risk-score math, the PDF
  generation, the SQLite storage.
- **Sample / placeholder, clearly labelled in the UI:** the "known exchange hot wallet",
  "known scam wallet", and "known mixer" lists in `backend/app/exchange_list.py`. These are
  procedurally generated addresses shaped like real TRON addresses — they are **not** the real
  hot wallets of Binance, WazirX, CoinDCX, OKX, or anyone else. Swap in real, verified addresses
  (from your own threat-intel feed) before using this for anything beyond a demo.
- **A note on the Tronscan integration:** I don't have live network access while building this,
  so `tron_client.py` is written against Tronscan's documented public
  `token_trc20/transfers` response shape from training knowledge, with defensive parsing
  (multiple fallback field names, timeouts, retries, clear error surfacing) rather than a single
  brittle assumption. **Test it against a real wallet address before relying on it** — if
  Tronscan has changed a field name since, you'll see a clear "Tronscan could not be reached /
  unexpected response shape" error rather than silently wrong data, and the fix is isolated to
  that one file.

---

## Tech stack

- **Backend:** Python 3.10+, FastAPI, SQLite (stdlib `sqlite3`, no ORM), ReportLab for PDFs
- **Frontend:** React 18 (Vite), Tailwind CSS, Cytoscape.js for the trace graph
- **No ML.** The risk score is the exact formula below — nothing learned, nothing hidden.

## Risk score formula

```
score = (taint_level          × 0.30)
      + (hop_depth_score      × 0.15)
      + (sweep_timing_match   × 0.25)
      + (bot_speed_flag       × 0.15)
      + (threat_intel_hit     × 0.15)
```

- `taint_level` — starts at 1.0 at the source wallet; each time a wallet splits its outflow
  across multiple transactions, taint is multiplied by the fraction that went to the wallet we
  followed (the largest one). Smaller side transfers are recorded as decoys, not followed.
- `hop_depth_score = 1 - (hop / max_hops)` — the trail earns more confidence the closer the
  match is to the source wallet.
- `sweep_timing_match` — 1.0 if a wallet forwarded ≥95% of what it received to a known exchange
  wallet within 24 hours (a "sweeper" pattern), even without an exact address-list hit.
- `bot_speed_flag` — 1.0 if a wallet's outgoing transfers have suspiciously regular time gaps
  (low coefficient of variation), suggesting automation rather than manual transfers.
- `threat_intel_hit` — 1.0 if any wallet in the trail is on the sample "known scam wallet" list.

`score ≥ 0.70` → **HIGH**, `0.40–0.69` → **MEDIUM**, `< 0.40` → **LOW**.

The UI never collapses this into just one number — the risk panel always shows all five factors,
their raw values, weights, and weighted contributions, next to the total.

---

## Running it locally

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt --break-system-packages   # drop the flag if not needed on your system
python run.py
```

This starts the API on `http://localhost:8000` (docs at `/docs`). On first startup it creates
`backend/data/chaintracer.db` and seeds it with 5 sample cases automatically — nothing manual to
run. If you ever want a completely fresh seed, stop the server, delete
`backend/data/chaintracer.db`, and restart.

You can also manually re-seed without starting the server:
```bash
python3 -m app.seed_data
```

Run the offline test suite (fake data, no network needed) any time with:
```bash
python3 -m tests.test_trace_offline
```

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
cp .env.example .env       # points the frontend at http://localhost:8000 by default
npm run dev
```

Open the printed local URL (typically `http://localhost:5173`).

---

## Project layout

```
backend/
  app/
    config.py          # constants: Tronscan URL, hop/weight/threshold config, storage paths
    database.py         # SQLite schema + row <-> dict helpers (no ORM)
    tron_client.py       # Tronscan API client + TRON address format validation
    exchange_list.py     # SAMPLE exchange / scam / mixer wallet lists
    trace_engine.py       # hop-following, sweeper/bot-speed detection, graph/evidence builders
    risk_engine.py         # the exact weighted scoring formula
    pdf_report.py           # ReportLab case summary report
    seed_data.py             # 5 sample cases, offline (doesn't call Tronscan)
    schemas.py                # request validation
    routers/cases.py           # all /api/cases* endpoints
    main.py                     # FastAPI app, CORS, startup seeding
  tests/test_trace_offline.py  # trace/risk engine tests against fake transfer data
  run.py
  requirements.txt

frontend/
  src/
    api/client.js               # fetch wrapper for the backend
    lib/statusMeta.js            # shared formatting/validation helpers
    components/                   # Header, Sidebar, CenterPanel (graph), RightPanel
                                    # (risk/exchange/evidence), modals for new case / report /
                                    # reference lists
    App.jsx
  index.html, package.json, vite.config.js, tailwind.config.js
```

---

## Screens

1. **Main dashboard** — sidebar of cases (ID, victim, amount, priority badge) · center panel with
   the interactive trace graph (tap a wallet to inspect it) · right panel with the risk-score
   breakdown, exchange attribution result, and transaction evidence table.
2. **New case form** — TRON address validated client- and server-side (`T` + 34 chars), amount,
   victim name, notes. Submitting starts the trace immediately with a loading state.
3. **Report view** — inline PDF preview plus a download button. Generated on demand by the
   backend with ReportLab; not stored as the source of truth (regenerated fresh each time).

## Deliberately not built

No ML model of any kind, no cross-chain bridge tracing, no real mixer tracing (address-list flag
only), no real government API integrations, no real SMS/email sending, and no automatic exchange
freezing or fund movement. "Simulate exchange alert" and the PDF report are the only actions this
tool takes — everything else is left to the officer.
