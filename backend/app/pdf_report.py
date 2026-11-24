"""
Generates a printable case-summary PDF for a traced case.

Layout is a plain, professional report (light background — this is meant
to be printed / attached to a case file, not read on a screen), with a
navy header band to keep a visual thread back to the console's theme.
"""
import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_LEFT

from app.config import REPORTS_DIR

NAVY = colors.HexColor("#0F1720")
STEEL = colors.HexColor("#3E7CB8")
INK_MUTED = colors.HexColor("#4A5568")
HIGH_RED = colors.HexColor("#B3452F")
MED_AMBER = colors.HexColor("#B8863B")
LOW_GREEN = colors.HexColor("#4C7A6B")

PRIORITY_COLORS = {"HIGH": HIGH_RED, "MEDIUM": MED_AMBER, "LOW": LOW_GREEN}
VERIFIED_GREEN = colors.HexColor("#276749")   # distinct from LOW priority's green — this means "confirmed real"
SAMPLE_AMBER = colors.HexColor("#9C6B1F")     # caution color for "this is placeholder data"

MATCH_STATUS_LABELS = {
    "EXCHANGE_MATCH": "Confirmed exchange match",
    "SWEEPER_MATCH": "Confirmed exchange match (sweeper pattern)",
    "IN_TRANSIT": "In transit — no exchange match yet",
    "MIXER_FLAGGED": "Trail entered a known mixer — tracing stopped",
    "TRACE_FAILED": "Trace could not complete — Tronscan unavailable",
}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle(name="ReportTitle", fontSize=18, leading=22, textColor=colors.white,
                           fontName="Helvetica-Bold"))
    ss.add(ParagraphStyle(name="ReportSubtitle", fontSize=10, leading=13, textColor=colors.whitesmoke))
    ss.add(ParagraphStyle(name="SectionHeading", fontSize=12, leading=15, textColor=NAVY,
                           fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle(name="BodySmall", fontSize=9, leading=12.5, textColor=colors.HexColor("#1A202C")))
    ss.add(ParagraphStyle(name="Mono", fontName="Courier", fontSize=8.5, leading=11,
                           textColor=colors.HexColor("#1A202C")))
    ss.add(ParagraphStyle(name="MonoSmallWhite", fontName="Courier", fontSize=8.5, leading=11,
                           textColor=colors.whitesmoke))
    ss.add(ParagraphStyle(name="Disclaimer", fontSize=7.5, leading=10, textColor=INK_MUTED,
                           fontName="Helvetica-Oblique"))
    return ss


def _header_flowables(case: dict, styles):
    flow = []
    header_table = Table(
        [[
            Paragraph("ChainTracer India", styles["ReportTitle"]),
            Paragraph(f"Case {case['case_number']}<br/>Cyber Cell Investigation Report",
                      styles["ReportSubtitle"]),
        ]],
        colWidths=[95 * mm, 85 * mm],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (0, 0), 14),
        ("RIGHTPADDING", (1, 0), (1, 0), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    flow.append(header_table)
    flow.append(Spacer(1, 10))
    return flow


def _case_details_table(case: dict, styles):
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    rows = [
        ["Victim name", case["victim_name"], "Reported amount", f"{case['amount_usdt']:,.2f} USDT"],
        ["Wallet reported", Paragraph(case["wallet_address"], styles["Mono"]), "Report generated", generated],
        ["Case filed", case.get("created_at", ""), "Investigating status", case.get("status", "")],
    ]
    t = Table(rows, colWidths=[32 * mm, 65 * mm, 32 * mm, 51 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), INK_MUTED),
        ("TEXTCOLOR", (2, 0), (2, -1), INK_MUTED),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    if case.get("notes"):
        return [t, Spacer(1, 6), Paragraph(f"<b>Notes:</b> {case['notes']}", styles["BodySmall"])]
    return [t]


def _priority_banner(case: dict, styles):
    priority = case.get("priority") or "LOW"
    score = case.get("risk_score") or 0.0
    color = PRIORITY_COLORS.get(priority, LOW_GREEN)
    match_label = MATCH_STATUS_LABELS.get(case.get("match_status"), case.get("match_status") or "Unknown")

    t = Table(
        [[
            Paragraph(f"<b>{priority} PRIORITY</b>", ParagraphStyle(
                name="P1", fontSize=13, textColor=colors.white, fontName="Helvetica-Bold")),
            Paragraph(f"Risk score: <b>{score:.2f}</b> / 1.00", ParagraphStyle(
                name="P2", fontSize=11, textColor=colors.white)),
            Paragraph(match_label, ParagraphStyle(
                name="P3", fontSize=10, textColor=colors.white, alignment=TA_LEFT)),
        ]],
        colWidths=[50 * mm, 55 * mm, 75 * mm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, 0), 12),
    ]))
    return t


