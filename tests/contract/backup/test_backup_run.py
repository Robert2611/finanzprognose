import re
from datetime import datetime, timedelta

import pytest

from app import backup, db
from tests.contract.backup.conftest import NAME, sha256, table_rows, version_of
from tests.contract.helpers.sqlite_view import integrity_check, scalar
from tests.contract.helpers.timing import next_second


def post_run(client):
    r = client.post("/api/backup/run")
    assert r.status_code == 200
    return r.json()


def status(client):
    return client.get("/api/backup/status").json()


# ------------------------------------------------------------------ triggers & change detection

@pytest.mark.contract("BKP-002", "API-BKP-005")
def test_manual_run_via_api_creates_a_backup(client, healthy):
    """BKP-002/API-BKP-005: POST /api/backup/run with pending changes -> last_result 'ok' and a manual attempt recorded."""
    st = post_run(client)
    assert st["last_result"] == "ok" and healthy.backups()
    assert st["last_reason"]            # reason text is German (OQ #11): only presence is asserted
    assert st["last_attempt"] and st["last_success"]


@pytest.mark.contract("BKP-003", "API-BKP-006")
def test_second_run_without_changes_is_unchanged_and_writes_nothing(client, healthy):
    """BKP-003/API-BKP-006: nothing changed since the last backup -> 'unchanged' and no new file."""
    post_run(client)
    names = healthy.names()
    st = post_run(client)
    assert st["last_result"] == "unchanged" and healthy.names() == names


@pytest.mark.contract("BKP-003", "API-BKP-009")
def test_unchanged_run_keeps_last_success_data(client, healthy):
    """BKP-003/API-BKP-009: the manual run is not forced; an 'unchanged' run leaves last_version/last_file as they were."""
    first = post_run(client)
    again = post_run(client)
    assert again["last_version"] == first["last_version"] and again["last_file"] == first["last_file"]


@pytest.mark.contract("API-BKP-007", "BKP-015")
def test_change_after_backup_creates_second_backup_and_keeps_first(client, healthy, bump):
    """API-BKP-007/BKP-015: after a data change a new backup appears and the old one is untouched."""
    post_run(client)
    (first,) = healthy.backups()
    digest = sha256(healthy.path / first)
    bump()
    st = post_run(client)
    assert st["last_result"] == "ok" and len(healthy.backups()) == 2
    assert first in healthy.backups() and sha256(healthy.path / first) == digest


@pytest.mark.contract("BKP-004")
def test_missing_last_backup_file_is_rewritten_even_if_nothing_changed(client, healthy):
    """BKP-004: if the last backup file is gone, a run writes a new one although data_version is unchanged."""
    st = post_run(client)
    (healthy.path / st["last_file"]).unlink()
    assert healthy.backups() == []
    st2 = post_run(client)
    assert st2["last_result"] == "ok" and len(healthy.backups()) == 1


@pytest.mark.contract("BKP-005")
def test_force_writes_a_new_artifact_even_when_nothing_changed(client, healthy, settings):
    """BKP-005: force=True bypasses the change check and always writes a new artifact."""
    first = backup.run_backup(settings)
    assert first["last_result"] == "ok"
    next_second()      # filenames carry a 1-second stamp; make the forced run's name differ
    forced = backup.run_backup(settings, force=True)
    assert forced["last_result"] == "ok" and len(healthy.backups()) == 2


# ------------------------------------------------------------------ NAS marker guard & target

@pytest.mark.contract("BKP-006", "API-BKP-004")
def test_missing_marker_fails_and_writes_nothing(client, nas, seed):
    """BKP-006/API-BKP-004: marker required but missing -> 'error', last_error names .nas-marker, no artifact."""
    seed.account()
    st = post_run(client)
    assert st["last_result"] == "error" and ".nas-marker" in st["last_error"]
    assert nas.names() == []


@pytest.mark.contract("BKP-006")
def test_marker_error_leaves_last_success_untouched(client, healthy, bump):
    """BKP-006/BKP-018: a failed run does not change last_success/last_version of the previous success."""
    ok = post_run(client)
    bump()
    healthy.remove_marker()
    err = post_run(client)
    assert err["last_result"] == "error"
    assert err["last_success"] == ok["last_success"] and err["last_version"] == ok["last_version"]
    assert err["pending_changes"] is True


