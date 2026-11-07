import base64
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, model_validator

from . import backup, db, forecast

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app):
    db.init()
    backup.start_scheduler()
    yield


app = FastAPI(title="Finanzprognose", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


# ---------------------------------------------------------------- Zugriffsschutz
@app.middleware("http")
async def basic_auth(request: Request, call_next):
    if APP_PASSWORD and request.url.path != "/healthz":
        ok = False
        h = request.headers.get("authorization", "")
        if h.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
                ok = (secrets.compare_digest(user.encode(), APP_USER.encode())
                      and secrets.compare_digest(pw.encode(), APP_PASSWORD.encode()))
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Finanzprognose"'})
    return await call_next(request)


@app.exception_handler(db.NotFound)
async def _nf(_, ex):
    return JSONResponse({"detail": str(ex)}, status_code=404)


@app.exception_handler(db.Conflict)
async def _cf(_, ex):
    return JSONResponse({"detail": str(ex)}, status_code=409)


# ---------------------------------------------------------------- Modelle
Money = int  # Cent


class Base(BaseModel):
    expected_updated_at: Optional[str] = None
    comment: str = Field("", max_length=500)


class AccountIn(Base):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["giro", "tagesgeld", "depot", "kreditkarte", "bar", "sonstiges"] = "giro"
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
            raise ValueError("Das Enddatum liegt vor dem Startdatum.")
        if self.kind == "once":
            self.end_date = None
            self.interval_months = 1
        if self.to_account_id is not None:
            if self.to_account_id == self.account_id:
                raise ValueError("Quell- und Zielkonto müssen verschieden sein.")
            if self.amount <= 0:
                raise ValueError("Der Umbuchungsbetrag muss positiv sein.")
        if self.amount == 0:
            raise ValueError("Der Betrag darf nicht 0 sein.")
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
                raise ValueError("Bitte den neuen Betrag angeben.")
            self.percent, self.repeat_yearly = None, False
        else:
            if self.percent is None:
                raise ValueError("Bitte die prozentuale Änderung angeben.")
            self.amount = None
        return self


class CheckpointIn(Base):
    account_id: int
    date: date
    balance: Money
    note: str = Field("", max_length=500)


MODELS = {"accounts": AccountIn, "entries": EntryIn, "adjustments": AdjustmentIn, "checkpoints": CheckpointIn}


def _parse(table: str, body: dict) -> Base:
    if table not in MODELS:
        raise HTTPException(404, "Unbekannter Datentyp")
    try:
        return MODELS[table].model_validate(body)
    except ValidationError as ex:
        msgs = [e["msg"].removeprefix("Value error, ") for e in ex.errors()]
        raise HTTPException(422, "; ".join(msgs)) from None


def _data(m: Base) -> dict:
    return m.model_dump(mode="json", exclude={"expected_updated_at", "comment"})


def _check_refs(conn, table: str, d: dict) -> None:
    refs = {"account_id": "accounts", "to_account_id": "accounts", "entry_id": "entries"}
    for field, ref in refs.items():
        if d.get(field) is not None and db.get(conn, ref, d[field]) is None:
            raise HTTPException(422, f"Verweis {field}={d[field]} existiert nicht.")


# ---------------------------------------------------------------- API
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/state")
def get_state():
    with db.read() as conn:
        return {t: db.all_rows(conn, t) for t in db.TABLES} | {"data_version": db.data_version(conn)}


@app.post("/api/accounts")
def create_account(body: dict = Body(...)):
    try:
        m = AccountCreate.model_validate(body)
    except ValidationError as ex:
        raise HTTPException(422, "; ".join(e["msg"] for e in ex.errors())) from None
    with db.tx() as conn:
        acc = db.create(conn, "accounts", {"name": m.name, "kind": m.kind, "note": m.note}, m.comment)
        db.create(conn, "checkpoints", {"account_id": acc["id"], "date": m.start_date.isoformat(),
                                        "balance": m.start_balance, "note": "Startstand bei Anlage"})
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


@app.get("/api/audit")
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


@app.get("/api/backup/status")
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
