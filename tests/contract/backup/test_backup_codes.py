"""B-020: backup status codes instead of German text (BKP-027, API-BKP-011)."""
import json
import re

import pytest

GERMAN = re.compile(r"[äöüÄÖÜß]|\b(fehlt|Sicherung|existiert|manuell|zeitplan|wiederholung)\b", re.I)


@pytest.mark.contract("BKP-027", "API-BKP-011")
def test_error_and_reason_are_codes(client, nas, seed):
    """BKP-027/API-BKP-011: a failed manual run reports last_error {code, params} and last_reason 'manual', no German."""
    seed.account()
    st = client.post("/api/backup/run").json()
    assert st["last_reason"] == "manual"
    assert st["last_error"]["code"] == "marker_missing"
    assert not GERMAN.search(json.dumps(st, ensure_ascii=False).replace(str(nas.path), ""))


@pytest.mark.contract("BKP-027", "BKP-014")
def test_backups_log_records_the_reason_code(client, healthy):
    """BKP-027/BKP-014: the backups.log line ends with the reason code."""
    client.post("/api/backup/run")
    line = (healthy.path / "backups.log").read_text(encoding="utf-8").splitlines()[-1]
    assert line.split("\t")[-1] == "manual"


@pytest.mark.contract("BKP-027")
def test_an_old_german_status_is_passed_through(client, settings, nas):
    """BKP-027: a status file from before B-020 with German strings is still served as-is."""
    with open(settings.status_file, "w", encoding="utf-8") as f:
        json.dump({"last_result": "error", "last_reason": "zeitplan",
                   "last_error": "Datei .nas-marker fehlt im Backup-Ziel – ist das NAS eingebunden?"}, f)
    st = client.get("/api/backup/status").json()
    assert st["last_reason"] == "zeitplan" and st["last_error"].startswith("Datei .nas-marker fehlt")


@pytest.mark.contract("BKP-027")
def test_success_clears_the_error(client, nas, seed):
    """BKP-027: after a successful run last_error is null again."""
    seed.account()
    client.post("/api/backup/run")
    nas.put_marker()
    st = client.post("/api/backup/run").json()
    assert st["last_result"] == "ok" and st["last_error"] is None
