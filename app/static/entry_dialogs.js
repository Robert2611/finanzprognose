// ------------------------------------------------------------ Buchungs-Dialoge (B-027)
// Recurring and one-time bookings are the same table on the server (`kind`), but the UI keeps
// them apart: each has its own view and its own dialog, and a booking never changes its kind
// in the UI. `entryDialog(e)` opens the dialog that matches an existing booking.
import { html } from './vendor/lit-html.js';
import { toInput, today, toast, api, RHYTHM, activeAccounts, formDialog, refresh } from './core.js';
import { entryType, categoryNames } from './grouping.js';

/** Known categories for the entry form, most used first (see categoryNames). */
function categorySuggestions() {
  return [...categoryNames().values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'de')).map(c => c.name);
}

const TYPE_OPTIONS = [{ value: 'income', label: 'Einnahme' }, { value: 'expense', label: 'Ausgabe' }, { value: 'transfer', label: 'Umbuchung zwischen Konten' }];
const ESTIMATED_HINT = 'Geschätzte Beträge werden mit „≈“ angezeigt. Die Abweichung zur Wirklichkeit zeigt der nächste Ist-Stand.';

/** The dialog for `kind` ('recurring' or 'once'); `e` is the booking to edit, or null for a new one. */
async function bookingDialog(kind, e) {
  const accs = activeAccounts();
  if (!accs.length) { toast('Bitte zuerst ein Konto anlegen', true); return; }
  const accOpts = accs.map(a => ({ value: a.id, label: a.name }));
  const recurring = kind === 'recurring';
  const values = e ? { ...e, type: entryType(e), amount: toInput(Math.abs(e.amount)), to_account_id: e.to_account_id ?? '', end_date: e.end_date ?? '' }
    : { type: 'expense', interval_months: 1, start_date: today(), account_id: accs[0].id };
  values.estimated = e?.estimated ? '1' : '0';
  const noun = recurring ? 'wiederkehrende Buchung' : 'einmalige Buchung';
  const ok = await formDialog({
    title: e ? `Buchung „${e.name}“ bearbeiten` : `Neue ${noun}`, values,
    intro: e && recurring ? html`<p class="small muted">Änderungen am Grundbetrag wirken rückwirkend auf alle Termine. Für eine Änderung <i>ab einem Datum</i> (z. B. Gehaltserhöhung) nutze stattdessen „Anpassungen“.</p>` : '',
    fields: [
      { name: 'name', label: 'Bezeichnung', required: true },
      { name: 'type', label: 'Typ', type: 'select', options: TYPE_OPTIONS },
      { name: 'account_id', label: 'Konto', type: 'select', options: accOpts },
      { name: 'to_account_id', label: 'Zielkonto', type: 'select', options: accOpts, showIf: v => v.type === 'transfer' },
      { name: 'amount', label: 'Betrag (positiv eingeben)', type: 'money', required: true },
      { name: 'estimated', label: 'Art', type: 'select', hint: ESTIMATED_HINT, options: recurring
        ? [{ value: '0', label: 'Fest (z. B. Miete, Abo)' }, { value: '1', label: 'Geschätzt (z. B. Lebensmittel)' }]
        : [{ value: '0', label: 'Fest (Betrag steht fest)' }, { value: '1', label: 'Geschätzt (z. B. Urlaub, Reparatur)' }] },
      ...(recurring ? [
        { name: 'interval_months', label: 'Rhythmus', type: 'select', options: Object.entries(RHYTHM).map(([k, l]) => ({ value: k, label: l })) },
        { name: 'start_date', label: 'Datum der ersten Fälligkeit', type: 'date', required: true, hint: 'Der Tag wird für alle Folgetermine übernommen (bei kürzeren Monaten der Monatsletzte).' },
        { name: 'end_date', label: 'Letzte Fälligkeit (optional)', type: 'date', hint: 'Leer lassen = unbegrenzt' },
      ] : [
        { name: 'start_date', label: 'Datum', type: 'date', required: true },
      ]),
      { name: 'category', label: 'Kategorie (optional)', type: 'text', suggestions: categorySuggestions() },
      { name: 'note', label: 'Notiz (optional)', type: 'textarea' },
    ],
    onSubmit: v => {
      const abs = Math.abs(v.amount);
      const body = {
        name: v.name, account_id: +v.account_id, to_account_id: v.type === 'transfer' ? +v.to_account_id : null,
        amount: v.type === 'expense' ? -abs : abs, kind, interval_months: recurring ? +(v.interval_months || 1) : 1,
        start_date: v.start_date, end_date: recurring ? v.end_date || null : null, category: v.category || '', note: v.note || '',
        estimated: v.estimated === '1',
      };
      return e ? api('PUT', `/api/entries/${e.id}`, { ...body, expected_updated_at: e.updated_at }) : api('POST', '/api/entries', body);
    },
  });
  if (ok) { toast('Gespeichert'); refresh(); }
}

/** New (or edit an existing) recurring booking. */
export const recurringDialog = (e = null) => bookingDialog('recurring', e);
/** New (or edit an existing) one-time booking. */
export const onceDialog = (e = null) => bookingDialog('once', e);
/** Edit an existing booking in the dialog that matches its kind. */
export const entryDialog = e => bookingDialog(e.kind === 'once' ? 'once' : 'recurring', e);
