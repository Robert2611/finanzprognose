"""deploy/update.sh (--auto-rollback) and the unit install, against a fake docker (contracts/deploy/auto-update.md).

update.sh insists on root; the tests run as root, or as a mapped root in a user namespace
(`unshare -r`), and are skipped where neither is possible."""
import os
import shutil
import subprocess

import pytest


def _root_prefix():
    if os.geteuid() == 0:
        return []
    if shutil.which("unshare") and subprocess.run(["unshare", "-r", "true"], capture_output=True).returncode == 0:
        return ["unshare", "-r"]
    pytest.skip("update.sh needs root (or unprivileged user namespaces)")


@pytest.fixture
def h(host):
    prefix = _root_prefix()
    host.install("update.sh", "docker-compose.yml")
    host.env(APP_VERSION="v1.0.0", APP_PASSWORD="x", BACKUP_HOST_DIR="/tmp")
    (host.dir / "data").mkdir()
    (host.dir / "data" / "finanzen.sqlite").write_text("data of v1.0.0\n")
    host.release("v1.0.0", "v1.1.0")
    host.docker["local"]["v1.0.0"] = "v1.0.0"
    host.docker["running"] = "v1.0.0"
    host.save_docker()
    host.prefix = prefix
    return host


def failed_dirs(h):
    return sorted(p for p in (h.dir / "data").iterdir() if p.name.startswith("failed-update_"))


@pytest.mark.contract("DEPLOY-UPD-011")
def test_auto_rollback_restores_the_copy_and_the_previous_version(h):
    h.docker["unhealthy"] = ["v1.1.0"]
    h.save_docker()
    r = h.run("update.sh", "--auto-rollback", "v1.1.0")
    assert r.returncode == 2, r.stdout + r.stderr
    d = h.load_docker()
    assert d["running"] == "v1.0.0" and h.env_get("APP_VERSION") == "v1.0.0"
    # the failed version's database is set aside, the pre-update copy is back
    (failed,) = failed_dirs(h)
    assert (failed / "finanzen.sqlite").read_text() == "data of v1.0.0\nopened by v1.1.0\n"
    assert (h.dir / "data" / "finanzen.sqlite").read_text() == "data of v1.0.0\nopened by v1.0.0\n"
    (copy,) = list((h.dir / "data" / "pre-update").iterdir())
    assert (copy / "finanzen.sqlite").read_text() == "data of v1.0.0\n"


@pytest.mark.contract("DEPLOY-UPD-012")
def test_a_failed_rollback_exits_3_with_the_manual_steps(h):
    h.docker["unhealthy"] = ["v1.1.0", "v1.0.0"]
    h.save_docker()
    r = h.run("update.sh", "--auto-rollback", "v1.1.0")
    assert r.returncode == 3
    assert "rollback to v1.0.0 failed" in r.stderr and "./update.sh v1.0.0" in r.stderr


@pytest.mark.contract("DEPLOY-UPD-012")
def test_without_the_flag_a_failed_update_only_prints_the_steps(h):
    h.docker["unhealthy"] = ["v1.1.0"]
    h.save_docker()
    r = h.run("update.sh", "v1.1.0")
    assert r.returncode == 1 and "./update.sh v1.0.0" in r.stderr
    assert h.load_docker()["running"] == "v1.1.0" and failed_dirs(h) == []


@pytest.mark.contract("DEPLOY-UPD-002", "DEPLOY-UPD-013")
def test_a_healthy_update_installs_the_updater_and_its_units(h):
    r = h.run("update.sh", "--auto-rollback", "v1.1.0")
    assert r.returncode == 0, r.stdout + r.stderr
    assert h.load_docker()["running"] == "v1.1.0" and h.env_get("APP_VERSION") == "v1.1.0"
    assert os.access(h.dir / "auto-update.sh", os.X_OK)
    service = (h.units / "finanzprognose-update.service").read_text()
    assert f"ExecStart={h.dir}/auto-update.sh" in service
    assert f"PathExists={h.dir}/updater/request.json" in (h.units / "finanzprognose-update.path").read_text()
    assert (h.units / "finanzprognose-update.timer").exists() and (h.dir / "updater").is_dir()
    calls = (h.dir.parent / "systemctl-calls").read_text()
    assert "enable --now finanzprognose-update.timer finanzprognose-update.path" in calls
