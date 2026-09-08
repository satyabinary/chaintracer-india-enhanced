"""
Seeds the database with 5 demo cases so the dashboard isn't empty on first
load.

Important: these synthetic cases are NOT hand-typed risk scores. Each one
defines a small fake USDT-transfer chain, temporarily patches
`tron_client.get_trc20_transfers` to serve that chain instead of calling
the real Tronscan API, then runs the exact same `trace_wallet` /
`compute_risk_score` / `build_graph` / `build_evidence_table` functions
that real officer-submitted cases use. This guarantees the seed scores
obey the same formula as everything else in the app.

All wallet addresses here are procedurally generated placeholders (valid
TRON address *format*, not real accounts) — this is clearly sample data,
which is also flagged via `is_seed=True` on the case record and surfaced
in the UI.
"""
import random
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from app import tron_client
from app.trace_engine import trace_wallet, build_graph, build_evidence_table
from app.risk_engine import compute_risk_score
from app.exchange_list import KNOWN_EXCHANGE_WALLETS, KNOWN_SCAM_WALLETS, KNOWN_MIXER_WALLETS
from app.database import get_cursor, init_db

HOUR = 3600 * 1000
BASE_TS = 1_735_000_000_000  # arbitrary fixed epoch ms so seed data is reproducible

WAZIRX_1 = "TxwsmFJr54bMV6Dc9xFfhZYV7SeEkfYWZr"
COINDCX_1 = "T6aXjDKzZCxkun4APZzjf8q7BsMAanTtWW"
OKX_1 = "TkB4S2TcythanfvNCyWM768vdMphYLfFaC"
SCAM_3 = "TAVKvjCxhYpUfur4qCKsnSXgzXesmfoWxe"
SCAM_2 = "Ti7vfU4NjjsmTkuW9BqrDutY49AtwEjpYY"
MIXER_1 = "TfngXPSGe9FP67ffhEc6EBhDxwkwBRKsGL"


def _addr(tag: str) -> str:
    """Deterministic, correctly-formatted (34 char, 'T'-prefixed, Base58) placeholder address."""
    rng = random.Random(f"chaintracer-seed::{tag}")
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    body = "".join(rng.choice(alphabet) for _ in range(33))
    return "T" + body


def _tx(h, frm, to, amount, ts_ms):
    return {
        "hash": h, "from_address": frm, "to_address": to,
        "amount": amount, "timestamp_ms": ts_ms, "confirmed": True, "success": True,
    }


@contextmanager
def _patched_tron_client(chain_db: dict):
    """Temporarily serve `chain_db` instead of calling the real Tronscan API."""
    original = tron_client.get_trc20_transfers

    def fake_get(address, direction="all", limit=50, **kwargs):
        return chain_db.get((direction, address), [])

    tron_client.get_trc20_transfers = fake_get
    try:
        yield
    finally:
        tron_client.get_trc20_transfers = original


def _case_1_direct_exchange_match():
    """2 hops, ends with a direct address match at a WazirX hot wallet. One
    hop wallet is on the known-scam list. Bot-speed rhythm on the final
    forward. Slow (>24h) final hop so this resolves as a plain address
    match rather than a sweeper match — a different flavour of 'confirmed'
    from case 3 below."""
    victim = _addr("c1_victim")
    a = _addr("c1_a")
    b = SCAM_3  # this hop wallet is itself a previously-flagged scam wallet
    decoy1, decoy2 = _addr("c1_decoy1"), _addr("c1_decoy2")
    d1, d2, d3 = _addr("c1_b_decoy1"), _addr("c1_b_decoy2"), None

    amount = 8500.0
    db = {
        ("in", a): [_tx("c1_victim_tx", victim, a, amount, BASE_TS)],
        ("out", a): [
            _tx("c1_a_main", a, b, 7650.0, BASE_TS + 2 * HOUR),
            _tx("c1_a_decoy1", a, decoy1, 500.0, BASE_TS + 2 * HOUR),
            _tx("c1_a_decoy2", a, decoy2, 350.0, BASE_TS + 2 * HOUR),
        ],
        ("out", b): [
            _tx("c1_b_main", b, WAZIRX_1, 7480.0, BASE_TS + 52 * HOUR),      # >24h later
            _tx("c1_b_decoy1", b, d1, 100.0, BASE_TS + 53 * HOUR),           # regular +1h gaps
            _tx("c1_b_decoy2", b, d2, 70.0, BASE_TS + 54 * HOUR),            # => bot-speed flag
        ],
    }
    return {
        "victim_name": "Rajesh Kumar", "city": "Bengaluru",
        "wallet_address": a, "amount_usdt": amount,
        "notes": "Victim responded to a fake trading-app investment ad on Instagram; "
                 "transferred USDT after being shown a fabricated profit dashboard.",
        "db": db, "max_hops": 4,
    }


