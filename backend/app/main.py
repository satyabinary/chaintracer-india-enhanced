"""
ChainTracer India — FastAPI application entrypoint.

Run from the `backend/` directory with:
    uvicorn app.main:app --reload --port 8000

Or simply:
    python run.py
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS
from app.database import init_db
from app.seed_data import seed_if_empty
from app.routers import cases

app = FastAPI(
    title="ChainTracer India",
    description="Crypto fraud investigation & fund-tracing API for cyber-cell officers.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_if_empty()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Last-resort handler so the officer always gets a readable JSON error
    # instead of a raw stack trace, even for bugs we didn't anticipate.
    return JSONResponse(
        status_code=500,
        content={"detail": f"Unexpected server error: {exc}"},
    )


app.include_router(cases.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "chaintracer-india-backend"}


@app.get("/")
def root():
    return {
        "service": "ChainTracer India API",
        "docs": "/docs",
        "health": "/api/health",
    }
