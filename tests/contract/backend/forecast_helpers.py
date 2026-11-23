"""Row builders for forecast.compute (rows shaped like the /api/export table dumps, see F-4)."""
from datetime import date

T = "2026-01-01T00:00:00.000+00:00"


def account(id, name=None, kind="checking", archived=0):
    return {"id": id, "name": name or f"Acc{id}", "kind": kind, "note": "", "archived": archived,
            "created_at": T, "updated_at": T}


def entry(id, account_id, amount, start_date, name=None, kind="recurring", interval_months=1, end_date=None,
          to_account_id=None, category="", archived=0, estimated=None):
    return {"id": id, "account_id": account_id, "to_account_id": to_account_id, "name": name or f"E{id}",
            "category": category, "kind": kind, "amount": amount, "start_date": start_date, "end_date": end_date,
            "interval_months": interval_months, "note": "", "archived": archived, "created_at": T, "updated_at": T,
            **({} if estimated is None else {"estimated": estimated})}


def adjustment(id, entry_id, effective_date, mode="set", amount=None, percent=None, repeat_yearly=0, note="", archived=0):
    return {"id": id, "entry_id": entry_id, "effective_date": effective_date, "mode": mode, "amount": amount,
            "percent": percent, "repeat_yearly": repeat_yearly, "note": note, "archived": archived,
            "created_at": T, "updated_at": T}


def checkpoint(id, account_id, date_, balance, note="", archived=0):
    return {"id": id, "account_id": account_id, "date": date_, "balance": balance, "note": note,
            "archived": archived, "created_at": T, "updated_at": T}


def state(accounts=(), entries=(), adjustments=(), checkpoints=()):
    return {"accounts": list(accounts), "entries": list(entries), "adjustments": list(adjustments),
            "checkpoints": list(checkpoints)}


def iso(d):
    return d.isoformat() if isinstance(d, date) else str(d)


def month(result, ym):
    return next(m for m in result["months"] if m["month"] == ym)


def acct(m, account_id):
    """Per-account block of a month; the contract writes keys as strings (F-16), accept either."""
    block = m["accounts"]
    return block[str(account_id)] if str(account_id) in block else block[account_id]


def items(result, ym, account_id):
    return acct(month(result, ym), account_id)["items"]
