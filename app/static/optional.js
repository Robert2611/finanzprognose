// ------------------------------------------------------------ Optionale Buchungen (B-029)
// Optional bookings are not yet decided: the forecast leaves them out unless they are switched
// in here. Which ones are switched in is a view setting of this browser (localStorage); it never
// changes data. Without browser storage the choice lasts until the next reload.
import { html, nothing } from './vendor/lit-html.js';
import { signed, eur, fDate, rhythm, S } from './core.js';
import { entryType } from './grouping.js';

const KEY = 'finanzprognose.includeOptional';
let included = null;   // Set of entry ids, loaded lazily

function load() {
  if (included) return included;
  let ids = [];
  try { ids = JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { /* storage unavailable or garbled */ }
  included = new Set(Array.isArray(ids) ? ids.filter(Number.isInteger) : []);
  return included;
}
function save() {
  try { localStorage.setItem(KEY, JSON.stringify([...included])); } catch { /* storage unavailable */ }
}

/** The active optional bookings, by date. */
export const optionalEntries = () => S.data.entries.filter(e => e.optional && !e.archived)
  .sort((a, b) => a.start_date.localeCompare(b.start_date) || a.name.localeCompare(b.name, 'de'));

/** Whether an optional booking is switched in (counts in the forecast). */
export const isIncluded = id => load().has(id);

/** The `include=` query part for the forecast: the switched-in ids that are still active optional bookings. */
export function includeQuery() {
  const live = new Set(optionalEntries().map(e => e.id));
  return [...load()].filter(id => live.has(id)).map(id => `&include=${id}`).join('');
}

/** A short German description of when a booking falls due. */
const when = e => e.kind === 'once' ? fDate(e.start_date) : `${rhythm(e.interval_months)} ab ${fDate(e.start_date)}${e.end_date ? ` bis ${fDate(e.end_date)}` : ''}`;

/** The "Optionale Posten" panel with one checkbox per optional booking; `onChange()` re-runs the forecast. */
export function optionalPanelTpl(onChange) {
  const list = optionalEntries();
  if (!list.length) return nothing;
  const set = load();
  const toggle = (id, on) => { on ? set.add(id) : set.delete(id); save(); onChange(); };
  return html`<div class="panel optional-panel"><div class="toolbar" style="margin-bottom:4px"><b>Optionale Posten</b>
      <span class="muted small">Noch nicht entschieden – zählen nur, wenn eingeschaltet. Die gestrichelte Linie zeigt den Stand mit allen.</span></div>
    ${list.map(e => html`<label class="opt-item"><input type="checkbox" name="include-optional" .checked=${set.has(e.id)}
        @change=${ev => toggle(e.id, ev.target.checked)}> <span>${e.name}</span>
      <span class="num">${entryType(e) === 'transfer' ? eur(e.amount) : signed(e.amount)}</span><span class="muted small">${when(e)}</span></label>`)}</div>`;
}