@pytest.mark.contract("BKP-006")
def test_adding_the_marker_makes_the_next_run_succeed(client, nas, seed):
    """BKP-006: once the NAS is 'mounted' (marker present) the same pending change is backed up."""
    seed.account()
    assert post_run(client)["last_result"] == "error"
    nas.put_marker()
    assert post_run(client)["last_result"] == "ok" and len(nas.backups()) == 1


@pytest.mark.contract("BKP-007")
@pytest.mark.app_settings(backup_require_marker=False)
def test_marker_not_required_when_guard_is_off(client, nas, seed):
    """BKP-007: with BACKUP_REQUIRE_MARKER off no marker file is needed."""
    seed.account()
    assert post_run(client)["last_result"] == "ok" and len(nas.backups()) == 1


@pytest.mark.contract("BKP-008")
@pytest.mark.parametrize("require_marker", [True, False])
def test_missing_backup_dir_fails_naming_the_target(client, nas, seed, settings, require_marker):
    """BKP-008: if BACKUP_DIR does not exist the run fails naming it and writes nothing."""
    seed.account()
    nas.remove()
    st = backup.run_backup(settings.__class__(**{**settings.__dict__, "backup_require_marker": require_marker}))
    assert st["last_result"] == "error" and st["last_error"]
    assert str(nas.path) in st["last_error"] or nas.path.name in st["last_error"]
    assert not nas.path.exists()


# ------------------------------------------------------------------ artifacts

@pytest.mark.contract("BKP-009", "BKP-013", "E2E-BKP-004")
def test_success_writes_exactly_a_sqlite_and_a_json_with_the_documented_name(client, healthy):
    """BKP-009/013: one run -> finanzen_YYYY-MM-DD_HHMMSS_v<N>.sqlite and the equally named .json (+ backups.log)."""
    st = post_run(client)
    sqlite_files, json_files = healthy.backups(".sqlite"), healthy.backups(".json")
    assert len(sqlite_files) == 1 and len(json_files) == 1
    assert NAME.match(sqlite_files[0]) and json_files[0] == sqlite_files[0][:-len(".sqlite")] + ".json"
    assert st["last_file"] == sqlite_files[0]
    assert set(healthy.names()) == {".nas-marker", "backups.log", sqlite_files[0], json_files[0]}


@pytest.mark.contract("BKP-013")
def test_filename_carries_local_time_and_data_version(client, healthy):
    """BKP-013: the stamp is local time and _v<N> equals the data version at backup time."""
    before = datetime.now().replace(microsecond=0)
    st = post_run(client)
    after = datetime.now()
    m = NAME.match(st["last_file"])
    stamp = datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M%S")
    assert before - timedelta(seconds=1) <= stamp <= after
    assert int(m.group(3)) == st["last_version"] == client.get("/api/state").json()["data_version"]


@pytest.mark.contract("BKP-010", "E2E-BKP-008")
def test_sqlite_artifact_is_a_valid_database(client, healthy):
    """BKP-010: the .sqlite artifact opens as SQLite and passes PRAGMA integrity_check."""
    post_run(client)
    path = healthy.path / healthy.backups()[0]
    assert integrity_check(path) == "ok"
    assert scalar(path, "SELECT COUNT(*) FROM accounts") == 1


@pytest.mark.contract("BKP-012", "E2E-BKP-008")
def test_sqlite_artifact_matches_source_at_snapshot_time(client, healthy, seed, db_path):
    """BKP-012: every table in the copy equals the source at snapshot time (incl. audit_log)."""
    w = seed.standard_world()
    seed.adjustment(w["salary"]["id"], "2026-03-01", amount=320000)
    seed.checkpoint(w["giro"]["id"], "2026-02-20", 500000)
    post_run(client)
    copy = healthy.path / healthy.backups()[0]
    for table in ("accounts", "entries", "adjustments", "checkpoints", "audit_log"):
        assert table_rows(copy, table) == table_rows(db_path, table), table


