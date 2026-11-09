import base64
import os
import secrets

from fastapi import Request
from fastapi.responses import Response

APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


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