def _case_2_in_transit():
    """4 full hops, never reaches an exchange or mixer — an honest 'still moving' case."""
    victim = _addr("c2_victim")
    wallets = [_addr(f"c2_w{i}") for i in range(5)]
    decoy = _addr("c2_decoy1")
    amount = 15000.0
    db = {("in", wallets[0]): [_tx("c2_victim_tx", victim, wallets[0], amount, BASE_TS)]}
    running = amount
    for i in range(4):
        ts = BASE_TS + (i + 1) * 5 * HOUR
        main_amt = round(running * 0.88, 2)
        decoy_amt = round(running - main_amt, 2)
        db[("out", wallets[i])] = [
            _tx(f"c2_hop{i}_main", wallets[i], wallets[i + 1], main_amt, ts),
            _tx(f"c2_hop{i}_decoy", wallets[i], decoy, decoy_amt, ts),
        ]
        running = main_amt
    return {
        "victim_name": "Sunita Devi", "city": "Lucknow",
        "wallet_address": wallets[0], "amount_usdt": amount,
        "notes": "Task-based 'part-time job' scam — victim was told to complete app "
                 "tasks and paid an upfront USDT 'registration deposit'.",
        "db": db, "max_hops": 4,
    }


def _case_3_sweeper_match():
    """1 hop, then a fast (~2h) 96% sweep straight to a CoinDCX hot wallet."""
    victim = _addr("c3_victim")
    a = _addr("c3_a")
    decoy = _addr("c3_decoy1")
    amount = 3200.0
    db = {
        ("in", a): [_tx("c3_victim_tx", victim, a, amount, BASE_TS)],
        ("out", a): [
            _tx("c3_a_main", a, COINDCX_1, 3072.0, BASE_TS + 2 * HOUR),  # 96% within 2h
            _tx("c3_a_decoy", a, decoy, 128.0, BASE_TS + 2 * HOUR),
        ],
    }
    return {
        "victim_name": "Mohammed Iqbal", "city": "Hyderabad",
        "wallet_address": a, "amount_usdt": amount,
        "notes": "Victim paid a refundable 'customs release fee' in USDT for a parcel "
                 "scam initiated over WhatsApp.",
        "db": db, "max_hops": 4,
    }


def _case_4_deep_diluted_match():
    """3 hops with heavy splitting at every hop, finally landing on OKX — a real
    match, but deep and diluted enough that it scores LOW."""
    victim = _addr("c4_victim")
    a, b, c = _addr("c4_a"), _addr("c4_b"), _addr("c4_c")
    da1, da2 = _addr("c4_a_decoy1"), _addr("c4_a_decoy2")
    db1, db2 = _addr("c4_b_decoy1"), _addr("c4_b_decoy2")
    amount = 640.0
    db = {
        ("in", a): [_tx("c4_victim_tx", victim, a, amount, BASE_TS)],
        ("out", a): [
            _tx("c4_a_main", a, b, 320.0, BASE_TS + 6 * HOUR),
            _tx("c4_a_decoy1", a, da1, 200.0, BASE_TS + 6 * HOUR),
            _tx("c4_a_decoy2", a, da2, 120.0, BASE_TS + 6 * HOUR),
        ],
        ("out", b): [
            _tx("c4_b_main", b, c, 160.0, BASE_TS + 30 * HOUR),
            _tx("c4_b_decoy1", b, db1, 100.0, BASE_TS + 30 * HOUR),
            _tx("c4_b_decoy2", b, db2, 60.0, BASE_TS + 30 * HOUR),
        ],
        ("out", c): [
            _tx("c4_c_main", c, OKX_1, 150.0, BASE_TS + 100 * HOUR),
        ],
    }
    return {
        "victim_name": "Priya Sharma", "city": "Pune",
        "wallet_address": a, "amount_usdt": amount,
        "notes": "Small 'pig-butchering' style romance scam — early-stage payment before "
                 "victim was asked for a larger sum.",
        "db": db, "max_hops": 4,
    }


