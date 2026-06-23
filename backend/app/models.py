import re

from pydantic import BaseModel, Field, field_validator

from . import config

USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-:.]{1,128}$")


class TransactionRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier of the user")
    amount: float = Field(..., description="Points/value earned in this transaction")
    idempotency_key: str = Field(
        ..., description="Client-generated key used to deduplicate retries of the same transaction"
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        v = v.strip()
        if not USER_ID_PATTERN.match(v):
            raise ValueError(
                "user_id must be 1-64 chars, alphanumeric, '-' or '_' only"
            )
        return v

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str) -> str:
        v = v.strip()
        if not IDEMPOTENCY_KEY_PATTERN.match(v):
            raise ValueError(
                "idempotency_key must be 1-128 chars, alphanumeric plus '-_:.' only"
            )
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):  # NaN / inf guard
            raise ValueError("amount must be a finite number")
        if v < config.MIN_TRANSACTION_AMOUNT:
            raise ValueError(f"amount must be >= {config.MIN_TRANSACTION_AMOUNT}")
        if v > config.MAX_TRANSACTION_AMOUNT:
            raise ValueError(f"amount must be <= {config.MAX_TRANSACTION_AMOUNT}")
        return round(v, 2)


class TransactionResponse(BaseModel):
    user_id: str
    amount: float
    idempotency_key: str
    created_at: str
    duplicate: bool = False


class SummaryResponse(BaseModel):
    user_id: str
    total_points: float
    transaction_count: int
    active_days: int
    ranking_points: float
    rank: int | None = None


class RankingEntry(BaseModel):
    rank: int
    user_id: str
    total_points: float
    active_days: int
    ranking_points: float


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
