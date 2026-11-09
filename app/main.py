import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import auth, backup, db, errors, forecast
from .contracts import AuditEntryOut, BackupStatusOut, StateResponse
from .schemas import AccountCreate, Base, MODELS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app):
    db.init()
    backup.start_scheduler()
    yield


app = FastAPI(title="Finanzprognose", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

app.middleware("http")(auth.basic_auth)
errors.register(app)


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
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/state", response_model=StateResponse)
def get_state():
    with db.read() as conn:
        return {t: db.all_rows(conn, t) for t in db.TABLES} | {"data_version": db.data_version(conn)}


@app.post("/api/accounts")
def create_account(body: dict = Body(...)):
    try:
        m = AccountCreate.model_validate(body)
    except ValidationError as ex:
        raise HTTPException(422, detail=errors.validation_detail(ex)) from None
    with db.tx() as conn:
        acc = db.create(conn, "accounts", {"name": m.name, "kind": m.kind, "note": m.note}, m.comment)
        db.create(conn, "checkpoints", {"account_id": acc["id"], "date": m.start_date.isoformat(),
                                        "balance": m.start_balance, "note": ""})
    return acc


@app.post("/api/{table}")
def create(table: str, body: dict = Body(...)):
    if table == "accounts":
        return create_account(body)
    m = _parse(table, body)
    d = _data(m)
    with db.tx() as conn:
        _check_refs(conn, table, d)
        return db.create(conn, table, d, m.comment)


@app.put("/api/{table}/{id_}")
def update(table: str, id_: int, body: dict = Body(...)):
    m = _parse(table, body)
    d = _data(m)
    with db.tx() as conn:
        _check_refs(conn, table, d)
        return db.update(conn, table, id_, d, m.expected_updated_at, m.comment)


@app.post("/api/{table}/{id_}/archive")
def archive(table: str, id_: int, body: dict = Body(default={})):
    if table not in db.TABLES:
        raise HTTPException(404)
    with db.tx() as conn:
        return db.set_archived(conn, table, id_, True, str(body.get("comment", ""))[:500])


@app.post("/api/{table}/{id_}/restore")
def restore(table: str, id_: int, body: dict = Body(default={})):
    if table not in db.TABLES:
        raise HTTPException(404)
    with db.tx() as conn:
        return db.set_archived(conn, table, id_, False, str(body.get("comment", ""))[:500])


@app.get("/api/audit", response_model=list[AuditEntryOut])
def audit(limit: int = Query(200, le=1000), before_id: Optional[int] = None,
          entity: Optional[str] = None, entity_id: Optional[int] = None):
    with db.read() as conn:
        return db.audit_list(conn, limit, before_id, entity, entity_id)


@app.post("/api/audit/{audit_id}/revert")
def revert(audit_id: int):
    with db.tx() as conn:
        return db.revert(conn, audit_id)


@app.get("/api/forecast")
def get_forecast(start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), months: int = Query(24, ge=1, le=240)):
    start = start or date.today().strftime("%Y-%m")
    with db.read() as conn:
        state = {t: db.all_rows(conn, t) for t in db.TABLES}
    return forecast.compute(state, start, months)


@app.get("/api/backup/status", response_model=BackupStatusOut)
def backup_status():
    return backup.status() | {"files": backup.list_backups(30)}


@app.post("/api/backup/run")
def backup_run():
    return backup.run_backup(force=False, reason="manuell")


@app.get("/api/export")
def export():
    with db.read() as conn:
        data = db.export_all(conn)
    fname = f"finanzen_export_{date.today().isoformat()}.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{fname}"'})


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="static")
