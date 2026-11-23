import os

import pytest

from app import backup

root_only = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions (environment)")


def run(client):
    r = client.post("/api/backup/run")
    assert r.status_code == 200
    return r.json()


def app_still_serves(client, seed):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/api/state").status_code == 200
    n = len(seed.state()["accounts"])
    seed.account(f"nach Fehler {n}")
    assert len(seed.state()["accounts"]) == n + 1


@pytest.mark.contract("BKP-017", "BKP-006")
@root_only
def test_permission_denied_records_an_error_and_writes_no_artifact(client, healthy, seed):
    """BKP-017/018: NAS directory not writable -> error recorded, no final .sqlite/.json, no leftovers, app keeps serving."""
    healthy.make_read_only()
    try:
        st = run(client)
        assert st["last_result"] == "error" and st["last_error"]
        assert healthy.names() == [".nas-marker"]
    finally:
        healthy.restore_permissions()
    app_still_serves(client, seed)


@pytest.mark.contract("BKP-017", "BKP-018")
@root_only
def test_permission_denied_keeps_previous_success_and_recovers(client, healthy, bump):
    """BKP-018: the error leaves last_success intact; once the directory is writable again the backup succeeds."""
    ok = run(client)
    bump()
    healthy.make_read_only()
    try:
        err = run(client)
        assert err["last_result"] == "error"
        assert err["last_success"] == ok["last_success"] and err["last_version"] == ok["last_version"]
        assert err["pending_changes"] is True
    finally:
        healthy.restore_permissions()
    again = run(client)
    assert again["last_result"] == "ok" and len(healthy.backups()) == 2


@pytest.mark.contract("BKP-008", "BKP-018")
def test_nas_becoming_unreachable_after_a_success(client, healthy, bump, seed):
    """BKP-008/018: the target vanishes after a good backup -> error, old backup lost with the NAS (not our problem), app serves."""
    run(client)
    bump()
    healthy.remove()
    st = run(client)
    assert st["last_result"] == "error" and st["last_error"]
    assert not healthy.path.exists()
    app_still_serves(client, seed)


@pytest.mark.contract("BKP-008", "BKP-006")
def test_nas_coming_back_is_picked_up_by_the_next_run(client, healthy, bump):
    """BKP-006/008: after the NAS is back (dir + marker), the pending change is backed up."""
    run(client)
    bump()
    healthy.remove()
    assert run(client)["last_result"] == "error"
    healthy.put_marker()
    st = run(client)
    assert st["last_result"] == "ok" and len(healthy.backups()) == 1


@pytest.mark.contract("BKP-006")
def test_unmounted_nas_with_stale_directory_but_no_marker_is_refused(client, nas, seed):
    """BKP-006: an empty mount-point directory without the marker is refused, nothing is written into it."""
    seed.account()
    assert run(client)["last_result"] == "error"
    assert nas.names() == []
    app_still_serves(client, seed)


@pytest.mark.contract("API-BKP-004")
def test_failed_backup_does_not_block_later_data_changes_or_other_endpoints(client, nas, seed):
    """API-BKP-004: while backups fail the rest of the API (state, forecast, audit, export) keeps working."""
    seed.account()
    run(client)
    for url in ("/api/state", "/api/forecast?start=2026-01&months=2", "/api/audit", "/api/export", "/api/backup/status"):
        assert client.get(url).status_code == 200, url


@pytest.mark.contract("BKP-018")
def test_error_status_is_visible_via_get_status(client, nas, seed):
    """BKP-018: GET /api/backup/status reports the last error after a failed run."""
    seed.account()
    run(client)
    st = client.get("/api/backup/status").json()
    assert st["last_result"] == "error" and st["last_error"]["code"] == "marker_missing" and st["pending_changes"] is True


@pytest.mark.contract("BKP-017")
@pytest.mark.skip(reason="Testability gap TG-4: no seam to inject a failure part-way through writing the temp files (ENOSPC/EIO)")
def test_failure_in_the_middle_of_a_write_leaves_no_final_artifact():
    """BKP-017: skipped, see ENVIRONMENT TG-4."""


@pytest.mark.contract("BKP-016")
@pytest.mark.skip(reason="Testability gap TG-4: fsync/atomic-rename internals and an interrupted run cannot be observed without an fs seam")
def test_interrupted_run_never_leaves_a_half_written_final_artifact():
    """BKP-016: skipped, see ENVIRONMENT TG-4."""


@pytest.mark.contract("BKP-017")
@pytest.mark.skip(reason="Testability gap TG-4: disk full needs a size-limited filesystem (no root/mount rights, no ENOSPC seam)")
def test_disk_full_is_reported_as_error():
    """BKP-017: skipped (disk full), see ENVIRONMENT TG-4."""


@pytest.mark.contract("BKP-021")
@pytest.mark.skip(reason="Testability gap TG-4: slow NAS needs a throttled filesystem or an injectable write function")
def test_slow_nas_does_not_block_the_app():
    """BKP-021: skipped (slow NAS), see ENVIRONMENT TG-4."""


@pytest.mark.contract("BKP-010")
@pytest.mark.skip(reason="Testability gap TG-7: no seam to make PRAGMA integrity_check fail during a run")
def test_failing_integrity_check_aborts_the_run_without_final_artifact():
    """BKP-010: skipped (abort half of the clause), see CONTRACT_FEEDBACK F-7."""


def staging_leftovers(db_path):
    return [n for n in os.listdir(os.path.dirname(db_path)) if n.endswith(".tmp")]


@pytest.mark.contract("BKP-024")
def test_sqlite_never_touches_the_backup_dir(client, healthy, monkeypatch):
    """BKP-024: sqlite3 opens only files outside BACKUP_DIR; the NAS only receives finished copies."""
    import sqlite3
    opened = []
    real = sqlite3.connect
    monkeypatch.setattr(backup.sqlite3, "connect", lambda p, *a, **k: (opened.append(str(p)), real(p, *a, **k))[1])
    assert run(client)["last_result"] == "ok"
    assert opened and not [p for p in opened if str(healthy.path) in p]


@pytest.mark.contract("BKP-025")
def test_staging_files_removed_after_success_and_failure(client, healthy, db_path, bump):
    """BKP-025: no .tmp staging files stay in the DB directory after an ok run or a failed run."""
    assert run(client)["last_result"] == "ok"
    assert staging_leftovers(db_path) == []
    bump()
    healthy.remove_marker()
    assert run(client)["last_result"] == "error"
    assert staging_leftovers(db_path) == []


@pytest.mark.contract("BKP-025", "BKP-017")
def test_failed_copy_to_nas_cleans_staging_and_nas(client, healthy, db_path, monkeypatch):
    """BKP-017/025: a failure while copying to the NAS leaves no temp files on either side and no final artifact."""
    def boom(*a, **k):
        raise OSError("copy failed")
    monkeypatch.setattr(backup.shutil, "copyfile", boom)
    st = run(client)
    assert st["last_result"] == "error" and st["last_error"] == {"code": "backup_failed", "params": {"detail": "copy failed"}}
    assert staging_leftovers(db_path) == []
    assert healthy.names() == [".nas-marker"]
