"""HTTP routes. Each request reads its configuration from the serving app's `Settings`
(via the `get_settings` dependency), never from module globals."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import backup, backup_verify, db, errors, forecast
from .contracts import AuditEntryOut, BackupStatusOut, BackupVerifyOut, StateResponse
from .schemas import AccountCreate, Base, MODELS
from .settings import Settings, get_settings

router = APIRouter()


# ---------------------------------------------------------------- Helpers
def _parse(table: str, body: dict) -> Base:
    if table not in MODELS:
        raise HTTPException(404, detail={"code": "unknown_table", "params": {"table": table}})
    try:
        return MODELS[table].model_validate(body)
    except ValidationError as ex:
        raise HTTPException(422, detail=errors.validation_detail(ex)) from None


def _data(m: Base) -> dict:
    return m.model_dump(mode="json", exclude={"expected_updated_at", "comment"})


def _check_refs(conn, table: str, d: dict) -> None:
    refs = {"account_id": "accounts", "to_account_id": "accounts", "entry_id": "entries"}
    for field, ref in refs.items():
        if d.get(field) is not None and db.get(conn, ref, d[field]) is None:
            raise HTTPException(422, detail={"code": "ref_not_found", "params": {"field": field, "id": d[field]}})


# ---------------------------------------------------------------- API
@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/api/state", response_model=StateResponse)
def get_state(s: Settings = Depends(get_settings)):
    with db.read(s.db_path) as conn:
        return {t: db.all_rows(conn, t) for t in db.TABLES} | {"data_version": db.data_version(conn)}


@router.post("/api/accounts")
def create_account(body: dict = Body(...), s: Settings = Depends(get_settings)):
    try:
        m = AccountCreate.model_validate(body)
    except ValidationError as ex:
        raise HTTPException(422, detail=errors.validation_detail(ex)) from None
    with db.tx(s.db_path) as conn:
        acc = db.create(conn, "accounts", {"name": m.name, "kind": m.kind, "reserve": m.reserve, "note": m.note}, m.comment)
        db.create(conn, "checkpoints", {"account_id": acc["id"], "date": m.start_date.isoformat(),
                                        "balance": m.start_balance, "note": ""})
    return acc


@router.post("/api/{table}")
def create(table: str, body: dict = Body(...), s: Settings = Depends(get_settings)):
    if table == "accounts":
        return create_account(body, s)
    m = _parse(table, body)
    d = _data(m)
    with db.tx(s.db_path) as conn:
        _check_refs(conn, table, d)
        return db.create(conn, table, d, m.comment)


@router.put("/api/{table}/{id_}")
def update(table: str, id_: int, body: dict = Body(...), s: Settings = Depends(get_settings)):
    m = _parse(table, body)
    d = _data(m)
    with db.tx(s.db_path) as conn:
        _check_refs(conn, table, d)
        return db.update(conn, table, id_, d, m.expected_updated_at, m.comment)


def _set_archived(table: str, id_: int, body: dict, archived: bool, s: Settings) -> dict:
    if table not in db.TABLES:
        raise HTTPException(404, detail={"code": "unknown_table", "params": {"table": table}})
    expected = body.get("expected_updated_at") or None
    with db.tx(s.db_path) as conn:
        return db.set_archived(conn, table, id_, archived, str(body.get("comment", ""))[:500],
                               str(expected) if expected is not None else None)


@router.post("/api/{table}/{id_}/archive")
def archive(table: str, id_: int, body: dict = Body(default={}), s: Settings = Depends(get_settings)):
    return _set_archived(table, id_, body, True, s)


@router.post("/api/{table}/{id_}/restore")
def restore(table: str, id_: int, body: dict = Body(default={}), s: Settings = Depends(get_settings)):
    return _set_archived(table, id_, body, False, s)


@router.get("/api/audit", response_model=list[AuditEntryOut])
def audit(limit: int = Query(200, le=1000), before_id: Optional[int] = None,
          entity: Optional[str] = None, entity_id: Optional[int] = None,
          s: Settings = Depends(get_settings)):
    with db.read(s.db_path) as conn:
        return db.audit_list(conn, limit, before_id, entity, entity_id)


@router.post("/api/audit/{audit_id}/revert")
def revert(audit_id: int, s: Settings = Depends(get_settings)):
    with db.tx(s.db_path) as conn:
        return db.revert(conn, audit_id)


@router.get("/api/forecast")
def get_forecast(start: Optional[str] = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), months: int = Query(24, ge=1, le=240),
                 s: Settings = Depends(get_settings)):
    start = start or date.today().strftime("%Y-%m")
    with db.read(s.db_path) as conn:
        state = {t: db.all_rows(conn, t) for t in db.TABLES}
    return forecast.compute(state, start, months)


@router.get("/api/backup/status", response_model=BackupStatusOut)
def backup_status(s: Settings = Depends(get_settings)):
    return backup.status(s) | {"files": backup.list_backups(s, 30)}


@router.post("/api/backup/run", response_model=BackupStatusOut)
def backup_run(s: Settings = Depends(get_settings)):
    return backup.run_backup(s, force=False, reason=backup.REASON_MANUAL) | {"files": backup.list_backups(s, 30)}


@router.get("/api/backup/verify", response_model=BackupVerifyOut)
def backup_verify_file(name: str = Query(..., max_length=200), s: Settings = Depends(get_settings)):
    """Read-only check of one backup file (B-022); never writes to BACKUP_DIR or the live DB."""
    try:
        return backup_verify.verify_backup(s, name)
    except backup_verify.BackupNotFound:
        raise HTTPException(404, detail={"code": "backup_not_found", "params": {"name": name}})


@router.get("/api/export")
def export(s: Settings = Depends(get_settings)):
    with db.read(s.db_path) as conn:
        data = db.export_all(conn)
    fname = f"finanzen_export_{date.today().isoformat()}.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{fname}"'})
