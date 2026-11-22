"""
All case-related API routes.

Endpoints:
    GET  /api/cases                     -> list of case summaries (sidebar)
    GET  /api/cases/{case_number}        -> full case detail (graph/risk/evidence)
    POST /api/cases                      -> file a new case; runs the trace synchronously
    GET  /api/cases/{case_number}/report -> generate + download the PDF summary
    POST /api/cases/{case_number}/alert  -> SIMULATED exchange-alert flag only
    GET  /api/reference-lists            -> the sample threat-intel lists (for transparency)
"""
import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.database import get_cursor, row_to_case_dict
from app.routers.auth import require_auth
from app.tron_client import TronApiError, TronRateLimitError, is_valid_tron_address
from app.trace_engine import trace_wallet, build_graph, build_evidence_table
from app.risk_engine import compute_risk_score
from app.pdf_report import generate_case_pdf
from app.exchange_list import KNOWN_EXCHANGE_WALLETS, KNOWN_SCAM_WALLETS, KNOWN_MIXER_WALLETS
from app.schemas import NewCaseRequest
from app.config import DEFAULT_MAX_HOPS

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _next_case_number(cur) -> str:
    year = datetime.now(timezone.utc).year
    cur.execute("SELECT COUNT(*) AS n FROM cases WHERE case_number LIKE ?", (f"CCU-{year}-%",))
    n = cur.fetchone()["n"] + 1
    return f"CCU-{year}-{n:04d}"


def _unverified_amount_message(trace_result: dict, reported_amount: float) -> str:
    hop0 = trace_result["hops"][0]
    nearby = hop0.get("nearby_incoming_amounts") or []
    if trace_result["stop_reason"] == "NO_INCOMING_HISTORY":
        return (
            f"This wallet has no recorded incoming USDT-TRC20 transfers at all, so the "
            f"reported amount ({reported_amount:,.2f} USDT) could not be verified against "
            f"anything. Double-check the wallet address with the victim — a single wrong "
            f"character produces a different, unrelated real wallet."
        )
    nearby_str = ", ".join(f"{a:,.2f}" for a in nearby) if nearby else "none close enough"
    return (
        f"Could not find an incoming transfer of about {reported_amount:,.2f} USDT to this "
        f"wallet. Closest amounts it actually received: {nearby_str} USDT. Double-check the "
        f"amount and wallet address with the victim before re-filing — this case was saved "
        f"but was not traced further, so nothing below is fabricated from an unrelated "
        f"transaction."
    )


