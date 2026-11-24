// ------------------------------------------------------------ Gruppierung (Buchungen, Einzelbuchungen, Prognose)
// A view-only grouping of bookings. Nothing is stored on the server: the chosen dimension is
// remembered per view in localStorage, folded groups only in memory.
import { html } from './vendor/lit-html.js';
import { rhythm, accName, S } from './core.js';

export function entryType(e) { return e.to_account_id ? 'transfer' : e.amount < 0 ? 'expense' : 'income'; }
/** German label of an entry type, as shown in the booking lists. */
export const TYPE_LABEL = { income: 'Einnahme', expense: 'Ausgabe', transfer: 'Umbuchung' };

/** Category names per case-insensitive key: key -> {name: most-used spelling, count}. All entries count, archived too. */
export function categoryNames(entries = S.data.entries) {
  const groups = new Map();
  for (const e of entries) {
    const name = (e.category || '').trim();
    if (!name) continue;
    const key = name.toLocaleLowerCase('de');
    const g = groups.get(key) ?? { count: 0, spellings: new Map() };
    g.count++;
    g.spellings.set(name, (g.spellings.get(name) ?? 0) + 1);
    groups.set(key, g);
  }
  const out = new Map();
  for (const [key, g] of groups) {
    const name = [...g.spellings].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'de'))[0][0];
    out.set(key, { name, count: g.count });
  }
  return out;
}

const TYPE_GROUPS = { income: [0, 'Einnahmen'], expense: [1, 'Ausgaben'], transfer: [2, 'Umbuchungen'] };

/** The grouping dimensions. key(entry, accountId) -> {key, label, order}; order sorts the groups. */
export const DIMENSIONS = {
  none: { label: 'Keine' },
  category: {
    label: 'Kategorie', key: e => {
      const k = (e.category || '').trim().toLocaleLowerCase('de');
      if (!k) return { key: '', label: 'Ohne Kategorie', order: [1, ''] };
      const name = categoryNames().get(k)?.name ?? e.category.trim();
      return { key: k, label: name, order: [0, name.toLocaleLowerCase('de')] };
    },
  },
  type: { label: 'Typ', key: e => { const [o, label] = TYPE_GROUPS[entryType(e)]; return { key: entryType(e), label, order: [o] }; } },
  account: {
    label: 'Konto', key: (e, accountId = e.account_id) =>
      ({ key: String(accountId), label: accName(accountId), order: [S.data.accounts.findIndex(a => a.id === accountId)] }),
  },
  rhythm: {
    label: 'Rhythmus', key: e => e.kind === 'once'
      ? { key: 'once', label: 'einmalig', order: [1, 0] }
      : { key: String(e.interval_months), label: rhythm(e.interval_months), order: [0, e.interval_months] },
  },
  estimated: {
    label: 'Art', key: e => e.estimated
      ? { key: 'estimated', label: 'geschätzt', order: [1] }
      : { key: 'fixed', label: 'fest', order: [0] },
  },
};

const cmpOrder = (a, b) => {
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] ?? '', y = b[i] ?? '';
    if (x !== y) return typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y), 'de');
  }
  return 0;
};

/** Group `items`; `keyOf(item)` returns the {key,label,order} of an item. Groups sorted by order; item order kept inside a group. */
export function groupItems(items, keyOf) {
  const groups = new Map();
  for (const it of items) {
    const k = keyOf(it);
    if (!groups.has(k.key)) groups.set(k.key, { ...k, items: [] });
    groups.get(k.key).items.push(it);
  }
  return [...groups.values()].sort((a, b) => cmpOrder(a.order, b.order));
}

/** Monthly equivalent of a booking's base amount in cents (amount / interval), null for one-time bookings. */
export const monthlyAmount = e => e.kind === 'once' ? null : e.amount / (e.interval_months || 1);

// ---- remembered choice (per view) and folded groups (in memory)
// The in-memory choice is the source of truth; localStorage only carries it across reloads.
const storeKey = view => `finanzprognose.groupBy.${view}`;
const chosen = {};
/** The view's chosen dimension; one not in `dims` (the view's offered dimensions) counts as 'none'. */
export function getDimension(view, dims = Object.keys(DIMENSIONS)) {
  if (!(view in chosen)) {
    let v = null;
    try { v = localStorage.getItem(storeKey(view)); } catch { /* storage unavailable */ }
    chosen[view] = v && DIMENSIONS[v] ? v : 'none';
  }
  return dims.includes(chosen[view]) ? chosen[view] : 'none';
}
function setDimension(view, dim) {
  chosen[view] = dim;
  try { localStorage.setItem(storeKey(view), dim); } catch { /* storage unavailable: choice lasts until reload */ }
}

const toggled = new Set();
/** Whether a group is open; `openByDefault` is the state before the user toggled it. */
export const isOpen = (view, dim, key, openByDefault) => toggled.has(`${view}|${dim}|${key}`) !== openByDefault;
export const toggleGroup = (view, dim, key) => { const k = `${view}|${dim}|${key}`; toggled.has(k) ? toggled.delete(k) : toggled.add(k); };

/** The "Gruppieren nach" select; calls onChange() after storing the new choice. `dims` limits the offered dimensions. */
export const dimensionSelect = (view, onChange, dims = Object.keys(DIMENSIONS)) => html`<label>Gruppieren nach <select name="group-by" @change=${ev => { setDimension(view, ev.target.value); onChange(); }}>
    ${dims.map(k => html`<option value=${k} ?selected=${k === getDimension(view, dims)}>${DIMENSIONS[k].label}</option>`)}</select></label>`;

/** Table body rows of a booking list grouped by the view's dimension: a `group-head` row per group
 *  ("<label> · N Buchung(en)" plus `sumTpl(items)`), followed by its rows unless folded. */
export function groupedRows({ view, dims, items, rowTpl, colspan, sumTpl, rerender }) {
  const dim = getDimension(view, dims);
  if (dim === 'none') return items.map(rowTpl);
  return groupItems(items, e => DIMENSIONS[dim].key(e)).map(g => {
    const open = isOpen(view, dim, g.key, true);
    const toggle = () => { toggleGroup(view, dim, g.key); rerender(); };
    return html`<tr class="group-head"><td colspan=${colspan}><button class="link" aria-expanded=${open} @click=${toggle}>${open ? '▾' : '▸'} ${g.label}</button>
      <span class="muted">· ${g.items.length} Buchung${g.items.length === 1 ? '' : 'en'}</span>${sumTpl(g.items)}</td></tr>
      ${open ? g.items.map(rowTpl) : ''}`;
  });
}