def _exchange_attribution_banner(case: dict, styles):
    """
    A dedicated callout for the exchange match result — kept visually
    separate from the priority banner specifically so a verified match
    can never be mistaken for (or visually blend in with) a sample-data
    match. Returns None when there's nothing to attribute (IN_TRANSIT,
    MIXER_FLAGGED, TRACE_FAILED, or no match yet).
    """
    if not case.get("matched_exchange"):
        return None

    verified = case.get("matched_exchange_verified")
    note = case.get("matched_exchange_note") or case["matched_exchange"]
    color = VERIFIED_GREEN if verified else SAMPLE_AMBER
    heading = "VERIFIED EXCHANGE MATCH" if verified else "SAMPLE-DATA EXCHANGE MATCH — NOT REAL"

    t = Table(
        [[
            Paragraph(f"<b>{heading}</b>", ParagraphStyle(
                name="EAHeading", fontSize=10, textColor=colors.white, fontName="Helvetica-Bold")),
            Paragraph(note, ParagraphStyle(
                name="EABody", fontSize=9.5, textColor=colors.white)),
        ]],
        colWidths=[62 * mm, 118 * mm],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, 0), 12),
    ]))
    return t


def _risk_breakdown_table(risk_breakdown: dict, styles):
    header = ["Factor", "Raw value", "Weight", "Weighted", "What it means"]
    rows = [header]
    for key, f in risk_breakdown["factors"].items():
        rows.append([
            Paragraph(f"<b>{f['label']}</b>", styles["BodySmall"]),
            f"{f['raw_value']:.2f}",
            f"{f['weight']:.2f}",
            f"{f['weighted']:.3f}",
            Paragraph(f["explanation"], styles["BodySmall"]),
        ])
    rows.append(["", "", "Total", f"{risk_breakdown['total_score']:.3f}", ""])

    t = Table(rows, colWidths=[36 * mm, 19 * mm, 16 * mm, 19 * mm, 92 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FAFC")]),
        ("FONTNAME", (2, -1), (3, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
    ]))
    return t


def _hop_trail_table(trace_result: dict, styles):
    header = ["Hop", "Wallet", "Role / outcome", "Amount forwarded"]
    rows = [header]
    for hop in trace_result["hops"]:
        role = "Source wallet (victim-reported)" if hop["hop_index"] == 0 else f"Hop {hop['hop_index']}"
        if hop["is_exchange_match"]:
            confidence_tag = "Verified" if hop["matched_exchange_verified"] else "Sample"
            role += f" — {confidence_tag} match: {hop['matched_exchange_name']}"
        elif hop["is_mixer_flag"]:
            role += " — known mixer, tracing stopped"
        amount = hop["chosen_outgoing"]["amount"] if hop.get("chosen_outgoing") else "—"
        amount_str = f"{amount:,.2f} USDT" if isinstance(amount, (int, float)) else amount
        rows.append([str(hop["hop_index"]), Paragraph(hop["wallet"], styles["Mono"]), role, amount_str])

    t = Table(rows, colWidths=[12 * mm, 62 * mm, 68 * mm, 40 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
    ]))
    return t


