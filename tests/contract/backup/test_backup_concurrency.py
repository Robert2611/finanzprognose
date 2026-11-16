import threading

import pytest

from app import backup, db
from tests.contract.backend.conftest import make_entry
from tests.contract.backup.conftest import table_rows
from tests.contract.helpers.sqlite_view import integrity_check, scalar


class Writers:
    """Background writers that add (account + checkpoint + entry) triples, each in ONE transaction."""

    def __init__(self, path, n_threads=3):
        self.path, self.stop, self.errors = path, threading.Event(), []
        self.cond, self.count = threading.Condition(), 0
        self.threads = [threading.Thread(target=self._loop, daemon=True) for _ in range(n_threads)]

    def _loop(self):
        try:
            while not self.stop.is_set():
                with db.tx(self.path) as c:
                    a = db.create(c, "accounts", {"name": "w", "kind": "checking", "note": ""})
                    db.create(c, "checkpoints", {"account_id": a["id"], "date": "2026-01-01", "balance": 1, "note": ""})
                    make_entry(c, a["id"], "e", -5)
                with self.cond:
                    self.count += 1
                    self.cond.notify_all()
        except Exception as ex:          # noqa: BLE001 - surfaced by the test
            self.errors.append(ex)

    def __enter__(self):
        for t in self.threads:
            t.start()
        return self

    def wait_for(self, n):
        with self.cond:
            assert self.cond.wait_for(lambda: self.count >= n or self.errors, timeout=30)

    def __exit__(self, *exc):
        self.stop.set()
        for t in self.threads:
            t.join(15)


def assert_consistent_snapshot(copy):
    """A consistent snapshot has data rows and audit rows from the same committed state."""
    assert integrity_check(copy) == "ok"
    n_acc = scalar(copy, "SELECT COUNT(*) FROM accounts")
    assert scalar(copy, "SELECT COUNT(*) FROM checkpoints") == n_acc
    assert scalar(copy, "SELECT COUNT(*) FROM entries") == n_acc
    assert scalar(copy, "SELECT COUNT(*) FROM audit_log") == 3 * n_acc
    assert scalar(copy, "SELECT COALESCE(MAX(id),0) FROM audit_log") == 3 * n_acc
    return n_acc


@pytest.mark.contract("BKP-011", "BKP-021")
def test_backup_taken_while_writes_happen_is_a_consistent_snapshot(client, nas, settings):
    """BKP-011/021: with writers running, every backup is valid and transactionally consistent."""
    nas.put_marker()
    with Writers(settings.db_path) as w:
        w.wait_for(5)
        results, seen = [], 5
        for _ in range(3):
            results.append(backup.run_backup(settings))
            seen += 2
            w.wait_for(seen)                 # make sure more changes land before the next backup
    assert not w.errors, w.errors
    assert [r["last_result"] for r in results] == ["ok"] * 3
    copies = [nas.path / n for n in sorted(nas.backups())]
    assert len(copies) == 3
    sizes = [assert_consistent_snapshot(c) for c in copies]
    assert sizes == sorted(sizes) and sizes[0] >= 5 - 3          # snapshots grow as writes continue (loose: writers race)
    live = table_rows(settings.db_path, "accounts")
    assert len(live) >= sizes[-1]


@pytest.mark.contract("BKP-011", "BKP-012")
def test_snapshot_rows_are_a_prefix_of_the_live_history(client, nas, settings):
    """BKP-011/012: everything in a snapshot's audit_log is identical to the live audit_log at those ids."""
    nas.put_marker()
    with Writers(settings.db_path) as w:
        w.wait_for(8)
        backup.run_backup(settings)
    copy = nas.path / nas.backups()[0]
    snap = table_rows(copy, "audit_log")
    live = {r["id"]: r for r in table_rows(settings.db_path, "audit_log")}
    assert snap and all(live[r["id"]] == r for r in snap)


@pytest.mark.contract("BKP-021")
def test_overlapping_runs_are_serialized(client, healthy, settings):
    """BKP-021: two runs started at the same moment don't overlap: one backs up, the other sees 'unchanged'."""
    barrier = threading.Barrier(2)
    out, errors = [], []

    def go():
        try:
            barrier.wait(10)
            out.append(backup.run_backup(settings)["last_result"])
        except Exception as ex:          # noqa: BLE001
            errors.append(ex)

    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors, errors
    assert sorted(out) == ["ok", "unchanged"]
    assert len(healthy.backups()) == 1 and len(healthy.backups(".json")) == 1


@pytest.mark.contract("BKP-021", "BKP-022")
def test_reads_and_writes_succeed_while_a_backup_runs(client, healthy, seed, settings):
    """BKP-021/022: requests are served normally while a backup runs in another thread."""
    started, done = threading.Event(), threading.Event()
    result = {}

    def go():
        started.set()
        result["r"] = backup.run_backup(settings)
        done.set()

    t = threading.Thread(target=go)
    t.start()
    started.wait(10)
    statuses = []
    while not done.is_set() and len(statuses) < 200:
        statuses.append(client.get("/api/state").status_code)
    seed.account("während des Backups")
    t.join(30)
    assert result["r"]["last_result"] == "ok"
    assert set(statuses) <= {200}
    assert len(seed.state()["accounts"]) == 2
