"""Forecast engine.

For every month and every account it computes:
  opening balance -> every single booking (with an explanation of how its amount came about) -> closing balance.

The anchor points are the checkpoints: the actual account balance at the end of a given day.
An account's first checkpoint is its starting point; bookings on or before that day are considered
already included in it. Later checkpoints reset the forecast to the real value and report the
deviation from the forecast.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


def add_months(y: int, m: int, n: int) -> tuple[int, int]:
    t = y * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def full_years(a: date, b: date) -> int:
    y = b.year - a.year
    if (b.month, b.day) < (a.month, a.day):
        y -= 1
    return y


def occurrences(e: dict, until: date):
    start = date.fromisoformat(e["start_date"])
    end = date.fromisoformat(e["end_date"]) if e.get("end_date") else None
    i = 0
    while True:
        y, m = add_months(start.year, start.month, i * e["interval_months"])
        d = date(y, m, min(start.day, monthrange(y, m)[1]))
        if d > until or (end and d > end):
            return
        yield d
        if e["kind"] == "once":
            return
        i += 1


def amount_at(e: dict, adjs: list[dict], d: date) -> tuple[int, list[dict]]:
    """Amount of an entry on a given date, including a complete derivation.

    Each explanation step is a {code, params} dict; app.js renders the German text.
    """
    amt = e["amount"]
    expl = [{"code": "base_amount", "amount": amt}]
    for a in adjs:  # sorted by date
        eff = date.fromisoformat(a["effective_date"])
        if eff > d:
            break
        note = a.get("note") or None
        if a["mode"] == "set":
            amt = a["amount"]
            expl.append({"code": "set_amount", "date": a["effective_date"], "amount": amt, "note": note})
        else:
            n = full_years(eff, d) + 1 if a["repeat_yearly"] else 1
            factor = Decimal(1) + Decimal(str(a["percent"])) / 100
            val = Decimal(amt)
            for _ in range(n):
                val = (val * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            amt = int(val)
            expl.append({
                "code": "percent_change", "date": a["effective_date"], "percent": a["percent"],
                "repeat_yearly": bool(a["repeat_yearly"]), "years": n, "amount": amt, "note": note,
            })
    return amt, expl


def compute(state: dict, start: str, months: int) -> dict:
    sy, sm = map(int, start.split("-"))
    bounds = []
    for k in range(months):
        y, m = add_months(sy, sm, k)
        bounds.append((f"{y:04d}-{m:02d}", date(y, m, 1), date(y, m, monthrange(y, m)[1])))
    range_start, horizon = bounds[0][1], bounds[-1][2]

    accounts = [a for a in state["accounts"] if not a["archived"]]
    acc_ids = {a["id"] for a in accounts}
    acc_name = {a["id"]: a["name"] for a in state["accounts"]}
    warnings: list[dict] = []

    adjs = defaultdict(list)
    for a in state["adjustments"]:
        if not a["archived"]:
            adjs[a["entry_id"]].append(a)
    for lst in adjs.values():
        lst.sort(key=lambda a: (a["effective_date"], a["id"]))

    # Events per account: (date, order, id, item). On the same day, bookings (0) come before checkpoints (1).
    events = defaultdict(list)
    for cp in state["checkpoints"]:
        if cp["archived"] or cp["account_id"] not in acc_ids:
            continue
        d = date.fromisoformat(cp["date"])
        if d <= horizon:
            events[cp["account_id"]].append((d, 1, cp["id"], {
                "type": "checkpoint", "checkpoint_id": cp["id"], "date": cp["date"],
                "balance": cp["balance"], "note": cp["note"],
            }))

    for e in state["entries"]:
        if e["archived"] or e["account_id"] not in acc_ids:
            continue
        to = e.get("to_account_id")
        if to and to not in acc_ids:
            warnings.append({"code": "transfer_target_archived", "entry_id": e["id"], "account_id": to})
            continue
        for d in occurrences(e, horizon):
            amt, expl = amount_at(e, adjs[e["id"]], d)
            base = {"entry_id": e["id"], "date": d.isoformat(), "category": e["category"], "explanation": expl}
            if to:
                events[e["account_id"]].append((d, 0, e["id"], {
                    **base, "type": "transfer", "amount": -amt, "label": f"{e['name']} → {acc_name[to]}"}))
                events[to].append((d, 0, e["id"], {
                    **base, "type": "transfer", "amount": amt, "label": f"{e['name']} ← {acc_name[e['account_id']]}"}))
            else:
                events[e["account_id"]].append((d, 0, e["id"], {**base, "type": "booking", "amount": amt, "label": e["name"]}))

    out_months = [{"month": key, "accounts": {}, "opening": 0, "closing": 0, "income": 0, "expense": 0}
                  for key, _, _ in bounds]

    for acc in accounts:
        evs = sorted(events[acc["id"]], key=lambda x: (x[0], x[1], x[2]))
        if not any(ev[3]["type"] == "checkpoint" for ev in evs):
            warnings.append({"code": "no_checkpoint", "account_id": acc["id"]})
        running = None
        i = 0

        def apply(item, sink):
            nonlocal running
            it = dict(item)
            if it["type"] == "checkpoint":
                if running is not None:
                    it["expected"] = running
                    it["deviation"] = it["balance"] - running
                running = it["balance"]
            else:
                if running is None:
                    return  # before the first checkpoint: already included in the starting balance
                running += it["amount"]
                it["balance"] = running
            if sink is not None:
                sink.append(it)

        while i < len(evs) and evs[i][0] < range_start:
            apply(evs[i][3], None)
            i += 1
        for k, (_, _, mend) in enumerate(bounds):
            opening, items = running, []
            while i < len(evs) and evs[i][0] <= mend:
                apply(evs[i][3], items)
                i += 1
            mo = out_months[k]
            if opening is None and items and items[0]["type"] == "checkpoint":
                opening = items[0]["balance"]  # account starts in this month: it opens at the start balance
            mo["accounts"][acc["id"]] = {"opening": opening, "closing": running, "items": items}
            mo["opening"] += opening or 0
            mo["closing"] += running or 0
            for it in items:
                if it["type"] == "booking":
                    mo["income" if it["amount"] > 0 else "expense"] += it["amount"]

    return {
        "start": start,
        "months": out_months,
        "accounts": [{"id": a["id"], "name": a["name"], "kind": a["kind"]} for a in accounts],
        "warnings": warnings,
    }