def _evidence_table(evidence: list, styles):
    header = ["Hop", "Role", "Tx hash", "From", "To", "Amount", "Timestamp (UTC)"]
    rows = [header]
    role_labels = {
        "victim_payment": "Victim payment",
        "main_trail": "Main trail",
        "sweeper_match": "Sweeper match",
        "decoy": "Decoy",
    }
    for row in evidence:
        rows.append([
            str(row["hop_index"]) if row["hop_index"] >= 0 else "—",
            role_labels.get(row["role"], row["role"]),
            Paragraph(row["hash"][:18] + "…" if len(row["hash"]) > 18 else row["hash"], styles["Mono"]),
            Paragraph(row["from_address"][:14] + "…", styles["Mono"]),
            Paragraph(row["to_address"][:14] + "…", styles["Mono"]),
            f"{row['amount']:,.2f}",
            row["timestamp_iso"],
        ])
    t = Table(rows, colWidths=[10 * mm, 22 * mm, 30 * mm, 28 * mm, 28 * mm, 20 * mm, 42 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
    ]))
    return t


TRONSCAN_TX_URL = "https://tronscan.org/#/transaction/{}"
TRONSCAN_ADDR_URL = "https://tronscan.org/#/address/{}"


def _plain_summary_text(case: dict) -> str:
    """
    One plain-language paragraph a non-technical reader can follow. Built
    only from fields the trace already produced — it never adds a claim
    the trace didn't make.
    """
    tr = case.get("trace_result") or {}
    hops = len(tr.get("hops") or [])
    max_hops = tr.get("max_hops")
    status = case.get("match_status") or ""
    wallet = case.get("wallet_address", "")
    amount = f"{case['amount_usdt']:,.2f} USDT"

    if case.get("status") == "RATE_LIMITED":
        return (f"{amount} was reported as sent to wallet {wallet}. The trace could not be "
                f"completed right now because the blockchain data service was temporarily busy. "
                f"Re-run the trace before relying on this report.")

    lead = f"{amount} was reported as sent to wallet {wallet}. The public blockchain record shows "
    if status in ("EXCHANGE_MATCH", "SWEEPER_MATCH"):
        ex = case.get("matched_exchange") or "a known exchange"
        verified = case.get("matched_exchange_verified")
        basis = ("a wallet listed as a verified exchange wallet" if verified
                 else "a wallet matching SAMPLE data only (not a real exchange address)")
        if verified:
            action = (f"Exchanges can identify their own account holders, so the next step is a "
                      f"request to {ex} with the transaction references below.")
        else:
            action = ("This match is not a verified exchange address, so do not send a complaint "
                      "to the exchange based on it. Re-check the wallet on tronscan.org first.")
        return (lead + f"the money moved through {hops} wallet(s) and reached {basis} "
                f"belonging to {ex}. " + action)
    if status == "MIXER_FLAGGED":
        return (lead + f"the money reached a wallet on a known mixing service after {hops} "
                f"step(s). Mixers hide the trail, so tracing stopped there.")
    if status == "IN_TRANSIT":
        limit = f" within {max_hops} steps" if max_hops else ""
        return (lead + f"the money was still moving between wallets when tracing ended{limit}. "
                f"No known exchange wallet was reached. The trail can be re-checked later as "
                f"new transactions appear.")
    return (lead + f"the trail was traced for {hops} step(s). See the evidence table for the "
            f"exact transactions.")


def _verify_section(case: dict, styles):
    """Links the complainant can open to check every reference independently."""
    if case.get("is_seed"):
        return [Paragraph(
            "Demonstration case: the references in this report are synthetic and will not open "
            "on tronscan.org. Verification links are only meaningful for real filed cases.",
            styles["BodySmall"])]
    items = [Paragraph(
        "<b>Verify it yourself:</b> every transaction and wallet below can be opened on "
        "tronscan.org, a public blockchain explorer. Matching the references here with the "
        "explorer confirms this report is accurate.", styles["BodySmall"])]
    items.append(Spacer(1, 4))
    items.append(Paragraph(
        "Reported wallet: " + TRONSCAN_ADDR_URL.format(case["wallet_address"]), styles["Mono"]))
    for row in (case.get("evidence") or [])[:8]:
        h = row.get("hash")
        if h:
            items.append(Paragraph(
                f"{row.get('role', 'transaction')}: " + TRONSCAN_TX_URL.format(h), styles["Mono"]))
    evidence_count = len(case.get("evidence") or [])
    if evidence_count > 8:
        items.append(Paragraph(
            f"...and {evidence_count - 8} more, listed in the Transaction evidence table.",
            styles["BodySmall"]))
    return items


