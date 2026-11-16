import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import create_app
from tests.contract.backup.conftest import NAME, sha256, version_of
from tests.contract.helpers.seed import Seed
from tests.contract.helpers.sqlite_view import integrity_check, scalar


def build_world(settings):
    """Run an app, create known data, back it up, then make a LATER change. Returns facts about it."""
    with TestClient(create_app(settings)) as c:
        seed = Seed(c)
        w = seed.standard_world()
        seed.adjustment(w["salary"]["id"], "2026-03-01", amount=320000, note="Raise")
        seed.checkpoint(w["giro"]["id"], "2026-02-20", 500000)
        at_backup = seed.state()
        st = c.post("/api/backup/run").json()
        assert st["last_result"] == "ok", st
        forecast = seed.forecast("2026-01", 6)
        seed.account("Erst nach dem Backup")
        assert seed.state()["data_version"] > at_backup["data_version"]
    return {"state": at_backup, "file": st["last_file"], "forecast": forecast}


def manual_restore(settings, backup_file):
    """README 'Wiederherstellen': app stopped -> move DB (+ -wal/-shm) aside -> copy backup to DB path."""
    db_file = Path(settings.db_path)
    alt = db_file.parent / "alt"
    alt.mkdir(exist_ok=True)
    for f in db_file.parent.glob(db_file.name + "*"):
        shutil.move(str(f), str(alt / f.name))
    shutil.copy(Path(settings.backup_dir) / backup_file, db_file)
    return alt


@pytest.fixture
def lost(settings, nas):
    nas.put_marker()
    return build_world(settings)


@pytest.mark.contract("RESTORE-001", "RESTORE-003", "E2E-BKP-010")
def test_backup_file_is_the_database_after_the_manual_steps(settings, lost):
    """RESTORE-001/003: after the documented steps the app serves exactly the backed-up data."""
    manual_restore(settings, lost["file"])
    with TestClient(create_app(settings)) as c:
        restored = Seed(c).state()
    for key in ("accounts", "entries", "adjustments", "checkpoints"):
        assert restored[key] == lost["state"][key], key
    assert all(a["name"] != "Erst nach dem Backup" for a in restored["accounts"])


@pytest.mark.contract("RESTORE-001")
def test_backup_opens_directly_in_a_fresh_location(make_settings, settings, lost):
    """RESTORE-001: copying the .sqlite to a fresh DB path is enough: no import/transform step."""
    other = make_settings()
    Path(other.db_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(Path(settings.backup_dir) / lost["file"], other.db_path)
    with TestClient(create_app(other)) as c:
        s = Seed(c).state()
    assert [a["name"] for a in s["accounts"]] == [a["name"] for a in lost["state"]["accounts"]]


@pytest.mark.contract("RESTORE-002")
def test_old_database_and_its_sidecar_files_are_set_aside_not_lost(settings, lost):
    """RESTORE-002: the old DB (all db-file siblings) moves to alt/ intact, and the live path holds only the backup."""
    db_file = Path(settings.db_path)
    before = {f.name: sha256(f) for f in db_file.parent.glob(db_file.name + "*")}
    alt = manual_restore(settings, lost["file"])
    assert {f.name for f in db_file.parent.glob(db_file.name + "*")} == {db_file.name}
    assert sha256(db_file) == sha256(Path(settings.backup_dir) / lost["file"])
    assert {f.name: sha256(f) for f in alt.iterdir()} == before
    assert scalar(alt / db_file.name, "SELECT COUNT(*) FROM accounts WHERE name='Erst nach dem Backup'") == 1


@pytest.mark.contract("RESTORE-004")
def test_init_on_a_restored_database_preserves_all_rows(settings, lost):
    """RESTORE-004: db.init() on the restored file applies only idempotent DDL; rows stay."""
    manual_restore(settings, lost["file"])
    counts = lambda: [scalar(settings.db_path, f"SELECT COUNT(*) FROM {t}")
                      for t in ("accounts", "entries", "adjustments", "checkpoints", "audit_log")]
    before = counts()
    db.init(settings.db_path)
    db.init(settings.db_path)
    assert counts() == before and scalar(settings.db_path, "PRAGMA user_version") == 1


@pytest.mark.contract("RESTORE-005")
def test_restored_data_version_equals_the_version_in_the_filename(settings, lost):
    """RESTORE-005: data_version of the restored DB equals the _v<N> of the backup file."""
    manual_restore(settings, lost["file"])
    with TestClient(create_app(settings)) as c:
        assert Seed(c).state()["data_version"] == version_of(lost["file"])
    with db.read(settings.db_path) as r:
        assert db.data_version(r) == version_of(lost["file"])


@pytest.mark.contract("RESTORE-006")
def test_restored_database_passes_integrity_check_and_stays_usable(settings, lost):
    """RESTORE-006: integrity_check is ok on the restored DB, also after the app has written to it."""
    manual_restore(settings, lost["file"])
    assert integrity_check(settings.db_path) == "ok"
    with TestClient(create_app(settings)) as c:
        s = Seed(c)
        v = s.state()["data_version"]
        s.account("Nach der Wiederherstellung")
        assert s.state()["data_version"] == v + 2
    assert integrity_check(settings.db_path) == "ok"


@pytest.mark.contract("RESTORE-003", "E2E-BKP-010")
def test_forecast_after_restore_equals_forecast_at_backup_time(settings, lost):
    """RESTORE-003: derived data matches too: the forecast on the restored DB equals the one at snapshot time."""
    manual_restore(settings, lost["file"])
    with TestClient(create_app(settings)) as c:
        assert Seed(c).forecast("2026-01", 6) == lost["forecast"]


@pytest.mark.contract("RESTORE-007")
def test_single_mistake_is_undone_in_the_app_without_a_file_restore(client, seed):
    """RESTORE-007: a single mistaken change is recoverable in-app via revert (no restore needed)."""
    a = seed.account("Richtig")
    client.put(f"/api/accounts/{a['id']}", json={"name": "Versehentlich", "kind": "checking"})
    upd = client.get(f"/api/audit?entity=accounts&entity_id={a['id']}").json()[0]
    assert client.post(f"/api/audit/{upd['id']}/revert").status_code == 200
    assert [x["name"] for x in seed.state()["accounts"]] == ["Richtig"]
