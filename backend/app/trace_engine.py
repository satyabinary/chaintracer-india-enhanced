"""
Fund-tracing engine.

Given a victim-reported wallet address, walks the USDT-TRC20 transfer graph
forward hop by hop. At every wallet, if there are multiple outgoing
transfers, the LARGEST is treated as the main trail and the rest are kept
as "decoys" for evidence purposes only (not followed further).

This module has no fastapi/pydantic dependency, so it can be run and
tested standalone (see backend/tests/).

--------------------------------------------------------------------------
HOW EACH RISK FACTOR IS OPERATIONALIZED (documented here since the exact
formula in the product brief leaves some real-world judgment calls open):

* taint_level: starts at 1.0 at the source wallet. Every time a wallet
  SPLITS its outgoing funds across more than one recipient, following the
  largest branch dilutes taint by (largest_amount / total_outgoing_amount).
  A wallet that forwards ~100% of what it received to a single address
  does not dilute taint at all (ratio ~1.0). "total_outgoing_amount" here
  is scoped to PLAUSIBLE candidates only — transfers sent after this
  wallet received the traced funds, and no larger than what it received
  (see the guard in trace_wallet() around plausible_candidates). A
  high-traffic wallet's unrelated transfers never enter this ratio, so
  they can't distort taint even indirectly.

* hop_depth_score = 1 - (hop_at_which_trail_ended / max_hops). Funds that
  reach an exchange (or dead-end) in fewer hops score higher — a short,
  fast path to cash-out is more urgent/actionable for an officer than one
  that's still bouncing through many mule wallets.

* sweep_timing_match: 1.0 only if a wallet forwarded >=95% of the amount
  it had just received to a KNOWN EXCHANGE wallet within 24 hours of
  receiving it. "Balance" here means "the amount received in this traced
  USDT flow", not the wallet's total on-chain balance (which could hold
  unrelated funds) — this keeps the check specific to the tainted funds
  actually being followed.

* bot_speed_flag: 1.0 if the most recent set of outgoing transfers we
  fetched (>=3 of them) have suspiciously regular time gaps between them
  (coefficient of variation below a threshold) — a signature of scripted/
  automated wallet behaviour rather than a human manually moving funds.

* threat_intel_hit: 1.0 if ANY wallet touched during the trace (source or
  any hop) appears on the hardcoded sample "known scam wallet" list.
--------------------------------------------------------------------------
"""
import statistics
from datetime import datetime, timezone

from app.config import (
    DEFAULT_MAX_HOPS,
    SWEEP_PERCENT_THRESHOLD,
    SWEEP_WINDOW_HOURS,
    BOT_SPEED_MIN_SAMPLES,
    BOT_SPEED_CV_THRESHOLD,
    MAX_DECOYS_STORED_PER_HOP,
)
from app import tron_client
from app.tron_client import TronApiError
from app.exchange_list import match_exchange, match_scam_wallet, match_mixer

HOURS_MS = 3600 * 1000


