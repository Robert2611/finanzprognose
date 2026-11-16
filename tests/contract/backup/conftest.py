import hashlib
import re

import pytest

from tests.contract.helpers.sqlite_view import open_db

NAME = re.compile(r"^finanzen_(\d{4}-\d{2}-\d{2})_(\d{6})_v(\d+)\.sqlite$")


@pytest.fixture
def healthy(client, nas, seed):
    """A running app with data and a mounted NAS (marker present)."""
    nas.put_marker()
    seed.account("Giro", 100000, "2026-01-15")
    return nas


@pytest.fixture
def bump(seed, client):
    """Make one more logged change (so the next backup has something new)."""
    counter = iter(range(1, 10_000))

    def make():
        a = seed.state()["accounts"][0]
        client.put(f"/api/accounts/{a['id']}", json={"name": f"Giro {next(counter)}", "kind": "checking"})

    return make


def sha256(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def table_rows(path, table):
    with open_db(path, foreign_keys=False) as c:
        return [dict(r) for r in c.execute(f"SELECT * FROM {table} ORDER BY id")]


def version_of(name: str) -> int:
    return int(NAME.match(name).group(3))
