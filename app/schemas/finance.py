"""Pydantic schemas for Finance API."""

from datetime import date

from pydantic import BaseModel


class TransactionFilter(BaseModel):
    operation_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    posting_number: str | None = None
    offset: int = 0
    limit: int = 100
