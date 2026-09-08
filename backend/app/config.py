"""
Central configuration for ChainTracer India backend.
"""
import os

# --- Tronscan public API -----------------------------------------------
# No API key required for the basic read-only endpoints used here.
TRONSCAN_BASE_URL = "https://apilist.tronscanapi.com"

# Official USDT (TetherToken) TRC20 contract address on Tron mainnet.
# All fund tracing in this tool follows USDT-TRC20 transfers only.
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# Network timeouts / limits for outbound calls to Tronscan.
HTTP_TIMEOUT_SECONDS = 12
TRANSFERS_PAGE_LIMIT = 50

# --- Tracing parameters ---------------------------------------------------
DEFAULT_MAX_HOPS = 4
SWEEP_PERCENT_THRESHOLD = 0.95      # 95%+ of a wallet's received amount
SWEEP_WINDOW_HOURS = 24             # ...moved on within 24 hours
BOT_SPEED_MIN_SAMPLES = 3           # need at least this many outgoing txs to judge rhythm
BOT_SPEED_CV_THRESHOLD = 0.15       # coefficient of variation below this = "too regular"
MAX_DECOYS_STORED_PER_HOP = 5       # cap how many non-chosen txs we keep as evidence

# --- Risk scoring weights (fixed formula, not learned) --------------------
WEIGHT_TAINT = 0.30
WEIGHT_HOP_DEPTH = 0.15
WEIGHT_SWEEP_TIMING = 0.25
WEIGHT_BOT_SPEED = 0.15
WEIGHT_THREAT_INTEL = 0.15

PRIORITY_HIGH_THRESHOLD = 0.70
PRIORITY_MEDIUM_THRESHOLD = 0.40

# --- Storage ---------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(APP_DIR)
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "chaintracer.db")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# --- CORS ---------------------------------------------------------------
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
