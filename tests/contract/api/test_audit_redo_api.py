"""B-019: revert of a revert row over HTTP (API-AUDIT-011)."""
import pytest


@pytest.mark.contract("API-AUDIT-011")
def test_revert_of_a_revert_row_is_a_redo(client, seed):
    """API-AUDIT-011: POST /api/audit/{undo}/revert -> 200, the rename is back, a new revert row references the undo."""
    acc = seed.account("X")
    client.put(f"/api/accounts/{acc['id']}", json={"name": "Y", "kind": "checking"})
    upd = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]
    assert client.post(f"/api/audit/{upd['id']}/revert").json()["name"] == "X"
    undo = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]
    r = client.post(f"/api/audit/{undo['id']}/revert")
    assert r.status_code == 200 and r.json()["name"] == "Y"
    newest = client.get(f"/api/audit?entity=accounts&entity_id={acc['id']}").json()[0]
    assert newest["action"] == "revert" and newest["reverts_id"] == undo["id"]