def _case_5_mixer_flagged():
    """Source wallet is itself a flagged scam wallet; forwards almost immediately
    (minimal dilution, regular rhythm) into a known mixer."""
    victim = _addr("c5_victim")
    a = SCAM_2  # source wallet itself is on the known-scam-wallet list
    d1, d2 = _addr("c5_decoy1"), _addr("c5_decoy2")
    amount = 22000.0
    db = {
        ("in", a): [_tx("c5_victim_tx", victim, a, amount, BASE_TS)],
        ("out", a): [
            _tx("c5_a_main", a, MIXER_1, 21500.0, BASE_TS + 1 * HOUR),
            _tx("c5_a_decoy1", a, d1, 300.0, BASE_TS + 2 * HOUR),   # regular +1h gaps
            _tx("c5_a_decoy2", a, d2, 200.0, BASE_TS + 3 * HOUR),   # => bot-speed flag
        ],
    }
    return {
        "victim_name": "Arvind Yadav", "city": "Delhi",
        "wallet_address": a, "amount_usdt": amount,
        "notes": "Large 'forex trading mentor' investment fraud; wallet was already "
                 "flagged internally from a prior FIR before this complaint.",
        "db": db, "max_hops": 4,
    }


CASE_BUILDERS = [
    _case_1_direct_exchange_match,
    _case_2_in_transit,
    _case_3_sweeper_match,
    _case_4_deep_diluted_match,
    _case_5_mixer_flagged,
]


def _trace_seed_case(spec: dict) -> dict:
    with _patched_tron_client(spec["db"]):
        trace_result = trace_wallet(spec["wallet_address"], spec["amount_usdt"], max_hops=spec["max_hops"])
    risk = compute_risk_score(trace_result)
    graph = build_graph(trace_result)
    evidence = build_evidence_table(trace_result)
    return trace_result, risk, graph, evidence


def seed_if_empty(force: bool = False):
    init_db()
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM cases")
        count = cur.fetchone()["n"]
    if count > 0 and not force:
        return {"seeded": False, "existing_count": count}

    if force:
        with get_cursor(commit=True) as cur:
            cur.execute("DELETE FROM cases")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    inserted = []
    for i, builder in enumerate(CASE_BUILDERS, start=1):
        spec = builder()
        trace_result, risk, graph, evidence = _trace_seed_case(spec)
        case_number = f"CCU-2026-{i:04d}"
        filed_on = f"2026-0{ (i % 6) + 1 }-{10 + i:02d} 09:15:00"

        with get_cursor(commit=True) as cur:
            cur.execute(
                """INSERT INTO cases (
                    case_number, victim_name, wallet_address, amount_usdt, notes,
                    status, match_status, matched_exchange, matched_wallet,
                    risk_score, priority, error_message,
                    trace_result_json, risk_breakdown_json, graph_json, evidence_json,
                    is_seed, alert_sent, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    case_number, f"{spec['victim_name']} ({spec['city']})", spec["wallet_address"],
                    spec["amount_usdt"], spec["notes"],
                    "TRACED", trace_result["match_status"], trace_result["matched_exchange"],
                    trace_result["matched_wallet"], risk["total_score"], risk["priority"], None,
                    json.dumps(trace_result), json.dumps(risk), json.dumps(graph), json.dumps(evidence),
                    1, 0, filed_on, now,
                ),
            )
        inserted.append({"case_number": case_number, "priority": risk["priority"],
                          "match_status": trace_result["match_status"], "score": risk["total_score"]})

    return {"seeded": True, "cases": inserted}


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = seed_if_empty(force=True)
    print(json.dumps(result, indent=2))
