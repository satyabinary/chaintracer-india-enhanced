"""
Hardcoded threat-intelligence lists used for attribution matching.

*** THESE ARE SAMPLE / PLACEHOLDER ADDRESSES FOR DEMONSTRATION ONLY. ***
They are procedurally-generated strings that merely look like valid TRON
addresses (34 chars, start with "T", Base58 alphabet). They are NOT the
real hot wallets of Binance, WazirX, CoinDCX, OKX, or anyone else.

In a production deployment this module would be replaced with a real,
regularly-updated threat-intel feed (exchange-confirmed deposit wallets,
FIR-reported scam addresses, known mixer/tumbler addresses) — most likely
loaded from a database table rather than hardcoded in source.
"""

# Wallet address -> exchange display name.
# 3 sample exchanges, a couple of hot wallets each = 6 addresses total.
KNOWN_EXCHANGE_WALLETS = {
    "TJJrZ7tLBpdJKZYnbPqb16uezLtb5Aa5zT": "Binance (sample hot wallet #1)",
    "TwaZ1tfzZkfA8P5jpDr6jJ7yjWXSpUxHr8": "Binance (sample hot wallet #2)",
    "TxwsmFJr54bMV6Dc9xFfhZYV7SeEkfYWZr": "WazirX (sample hot wallet #1)",
    "TiDccBndCNzuoTdwZxwaSPzu3ujSQQmnyL": "WazirX (sample hot wallet #2)",
    "T6aXjDKzZCxkun4APZzjf8q7BsMAanTtWW": "CoinDCX (sample hot wallet #1)",
    "TkB4S2TcythanfvNCyWM768vdMphYLfFaC": "OKX (sample hot wallet #1)",
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
    """Return the exchange display name if address is a known exchange wallet, else None."""
    return KNOWN_EXCHANGE_WALLETS.get(address)


def match_scam_wallet(address: str):
    """Return the threat-intel note if address is a known flagged scam wallet, else None."""
    return KNOWN_SCAM_WALLETS.get(address)


def match_mixer(address: str):
    """Return the mixer note if address is a known mixer wallet, else None."""
    return KNOWN_MIXER_WALLETS.get(address)
