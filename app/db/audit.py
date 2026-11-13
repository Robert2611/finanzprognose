"""Read and undo side of the append-only audit log, plus the export/version
helpers that are derived from it."""
import json

from .connection import now
from .crud import _write, all_rows
from .errors import NotFound
from .schema import TABLES


def revert(conn, audit_id: int) -> dict:
    """Undoes a single logged change (as a new, logged change)."""
    a = conn.execute("SELECT * FROM audit_log WHERE id=?", (audit_id,)).fetchone()
    if a is None:
        raise NotFound("not_found", entity="audit_log", id=audit_id)
    table, eid = a["entity"], a["entity_id"]
    if a["action"] == "create":
        return _write(conn, table, eid, {"archived": 1}, "revert", reverts_id=audit_id)
    before = json.loads(a["before"])
    changes = {f: before[f] for f in TABLES[table] + ["archived"] if f in before}
    return _write(conn, table, eid, changes, "revert", reverts_id=audit_id)


def audit_list(conn, limit=200, before_id=None, entity=None, entity_id=None) -> list[dict]:
    q, p = "SELECT * FROM audit_log WHERE 1=1", []
    if before_id:
        q += " AND id<?"
        p.append(before_id)
    if entity:
        q += " AND entity=?"
        p.append(entity)
    if entity_id:
        q += " AND entity_id=?"
        p.append(entity_id)
    q += " ORDER BY id DESC LIMIT ?"
    p.append(limit)
    out = []
    for r in conn.execute(q, p):
        d = dict(r)
        d["before"] = json.loads(d["before"]) if d["before"] else None
        d["after"] = json.loads(d["after"]) if d["after"] else None
        out.append(d)
    return out


def data_version(conn) -> int:
    """Increases with every change; basis for 'only back up if something changed'."""
    return conn.execute("SELECT COALESCE(MAX(id),0) FROM audit_log").fetchone()[0]


def export_all(conn) -> dict:
    data = {t: all_rows(conn, t) for t in TABLES}
    data["audit_log"] = list(reversed(audit_list(conn, limit=10**9)))
    data["exported_at"] = now()
    data["data_version"] = data_version(conn)
    return data
