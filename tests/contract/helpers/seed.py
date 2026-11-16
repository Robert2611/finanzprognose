"""API-driven fixture builders. Only the public HTTP API is used (never SQL)."""


class Seed:
    def __init__(self, client):
        self.c = client

    def _ok(self, r):
        assert r.status_code == 200, f"{r.request.method} {r.request.url}: {r.status_code} {r.text}"
        return r.json()

    def account(self, name="Giro", start_balance=100000, start_date="2026-01-15", kind="checking", note="", **extra):
        return self._ok(self.c.post("/api/accounts", json={
            "name": name, "kind": kind, "note": note,
            "start_balance": start_balance, "start_date": start_date, **extra}))

    def entry(self, account_id, name="Booking", amount=-1000, start_date="2026-01-01", kind="recurring",
              interval_months=1, to_account_id=None, end_date=None, category="", note="", **extra):
        body = {"account_id": account_id, "to_account_id": to_account_id, "name": name, "category": category,
                "kind": kind, "amount": amount, "start_date": start_date, "end_date": end_date,
                "interval_months": interval_months, "note": note, **extra}
        return self._ok(self.c.post("/api/entries", json=body))

    def adjustment(self, entry_id, effective_date, mode="set", amount=None, percent=None, repeat_yearly=False,
                   note="", **extra):
        body = {"entry_id": entry_id, "effective_date": effective_date, "mode": mode, "amount": amount,
                "percent": percent, "repeat_yearly": repeat_yearly, "note": note, **extra}
        return self._ok(self.c.post("/api/adjustments", json=body))

    def checkpoint(self, account_id, date, balance, note="", **extra):
        return self._ok(self.c.post("/api/checkpoints", json={
            "account_id": account_id, "date": date, "balance": balance, "note": note, **extra}))

    def state(self):
        return self._ok(self.c.get("/api/state"))

    def forecast(self, start="2026-01", months=12):
        return self._ok(self.c.get(f"/api/forecast?start={start}&months={months}"))

    def standard_world(self):
        """Giro (1.000,00 on 2026-01-15) + Tagesgeld (0), salary, rent, a monthly transfer and a one-off."""
        giro = self.account("Giro", 100000, "2026-01-15")
        tg = self.account("Tagesgeld", 0, "2026-01-15", kind="savings")
        salary = self.entry(giro["id"], "Gehalt", 300000, "2026-01-31")
        rent = self.entry(giro["id"], "Miete", -120000, "2026-01-01")
        saving = self.entry(giro["id"], "Sparen", 50000, "2026-02-05", to_account_id=tg["id"])
        trip = self.entry(giro["id"], "Urlaub", -200000, "2026-03-10", kind="once")
        return {"giro": giro, "tg": tg, "salary": salary, "rent": rent, "saving": saving, "trip": trip}
