"""The app's side of the automatic update (B-026).

The update itself runs on the Docker host (`deploy/auto-update.sh`, started by a systemd timer
and path unit). App and host only share a folder (`Settings.update_dir`, `/updater` in the
container) with three files:

  status.json      written by the host, only read here
  last-update.log  written by the host, only read here (its last lines are shown in the app)
  request.json     written here when the user asks for an update; the host consumes it

The app never runs Docker or the update script, and never changes the host's files.
"""
import json
import os
import re
from datetime import datetime
from typing import Optional

from pydantic import ValidationError

from .contracts import UpdaterHostOut
from .settings import Settings

STATUS_FILE = "status.json"
REQUEST_FILE = "request.json"
LOG_FILE = "last-update.log"
LOG_LINES = 40
LOG_LINE_MAX = 500
MAX_FILE_BYTES = 256 * 1024
VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")


class NotConfigured(Exception):
    """No update folder is configured (UPDATE_DIR is empty)."""


class UpdateInProgress(Exception):
    """The host is running an update right now."""


def _path(s: Settings, name: str) -> str:
    return os.path.join(s.update_dir, name)


def _read_host(s: Settings) -> tuple[Optional[UpdaterHostOut], Optional[dict]]:
    """Returns (host status, None) or (None, {code, params}) when the file is missing or unreadable."""
    try:
        with open(_path(s, STATUS_FILE), "rb") as f:
            raw = f.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        return None, {"code": "updater_status_missing", "params": {}}
    except OSError:
        return None, {"code": "updater_status_unreadable", "params": {}}
    try:
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError("too large")
        return UpdaterHostOut.model_validate(json.loads(raw)), None
    except (ValueError, ValidationError):
        return None, {"code": "updater_status_unreadable", "params": {}}


def _log_tail(s: Settings) -> list[str]:
    try:
        with open(_path(s, LOG_FILE), "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - MAX_FILE_BYTES))
            text = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return [line[:LOG_LINE_MAX] for line in text.splitlines()[-LOG_LINES:]]


def status(s: Settings) -> dict:
    """The data behind GET /api/update/status (`UpdateStatusOut`)."""
    out = {"enabled": bool(s.update_dir), "running_version": s.app_version, "host": None,
           "host_error": None, "update_available": False, "request_pending": False, "log_tail": []}
    if not s.update_dir:
        return out
    host, error = _read_host(s)
    out["host"], out["host_error"] = host, error
    out["request_pending"] = os.path.exists(_path(s, REQUEST_FILE))
    out["update_available"] = bool(host and host.latest and host.latest != s.app_version)
    out["log_tail"] = _log_tail(s)
    return out


def request_update(s: Settings, version: Optional[str] = None) -> None:
    """Asks the host for an update (to `version`, or the latest release) by writing request.json.

    Written to a temp file and renamed, so the host never sees a half-written request.
    Raises NotConfigured, UpdateInProgress, or OSError if the folder can't be written.
    """
    if not s.update_dir:
        raise NotConfigured()
    if version is not None and not VERSION_RE.match(version):
        raise ValueError("invalid version")
    host, _ = _read_host(s)
    if host is not None and host.state == "updating":
        raise UpdateInProgress()
    body = {"requested_at": datetime.now().astimezone().isoformat(timespec="seconds"), "version": version}
    tmp = _path(s, f".{REQUEST_FILE}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, _path(s, REQUEST_FILE))
