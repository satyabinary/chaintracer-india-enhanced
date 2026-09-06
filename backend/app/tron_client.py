"""
Thin client around the public Tronscan API (https://apilist.tronscanapi.com).

Only one endpoint is used: the TRC20 token-transfer list for an address,
filtered to the USDT contract. No API key is required for this endpoint
at the read volumes this tool needs.

This module deliberately has NO fastapi/pydantic dependency so it can be
imported and unit-tested with plain `python3` (see the __main__ block).

IMPORTANT: Tronscan's public JSON shape has shifted slightly across
versions in the past, so parsing below is defensive (it tries a few
known field-name variants). If Tronscan changes their schema again,
`_normalize_transfer` is the only place that needs updating.
"""
import re
import time
import requests

from app.config import (
    TRONSCAN_BASE_URL,
    USDT_TRC20_CONTRACT,
    HTTP_TIMEOUT_SECONDS,
    TRANSFERS_PAGE_LIMIT,
)

TRON_ADDRESS_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


class TronApiError(Exception):
    """Raised when the Tronscan API can't be reached or returns something unusable."""


def is_valid_tron_address(address: str) -> bool:
    """
    Cheap client-side sanity check: TRON (base58check) addresses start
    with 'T' and are 34 characters long, using the Base58 alphabet
    (no 0, O, I, l). This does NOT verify a checksum against the network —
    it's the same lightweight validation a data-entry form should do.
    """
    if not isinstance(address, str):
        return False
    return bool(TRON_ADDRESS_RE.match(address.strip()))


def _normalize_transfer(raw: dict) -> dict:
    """Convert a raw Tronscan token_transfers record into our internal shape."""
    tx_hash = raw.get("transaction_id") or raw.get("hash") or raw.get("transactionHash") or ""

    from_addr = raw.get("from_address") or raw.get("from") or ""
    to_addr = raw.get("to_address") or raw.get("to") or ""

    token_info = raw.get("tokenInfo") or {}
    decimals = raw.get("decimals")
    if decimals is None:
        decimals = token_info.get("tokenDecimal", 6)
    try:
        decimals = int(decimals)
    except (TypeError, ValueError):
        decimals = 6

    raw_amount = raw.get("quant")
    if raw_amount is None:
        raw_amount = raw.get("amount", 0)
    try:
        amount = float(raw_amount) / (10 ** decimals)
    except (TypeError, ValueError):
        amount = 0.0

    ts_ms = raw.get("block_ts") or raw.get("block_timestamp") or raw.get("timestamp") or 0
    try:
        ts_ms = int(ts_ms)
    except (TypeError, ValueError):
        ts_ms = 0

    confirmed = raw.get("confirmed", True)
    contract_ret = raw.get("contractRet") or raw.get("finalResult") or "SUCCESS"

    return {
        "hash": tx_hash,
        "from_address": from_addr,
        "to_address": to_addr,
        "amount": round(amount, 6),
        "timestamp_ms": ts_ms,
        "confirmed": bool(confirmed),
        "success": contract_ret == "SUCCESS",
    }


def get_trc20_transfers(address: str, direction: str = "all", limit: int = TRANSFERS_PAGE_LIMIT,
                         contract_address: str = USDT_TRC20_CONTRACT, retries: int = 2) -> list:
    """
    Fetch USDT-TRC20 transfers involving `address` from Tronscan, newest first.

    direction: "out" -> only transfers FROM address
               "in"  -> only transfers TO address
               "all" -> both (default)

    Returns a list of normalized transfer dicts. Raises TronApiError if the
    API can't be reached at all (network/HTTP failure) so callers can show
    an honest error rather than silently fabricating a trace.
    """
    params = {
        "limit": limit,
        "start": 0,
        "sort": "-timestamp",
        "count": "true",
        "relatedAddress": address,
        "contract_address": contract_address,
    }
    url = f"{TRONSCAN_BASE_URL}/api/token_trc20/transfers"

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=HTTP_TIMEOUT_SECONDS,
                                 headers={"Accept": "application/json"})
            if resp.status_code != 200:
                last_error = f"Tronscan returned HTTP {resp.status_code}"
                time.sleep(0.5)
                continue
            payload = resp.json()
            raw_transfers = (
                payload.get("token_transfers")
                or payload.get("data")
                or []
            )
            transfers = [_normalize_transfer(r) for r in raw_transfers]

            if direction == "out":
                transfers = [t for t in transfers if t["from_address"] == address]
            elif direction == "in":
                transfers = [t for t in transfers if t["to_address"] == address]

            # newest first is what Tronscan gives us with sort=-timestamp;
            # keep that guarantee even if the API's own sort is inconsistent
            transfers.sort(key=lambda t: t["timestamp_ms"], reverse=True)
            return transfers
        except requests.RequestException as exc:
            last_error = str(exc)
            time.sleep(0.5)
        except ValueError as exc:  # JSON decode error
            last_error = f"Could not parse Tronscan response: {exc}"
            time.sleep(0.5)

    raise TronApiError(
        f"Could not fetch transfer history for {address} from Tronscan "
        f"after {retries + 1} attempt(s): {last_error}"
    )


if __name__ == "__main__":
    # Quick manual smoke test (requires outbound internet access):
    #   python3 -m app.tron_client TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE
    import sys
    test_addr = sys.argv[1] if len(sys.argv) > 1 else "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"
    print(f"valid address? {is_valid_tron_address(test_addr)}")
    txs = get_trc20_transfers(test_addr, direction="out", limit=10)
    for t in txs:
        print(t)
