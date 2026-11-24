"""deploy/auto-update.sh against a fake docker and a stub update.sh (contracts/deploy/auto-update.md)."""
import json
import subprocess

import pytest

STUB_UPDATE = r'''#!/usr/bin/env bash
# stub of update.sh; understands --auto-rollback
here=$(cd "$(dirname "$0")" && pwd)
echo "$*" >> "$here/update-calls"
cp "$here/updater/status.json" "$here/status-during-update.json" 2>/dev/null || true
echo "stub update output"
rc=${STUB_RC:-0}
if [[ $rc == 0 ]]; then sed -i "s/^APP_VERSION=.*/APP_VERSION=${@: -1}/" "$here/.env"; fi
exit "$rc"
'''


@pytest.fixture
def h(host):
    host.install("auto-update.sh")
    (host.dir / "update.sh").write_text(STUB_UPDATE)
    (host.dir / "update.sh").chmod(0o755)
    host.env(APP_VERSION="v1.0.0", AUTO_UPDATE="auto")
    return host


def calls(h):
    f = h.dir / "update-calls"
    return f.read_text().splitlines() if f.exists() else []


def request(h, version=None):
    h.updater.mkdir(exist_ok=True)
    (h.updater / "request.json").write_text(json.dumps({"requested_at": "2026-11-24T10:00:00+01:00", "version": version}))


@pytest.mark.contract("DEPLOY-UPD-001")
def test_every_run_writes_a_status_with_the_latest_release(h):
    h.release("v1.0.0")
    r = h.run("auto-update.sh")
    assert r.returncode == 0, r.stderr
    st = h.status()
    assert st["schema"] == 1 and st["mode"] == "auto" and st["state"] == "idle"
    assert st["current"] == "v1.0.0" and st["latest"] == "v1.0.0" and st["checked_at"]
    assert st["check_error"] is None and st["last_update"] is None
    assert calls(h) == []


@pytest.mark.contract("DEPLOY-UPD-002", "DEPLOY-UPD-007")
def test_auto_mode_installs_a_new_release_with_auto_rollback(h):
    h.release("v1.0.0", "v1.1.0")
    r = h.run("auto-update.sh")
    assert r.returncode == 0, r.stderr
    assert calls(h) == ["--auto-rollback v1.1.0"]
    during = json.loads((h.dir / "status-during-update.json").read_text())
    assert during["state"] == "updating" and during["target"] == "v1.1.0"
    st = h.status()
    assert st["state"] == "idle" and st["current"] == "v1.1.0"
    assert st["last_update"]["from"] == "v1.0.0" and st["last_update"]["to"] == "v1.1.0"
    assert st["last_update"]["result"] == "success" and st["last_update"]["at"]
    assert "stub update output" in (h.updater / "last-update.log").read_text()
    # nothing new on the next run
    h.run("auto-update.sh")
    assert calls(h) == ["--auto-rollback v1.1.0"]


@pytest.mark.contract("DEPLOY-UPD-003")
def test_notify_mode_only_reports_a_new_release(h):
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="notify")
    h.release("v1.0.0", "v1.1.0")
    assert h.run("auto-update.sh").returncode == 0
    st = h.status()
    assert st["mode"] == "notify" and st["latest"] == "v1.1.0" and st["current"] == "v1.0.0"
    assert calls(h) == []


@pytest.mark.contract("DEPLOY-UPD-003")
def test_missing_or_unknown_mode_means_auto(h):
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="sometimes")
    h.release("v1.0.0")
    h.run("auto-update.sh")
    assert h.status()["mode"] == "auto"


@pytest.mark.contract("DEPLOY-UPD-004")
def test_a_request_is_consumed_and_updates_even_in_notify_mode(h):
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="notify")
    h.release("v1.0.0", "v1.1.0")
    request(h, "v1.1.0")
    assert h.run("auto-update.sh").returncode == 0
    assert not (h.updater / "request.json").exists()
    assert calls(h) == ["--auto-rollback v1.1.0"]
    assert h.status()["last_update"]["result"] == "success"


@pytest.mark.contract("DEPLOY-UPD-004")
def test_a_request_without_a_valid_version_updates_to_the_latest(h):
    h.release("v1.0.0", "v1.2.0")
    request(h, "; rm -rf /")
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="notify")
    h.run("auto-update.sh")
    assert calls(h) == ["--auto-rollback v1.2.0"]


@pytest.mark.contract("DEPLOY-UPD-005")
@pytest.mark.parametrize("rc, result", [(2, "rolled_back"), (3, "rollback_failed"), (1, "failed")])
def test_a_failed_update_is_recorded_and_not_retried_automatically(h, rc, result):
    h.release("v1.0.0", "v1.1.0")
    r = h.run("auto-update.sh", env={"STUB_RC": str(rc)})
    assert r.returncode == 1
    st = h.status()
    assert st["last_update"]["result"] == result and st["failed_version"] == "v1.1.0"
    assert st["current"] == "v1.0.0" and st["state"] == "idle"
    h.run("auto-update.sh")
    assert len(calls(h)) == 1  # not retried by the timer
    request(h, "v1.1.0")
    assert h.run("auto-update.sh").returncode == 0  # a request retries it
    st = h.status()
    assert len(calls(h)) == 2 and st["last_update"]["result"] == "success" and st["failed_version"] is None


@pytest.mark.contract("DEPLOY-UPD-005")
def test_a_newer_release_after_a_failed_one_is_installed(h):
    h.release("v1.0.0", "v1.1.0")
    h.run("auto-update.sh", env={"STUB_RC": "2"})
    h.release("v1.1.1")
    h.run("auto-update.sh")
    assert calls(h)[-1] == "--auto-rollback v1.1.1"


@pytest.mark.contract("DEPLOY-UPD-006")
def test_a_failed_check_is_reported_and_keeps_the_last_known_release(h):
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="notify")
    h.release("v1.0.0", "v1.1.0")
    h.run("auto-update.sh")
    h.load_docker()
    h.docker["pull_fail"] = True
    h.save_docker()
    h.env(APP_VERSION="v1.0.0", AUTO_UPDATE="auto")
    assert h.run("auto-update.sh").returncode == 0
    st = h.status()
    assert st["check_error"] == "pull_failed" and st["latest"] == "v1.1.0"
    assert calls(h) == []  # no automatic update after a failed check


@pytest.mark.contract("DEPLOY-UPD-008")
def test_a_second_run_exits_while_one_is_busy(h):
    h.release("v1.0.0", "v1.1.0")
    h.updater.mkdir()
    lock = subprocess.Popen(["flock", str(h.updater / ".lock"), "sleep", "5"])
    try:
        import time
        time.sleep(0.3)
        r = h.run("auto-update.sh")
    finally:
        lock.kill()
    assert r.returncode == 0 and calls(h) == [] and not (h.updater / "status.json").exists()


@pytest.mark.contract("DEPLOY-UPD-009")
def test_only_versions_codes_and_timestamps_reach_the_status(h):
    h.env(APP_VERSION='dev"; "x": "y', AUTO_UPDATE="notify")
    h.release("v1.0.0")
    h.run("auto-update.sh")
    st = h.status()  # still valid JSON
    assert st["current"] is None and "x" not in st


@pytest.mark.contract("DEPLOY-UPD-010")
def test_an_old_update_sh_without_auto_rollback_is_called_without_it(h):
    (h.dir / "update.sh").write_text(STUB_UPDATE.replace("auto-rollback", "old"))
    h.release("v1.0.0", "v1.1.0")
    h.run("auto-update.sh")
    assert calls(h) == ["v1.1.0"]