def _complaint_guidance(styles):
    return Paragraph(
        "<b>Using this report for a complaint:</b> attach this PDF along with the victim's "
        "screenshots, bank or wallet receipts and the transaction references above when "
        "filing with the national cybercrime reporting portal (cybercrime.gov.in), the bank, "
        "or the exchange's support team. The investigating authority decides what action to "
        "take. This report does not itself establish who received the money.",
        styles["BodySmall"])


def generate_case_pdf(case: dict) -> str:
    """
    Build the PDF for a case dict (as produced by database.row_to_case_dict)
    and return the absolute file path it was written to.
    """
    filename = f"{case['case_number']}_report.pdf"
    output_path = os.path.join(REPORTS_DIR, filename)
    styles = _styles()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=0, bottomMargin=16 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
        title=f"ChainTracer India — Case {case['case_number']}",
    )

    story = []
    story += _header_flowables(case, styles)
    story.append(Spacer(1, 4))
    story += _case_details_table(case, styles)
    story.append(Spacer(1, 12))

    story.append(_priority_banner(case, styles))
    story.append(Spacer(1, 8))

    exchange_banner = _exchange_attribution_banner(case, styles)
    if exchange_banner:
        story.append(exchange_banner)
        story.append(Spacer(1, 14))
    else:
        story.append(Spacer(1, 6))

    story.append(Paragraph("What this report shows", styles["SectionHeading"]))
    story.append(Paragraph(_plain_summary_text(case), styles["BodySmall"]))
    story.append(Spacer(1, 10))
    story.append(_complaint_guidance(styles))
    story.append(Spacer(1, 10))

    if case.get("is_seed"):
        story.append(Paragraph(
            "This is a demonstration case pre-loaded with the application. Wallet addresses, "
            "exchange attributions, and transaction data below are synthetic sample data, not "
            "real blockchain records.", styles["Disclaimer"]))
        story.append(Spacer(1, 8))

    if case.get("risk_breakdown"):
        story.append(Paragraph("Risk score breakdown", styles["SectionHeading"]))
        story.append(Paragraph(
            "Fixed weighted formula — not a machine-learning prediction. Every factor below is "
            "shown so the score can be independently checked.", styles["BodySmall"]))
        story.append(Spacer(1, 6))
        story.append(_risk_breakdown_table(case["risk_breakdown"], styles))
        story.append(Spacer(1, 14))

    if case.get("trace_result"):
        story.append(Paragraph("Fund trail", styles["SectionHeading"]))
        story.append(Paragraph(
            "At each wallet, the largest outgoing transfer was followed as the main trail; "
            "smaller simultaneous transfers are logged separately as decoys in the evidence table.",
            styles["BodySmall"]))
        story.append(Spacer(1, 6))
        story.append(_hop_trail_table(case["trace_result"], styles))
        story.append(Spacer(1, 14))

    if case.get("evidence"):
        story.append(PageBreak())
        story.append(Paragraph("Transaction evidence", styles["SectionHeading"]))
        story.append(_evidence_table(case["evidence"], styles))
        story.append(Spacer(1, 14))

    if case.get("status") != "RATE_LIMITED":
        story.append(Spacer(1, 4))
        story.append(Paragraph("Verify on the public blockchain", styles["SectionHeading"]))
        story += _verify_section(case, styles)
        story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Disclaimer: this report is an investigative aid generated by ChainTracer India from "
        "publicly available blockchain records. It is not a legal finding and does not establish "
        "who controls any wallet. It does not freeze accounts, contact exchanges, or move funds. "
        "The trail, risk score and exchange attribution should be independently verified by the "
        "receiving authority before any action is taken.", styles["Disclaimer"]))

    doc.build(story)
    return output_path