@pytest.mark.contract("BKP-012")
def test_later_changes_are_not_in_an_earlier_backup(client, healthy, seed, db_path):
    """BKP-012: a backup is a snapshot; data written afterwards is not in it."""
    post_run(client)
    copy = healthy.path / healthy.backups()[0]
    seed.account("Nach dem Backup")
    assert scalar(copy, "SELECT COUNT(*) FROM accounts") == 1
    assert scalar(db_path, "SELECT COUNT(*) FROM accounts") == 2


@pytest.mark.contract("BKP-009")
def test_json_artifact_is_the_readable_export(client, healthy, seed):
    """BKP-009: the .json artifact holds the same data as GET /api/export."""
    import json
    post_run(client)
    body = json.loads((healthy.path / healthy.backups(".json")[0]).read_text(encoding="utf-8"))
    live = client.get("/api/export").json()
    assert {"accounts", "entries", "adjustments", "checkpoints", "audit_log", "data_version"} <= set(body)
    assert body["accounts"] == live["accounts"] and body["audit_log"] == live["audit_log"]
    assert body["data_version"] == live["data_version"]


@pytest.mark.contract("BKP-014")
def test_backups_log_gets_one_line_per_successful_backup(client, healthy, bump, settings):
    """BKP-014: backups.log gains one line (stamp, v<N>, sqlite name, sha256=, reason) per successful backup only."""
    backup.run_backup(settings, reason="testgrund-eins")
    backup.run_backup(settings, reason="ignored-unchanged")      # unchanged: no line
    bump()
    backup.run_backup(settings, reason="testgrund-zwei")
    lines = (healthy.path / "backups.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line, reason in zip(lines, ("testgrund-eins", "testgrund-zwei")):
        name = re.search(r"finanzen_\S+?\.sqlite", line).group(0)
        m = NAME.match(name)
        assert m and f"{m.group(1)}_{m.group(2)}" in line and f"v{m.group(3)}" in line
        assert f"sha256={sha256(healthy.path / name)}" in line
        assert reason in line


@pytest.mark.contract("BKP-014")
def test_failed_run_adds_no_log_line(client, nas, seed):
    """BKP-014: only successful backups are logged."""
    seed.account()
    post_run(client)       # marker missing -> error
    assert not (nas.path / "backups.log").exists()


@pytest.mark.contract("BKP-016")
def test_no_temporary_files_remain_after_success(client, healthy, bump):
    """BKP-016: after successful runs the directory holds no leftover .tmp/dot-prefixed temp files."""
    post_run(client)
    bump()
    post_run(client)
    assert [n for n in healthy.names() if n.endswith(".tmp") or (n.startswith(".") and n != ".nas-marker")] == []


# ------------------------------------------------------------------ status & listing

@pytest.mark.contract("API-BKP-001")
def test_status_contains_the_documented_fields(client, healthy):
    """API-BKP-001: status has backup_dir, backup_time, current_version, pending_changes (bool) and files."""
    st = status(client)
    assert {"backup_dir", "backup_time", "current_version", "pending_changes", "files", "last_attempt", "last_reason",
            "last_success", "last_version", "last_file", "last_result", "last_error"} <= set(st)
    assert isinstance(st["pending_changes"], bool) and isinstance(st["files"], list)
    assert st["last_result"] is None and st["last_attempt"] is None


@pytest.mark.contract("API-BKP-001")
def test_run_response_has_the_same_fields_as_status(client, nas, seed):
    """API-BKP-001: POST /api/backup/run returns a BackupStatusOut with every field (nullable ones as null)."""
    seed.account()
    assert set(post_run(client)) == set(status(client))


@pytest.mark.contract("API-BKP-002", "BKP-020")
def test_pending_changes_follow_data_version(client, healthy, bump):
    """API-BKP-002/BKP-020: current_version == data_version; pending_changes is true iff it differs from last_version."""
    st = status(client)
    assert st["current_version"] == client.get("/api/state").json()["data_version"] and st["pending_changes"] is True
    post_run(client)
    st = status(client)
    assert st["pending_changes"] is False and st["current_version"] == st["last_version"]
    bump()
    st = status(client)
    assert st["pending_changes"] is True and st["current_version"] > st["last_version"]


@pytest.mark.contract("API-BKP-003")
def test_status_echoes_configuration(client, healthy, settings):
    """API-BKP-003: backup_dir and backup_time echo the configuration."""
    st = status(client)
    assert st["backup_dir"] == settings.backup_dir and st["backup_time"] == settings.backup_time


@pytest.mark.contract("API-BKP-003")
@pytest.mark.app_settings(backup_time="04:30")
def test_status_echoes_a_custom_backup_time(client, healthy):
    """API-BKP-003: a configured backup_time is reported."""
    assert status(client)["backup_time"] == "04:30"


@pytest.mark.contract("BKP-018")
def test_status_after_success(client, healthy):
    """BKP-018: after an ok run last_attempt/last_reason/last_result/last_success/last_version/last_file are set."""
    st = post_run(client)
    assert st["last_result"] == "ok" and st["last_error"] in (None, "")
    assert st["last_file"] == healthy.backups()[0] and st["last_version"] == version_of(st["last_file"])


@pytest.mark.contract("BKP-018")
def test_status_after_error_sets_last_error(client, nas, seed):
    """BKP-018: after an error last_error is set; there is no last_success yet."""
    seed.account()
    st = post_run(client)
    assert st["last_result"] == "error" and st["last_error"] and st["last_attempt"]
    assert st["last_success"] is None and st["last_version"] is None


@pytest.mark.contract("BKP-018")
def test_status_after_unchanged(client, healthy):
    """BKP-018: an unchanged run reports last_result 'unchanged'."""
    post_run(client)
    assert post_run(client)["last_result"] == "unchanged"


@pytest.mark.contract("BKP-018")
def test_status_survives_in_a_status_file_next_to_the_database(client, healthy, db_path):
    """BKP-018 / interface: backup_status.json sits next to the DB file (not in BACKUP_DIR)."""
    import os
    post_run(client)
    assert os.path.exists(os.path.join(os.path.dirname(db_path), "backup_status.json"))
    assert "backup_status.json" not in healthy.names()


@pytest.mark.contract("API-BKP-008", "BKP-023")
def test_no_retention_and_files_list_is_capped_at_30_newest_first(client, healthy, bump):
    """BKP-023/API-BKP-008: nothing is ever pruned; the status lists the newest 30, each {name,size,mtime}."""
    for _ in range(34):
        bump()
        assert post_run(client)["last_result"] == "ok"
    assert len(healthy.backups()) == 34
    files = status(client)["files"]
    assert len(files) == 30
    assert all(set(f) >= {"name", "size", "mtime"} and isinstance(f["size"], int) and f["size"] > 0 for f in files)
    # newest first by timestamp; the order of backups within the same second is not specified (F-23)
    stamps = [NAME.match(f["name"]).group(1) + NAME.match(f["name"]).group(2) for f in files]
    assert stamps == sorted(stamps, reverse=True)
    assert {f["name"] for f in files} <= set(healthy.backups())


@pytest.mark.contract("API-BKP-008")
def test_list_backups_ignores_non_backup_files(client, healthy, bump, settings):
    """API-BKP-008/interface: list_backups returns only finanzen_*.sqlite, newest first."""
    post_run(client)
    bump()
    post_run(client)
    (healthy.path / "notes.txt").write_text("x")
    (healthy.path / "finanzen_other.json").write_text("{}")
    got = backup.list_backups(settings)
    assert [g["name"] for g in got] == sorted(healthy.backups(), reverse=True)
    assert all(set(g) >= {"name", "size", "mtime"} for g in got)


@pytest.mark.contract("API-BKP-008")
def test_list_backups_limit(client, healthy, bump, settings):
    """API-BKP-008/interface: list_backups(limit=n) returns at most n entries."""
    for _ in range(3):
        bump()
        post_run(client)
    assert len(backup.list_backups(settings, limit=2)) == 2


@pytest.mark.contract("BKP-021")
def test_app_keeps_serving_during_and_after_a_backup(client, healthy, seed):
    """BKP-021: backups need no stop of the app; reads and writes work right after (and around) a run."""
    assert client.get("/api/state").status_code == 200
    post_run(client)
    seed.account("Neu nach Backup")
    assert client.get("/api/state").status_code == 200 and len(seed.state()["accounts"]) == 2