def _short(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr or "?"
    return f"{addr[:6]}...{addr[-4:]}"


def _iso(ts_ms: int) -> str:
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _coefficient_of_variation(candidates: list) -> float:
    ts_sorted = sorted(c["timestamp_ms"] for c in candidates if c.get("timestamp_ms"))
    if len(ts_sorted) < BOT_SPEED_MIN_SAMPLES:
        return None
    gaps = [ts_sorted[i + 1] - ts_sorted[i] for i in range(len(ts_sorted) - 1)]
    gaps = [g for g in gaps if g > 0]
    if len(gaps) < 2:
        return None
    mean = statistics.mean(gaps)
    if mean <= 0:
        return None
    stdev = statistics.pstdev(gaps)
    return stdev / mean


def trace_wallet(source_address: str, reported_amount: float, max_hops: int = DEFAULT_MAX_HOPS) -> dict:
    """
    Trace funds forward from `source_address` (the victim-reported wallet)
    through up to `max_hops` additional wallets.

    Returns a fully-formed trace_result dict (see module docstring / README
    for the schema). Never raises for "no results found" conditions — those
    are legitimate, honest outcomes (IN_TRANSIT). It DOES raise TronApiError
    upward if Tronscan is unreachable for the very first lookup, since at
    that point we have nothing honest to show at all.
    """
    if not tron_client.is_valid_tron_address(source_address):
        raise ValueError(f"'{source_address}' does not look like a valid TRON address")

    hops = []
    threat_intel_hit = False
    threat_intel_wallet = None
    threat_intel_note = None
    last_fetched_candidates = []

    current_wallet = source_address
    incoming_amount = float(reported_amount) if reported_amount else None
    incoming_ts_ms = None

    # Try to find the actual victim -> wallet-A transaction for the evidence
    # table (best-effort; purely cosmetic, does not affect scoring maths).
    victim_tx = None
    try:
        incoming_to_source = tron_client.get_trc20_transfers(source_address, direction="in", limit=50)
        if incoming_to_source:
            if reported_amount:
                close_matches = [
                    t for t in incoming_to_source
                    if abs(t["amount"] - float(reported_amount)) <= max(0.5, float(reported_amount) * 0.01)
                ]
                victim_tx = close_matches[0] if close_matches else incoming_to_source[0]
            else:
                victim_tx = incoming_to_source[0]
            incoming_ts_ms = victim_tx["timestamp_ms"]
            if not reported_amount:
                incoming_amount = victim_tx["amount"]
    except TronApiError:
        victim_tx = None  # non-fatal: we can still trace forward from A

    running_taint = 1.0
    match_status = None
    matched_exchange = None
    matched_wallet = None
    stop_reason = None

    hop_index = 0
    while True:
        hop_record = {
            "hop_index": hop_index,
            "wallet": current_wallet,
            "wallet_short": _short(current_wallet),
            "received_amount": round(incoming_amount, 6) if incoming_amount is not None else None,
            "received_at_ms": incoming_ts_ms,
            "received_at_iso": _iso(incoming_ts_ms) if incoming_ts_ms else None,
            "taint_level_here": round(running_taint, 4),
            "is_exchange_match": False,
            "matched_exchange_name": None,
            "is_sweeper_match": False,
            "is_mixer_flag": False,
            "is_threat_intel_hit": False,
            "chosen_outgoing": None,
            "decoys": [],
        }

        # 1. Does this wallet itself sit on the threat-intel (known scam) list?
        scam_note = match_scam_wallet(current_wallet)
        if scam_note:
            threat_intel_hit = True
            threat_intel_wallet = current_wallet
            threat_intel_note = scam_note
            hop_record["is_threat_intel_hit"] = True

        # 2. Does this wallet itself sit on the exchange hot-wallet list?
        exchange_name = match_exchange(current_wallet)
        if exchange_name:
            hop_record["is_exchange_match"] = True
            hop_record["matched_exchange_name"] = exchange_name
            match_status = "EXCHANGE_MATCH"
            matched_exchange = exchange_name
            matched_wallet = current_wallet
            stop_reason = "EXCHANGE_MATCH"
            hops.append(hop_record)
            break

        # 3. Does this wallet sit on the known-mixer list?
        mixer_note = match_mixer(current_wallet)
        if mixer_note:
            hop_record["is_mixer_flag"] = True
            match_status = "MIXER_FLAGGED"
            matched_wallet = current_wallet
            stop_reason = "MIXER_FLAGGED"
            hops.append(hop_record)
            break

        # 4. Have we hit the hop cap? Record this wallet as the final node,
        #    but don't fetch further outgoing activity beyond it.
        if hop_index >= max_hops:
            match_status = "IN_TRANSIT"
            stop_reason = "MAX_HOPS_REACHED"
            hops.append(hop_record)
            break

        # 5. Fetch this wallet's outgoing USDT-TRC20 transfers.
        try:
            candidates = tron_client.get_trc20_transfers(current_wallet, direction="out", limit=50)
        except TronApiError:
            match_status = "TRACE_FAILED"
            stop_reason = "TRONSCAN_UNAVAILABLE"
            hops.append(hop_record)
            break

        # only consider confirmed, successful transfers as real fund movement
        candidates = [c for c in candidates if c["confirmed"] and c["success"] and c["amount"] > 0]

        # ------------------------------------------------------------------
        # GUARD — do not remove: high-traffic TRON wallets (exchange deposit
        # funnels, payment processors, mule accounts used by many unrelated
        # people) routinely move money that has nothing to do with the
        # specific funds we're tracing. If we naively picked "the single
        # largest outgoing transfer this wallet has ever made", we would
        # regularly pick up someone else's unrelated transfer and silently
        # "inflate" the trail — e.g. a wallet that received 4,999 USDT from
        # our trail appearing to forward 1,200,000 USDT, because that
        # 1.2M transfer was actually unrelated activity from a different
        # sender entirely.
        #
        # A wallet can only ever forward money it actually holds, so any
        # candidate we treat as "the continuation of OUR trail" must be:
        #   (a) sent AFTER the money we're tracing arrived here — a wallet
        #       cannot forward funds before it has received them, and
        #   (b) no larger than the amount that arrived here — funds may
        #       shrink hop-to-hop (fees, splitting across recipients), but a
        #       single incoming transfer can never legitimately balloon
        #       into a larger single outgoing one.
        # Transfers that fail either check are not "decoys of this money"
        # either (a decoy, by definition, is an alternate destination for
        # THIS incoming batch) — they're just unrelated wallet activity, so
        # they are excluded from this hop's evidence entirely rather than
        # mislabeled as a decoy.
        # ------------------------------------------------------------------
        if incoming_ts_ms is not None:
            candidates = [c for c in candidates if c["timestamp_ms"] >= incoming_ts_ms]

        if not candidates:
            match_status = "IN_TRANSIT"
            stop_reason = "DEAD_END_NO_OUTFLOW"
            hops.append(hop_record)
            break

        # last_fetched_candidates feeds bot_speed_flag (timing pattern across
        # this wallet's post-arrival outgoing activity) — deliberately NOT
        # amount-bounded, since scripted/bot payout behaviour is a property
        # of the wallet's operation, not specifically of our traced amount.
        last_fetched_candidates = candidates
        candidates_sorted = sorted(candidates, key=lambda c: c["amount"], reverse=True)

        # Candidates that could plausibly BE (a split of) the money we're
        # tracing — see guard above. Everything downstream (sweeper check,
        # main-trail pick, decoys, taint split-ratio) is computed from this
        # list only, so an unrelated oversized transfer can't distort any of
        # them even indirectly.
        if incoming_amount is not None:
            plausible_candidates = [c for c in candidates_sorted if c["amount"] <= incoming_amount]
        else:
            # No known incoming amount to compare against — can only happen
            # if trace_wallet() was called without a reported_amount AND the
            # victim's own inbound transfer couldn't be found. Fall back to
            # considering everything, same as before this fix.
            plausible_candidates = candidates_sorted

        # 6. Sweeper-pattern check: a fast, near-total forward to a known
        #    exchange. Restricted to plausible_candidates, so (combined with
        #    the SWEEP_PERCENT_THRESHOLD floor) a matched transfer is always
        #    between ~95% and 100% of the incoming amount — never inflated.
        sweeper_hit = None
        if incoming_amount and incoming_ts_ms:
            for c in plausible_candidates:
                ex_name = match_exchange(c["to_address"])
                if not ex_name:
                    continue
                pct = c["amount"] / incoming_amount if incoming_amount else 0
                gap_hours = (c["timestamp_ms"] - incoming_ts_ms) / HOURS_MS
                if pct >= SWEEP_PERCENT_THRESHOLD and 0 <= gap_hours <= SWEEP_WINDOW_HOURS:
                    sweeper_hit = (c, ex_name)
                    break

        if sweeper_hit:
            main, ex_name = sweeper_hit
            decoys = [c for c in plausible_candidates if c["hash"] != main["hash"]][:MAX_DECOYS_STORED_PER_HOP]
            hop_record["chosen_outgoing"] = main
            hop_record["decoys"] = decoys
            hop_record["is_sweeper_match"] = True
            hop_record["is_exchange_match"] = True
            hop_record["matched_exchange_name"] = ex_name
            match_status = "SWEEPER_MATCH"
            matched_exchange = ex_name
            matched_wallet = main["to_address"]
            stop_reason = "SWEEPER_MATCH"
            hops.append(hop_record)
            break

        # 7. No match here: follow the largest PLAUSIBLE outgoing transfer as
        #    the main trail (never an unrelated oversized one — see guard
        #    above); everything else plausible is logged as a decoy. If
        #    NOTHING plausible exists, the trail honestly ends here rather
        #    than following an unrelated transfer just to keep moving.
        if not plausible_candidates:
            match_status = "IN_TRANSIT"
            stop_reason = "NO_PLAUSIBLE_CONTINUATION"
            hops.append(hop_record)
            break

        main = plausible_candidates[0]
        decoys = [c for c in plausible_candidates if c["hash"] != main["hash"]][:MAX_DECOYS_STORED_PER_HOP]
        total_out = sum(c["amount"] for c in plausible_candidates)
        split_ratio = (main["amount"] / total_out) if total_out > 0 else 1.0
        running_taint = running_taint * split_ratio

        hop_record["chosen_outgoing"] = main
        hop_record["decoys"] = decoys
        hops.append(hop_record)

        current_wallet = main["to_address"]
        incoming_amount = main["amount"]
        incoming_ts_ms = main["timestamp_ms"]
        hop_index += 1

    terminal_hop = hops[-1]
    final_taint = terminal_hop["taint_level_here"]

    bot_speed_flag = False
    cv = _coefficient_of_variation(last_fetched_candidates)
    if cv is not None and cv < BOT_SPEED_CV_THRESHOLD:
        bot_speed_flag = True

    return {
        "source_wallet": source_address,
        "reported_amount": reported_amount,
        "max_hops": max_hops,
        "victim_tx": victim_tx,
        "hops": hops,
        "terminal_hop_index": terminal_hop["hop_index"],
        "match_status": match_status,
        "stop_reason": stop_reason,
        "matched_exchange": matched_exchange,
        "matched_wallet": matched_wallet,
        "threat_intel_hit": threat_intel_hit,
        "threat_intel_wallet": threat_intel_wallet,
        "threat_intel_note": threat_intel_note,
        "bot_speed_flag": bot_speed_flag,
        "final_taint_level": final_taint,
    }


# --------------------------------------------------------------------------
# Presentation helpers: turn a trace_result into graph nodes/edges and an
# evidence table. Kept separate from the tracing math above.
# --------------------------------------------------------------------------

def build_graph(trace_result: dict) -> dict:
    """Build a Cytoscape-ready {nodes, edges} structure from a trace_result."""
    nodes = []
    edges = []
    hops = trace_result["hops"]

    if trace_result.get("victim_tx"):
        victim_id = "victim"
        nodes.append({
            "data": {
                "id": victim_id,
                "label": "Victim",
                "role": "victim",
                "sublabel": "Reported payment",
            }
        })
        edges.append({
            "data": {
                "id": "e-victim",
                "source": victim_id,
                "target": hops[0]["wallet"],
                "amount": trace_result["victim_tx"]["amount"],
                "label": f"{trace_result['victim_tx']['amount']:,.2f} USDT",
                "kind": "main",
            }
        })

    for i, hop in enumerate(hops):
        role = "intermediate"
        if i == 0:
            role = "source"
        if hop["is_exchange_match"]:
            role = "exchange"
        elif hop["is_mixer_flag"]:
            role = "mixer"

        nodes.append({
            "data": {
                "id": hop["wallet"],
                "label": hop["wallet_short"],
                "full_address": hop["wallet"],
                "role": role,
                "sublabel": hop["matched_exchange_name"] or ("Mixer flagged" if hop["is_mixer_flag"] else f"Hop {i}"),
                "taint": hop["taint_level_here"],
                "threat_intel": hop["is_threat_intel_hit"],
            }
        })

        chosen = hop.get("chosen_outgoing")
        if chosen:
            edges.append({
                "data": {
                    "id": f"e-main-{i}",
                    "source": hop["wallet"],
                    "target": chosen["to_address"],
                    "amount": chosen["amount"],
                    "label": f"{chosen['amount']:,.2f} USDT",
                    "kind": "sweeper" if hop["is_sweeper_match"] else "main",
                }
            })
            for j, decoy in enumerate(hop.get("decoys", [])):
                # add a light node for decoy destinations so officers can see
                # what was ruled out, without following them further
                decoy_node_id = f"decoy-{i}-{j}-{decoy['to_address']}"
                nodes.append({
                    "data": {
                        "id": decoy_node_id,
                        "label": _short(decoy["to_address"]),
                        "full_address": decoy["to_address"],
                        "role": "decoy",
                        "sublabel": "Smaller amount — not followed",
                        "taint": None,
                        "threat_intel": False,
                    }
                })
                edges.append({
                    "data": {
                        "id": f"e-decoy-{i}-{j}",
                        "source": hop["wallet"],
                        "target": decoy_node_id,
                        "amount": decoy["amount"],
                        "label": f"{decoy['amount']:,.2f} USDT",
                        "kind": "decoy",
                    }
                })

    return {"nodes": nodes, "edges": edges}


def build_evidence_table(trace_result: dict) -> list:
    """Flatten the trace into a list of transaction rows for the evidence table."""
    rows = []
    if trace_result.get("victim_tx"):
        vt = trace_result["victim_tx"]
        rows.append({
            "hop_index": -1,
            "role": "victim_payment",
            "hash": vt["hash"],
            "from_address": vt["from_address"],
            "to_address": vt["to_address"],
            "amount": vt["amount"],
            "timestamp_iso": _iso(vt["timestamp_ms"]),
        })

    for hop in trace_result["hops"]:
        chosen = hop.get("chosen_outgoing")
        if chosen:
            rows.append({
                "hop_index": hop["hop_index"],
                "role": "sweeper_match" if hop["is_sweeper_match"] else "main_trail",
                "hash": chosen["hash"],
                "from_address": chosen["from_address"],
                "to_address": chosen["to_address"],
                "amount": chosen["amount"],
                "timestamp_iso": _iso(chosen["timestamp_ms"]),
            })
        for decoy in hop.get("decoys", []):
            rows.append({
                "hop_index": hop["hop_index"],
                "role": "decoy",
                "hash": decoy["hash"],
                "from_address": decoy["from_address"],
                "to_address": decoy["to_address"],
                "amount": decoy["amount"],
                "timestamp_iso": _iso(decoy["timestamp_ms"]),
            })
    return rows
