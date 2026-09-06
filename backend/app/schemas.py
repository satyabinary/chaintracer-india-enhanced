"""
Pydantic models for API request bodies. Response bodies are returned as
plain dicts (see app.database.row_to_case_dict) rather than typed response
models — the case record already carries a well-documented shape from the
trace/risk engines, and re-declaring it here would just be a second place
for that shape to drift out of sync.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class NewCaseRequest(BaseModel):
    victim_name: str = Field(..., min_length=2, max_length=120,
                              description="Victim's full name, for the case file")
    wallet_address: str = Field(..., min_length=30, max_length=42,
                                 description="Scammer's TRON wallet, as reported by the victim")
    amount_usdt: float = Field(..., gt=0, description="Amount the victim reports having sent, in USDT")
    notes: Optional[str] = Field("", max_length=2000, description="Free-text investigator notes")

    @field_validator("wallet_address")
    @classmethod
    def _strip_wallet(cls, v: str) -> str:
        return v.strip()

    @field_validator("victim_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("notes")
    @classmethod
    def _default_notes(cls, v):
        return v or ""
