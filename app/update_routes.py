"""HTTP routes of the automatic update (B-026): the host updater's status and the update request.
The work is in `updater_link`; nothing here touches Docker or the host."""
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import ValidationError

from . import errors, updater_link
from .contracts import UpdateStatusOut
from .schemas import UpdateRequestIn
from .settings import Settings, get_settings

router = APIRouter()


@router.get("/api/update/status", response_model=UpdateStatusOut)
def update_status(s: Settings = Depends(get_settings)):
    return updater_link.status(s)


@router.post("/api/update/request", response_model=UpdateStatusOut, status_code=202)
def update_request(body: dict = Body(default={}), s: Settings = Depends(get_settings)):
    try:
        m = UpdateRequestIn.model_validate(body)
    except ValidationError as ex:
        raise HTTPException(422, detail=errors.validation_detail(ex)) from None
    try:
        updater_link.request_update(s, m.version)
    except updater_link.NotConfigured:
        raise HTTPException(409, detail={"code": "updater_not_configured", "params": {}}) from None
    except updater_link.UpdateInProgress:
        raise HTTPException(409, detail={"code": "update_in_progress", "params": {}}) from None
    except OSError:
        raise HTTPException(503, detail={"code": "updater_unavailable", "params": {}}) from None
    return updater_link.status(s)
