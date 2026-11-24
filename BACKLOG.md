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
this order, each as its own small PR (B-028, reserve accounts, is done).

## B-029 Optional bookings

- **Status:** open
- **Problem:** planned but undecided expenses (a second holiday, a renovation) can only be in
  or out of the forecast; comparing "with" and "without" means archiving and restoring.
- **Decision (with the user):** a flag `optional` on bookings, default off (= planned).
  Optional bookings are **excluded** from the main numbers by default; the forecast shows
  them as a dashed comparison („mit optionalen Posten“) and each one can be switched into the
  main numbers with a checkbox. That choice is a view setting remembered in the browser; it
  never changes data. No named scenarios (too heavy for this app).

## B-030 Main chart: monthly surplus instead of the cumulative balance

- **Status:** open
- **Problem:** the balance line is cumulative, so the ~80 % recurring part turns into a
  straight slope and the interesting events (planned expenses, income changes) are only
  barely visible bends.
- **Idea:** one bar per month (income up, expenses down, net marker), split into monthly
  recurring / irregular recurring (quarterly, yearly) / one-time, estimates lighter, optional
  items dashed (B-029). Markers for events: one-time bookings, adjustments taking effect, end
  dates of recurring bookings. The balance line stays available as a toggle. Built on the
  available money (B-028).

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