def _fetch_case_row(case_number: str, user_id: int):
    """
    Fetch a case ONLY if it belongs to this user. A case owned by someone
    else is indistinguishable from a case that doesn't exist — both return
    None, so callers 404. Returning 403 would confirm the case number exists.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM cases WHERE case_number=? AND owner_user_id=?",
            (case_number, user_id),
        )
        return cur.fetchone()


@router.get("/cases")
def list_cases(user: dict = Depends(require_auth)):
    with get_cursor() as cur:
        cur.execute("""
            SELECT case_number, victim_name, wallet_address, amount_usdt, status,
                   match_status, matched_exchange, matched_exchange_verified, risk_score,
                   priority, is_seed, alert_sent, created_at
            FROM cases WHERE owner_user_id=? ORDER BY id DESC
        """, (user["id"],))
        rows = cur.fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["is_seed"] = bool(d["is_seed"])
        d["alert_sent"] = bool(d["alert_sent"])
        if d.get("matched_exchange_verified") is not None:
            d["matched_exchange_verified"] = bool(d["matched_exchange_verified"])
        out.append(d)
    return out


@router.get("/cases/{case_number}")
def get_case(case_number: str, user: dict = Depends(require_auth)):
    row = _fetch_case_row(case_number, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
    return row_to_case_dict(row)


@router.post("/cases", status_code=201)
async def create_case(payload: NewCaseRequest, user: dict = Depends(require_auth)):
    wallet = payload.wallet_address

    if not is_valid_tron_address(wallet):
        raise HTTPException(
            status_code=400,
            detail=(
                "That doesn't look like a valid TRON address. A TRON address starts "
                "with 'T' and is 34 characters long. Double-check it against what the "
                "victim shared (screenshot, receipt, or wallet app)."
            ),
        )

    now = _now()
    with get_cursor(commit=True) as cur:
        case_number = _next_case_number(cur)
        cur.execute(
            """INSERT INTO cases (case_number, victim_name, wallet_address, amount_usdt, notes,
                                   status, is_seed, alert_sent, created_at, updated_at,
                                   owner_user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (case_number, payload.victim_name, wallet, payload.amount_usdt,
             payload.notes, "TRACING", 0, 0, now, now, user["id"]),
        )

    # The Tronscan calls inside trace_wallet are blocking (requests library),
    # so run the whole trace in a worker thread and let this coroutine await it —
    # this keeps the event loop free for other officers' requests in the meantime.
    try:
        trace_result = await asyncio.to_thread(
            trace_wallet, wallet, payload.amount_usdt, DEFAULT_MAX_HOPS
        )
    except TronRateLimitError as exc:
        # Distinct from a genuine failure: Tronscan is rate-limiting us
        # right now, which says nothing about whether the wallet address
        # or amount the officer entered was correct. Its own status
        # (RATE_LIMITED, not FAILED) and HTTP 429 (not 502) so nothing
        # here reads as "your input was wrong" — because it wasn't.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE cases SET status=?, match_status=?, error_message=?, updated_at=?
                   WHERE case_number=?""",
                ("RATE_LIMITED", "RATE_LIMITED", str(exc), _now(), case_number),
            )
        raise HTTPException(
            status_code=429,
            detail=f"Tronscan is rate-limiting requests right now — this is not a problem "
                   f"with the wallet address or amount you entered. Please wait a moment and "
                   f"try again. (Case {case_number} was saved; re-file it to retry, or add a "
                   f"free Tronscan API key to raise the limit — see the README.)",
        )
    except TronApiError as exc:
        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE cases SET status=?, match_status=?, error_message=?, updated_at=?
                   WHERE case_number=?""",
                ("FAILED", "TRACE_FAILED", str(exc), _now(), case_number),
            )
        raise HTTPException(
            status_code=502,
            detail=f"Tronscan could not be reached to trace this wallet: {exc}. "
                   f"The case has been saved as {case_number} — retry once connectivity is back.",
        )
    except ValueError as exc:
        # Defensive: address format already validated above, but don't lose the
        # saved case record if trace_wallet's own check disagrees for some reason.
        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE cases SET status=?, match_status=?, error_message=?, updated_at=?
                   WHERE case_number=?""",
                ("FAILED", "TRACE_FAILED", str(exc), _now(), case_number),
            )
        raise HTTPException(status_code=400, detail=str(exc))

    if trace_result["match_status"] == "TRACE_INCOMPLETE_RATE_LIMITED":
        # The trace got partway through (real hops may have completed)
        # before Tronscan started rate-limiting mid-trace. This is NOT a
        # conclusion that the trail ended — don't score it as if it were.
        # Reuses the same "RATE_LIMITED" case status as the hop-0 case so
        # the UI gives the identical "try again" treatment either way.
        graph = build_graph(trace_result)
        evidence = build_evidence_table(trace_result)
        hops_done = len(trace_result["hops"])
        message = (
            f"Tracing stopped after {hops_done} hop(s) because Tronscan started "
            f"rate-limiting requests — this is not a conclusion that the trail ended, just "
            f"that we couldn't check further right now. Re-file this case to retry with a "
            f"fresh trace, or add a free Tronscan API key to raise the limit."
        )
        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE cases SET
                       status=?, match_status=?, error_message=?,
                       trace_result_json=?, graph_json=?, evidence_json=?, updated_at=?
                   WHERE case_number=?""",
                ("RATE_LIMITED", "TRACE_INCOMPLETE_RATE_LIMITED", message,
                 json.dumps(trace_result), json.dumps(graph), json.dumps(evidence),
                 _now(), case_number),
            )
        row = _fetch_case_row(case_number, user["id"])
        return row_to_case_dict(row)

    if trace_result["match_status"] == "AMOUNT_NOT_VERIFIED":
        # Do NOT compute a risk score or an exchange match for this case —
        # there is nothing verified to score. Store just the source-wallet
        # graph (one node, no trail) and a clear, actionable message so the
        # officer can fix the amount or address rather than being shown a
        # confident-looking result built on an unconfirmed premise.
        graph = build_graph(trace_result)
        evidence = build_evidence_table(trace_result)
        message = _unverified_amount_message(trace_result, payload.amount_usdt)

        with get_cursor(commit=True) as cur:
            cur.execute(
                """UPDATE cases SET
                       status=?, match_status=?, error_message=?,
                       trace_result_json=?, graph_json=?, evidence_json=?, updated_at=?
                   WHERE case_number=?""",
                ("UNVERIFIED", "AMOUNT_NOT_VERIFIED", message,
                 json.dumps(trace_result), json.dumps(graph), json.dumps(evidence),
                 _now(), case_number),
            )
        row = _fetch_case_row(case_number, user["id"])
        return row_to_case_dict(row)

    risk = compute_risk_score(trace_result)
    graph = build_graph(trace_result)
    evidence = build_evidence_table(trace_result)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE cases SET
                   status=?, match_status=?, matched_exchange=?, matched_exchange_verified=?,
                   matched_exchange_note=?, matched_wallet=?,
                   risk_score=?, priority=?, trace_result_json=?, risk_breakdown_json=?,
                   graph_json=?, evidence_json=?, updated_at=?
               WHERE case_number=?""",
            ("TRACED", trace_result["match_status"], trace_result["matched_exchange"],
             trace_result["matched_exchange_verified"], trace_result["matched_exchange_note"],
             trace_result["matched_wallet"], risk["total_score"], risk["priority"],
             json.dumps(trace_result), json.dumps(risk), json.dumps(graph),
             json.dumps(evidence), _now(), case_number),
        )

    row = _fetch_case_row(case_number, user["id"])
    return row_to_case_dict(row)


@router.get("/cases/{case_number}/report")
def download_report(case_number: str, user: dict = Depends(require_auth)):
    row = _fetch_case_row(case_number, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
    case = row_to_case_dict(row)
    if case["status"] != "TRACED":
        raise HTTPException(
            status_code=409,
            detail="A report can only be generated once tracing has finished for this case.",
        )
    path = generate_case_pdf(case)
    return FileResponse(
        path, media_type="application/pdf", filename=os.path.basename(path)
    )


@router.post("/cases/{case_number}/alert")
def send_alert(case_number: str, user: dict = Depends(require_auth)):
    """
    SIMULATION ONLY. This never contacts a real exchange, sends a real email/SMS,
    or freezes anything — it just records that an officer chose to raise an alert,
    so the UI can show that state. Wiring this to a real liaison channel is out
    of scope for this tool by design.
    """
    row = _fetch_case_row(case_number, user["id"])
    if not row:
        raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
    case = row_to_case_dict(row)
    if not case.get("matched_exchange"):
        raise HTTPException(
            status_code=409,
            detail="This case has no exchange match yet, so there's no destination to alert.",
        )

    now = _now()
    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE cases SET alert_sent=1, updated_at=? WHERE case_number=? AND owner_user_id=?",
            (now, case_number, user["id"]),
        )

    verified = case.get("matched_exchange_verified")
    confidence_note = (
        "This is a verified, Tronscan-labeled address."
        if verified
        else "Note: this match is against SAMPLE/placeholder data, not a real exchange address."
    )

    return {
        "simulated": True,
        "case_number": case_number,
        "sent_at": now,
        "message": (
            f"Simulated alert prepared for {case['matched_exchange']}. No real email, SMS, "
            "or API call was sent — connect an official liaison channel to actually notify "
            f"an exchange or freeze funds. {confidence_note}"
        ),
    }


@router.get("/reference-lists")
def reference_lists():
    """Expose the hardcoded sample lists so the UI can show officers exactly what's being checked."""
    return {
        "known_exchange_wallets": KNOWN_EXCHANGE_WALLETS,
        "known_scam_wallets": KNOWN_SCAM_WALLETS,
        "known_mixer_wallets": KNOWN_MIXER_WALLETS,
        "disclaimer": (
            "Sample / placeholder addresses for demonstration only. These are procedurally "
            "generated strings shaped like real TRON addresses — they are NOT the real hot "
            "wallets of Binance, WazirX, CoinDCX, OKX, or any other exchange."
        ),
    }