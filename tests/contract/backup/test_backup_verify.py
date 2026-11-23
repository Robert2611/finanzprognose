"""B-022: the read-only check of one backup file (BKP-028..031, API-BKP-010)."""
import os
import shutil

import pytest

from tests.contract.backup.conftest import sha256, version_of


@pytest.fixture
def made(client, healthy, seed):
    """One real backup (account + 2 entries); returns its name."""
    acc = seed.state()["accounts"][0]
    seed.entry(acc["id"], "Miete", -120000)
    seed.entry(acc["id"], "Gehalt", 300000)
    return client.post("/api/backup/run").json()["last_file"]


def verify(client, name):
    return client.get("/api/backup/verify", params={"name": name})


def snapshot(nas):
    return {n: (sha256(nas.path / n), os.path.getmtime(nas.path / n)) for n in nas.names()}


@pytest.mark.contract("BKP-030", "API-BKP-010")
def test_a_good_backup_is_ok_with_its_numbers(client, made, settings):
    """BKP-030/API-BKP-010: a fresh backup is ok; versions, checksum and row counts are reported."""
    r = verify(client, made)
    assert r.status_code == 200
    v = r.json()
    assert v["ok"] is True and v["problems"] == []
    assert v["name"] == made and v["file_version"] == version_of(made) == v["data_version"]
    assert v["sha256"] == v["sha256_logged"] == sha256(os.path.join(settings.backup_dir, made))
    assert v["counts"] == {"accounts": 1, "entries": 2, "adjustments": 0, "checkpoints": 1, "audit_log": v["data_version"]}
    assert v["schema_version"] >= 2 and v["size"] == os.path.getsize(os.path.join(settings.backup_dir, made))


@pytest.mark.contract("BKP-029")
def test_verify_changes_nothing(client, made, healthy, settings, seed):
    """BKP-029: the NAS directory and file bytes are unchanged, the live DB is untouched, no staging leftovers."""
    before_nas, before_version = snapshot(healthy), seed.state()["data_version"]
    db_dir = os.path.dirname(settings.db_path)
    before_db_dir = sorted(os.listdir(db_dir))
    assert verify(client, made).json()["ok"] is True
    assert snapshot(healthy) == before_nas
    assert seed.state()["data_version"] == before_version
    assert sorted(os.listdir(db_dir)) == before_db_dir


@pytest.mark.contract("BKP-028")
@pytest.mark.parametrize("name", [
    "finanzen_2020-01-01_000000_v1.sqlite",        # well-formed, but no such file
    "../data/finanzen.sqlite",                      # a path
    "finanzen.sqlite", "backups.log", ".nas-marker", "",
])
def test_unknown_or_foreign_names_are_not_found(client, made, name):
    """BKP-028: only an existing finanzen_<stamp>_v<N>.sqlite directly in BACKUP_DIR can be checked."""
    r = verify(client, name)
    assert r.status_code == 404
    assert r.json() == {"code": "backup_not_found", "params": {"name": name}}


@pytest.mark.contract("BKP-028")
def test_a_path_to_a_real_backup_is_rejected(client, made, settings):
    """BKP-028: even a path that points at a real backup file is refused (the name must be a bare file name)."""
    sub = os.path.basename(settings.backup_dir)
    assert verify(client, f"../{sub}/{made}").status_code == 404


@pytest.mark.contract("BKP-031")
def test_a_modified_file_fails_the_checksum(client, made, healthy):
    """BKP-031: bytes changed after writing -> checksum_mismatch (the logged checksum no longer matches)."""
    path = healthy.path / made
    data = bytearray(path.read_bytes())
    data[-1] ^= 0xFF                                  # flip a byte in the last page
    path.write_bytes(bytes(data))
    v = verify(client, made).json()
    assert v["ok"] is False and {"code": "checksum_mismatch", "params": {}} in v["problems"]


@pytest.mark.contract("BKP-031")
def test_garbage_is_not_a_database(client, made, healthy):
    """BKP-031: a file with a backup name that isn't SQLite -> not_a_database."""
    name = "finanzen_2026-01-01_000000_v7.sqlite"
    (healthy.path / name).write_bytes(b"not a database at all" * 100)
    v = verify(client, name).json()
    assert v["ok"] is False and [p["code"] for p in v["problems"]] == ["not_a_database"]
    assert v["sha256_logged"] is None                 # not in backups.log: reported, not a problem by itself


@pytest.mark.contract("BKP-031")
def test_a_renamed_backup_has_a_version_mismatch(client, made, healthy):
    """BKP-031: the data version inside differs from the _v<N> in the name -> version_mismatch."""
    other = made.rsplit("_v", 1)[0] + "_v999.sqlite"
    shutil.copyfile(healthy.path / made, healthy.path / other)
    v = verify(client, other).json()
    assert v["ok"] is False
    assert v["problems"] == [{"code": "version_mismatch", "params": {"file_version": 999, "data_version": version_of(made)}}]


@pytest.mark.contract("BKP-031")
def test_a_database_without_the_app_tables(client, made, healthy):
    """BKP-031: a valid SQLite file without the app's tables -> tables_missing."""
    import sqlite3
    name = "finanzen_2026-01-01_000000_v3.sqlite"
    c = sqlite3.connect(healthy.path / name)
    c.execute("CREATE TABLE accounts(id INTEGER)")
    c.commit(); c.close()
    v = verify(client, name).json()
    assert [p["code"] for p in v["problems"]] == ["tables_missing"]
    assert v["problems"][0]["params"]["tables"] == "entries, adjustments, checkpoints, audit_log"
