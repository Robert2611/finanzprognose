"""Output contract for the read endpoints (B-005 phase 2).

These models define the wire shape of `/api/state`, `/api/audit` and `/api/backup/status`
independently of the storage schema: extra columns added to a table (e.g. by a future
migration) are silently dropped here unless also added to the matching model, so unrelated
schema changes don't change the API. Internal-only columns (`created_at`) are dropped for
the same reason; `archived` is exposed as a real boolean instead of the stored 0/1.
"""
from typing import Optional, Union

from pydantic import BaseModel


class AccountOut(BaseModel):
    id: int
    name: str
    kind: str
    note: str
    archived: bool
    updated_at: str


class EntryOut(BaseModel):
    id: int
    account_id: int
    to_account_id: Optional[int] = None
    name: str
    category: str
    kind: str
    amount: int
    start_date: str
    end_date: Optional[str] = None
    interval_months: int
    estimated: bool
    note: str
    archived: bool
    updated_at: str


class AdjustmentOut(BaseModel):
    id: int
    entry_id: int
    effective_date: str
    mode: str
    amount: Optional[int] = None
    percent: Optional[float] = None
    repeat_yearly: bool
    note: str
    archived: bool
    updated_at: str


class CheckpointOut(BaseModel):
    id: int
    account_id: int
    date: str
    balance: int
    note: str
    archived: bool
    updated_at: str


class StateResponse(BaseModel):
    accounts: list[AccountOut]
    entries: list[EntryOut]
    adjustments: list[AdjustmentOut]
    checkpoints: list[CheckpointOut]
    data_version: int


class AuditEntryOut(BaseModel):
    id: int
    ts: str
    action: str
    entity: str
    entity_id: int
    before: Optional[dict] = None
    after: Optional[dict] = None
    comment: str
    reverts_id: Optional[int] = None


class BackupFileOut(BaseModel):
    name: str
    size: int
    mtime: str


class CodeOut(BaseModel):
    """A language-neutral message: the frontend turns code + params into German text."""
    code: str
    params: dict = {}


class BackupStatusOut(BaseModel):
    backup_dir: str
    backup_time: str
    current_version: int
    pending_changes: bool
    last_attempt: Optional[str] = None
    last_reason: Optional[str] = None
    last_success: Optional[str] = None
    last_version: Optional[int] = None
    last_file: Optional[str] = None
    last_result: Optional[str] = None
    # {code, params}; a plain string only in a status file written before B-020
    last_error: Optional[Union[CodeOut, str]] = None
    last_scheduled_run: Optional[str] = None
    files: list[BackupFileOut] = []


class BackupVerifyOut(BaseModel):
    """Result of the read-only check of one backup file (B-022)."""
    name: str
    ok: bool
    problems: list[CodeOut]
    size: int
    file_version: int
    data_version: Optional[int] = None
    schema_version: Optional[int] = None
    counts: dict[str, int]
    sha256: Optional[str] = None
    sha256_logged: Optional[str] = None
