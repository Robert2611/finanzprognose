// ------------------------------------------------------------ Ereignisse (B-030)
// What makes a month different from the routine: one-time bookings, adjustments taking effect,
// and recurring bookings starting or ending. Derived from S.data for the bookings the forecast
// counts (active, on an active account, optional ones only when switched in). View-only.
// A recurring booking starting in the first shown month is not an event: that is usually just
// when it was entered, and the bookings already running then are the baseline.
import { eur, fDate, rhythm, S } from './core.js';
import { adjLabel } from './adjustments.js';
import { entryType } from './grouping.js';
import { isIncluded } from './optional.js';

/** An entry's base amount as text: signed for income/expense, plain for a transfer. */
const amountText = e => entryType(e) === 'transfer' ? `Umbuchung ${eur(e.amount)}` : `${e.amount > 0 ? '+' : ''}${eur(e.amount)}`;

/** Events per month: Map 'YYYY-MM' -> [{kind, date, entry, text}], sorted by date then name.
 *  kind is once / start / end / adjustment; text is the German one-line description. */
export function eventsByMonth(fc) {
  const months = new Set(fc.months.map(m => m.month));
  const accs = new Set(fc.accounts.map(a => a.id));
  const live = S.data.entries.filter(e => !e.archived && accs.has(e.account_id) && (!e.optional || isIncluded(e.id)));
  const byId = new Map(live.map(e => [e.id, e]));
  const out = new Map();
  const add = (date, kind, entry, text) => {
    const k = date.slice(0, 7);
    if (!months.has(k)) return;
    if (!out.has(k)) out.set(k, []);
    out.get(k).push({ kind, date, entry, text });
  };
  for (const e of live) {
    if (e.kind === 'once') { add(e.start_date, 'once', e, `${e.name}: ${amountText(e)} (einmalig)`); continue; }
    if (e.start_date.slice(0, 7) !== fc.months[0].month) add(e.start_date, 'start', e, `Neu: ${e.name} ${amountText(e)} ${rhythm(e.interval_months)}`);
    if (e.end_date) add(e.end_date, 'end', e, `Endet: ${e.name} (letzte Fälligkeit ${fDate(e.end_date)})`);
  }
  for (const a of S.data.adjustments) {
    const e = byId.get(a.entry_id);
    if (!a.archived && e) add(a.effective_date, 'adjustment', e, `${e.name}: ab ${fDate(a.effective_date)} ${adjLabel(a)}`);
  }
  for (const list of out.values()) list.sort((x, y) => x.date.localeCompare(y.date) || x.entry.name.localeCompare(y.entry.name, 'de'));
  return out;
}
