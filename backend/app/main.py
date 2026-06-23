import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import db, rate_limiter, repository
from .models import (
    RankingEntry,
    SummaryResponse,
    TransactionRequest,
    TransactionResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ranking_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Ranking Service", version="1.0.0", lifespan=lifespan)

# Wide-open CORS so the static frontend (hosted on a different origin, e.g.
# GitHub Pages) can call this API. Fine for a demo/take-home; a production
# deployment should restrict this to the known frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": "; ".join(messages)})


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transaction", response_model=TransactionResponse, status_code=201)
def create_transaction(payload: TransactionRequest):
    if not rate_limiter.check_and_record(payload.user_id):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: max {rate_limiter.config.RATE_LIMIT_MAX_REQUESTS} "
            f"requests per {rate_limiter.config.RATE_LIMIT_WINDOW_SECONDS}s per user.",
        )

    try:
        row = repository.insert_transaction(
            payload.user_id, payload.amount, payload.idempotency_key
        )
        return TransactionResponse(
            user_id=row["user_id"],
            amount=row["amount"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
            duplicate=False,
        )
    except repository.DuplicateTransactionError as e:
        row = e.existing_row
        # Idempotent response: same 2xx shape, flagged as a duplicate rather
        # than reprocessed. The original transaction's data is returned so
        # the caller can confirm what was actually recorded.
        return JSONResponse(
            status_code=200,
            content=TransactionResponse(
                user_id=row["user_id"],
                amount=row["amount"],
                idempotency_key=row["idempotency_key"],
                created_at=row["created_at"],
                duplicate=True,
            ).model_dump(),
        )
    except Exception:
        logger.exception("Failed to process transaction")
        raise HTTPException(status_code=500, detail="Internal error processing transaction")


@app.get("/summary/{user_id}", response_model=SummaryResponse)
def get_summary(user_id: str = Path(..., min_length=1, max_length=64)):
    row = repository.get_summary(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No transactions found for user_id '{user_id}'")
    rank = repository.get_user_rank(user_id)
    return SummaryResponse(
        user_id=row["user_id"],
        total_points=row["total_points"],
        transaction_count=row["transaction_count"],
        active_days=row["active_days"],
        ranking_points=row["ranking_points"],
        rank=rank,
    )


@app.get("/ranking", response_model=list[RankingEntry])
def get_ranking(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    rows = repository.get_ranking(limit=limit, offset=offset)
    return [
        RankingEntry(
            rank=offset + i + 1,
            user_id=row["user_id"],
            total_points=row["total_points"],
            active_days=row["active_days"],
            ranking_points=row["ranking_points"],
        )
        for i, row in enumerate(rows)
    ]
