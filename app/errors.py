from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import db


def validation_detail(ex: ValidationError | RequestValidationError) -> dict:
    """Turns a Pydantic ValidationError into a {code, params} envelope: built-in constraint
    violations keep Pydantic's own machine-readable `type`/`ctx`; our custom model_validators
    raise ValueError(<short code>), which becomes the `code` with no params."""
    errors = []
    for e in ex.errors():
        loc = list(e["loc"])
        if isinstance(ex, RequestValidationError) and loc and loc[0] in ("query", "path", "body"):
            loc = loc[1:]  # request parameters: the field is the parameter name, e.g. "start"
        field = ".".join(str(p) for p in loc)
        if e["type"] == "value_error":
            code, params = e["msg"].removeprefix("Value error, "), {}
        else:
            code = e["type"]
            params = {k: v for k, v in e.get("ctx", {}).items() if isinstance(v, (str, int, float, bool))}
        errors.append({"field": field, "code": code, "params": params})
    return {"code": "validation_error", "params": {"errors": errors}}


def register(app: FastAPI) -> None:
    @app.exception_handler(db.NotFound)
    async def _nf(_, ex):
        return JSONResponse({"code": ex.code, "params": ex.params}, status_code=404)

    @app.exception_handler(db.Conflict)
    async def _cf(_, ex):
        return JSONResponse({"code": ex.code, "params": ex.params}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def _req_invalid(_, ex):
        """Invalid query/path parameters (e.g. ?start=2026-13) get the same envelope as invalid bodies."""
        return JSONResponse(validation_detail(ex), status_code=422)

    @app.exception_handler(HTTPException)
    async def _http_err(_, ex):
        """Pass through the {code, params} envelope raised via HTTPException(detail=...); fall back to
        FastAPI's plain-string {detail} shape for exceptions outside our own routes (e.g. the framework's
        own 404/405)."""
        if isinstance(ex.detail, dict) and "code" in ex.detail:
            return JSONResponse(ex.detail, status_code=ex.status_code, headers=ex.headers)
        return JSONResponse({"detail": ex.detail}, status_code=ex.status_code, headers=ex.headers)
