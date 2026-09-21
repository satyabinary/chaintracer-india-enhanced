"""
Offline test harness for the trace + scoring pipeline.

This monkeypatches app.tron_client.get_trc20_transfers so the whole
pipeline (trace_engine -> risk_engine -> graph/evidence builders) can be
exercised deterministically without hitting the real Tronscan API.

Run with:  python3 -m tests.test_trace_offline   (from backend/)
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tron_client
from app.exchange_list import KNOWN_EXCHANGE_WALLETS, KNOWN_SCAM_WALLETS

EXCHANGE_ADDR = list(KNOWN_EXCHANGE_WALLETS.keys())[0]
SCAM_ADDR = list(KNOWN_SCAM_WALLETS.keys())[0]

def _fake_addr(tag: str) -> str:
    """34-char, 'T'-prefixed, Base58-alphabet placeholder address for tests."""
    body = (tag * 10)[:33]
    # map any disallowed chars (0/O/I/l and non-alnum) to safe stand-ins
    body = body.replace("0", "5").replace("O", "o").replace("I", "i").replace("l", "k")
    return "T" + body.ljust(33, "9")


WALLET_A = _fake_addr("wA")
WALLET_B = _fake_addr("wB")
WALLET_C = _fake_addr("wC")
DECOY_1 = _fake_addr("d1")
DECOY_2 = _fake_addr("d2")

BASE_TS = 1_700_000_000_000  # arbitrary ms epoch


def fake_transfers_db():
    """
    Simulated chain:
      victim -> A (1000 USDT)
      A -> B (900 USDT, main) + A -> DECOY_1 (100 USDT, decoy)
      B -> EXCHANGE (860 USDT, 2 hours later, ~95.5% of 900) => sweeper match
      (SCAM_ADDR never appears in this particular fixture; see test 2)
    """
    return {
        ("in", WALLET_A): [
            {"hash": "victim_tx", "from_address": "TVICTIM00000000000000000000000001",
             "to_address": WALLET_A, "amount": 1000.0, "timestamp_ms": BASE_TS,
             "confirmed": True, "success": True},
        ],
        ("out", WALLET_A): [
            {"hash": "a_to_b", "from_address": WALLET_A, "to_address": WALLET_B,
             "amount": 900.0, "timestamp_ms": BASE_TS + 3600_000, "confirmed": True, "success": True},
            {"hash": "a_to_decoy1", "from_address": WALLET_A, "to_address": DECOY_1,
             "amount": 100.0, "timestamp_ms": BASE_TS + 3600_000, "confirmed": True, "success": True},
        ],
        ("out", WALLET_B): [
            {"hash": "b_to_exchange", "from_address": WALLET_B, "to_address": EXCHANGE_ADDR,
             "amount": 860.0, "timestamp_ms": BASE_TS + 3600_000 + 2 * 3600_000,
             "confirmed": True, "success": True},
            {"hash": "b_to_decoy2", "from_address": WALLET_B, "to_address": DECOY_2,
             "amount": 20.0, "timestamp_ms": BASE_TS + 3600_000 + 2 * 3600_000,
             "confirmed": True, "success": True},
        ],
    }


def fake_transfers_in_transit_db():
    """Simulated chain that never resolves: A -> B -> C -> D -> ... (dead end, no exchange, no mixer)."""
    chain = {}
    wallets = [_fake_addr(f"c{i}x") for i in range(6)]
    chain[("in", wallets[0])] = [
        {"hash": "victim_tx2", "from_address": "TVICTIM00000000000000000000000002",
         "to_address": wallets[0], "amount": 500.0, "timestamp_ms": BASE_TS,
         "confirmed": True, "success": True},
    ]
    for i in range(len(wallets) - 1):
        chain[("out", wallets[i])] = [
            {"hash": f"hop_{i}", "from_address": wallets[i], "to_address": wallets[i + 1],
             "amount": 500.0 - i, "timestamp_ms": BASE_TS + (i + 1) * 3600_000,
             "confirmed": True, "success": True},
        ]
    return chain, wallets[0]


def run_test_1_sweeper_and_decoys():
    db = fake_transfers_db()

    def fake_get(address, direction="all", limit=50, **kwargs):
        return db.get((direction, address), [])

    tron_client.get_trc20_transfers = fake_get

    from app.trace_engine import trace_wallet, build_graph, build_evidence_table
    from app.risk_engine import compute_risk_score

    result = trace_wallet(WALLET_A, reported_amount=1000.0, max_hops=4)
    score = compute_risk_score(result)
    graph = build_graph(result)
    evidence = build_evidence_table(result)

    print("=== TEST 1: sweeper pattern + decoys ===")
    print("match_status:", result["match_status"])
    print("matched_exchange:", result["matched_exchange"])
    print("terminal_hop_index:", result["terminal_hop_index"])
    print("final_taint_level:", result["final_taint_level"])
    print("score:", json.dumps(score, indent=2))
    print(f"graph nodes: {len(graph['nodes'])}, edges: {len(graph['edges'])}")
    print(f"evidence rows: {len(evidence)}")

    assert result["match_status"] == "SWEEPER_MATCH"
    assert result["matched_exchange"] == KNOWN_EXCHANGE_WALLETS[EXCHANGE_ADDR]["name"]
    # EXCHANGE_ADDR is one of the SAMPLE placeholder addresses, not a real
    # Tronscan-labeled one — confirm that distinction survives the whole
    # pipeline instead of getting lost or defaulting to "verified" by mistake.
    assert result["matched_exchange_verified"] is False
    assert "Sample match" in result["matched_exchange_note"]
    assert score["factors"]["sweep_timing_match"]["raw_value"] == 1.0
    assert score["priority"] in ("HIGH", "MEDIUM", "LOW")
    assert len(evidence) >= 4  # victim + a->b + a->decoy1 + b->exchange (+ b->decoy2)
    print("TEST 1 PASSED\n")


def run_test_2_in_transit():
    db, start_wallet = fake_transfers_in_transit_db()

    def fake_get(address, direction="all", limit=50, **kwargs):
        return db.get((direction, address), [])

    tron_client.get_trc20_transfers = fake_get

    from app.trace_engine import trace_wallet
    from app.risk_engine import compute_risk_score

    result = trace_wallet(start_wallet, reported_amount=500.0, max_hops=4)
    score = compute_risk_score(result)

    print("=== TEST 2: in-transit (no match within hop cap) ===")
    print("match_status:", result["match_status"])
    print("stop_reason:", result["stop_reason"])
    print("terminal_hop_index:", result["terminal_hop_index"])
    print("score:", json.dumps(score, indent=2))

    assert result["match_status"] == "IN_TRANSIT"
    assert result["terminal_hop_index"] == 4
    assert score["factors"]["hop_depth_score"]["raw_value"] == 0.0
    print("TEST 2 PASSED\n")


def run_test_3_direct_exchange_hit_and_threat_intel():
    # Source wallet is itself flagged AND forwards straight to an exchange at hop 1
    def fake_get(address, direction="all", limit=50, **kwargs):
        if direction == "in" and address == SCAM_ADDR:
            return [{"hash": "victim_tx3", "from_address": "TVICTIM00000000000000000000000003",
                      "to_address": SCAM_ADDR, "amount": 250.0, "timestamp_ms": BASE_TS,
                      "confirmed": True, "success": True}]
        if direction == "out" and address == SCAM_ADDR:
            return [{"hash": "scam_to_exchange", "from_address": SCAM_ADDR, "to_address": EXCHANGE_ADDR,
                      "amount": 250.0, "timestamp_ms": BASE_TS + 5000_000, "confirmed": True, "success": True}]
        return []

    tron_client.get_trc20_transfers = fake_get

    from app.trace_engine import trace_wallet
    from app.risk_engine import compute_risk_score

    result = trace_wallet(SCAM_ADDR, reported_amount=250.0, max_hops=4)
    score = compute_risk_score(result)

    print("=== TEST 3: source wallet itself is flagged threat-intel + moves to exchange next hop ===")
    print("match_status:", result["match_status"])
    print("threat_intel_hit:", result["threat_intel_hit"])
    print("score:", json.dumps(score, indent=2))

    assert result["threat_intel_hit"] is True
    assert score["factors"]["threat_intel_hit"]["raw_value"] == 1.0
    # SCAM_ADDR is not itself an exchange, so it should hop once more and match
    # there. Because it forwards ~100% within the sweep window, this fixture
    # correctly resolves as a SWEEPER_MATCH (a stronger, behavior-based hit).
    assert result["match_status"] in ("EXCHANGE_MATCH", "SWEEPER_MATCH")
    assert result["matched_exchange"] == KNOWN_EXCHANGE_WALLETS[EXCHANGE_ADDR]["name"]
    assert result["matched_exchange_verified"] is False
    print("TEST 3 PASSED\n")


def fake_transfers_unrelated_large_tx_db():
    """
    Two isolated scenarios covering the "unrelated large transfer" bug fix
    (a wallet forwarding what LOOKS like a huge amount that actually belongs
    to someone else's unrelated activity, not our traced funds):

    Scenario A (time guard): wallet P receives 1000 USDT. It ALSO has an
    unrelated 50,000 USDT outgoing transfer that happened BEFORE it received
    that money (so it structurally cannot be part of this trail), alongside
    a legitimate 950 USDT transfer sent AFTER. The tracer must follow the
    950 USDT one and must never surface the 50,000 one, not even as a decoy.

    Scenario B (amount guard): wallet R receives 4,999 USDT, and its ONLY
    outgoing transfer afterwards is an unrelated 1,200,000 USDT transfer —
    exactly the "received 4,999, shows 1,200,000 forwarded" bug pattern.
    With no plausible candidate, the trace must end honestly at R instead
    of following that 1.2M transfer.
    """
    wallet_p = _fake_addr("wP")
    wallet_q = _fake_addr("wQ")
    unrelated_1 = _fake_addr("u1")
    wallet_r = _fake_addr("wR")
    unrelated_2 = _fake_addr("u2")

    db = {
        ("in", wallet_p): [
            {"hash": "victim_tx_p", "from_address": "TVICTIM00000000000000000000000005",
             "to_address": wallet_p, "amount": 1000.0, "timestamp_ms": BASE_TS,
             "confirmed": True, "success": True},
        ],
        ("out", wallet_p): [
            # Unrelated, much larger, but happened BEFORE the money arrived —
            # only the time guard excludes this one (it would pass an
            # amount-only check if amount were compared against nothing).
            {"hash": "p_to_unrelated1", "from_address": wallet_p, "to_address": unrelated_1,
             "amount": 50000.0, "timestamp_ms": BASE_TS - 1_000_000,
             "confirmed": True, "success": True},
            # Legitimate continuation: smaller, sent AFTER arrival.
            {"hash": "p_to_q", "from_address": wallet_p, "to_address": wallet_q,
             "amount": 950.0, "timestamp_ms": BASE_TS + 3600_000,
             "confirmed": True, "success": True},
        ],
        ("out", wallet_q): [],  # dead end -> IN_TRANSIT

        ("in", wallet_r): [
            {"hash": "victim_tx_r", "from_address": "TVICTIM00000000000000000000000006",
             "to_address": wallet_r, "amount": 4999.0, "timestamp_ms": BASE_TS,
             "confirmed": True, "success": True},
        ],
        ("out", wallet_r): [
            # Unrelated, sent AFTER arrival (passes the time guard), but WAY
            # larger than what came in — only the amount guard excludes it.
            {"hash": "r_to_unrelated2", "from_address": wallet_r, "to_address": unrelated_2,
             "amount": 1_200_000.0, "timestamp_ms": BASE_TS + 3600_000,
             "confirmed": True, "success": True},
        ],
    }
    return db, wallet_p, wallet_r


def run_test_5_ignores_unrelated_large_transfers():
    db, wallet_p, wallet_r = fake_transfers_unrelated_large_tx_db()

    def fake_get(address, direction="all", limit=50, **kwargs):
        return db.get((direction, address), [])

    tron_client.get_trc20_transfers = fake_get

    from app.trace_engine import trace_wallet

    print("=== TEST 5: unrelated large transfers must not be followed ===")

    # --- Scenario A: pre-arrival unrelated transfer excluded by the TIME guard ---
    result_a = trace_wallet(wallet_p, reported_amount=1000.0, max_hops=4)
    hop0 = result_a["hops"][0]
    chosen = hop0.get("chosen_outgoing")
    print("A: chosen_outgoing:", chosen["hash"] if chosen else None, chosen["amount"] if chosen else None)
    print("A: decoy hashes:", [d["hash"] for d in hop0.get("decoys", [])])

    assert chosen is not None
    assert chosen["hash"] == "p_to_q"
    assert chosen["amount"] == 950.0
    # The pre-arrival 50,000 transfer must not appear anywhere in this hop's
    # record — not as the chosen trail, and not even as a decoy.
    all_hashes_seen = [chosen["hash"]] + [d["hash"] for d in hop0["decoys"]]
    assert "p_to_unrelated1" not in all_hashes_seen
    assert result_a["match_status"] == "IN_TRANSIT"  # wallet_q is a dead end

    # --- Scenario B: post-arrival unrelated transfer excluded by the AMOUNT guard ---
    result_b = trace_wallet(wallet_r, reported_amount=4999.0, max_hops=4)
    hop0_r = result_b["hops"][0]
    print("B: match_status:", result_b["match_status"], "stop_reason:", result_b["stop_reason"])
    print("B: chosen_outgoing:", hop0_r.get("chosen_outgoing"))
    print("B: decoys:", hop0_r.get("decoys"))

    assert hop0_r.get("chosen_outgoing") is None
    assert hop0_r.get("decoys") == []
    assert result_b["match_status"] == "IN_TRANSIT"
    assert result_b["stop_reason"] == "NO_PLAUSIBLE_CONTINUATION"
    # Taint must not have been diluted by an unrelated transfer that was
    # correctly excluded rather than counted into the split-ratio math.
    assert result_b["final_taint_level"] == 1.0
    print("TEST 5 PASSED\n")


def run_test_6_verified_vs_sample_exchange_match():
    """
    Regression test for the verified/sample exchange-match distinction added
    alongside the 9 real Tronscan-labeled addresses: a trail landing on one
    of those real addresses must report matched_exchange_verified=True and
    a "Verified match" note, never blending in with sample-data matches
    (which tests 1 and 3 already confirm report verified=False). This
    guards against the two ever being displayed identically to an officer.
    """
    from app.trace_engine import trace_wallet
    from app.exchange_list import KNOWN_EXCHANGE_WALLETS

    verified_addr = next(addr for addr, rec in KNOWN_EXCHANGE_WALLETS.items() if rec["verified"])
    victim = "TVICTIM00000000000000000000000006"
    source = _fake_addr("v6src")

    def fake_get(address, direction="all", limit=50, **kwargs):
        if direction == "in" and address == source:
            return [{"hash": "victim_tx6", "from_address": victim, "to_address": source,
                      "amount": 777.0, "timestamp_ms": BASE_TS, "confirmed": True, "success": True}]
        if direction == "out" and address == source:
            return [{"hash": "source_to_verified", "from_address": source, "to_address": verified_addr,
                      "amount": 777.0, "timestamp_ms": BASE_TS + 3600_000, "confirmed": True, "success": True}]
        return []

    tron_client.get_trc20_transfers = fake_get

    result = trace_wallet(source, reported_amount=777.0, max_hops=4)

    print("=== TEST 6: verified (Tronscan-labeled) exchange match ===")
    print("match_status:", result["match_status"])
    print("matched_exchange:", result["matched_exchange"])
    print("matched_exchange_verified:", result["matched_exchange_verified"])
    print("matched_exchange_note:", result["matched_exchange_note"])

    assert result["match_status"] in ("EXCHANGE_MATCH", "SWEEPER_MATCH")
    assert result["matched_exchange"] == KNOWN_EXCHANGE_WALLETS[verified_addr]["name"]
    assert result["matched_exchange_verified"] is True
    assert "Verified match" in result["matched_exchange_note"]

    # the hop record itself (what the graph node and PDF row both read from)
    # must carry the identical flag — this is the single-source-of-truth
    # guarantee, not just the top-level trace_result summary field.
    matched_hop = next(h for h in result["hops"] if h["is_exchange_match"])
    assert matched_hop["matched_exchange_verified"] is True
    print("TEST 6 PASSED\n")


def run_test_4_invalid_address():
    from app.trace_engine import trace_wallet
    try:
        trace_wallet("not_a_real_address", reported_amount=100)
        raise AssertionError("expected ValueError for invalid address")
    except ValueError:
        print("=== TEST 4: invalid address correctly rejected ===")
        print("TEST 4 PASSED\n")


if __name__ == "__main__":
    run_test_1_sweeper_and_decoys()
    run_test_2_in_transit()
    run_test_3_direct_exchange_hit_and_threat_intel()
    run_test_4_invalid_address()
    run_test_5_ignores_unrelated_large_transfers()
    run_test_6_verified_vs_sample_exchange_match()
    print("ALL OFFLINE TESTS PASSED")
