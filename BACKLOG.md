# Backlog

Open work items for this project. Each item has a stable ID that is never changed or reused.
When an item is done, add its **Resolution** and move it, unchanged otherwise, to the end of
[`docs/backlog-done.md`](docs/backlog-done.md); references like "B-020" in the code, the
contracts and `CLAUDE.md` point there.

Status values: `open`, `in progress`.

**Next free ID:** B-033

The forecast page should answer the questions the app is really used for: planning a year with
its events (holidays, renovations, raises, parental leave ending) and seeing whether the money
works out. B-028..B-032 came out of one discussion with the user and are meant to be done in
this order, each as its own small PR (B-028 reserve accounts, B-029 optional bookings and B-030 the monthly surplus chart are done).

## B-031 „Was ist diesen Monat anders?“

- **Status:** open
- **Idea:** clicking a month shows per category how much it differs from a reference (a
  "normal month" = the monthly equivalent of the recurring bookings, or the previous month),
  as diverging bars sorted by size, plus the category breakdown of the month as horizontal
  bars. Checkpoint corrections appear as their own bar.

## B-032 Year summary

- **Status:** open
- **Idea:** per year: income, recurring expenses, planned one-time expenses, transfers into
  the reserve, and what is left — the "idea of the year" in one row.
