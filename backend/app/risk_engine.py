"""
Risk scoring — a fixed, transparent weighted formula. No machine learning,
no training pipeline. Every factor is shown in the breakdown so an officer
(or a defense lawyer) can see exactly how a score was produced.

    score = taint_level        * 0.30
          + hop_depth_score    * 0.15
          + sweep_timing_match * 0.25
          + bot_speed_flag     * 0.15
          + threat_intel_hit   * 0.15

    >= 0.70            -> HIGH
    0.40 <= score < 0.70 -> MEDIUM
    < 0.40             -> LOW
"""
from app.config import (
    WEIGHT_TAINT,
    WEIGHT_HOP_DEPTH,
    WEIGHT_SWEEP_TIMING,
    WEIGHT_BOT_SPEED,
    WEIGHT_THREAT_INTEL,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
)


def compute_risk_score(trace_result: dict) -> dict:
    max_hops = trace_result["max_hops"]
    terminal_hop = trace_result["terminal_hop_index"]

    taint_level = trace_result["final_taint_level"]
    hop_depth_score = round(1 - (terminal_hop / max_hops), 4) if max_hops else 0.0
    sweep_timing_match = 1.0 if trace_result["match_status"] == "SWEEPER_MATCH" else 0.0
    bot_speed_flag = 1.0 if trace_result["bot_speed_flag"] else 0.0
    threat_intel_hit = 1.0 if trace_result["threat_intel_hit"] else 0.0

    contributions = {
        "taint_level": {
            "raw_value": round(taint_level, 4),
            "weight": WEIGHT_TAINT,
            "weighted": round(taint_level * WEIGHT_TAINT, 4),
            "label": "Taint level",
            "explanation": "How much of the traced fund's identity survives the splits along the path.",
        },
        "hop_depth_score": {
            "raw_value": hop_depth_score,
            "weight": WEIGHT_HOP_DEPTH,
            "weighted": round(hop_depth_score * WEIGHT_HOP_DEPTH, 4),
            "label": "Hop depth",
            "explanation": f"Trail resolved at hop {terminal_hop} of {max_hops} — fewer hops scores higher.",
        },
        "sweep_timing_match": {
            "raw_value": sweep_timing_match,
            "weight": WEIGHT_SWEEP_TIMING,
            "weighted": round(sweep_timing_match * WEIGHT_SWEEP_TIMING, 4),
            "label": "Sweep-timing match",
            "explanation": "Wallet forwarded 95%+ of received funds to a known exchange within 24 hours."
            if sweep_timing_match else "No fast near-total sweep to a known exchange detected.",
        },
        "bot_speed_flag": {
            "raw_value": bot_speed_flag,
            "weight": WEIGHT_BOT_SPEED,
            "weighted": round(bot_speed_flag * WEIGHT_BOT_SPEED, 4),
            "label": "Automated timing pattern",
            "explanation": "Outgoing transfers fire at suspiciously regular intervals (script-like)."
            if bot_speed_flag else "Outgoing transfer timing looks human / irregular.",
        },
        "threat_intel_hit": {
            "raw_value": threat_intel_hit,
            "weight": WEIGHT_THREAT_INTEL,
            "weighted": round(threat_intel_hit * WEIGHT_THREAT_INTEL, 4),
            "label": "Threat-intel hit",
            "explanation": trace_result.get("threat_intel_note") or "No wallet in this trail is on the known-scam-wallet list.",
        },
    }

    total_score = round(sum(c["weighted"] for c in contributions.values()), 4)
    # guard against float creep just above 1.0 from rounding
    total_score = min(total_score, 1.0)

    if total_score >= PRIORITY_HIGH_THRESHOLD:
        priority = "HIGH"
    elif total_score >= PRIORITY_MEDIUM_THRESHOLD:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "total_score": total_score,
        "priority": priority,
        "factors": contributions,
    }
