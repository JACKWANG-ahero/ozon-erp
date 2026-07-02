"""Pydantic models for Ozon Finance API request/response."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── POST /v3/finance/transaction/list ────────────────────────────


class FinanceTransactionFilter(BaseModel):
    """Filter for /v3/finance/transaction/list."""

    date: dict[str, str] = Field(default_factory=dict)  # {"from": "...", "to": "..."}
    operation_type: list[str] | None = None
    posting_number: str | None = None
    transaction_type: str = "all"


class FinanceTransactionRequest(BaseModel):
    """Body for /v3/finance/transaction/list."""

    filter: FinanceTransactionFilter
    page: int = 1
    page_size: int = 100


class FinanceTransactionItem(BaseModel):
    """Single finance transaction from Ozon."""

    operation_id: str = ""
    operation_type: str = ""
    operation_date: datetime | None = None
    operation_type_name: str = ""
    posting: dict[str, Any] | None = None
    amount: float = 0.0
    accruals_for_sale: float = 0.0
    sale_commission: float = 0.0
    delivery_charge: float = 0.0
    return_commission: float = 0.0
    currency_code: str = "RUB"
    items: list[dict[str, Any]] = Field(default_factory=list)


class FinanceTransactionResult(BaseModel):
    """Result from /v3/finance/transaction/list."""

    result: dict[str, Any] = Field(default_factory=dict)
    operations: list[FinanceTransactionItem] = Field(default_factory=list)
    page_count: int = 0
    row_count: int = 0


# ── POST /v3/finance/transaction/totals ──────────────────────────


class FinanceTotalsRequest(BaseModel):
    """Body for /v3/finance/transaction/totals."""

    date: dict[str, str]  # {"from": "...", "to": "..."}


class FinanceTotalsItem(BaseModel):
    """Totals entry."""

    operation_type: str = ""
    amount: float = 0.0
    currency_code: str = "RUB"
    count: int = 0
