// ------------------------------------------------------------ Einmalige Buchungen (B-027)
// Only bookings with kind 'once': single payments into or out of an account, or a single transfer.
import { html, render as renderLit } from './vendor/lit-html.js';
import { eur, signed, approx, fDate, accName, S, archiveDialog, restoreRow } from './core.js';
import { historyDialog } from './audit.js';
import { adjustmentsDialog } from './adjustments.js';
import { onceDialog } from './entry_dialogs.js';
import { entryType, TYPE_LABEL, dimensionSelect, groupedRows } from './grouping.js';

/** "Gruppieren nach" options of this view: a rhythm makes no sense for one-time bookings. */
const DIMS = ['none', 'category', 'type', 'account', 'estimated'];

/** Total of a group's active planned one-time bookings (optional ones left out, B-029); transfers shown separately.
 *  A sum that contains an estimated booking is marked "≈" itself. */
function groupSumTpl(entries) {
  const active = entries.filter(e => !e.archived && !e.optional);
  const sum = list => list.reduce((t, e) => t + e.amount, 0);
  const est = list => approx(list.some(e => e.estimated));
  const bookings = active.filter(e => entryType(e) !== 'transfer'), transfers = active.filter(e => entryType(e) === 'transfer');
  return html`${bookings.length ? html` <span class="muted">· Summe</span> <span class="group-sum">${est(bookings)}${signed(sum(bookings))}</span>` : ''}${
    transfers.length ? html` <span class="muted">· Umbuchungen</span> <span class="group-transfers">${est(transfers)}${eur(sum(transfers))}</span>` : ''}`;
}

export async function renderOnce(main) {
  const entries = S.data.entries.filter(e => e.kind === 'once' && (S.showArchived || !e.archived));
  const adjCount = id => S.data.adjustments.filter(a => a.entry_id === id && !a.archived).length;
  const hasAdj = id => S.data.adjustments.some(a => a.entry_id === id);
  const sorted = entries.slice().sort((a, b) => a.archived - b.archived || a.start_date.localeCompare(b.start_date) || a.name.localeCompare(b.name, 'de'));
  const rerender = () => renderOnce(main);
  const rowTpl = e => html`<tr class="${e.archived ? 'archived' : ''}">
      <td>${fDate(e.start_date)}</td>
      <td><b>${e.name}</b>${e.optional ? html`<span class="tag optional">optional</span>` : ''}${e.category ? html`<span class="tag">${e.category}</span>` : ''}${e.note ? html`<div class="small muted">${e.note}</div>` : ''}</td>
      <td>${TYPE_LABEL[entryType(e)]}</td>
      <td>${accName(e.account_id)}${e.to_account_id ? html` → ${accName(e.to_account_id)}` : ''}</td>
      <td class="num">${approx(e.estimated)}${entryType(e) === 'transfer' ? eur(e.amount) : signed(e.amount)}</td>
      <td style="white-space:nowrap">${e.archived
        ? html`<button class="small" @click=${() => restoreRow('entries', e)}>Wiederherstellen</button>`
        : html`<button class="small" @click=${() => onceDialog(e)}>Bearbeiten</button> <button class="small" @click=${() => archiveDialog('entries', e, e.name)}>Archivieren</button>`}
        <button class="small" title="Änderungsverlauf" @click=${() => historyDialog('entries', e.id)}>Verlauf</button>
        ${hasAdj(e.id) ? html`<button class="small" @click=${() => adjustmentsDialog(e)}>${adjCount(e.id)} Anpassung${adjCount(e.id) === 1 ? '' : 'en'}</button>` : ''}</td></tr>`;
  renderLit(html`<div class="toolbar"><h2 style="margin:0">Einmalige Buchungen</h2><span class="spacer"></span>
    <label><input type="checkbox" .checked=${S.showArchived} @change=${ev => { S.showArchived = ev.target.checked; rerender(); }}> Archivierte zeigen</label>
    ${dimensionSelect('einmalig', rerender, DIMS)}
    <button class="primary" @click=${() => onceDialog()}>+ Neue Buchung</button></div>
    <div class="panel table-wrap page-scroll"><table><thead><tr><th>Datum</th><th>Bezeichnung</th><th>Typ</th><th>Konto</th><th class="num">Betrag</th><th></th></tr></thead><tbody>
    ${!sorted.length ? html`<tr><td colspan="6" class="muted">Noch keine einmaligen Buchungen.</td></tr>`
      : groupedRows({ view: 'einmalig', dims: DIMS, items: sorted, rowTpl, colspan: 6, sumTpl: groupSumTpl, rerender })}
    </tbody></table></div>`, main);
}
