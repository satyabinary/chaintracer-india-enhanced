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

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.database import get_cursor, row_to_case_dict
from app.tron_client import TronApiError, is_valid_tron_address
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


def _fetch_case_row(case_number: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM cases WHERE case_number=?", (case_number,))
        return cur.fetchone()


@router.get("/cases")
def list_cases():
    with get_cursor() as cur:
        cur.execute("""
            SELECT case_number, victim_name, wallet_address, amount_usdt, status,
                   match_status, matched_exchange, risk_score, priority, is_seed,
                   alert_sent, created_at
            FROM cases ORDER BY id DESC
        """)
        rows = cur.fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["is_seed"] = bool(d["is_seed"])
        d["alert_sent"] = bool(d["alert_sent"])
        out.append(d)
    return out


@router.get("/cases/{case_number}")
def get_case(case_number: str):
    row = _fetch_case_row(case_number)
    if not row:
        raise HTTPException(status_code=404, detail=f"Case {case_number} not found")
    return row_to_case_dict(row)


@router.post("/cases", status_code=201)
async def create_case(payload: NewCaseRequest):
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
                                   status, is_seed, alert_sent, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (case_number, payload.victim_name, wallet, payload.amount_usdt,
             payload.notes, "TRACING", 0, 0, now, now),
        )

    # The Tronscan calls inside trace_wallet are blocking (requests library),
    # so run the whole trace in a worker thread and let this coroutine await it —
    # this keeps the event loop free for other officers' requests in the meantime.
    try:
        trace_result = await asyncio.to_thread(
            trace_wallet, wallet, payload.amount_usdt, DEFAULT_MAX_HOPS
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

    risk = compute_risk_score(trace_result)
    graph = build_graph(trace_result)
    evidence = build_evidence_table(trace_result)

    with get_cursor(commit=True) as cur:
        cur.execute(
            """UPDATE cases SET
                   status=?, match_status=?, matched_exchange=?, matched_wallet=?,
                   risk_score=?, priority=?, trace_result_json=?, risk_breakdown_json=?,
                   graph_json=?, evidence_json=?, updated_at=?
               WHERE case_number=?""",
            ("TRACED", trace_result["match_status"], trace_result["matched_exchange"],
             trace_result["matched_wallet"], risk["total_score"], risk["priority"],
             json.dumps(trace_result), json.dumps(risk), json.dumps(graph),
             json.dumps(evidence), _now(), case_number),
        )

    row = _fetch_case_row(case_number)
    return row_to_case_dict(row)


@router.get("/cases/{case_number}/report")
def download_report(case_number: str):
    row = _fetch_case_row(case_number)
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
def send_alert(case_number: str):
    """
    SIMULATION ONLY. This never contacts a real exchange, sends a real email/SMS,
    or freezes anything — it just records that an officer chose to raise an alert,
    so the UI can show that state. Wiring this to a real liaison channel is out
    of scope for this tool by design.
    """
    row = _fetch_case_row(case_number)
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
        cur.execute("UPDATE cases SET alert_sent=1, updated_at=? WHERE case_number=?", (now, case_number))

    return {
        "simulated": True,
        "case_number": case_number,
        "sent_at": now,
        "message": (
            f"Simulated alert prepared for {case['matched_exchange']}. No real email, SMS, "
            "or API call was sent — connect an official liaison channel to actually notify "
            "an exchange or freeze funds."
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
