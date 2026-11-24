// ------------------------------------------------------------ Wiederkehrende Buchungen
// Only bookings with kind 'recurring'; one-time bookings have their own view (once.js, B-027).
import { html, render as renderLit } from './vendor/lit-html.js';
import { eur, signed, approx, fDate, rhythm, accName, S, archiveDialog, restoreRow } from './core.js';
import { historyDialog } from './audit.js';
import { adjustmentsDialog } from './adjustments.js';
import { recurringDialog } from './entry_dialogs.js';
import { entryType, TYPE_LABEL, monthlyAmount, dimensionSelect, groupedRows } from './grouping.js';

/** Monthly equivalent of a group's active bookings; transfers shown separately.
 *  A sum that contains an estimated booking is marked "≈" itself. */
function groupSumTpl(entries) {
  const active = entries.filter(e => !e.archived && monthlyAmount(e) != null);
  const sum = list => Math.round(list.reduce((t, e) => t + monthlyAmount(e), 0));
  const est = list => approx(list.some(e => e.estimated));
  const bookings = active.filter(e => entryType(e) !== 'transfer'), transfers = active.filter(e => entryType(e) === 'transfer');
  return html`${bookings.length ? html` <span class="muted">·</span> <span class="group-sum">${est(bookings)}${signed(sum(bookings))}/Monat</span>` : ''}${
    transfers.length ? html` <span class="muted">· Umbuchungen</span> <span class="group-transfers">${est(transfers)}${eur(sum(transfers))}/Monat</span>` : ''}`;
}

export async function renderEntries(main) {
  const entries = S.data.entries.filter(e => e.kind !== 'once' && (S.showArchived || !e.archived));
  const adjCount = id => S.data.adjustments.filter(a => a.entry_id === id && !a.archived).length;
  const sorted = entries.slice().sort((a, b) => a.archived - b.archived || a.name.localeCompare(b.name, 'de'));
  const rerender = () => renderEntries(main);
  const rowTpl = e => html`<tr class="${e.archived ? 'archived' : ''}">
      <td><b>${e.name}</b>${e.category ? html`<span class="tag">${e.category}</span>` : ''}${e.note ? html`<div class="small muted">${e.note}</div>` : ''}</td>
      <td>${TYPE_LABEL[entryType(e)]}</td>
      <td>${accName(e.account_id)}${e.to_account_id ? html` → ${accName(e.to_account_id)}` : ''}</td>
      <td class="num">${approx(e.estimated)}${entryType(e) === 'transfer' ? eur(e.amount) : signed(e.amount)}</td>
      <td>${rhythm(e.interval_months)}</td>
      <td>${`ab ${fDate(e.start_date)}${e.end_date ? ` bis ${fDate(e.end_date)}` : ''}`}</td>
      <td><button class="small" @click=${() => adjustmentsDialog(e)}>${adjCount(e.id)} Anpassung${adjCount(e.id) === 1 ? '' : 'en'}</button></td>
      <td style="white-space:nowrap">${e.archived
        ? html`<button class="small" @click=${() => restoreRow('entries', e)}>Wiederherstellen</button>`
        : html`<button class="small" @click=${() => recurringDialog(e)}>Bearbeiten</button> <button class="small" @click=${() => archiveDialog('entries', e, e.name)}>Archivieren</button>`}
        <button class="small" title="Änderungsverlauf" @click=${() => historyDialog('entries', e.id)}>Verlauf</button></td></tr>`;
  renderLit(html`<div class="toolbar"><h2 style="margin:0">Wiederkehrende Buchungen</h2><span class="spacer"></span>
    <label><input type="checkbox" .checked=${S.showArchived} @change=${ev => { S.showArchived = ev.target.checked; rerender(); }}> Archivierte zeigen</label>
    ${dimensionSelect('buchungen', rerender)}
    <button class="primary" @click=${() => recurringDialog()}>+ Neue Buchung</button></div>
    <div class="panel table-wrap page-scroll"><table><thead><tr><th>Bezeichnung</th><th>Typ</th><th>Konto</th><th class="num">Grundbetrag</th><th>Rhythmus</th><th>Zeitraum</th><th>Anpassungen</th><th></th></tr></thead><tbody>
    ${!sorted.length ? html`<tr><td colspan="8" class="muted">Noch keine wiederkehrenden Buchungen.</td></tr>`
      : groupedRows({ view: 'buchungen', items: sorted, rowTpl, colspan: 8, sumTpl: groupSumTpl, rerender })}
    </tbody></table></div>`, main);
}
