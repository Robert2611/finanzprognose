"""app/updater_link.py: the app's side of the shared update folder (contracts/backend/updater.md)."""
import json
import os

import pytest

from app import updater_link
from app.settings import Settings

HOST = {"schema": 1, "mode": "auto", "state": "idle", "current": "v1.0.0", "latest": "v1.1.0",
        "checked_at": "2026-11-24T10:00:00+01:00", "check_error": None, "target": None, "failed_version": None,
        "last_update": {"from": "v0.9.0", "to": "v1.0.0", "result": "success", "at": "2026-11-20T10:00:00+01:00"}}


@pytest.fixture
def upd(tmp_path):
    d = tmp_path / "updater"
    d.mkdir()
    return d


def make(upd, **kw):
    return Settings(db_path=str(upd.parent / "db.sqlite"), update_dir=str(upd), app_version=kw.pop("version", "v1.0.0"), **kw)


def write_host(upd, **changes):
    (upd / "status.json").write_text(json.dumps(HOST | changes))


def snapshot(d):
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in d.iterdir()}


@pytest.mark.contract("UPDATER-001")
def test_not_configured(upd):
    s = Settings(update_dir="", app_version="v1.0.0")
    st = updater_link.status(s)
    assert st["enabled"] is False and st["running_version"] == "v1.0.0" and st["host"] is None
    assert st["update_available"] is False and st["request_pending"] is False
    with pytest.raises(updater_link.NotConfigured):
        updater_link.request_update(s)


@pytest.mark.contract("UPDATER-002")
def test_host_status_is_read(upd):
    write_host(upd, extra_key="ignored")
    st = updater_link.status(make(upd))
    assert st["enabled"] is True and st["host_error"] is None
    assert st["host"].mode == "auto" and st["host"].latest == "v1.1.0"
    assert st["host"].last_update.from_ == "v0.9.0"


@pytest.mark.contract("UPDATER-002")
def test_missing_status_file(upd):
    st = updater_link.status(make(upd))
    assert st["host"] is None and st["host_error"] == {"code": "updater_status_missing", "params": {}}


@pytest.mark.contract("UPDATER-002")
@pytest.mark.parametrize("content", ["{not json", json.dumps(HOST | {"mode": "sometimes"}),
                                     json.dumps(HOST | {"state": "?"}),
                                     json.dumps(HOST | {"last_update": HOST["last_update"] | {"result": "meh"}}),
                                     json.dumps(HOST | {"pad": "x" * (300 * 1024)}), "[]"])
def test_unreadable_status_file(upd, content):
    (upd / "status.json").write_text(content)
    st = updater_link.status(make(upd))
    assert st["host"] is None and st["host_error"]["code"] == "updater_status_unreadable"


@pytest.mark.contract("UPDATER-003")
@pytest.mark.parametrize("latest, running, available", [("v1.1.0", "v1.0.0", True), ("v1.0.0", "v1.0.0", False),
                                                         (None, "v1.0.0", False), ("v1.0.0", "dev", True)])
def test_update_available(upd, latest, running, available):
    write_host(upd, latest=latest)
    assert updater_link.status(make(upd, version=running))["update_available"] is available


@pytest.mark.contract("UPDATER-004", "UPDATER-006")
def test_request_writes_the_file_atomically(upd):
    write_host(upd)
    s = make(upd)
    updater_link.request_update(s, "v1.1.0")
    body = json.loads((upd / "request.json").read_text())
    assert body["version"] == "v1.1.0" and body["requested_at"][:4].isdigit()
    assert sorted(os.listdir(upd)) == ["request.json", "status.json"]  # no temp file left
    assert updater_link.status(s)["request_pending"] is True
    updater_link.request_update(s)  # replaces the pending request
    assert json.loads((upd / "request.json").read_text())["version"] is None


@pytest.mark.contract("UPDATER-005")
def test_log_tail(upd):
    lines = [f"line {i}" for i in range(100)] + ["x" * 2000]
    (upd / "last-update.log").write_text("\n".join(lines) + "\n")
    tail = updater_link.status(make(upd))["log_tail"]
    assert len(tail) == 40 and tail[0] == "line 61" and tail[-1] == "x" * 500
    (upd / "last-update.log").unlink()
    assert updater_link.status(make(upd))["log_tail"] == []


@pytest.mark.contract("UPDATER-007")
def test_no_request_while_updating(upd):
    write_host(upd, state="updating", target="v1.1.0")
    with pytest.raises(updater_link.UpdateInProgress):
        updater_link.request_update(make(upd))
    assert not (upd / "request.json").exists()


@pytest.mark.contract("UPDATER-008")
def test_host_files_are_never_changed(upd):
    write_host(upd)
    (upd / "last-update.log").write_text("log\n")
    (upd / "state").write_text("LATEST=v1.1.0\n")
    before = snapshot(upd)
    s = make(upd)
    updater_link.status(s)
    updater_link.request_update(s, "v1.1.0")
    after = snapshot(upd)
    assert after.pop("request.json")
    assert after == before
