"""HTTP Basic Auth middleware. Credentials come from the serving app's `Settings`;
an empty `app_password` disables auth. `/healthz` is always open."""
import base64
import secrets

from fastapi import Request
from fastapi.responses import Response


async def basic_auth(request: Request, call_next):
    s = request.app.state.settings
    if s.app_password and request.url.path != "/healthz":
        ok = False
        h = request.headers.get("authorization", "")
        if h.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
                ok = (secrets.compare_digest(user.encode(), s.app_user.encode())
                      and secrets.compare_digest(pw.encode(), s.app_password.encode()))
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Finanzprognose"'})
    return await call_next(request)
