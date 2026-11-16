"""Generic CRUD over TABLES. Every write lands here and logs to audit_log
in the same transaction (see errors.NotFound/Conflict and audit.py for the
read/undo side of the log)."""
import json

from .connection import now
from .errors import Conflict, NotFound
from .schema import TABLES


def get(conn, table: str, id_: int) -> dict | None:
    assert table in TABLES
    r = conn.execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone()
    return dict(r) if r else None


def all_rows(conn, table: str) -> list[dict]:
    assert table in TABLES
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]


def _audit(conn, action, entity, entity_id, before, after, comment="", reverts_id=None):
    conn.execute(
        "INSERT INTO audit_log(ts, action, entity, entity_id, before, after, comment, reverts_id) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (now(), action, entity, entity_id,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False) if after is not None else None,
         comment or "", reverts_id),
    )


def create(conn, table: str, data: dict, comment: str = "") -> dict:
    fields = TABLES[table]
    ts = now()
    given = [f for f in fields if f in data]  # missing keys fall back to the column default
    cols = given + ["created_at", "updated_at"]
    vals = [data[f] for f in given] + [ts, ts]
    cur = conn.execute(
        f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", vals
    )
    new = get(conn, table, cur.lastrowid)
    _audit(conn, "create", table, new["id"], None, new, comment)
    return new


def _write(conn, table, id_, changes: dict, action: str, comment="", expected_updated_at=None, reverts_id=None) -> dict:
    before = get(conn, table, id_)
    if before is None:
        raise NotFound("not_found", entity=table, id=id_)
    if expected_updated_at and before["updated_at"] != expected_updated_at:
        raise Conflict("conflict")
    changes = {k: v for k, v in changes.items() if before.get(k) != v}
    if not changes:
        return before
    changes["updated_at"] = now()
    sets = ",".join(f"{k}=?" for k in changes)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*changes.values(), id_])
    after = get(conn, table, id_)
    _audit(conn, action, table, id_, before, after, comment, reverts_id)
    return after


def update(conn, table, id_, data: dict, expected_updated_at=None, comment="") -> dict:
    changes = {f: data[f] for f in TABLES[table] if f in data}
    return _write(conn, table, id_, changes, "update", comment, expected_updated_at)


def set_archived(conn, table, id_, archived: bool, comment="") -> dict:
    return _write(conn, table, id_, {"archived": 1 if archived else 0},
                  "archive" if archived else "restore", comment)
