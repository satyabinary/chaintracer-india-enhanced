"""
Hardcoded threat-intelligence lists used for attribution matching.

HOW THIS IS USED — important: this is a general pattern-lookup, not a list
tied to any particular case or expected destination. Every wallet in every
trail, for every case, gets checked against KNOWN_EXCHANGE_WALLETS as the
trace walks forward. A match just means "this specific wallet, wherever it
turned up, happens to be a known exchange deposit address" — it says
nothing about which exchange a given scammer was expected to use, and
nothing here should be read as "scammer X will use exchange Y". Real
scammers can and do cash out at any exchange; the list only helps
recognise it *when it happens*, for any trail that reaches one of these
addresses.

Two kinds of entries live in KNOWN_EXCHANGE_WALLETS, distinguished by the
"verified" field on each record:

  verified=True  — sourced from Tronscan's own address labels, as supplied
                   by the investigating officer. ChainTracer's own tooling
                   could not independently re-confirm these against a
                   second public source (see note below) — reconfirm on
                   tronscan.org yourself before relying on this label in
                   front of anyone, especially before a live presentation.

  verified=False — SAMPLE / PLACEHOLDER addresses for demonstration only.
                   Procedurally-generated strings that merely look like
                   valid TRON addresses (34 chars, start with "T", Base58
                   alphabet). They are NOT real hot wallets of Binance,
                   WazirX, CoinDCX, OKX, or anyone else.

In a production deployment this module would be replaced with a real,
regularly-updated threat-intel feed (exchange-confirmed deposit wallets,
FIR-reported scam addresses, known mixer/tumbler addresses) — most likely
loaded from a database table rather than hardcoded in source.
"""

# Wallet address -> {"name": exchange display name, "verified": bool, "note": str}.
#
# The 9 "verified" entries were supplied by the investigating officer as
# sourced from Tronscan's own address labels. Before relying on this flag
# in a presentation: reload each address on tronscan.org yourself and
# confirm the label still shows — a single wrong character turns a real
# address into a dead (or worse, a *different real*) one, and exchanges
# occasionally rotate hot wallets, so a label can also simply go stale.
KNOWN_EXCHANGE_WALLETS = {
    # --- Sample / placeholder data (demo only, not real addresses) --------
    "TJJrZ7tLBpdJKZYnbPqb16uezLtb5Aa5zT": {
        "name": "Binance", "verified": False, "note": "Sample hot wallet #1 (placeholder)",
    },
    "TwaZ1tfzZkfA8P5jpDr6jJ7yjWXSpUxHr8": {
        "name": "Binance", "verified": False, "note": "Sample hot wallet #2 (placeholder)",
    },
    "TxwsmFJr54bMV6Dc9xFfhZYV7SeEkfYWZr": {
        "name": "WazirX", "verified": False, "note": "Sample hot wallet #1 (placeholder)",
    },
    "TiDccBndCNzuoTdwZxwaSPzu3ujSQQmnyL": {
        "name": "WazirX", "verified": False, "note": "Sample hot wallet #2 (placeholder)",
    },
    "T6aXjDKzZCxkun4APZzjf8q7BsMAanTtWW": {
        "name": "CoinDCX", "verified": False, "note": "Sample hot wallet #1 (placeholder)",
    },
    "TkB4S2TcythanfvNCyWM768vdMphYLfFaC": {
        "name": "OKX", "verified": False, "note": "Sample hot wallet #1 (placeholder)",
    },

    # --- Verified — sourced from Tronscan address labels ------------------
    "TNXoiAJ3dct8Fjg4M9fkLFh9S2v9TXc32G": {
        "name": "Binance", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y": {
        "name": "Binance", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TCLgK89AnXbC9rewvhNb9UgXCc2qJJpBXh": {
        "name": "Binance", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TAzsQ9Gx8eqFNFSKbeXrbi45CuVPHzA8wr": {
        "name": "Binance", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TLaGjwhvA8XQYSxFAcAXy7Dvuue9eGYitv": {
        "name": "OKX", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TUpHuDkiCCmwaTZBHZvQdwWzGNm5t8J2b9": {
        "name": "KuCoin", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TBA6CypYJizwA9XdC7Ubgc5F1bxrQ7SqPt": {
        "name": "Gate.io", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TU4vEruvZwLLkSfV9bNw12EJTPvNr7Pvaa": {
        "name": "Bybit", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
    "TJ7hhYhVhaxNx6BPyq7yFpqZrQULL3JSdb": {
        "name": "Bitget", "verified": True, "note": "Tronscan-labeled hot wallet",
    },
}

# Wallets previously reported / flagged in prior cyber-cell cases.
# A hit here means "this exact address has come up in fraud investigations
# before" — independent of whether it happens to sit in today's trail.
KNOWN_SCAM_WALLETS = {
    "T5BBGJPggSXsK4QM8FyZYm4aHfsYsEXrHd": "Flagged in prior FIR — investment scam ring (sample)",
    "Ti7vfU4NjjsmTkuW9BqrDutY49AtwEjpYY": "Flagged in prior FIR — task-scam mule network (sample)",
    "TAVKvjCxhYpUfur4qCKsnSXgzXesmfoWxe": "Flagged by community threat-intel report (sample)",
    "Tip3WVChCukFbTRTW9DxpH4SNXGQsjdAby": "Flagged in prior FIR — romance scam (sample)",
}

# Known mixer / tumbler style addresses. This tool does NOT trace *through*
# mixers — it only flags that a trail touched one, per the "no real mixer
# tracing" scope decision. Tracing stops the moment one of these is hit.
KNOWN_MIXER_WALLETS = {
    "TfngXPSGe9FP67ffhEc6EBhDxwkwBRKsGL": "Known mixer/tumbler service (sample)",
    "TkKb5swwALujrZoyw2cUqU2C8D87WxhVaR": "Known mixer/tumbler service (sample)",
}


def match_exchange(address: str):
    """
    Return the full record {"name", "verified", "note"} if address is a
    known exchange wallet, else None. Callers needing just the display
    name use record["name"]; callers surfacing the match to a human should
    use format_exchange_label(record) below so the verified/sample wording
    can't drift out of sync between call sites.
    """
    return KNOWN_EXCHANGE_WALLETS.get(address)


def format_exchange_label(record: dict) -> str:
    """
    Single source of truth for how a matched exchange is described to a
    human (hop labels, PDF report, API 'matched_exchange_note' field). Kept
    here, next to the data it describes, so the frontend and PDF report
    can't independently invent their own wording for "verified" vs
    "sample" that might disagree with each other.
    """
    if record["verified"]:
        return f"Verified match — {record['name']} ({record['note']})"
    return f"Sample match — {record['name']} ({record['note']}, not a real address)"


def match_scam_wallet(address: str):
    """Return the threat-intel note if address is a known flagged scam wallet, else None."""
    return KNOWN_SCAM_WALLETS.get(address)


def match_mixer(address: str):
    """Return the mixer note if address is a known mixer wallet, else None."""
    return KNOWN_MIXER_WALLETS.get(address)
