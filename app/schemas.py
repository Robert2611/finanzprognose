from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Money = int  # cents


class Base(BaseModel):
    expected_updated_at: Optional[str] = None
    comment: str = Field("", max_length=500)


class AccountIn(Base):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["checking", "savings", "custody", "credit_card", "cash", "other"] = "checking"
    note: str = Field("", max_length=2000)


class AccountCreate(AccountIn):
    start_balance: Money
    start_date: date


class EntryIn(Base):
    account_id: int
    to_account_id: Optional[int] = None
    name: str = Field(min_length=1, max_length=100)
    category: str = Field("", max_length=100)
    kind: Literal["recurring", "once"]
    amount: Money
    start_date: date
    end_date: Optional[date] = None
    interval_months: int = Field(1, ge=1, le=120)
    note: str = Field("", max_length=2000)

    @model_validator(mode="after")
    def _check(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_before_start")
        if self.kind == "once":
            self.end_date = None
            self.interval_months = 1
        if self.to_account_id is not None:
            if self.to_account_id == self.account_id:
                raise ValueError("transfer_same_account")
            if self.amount <= 0:
                raise ValueError("transfer_amount_not_positive")
        if self.amount == 0:
            raise ValueError("amount_zero")
        return self


class AdjustmentIn(Base):
    entry_id: int
    effective_date: date
    mode: Literal["set", "percent"]
    amount: Optional[Money] = None
    percent: Optional[float] = Field(None, gt=-100, lt=1000)
    repeat_yearly: bool = False
    note: str = Field("", max_length=500)

    @model_validator(mode="after")
    def _check(self):
        if self.mode == "set":
            if self.amount is None:
                raise ValueError("amount_required")
            self.percent, self.repeat_yearly = None, False
        else:
            if self.percent is None:
                raise ValueError("percent_required")
            self.amount = None
        return self


class CheckpointIn(Base):
    account_id: int
    date: date
    balance: Money
    note: str = Field("", max_length=500)


MODELS = {"accounts": AccountIn, "entries": EntryIn, "adjustments": AdjustmentIn, "checkpoints": CheckpointIn}
