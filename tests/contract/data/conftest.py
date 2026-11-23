import pytest


@pytest.fixture
def world(client, db_path, seed):
    """An app-written database holding one row in every data table (+ audit rows)."""
    giro = seed.account("Giro", 100000, "2026-01-15")
    tg = seed.account("Tagesgeld", 0, "2026-01-15", kind="savings")
    entry = seed.entry(giro["id"], "Miete", -120000, "2026-01-01")
    adj = seed.adjustment(entry["id"], "2026-03-01", mode="set", amount=-130000)
    cp = seed.checkpoint(giro["id"], "2026-02-20", 500000)
    return {"db": db_path, "account": giro, "account2": tg, "entry": entry, "adjustment": adj, "checkpoint": cp}
