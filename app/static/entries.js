// ------------------------------------------------------------ Buchungen
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, eur, signed, approx, fDate, toInput, today, toast, api, RHYTHM, rhythm, accName, activeAccounts, S, formDialog, refresh, load, archiveDialog, restoreRow, setArchived } from './core.js';
import { historyDialog } from './audit.js';
import { entryType, categoryNames, DIMENSIONS, groupItems, monthlyAmount, getDimension, isOpen, toggleGroup, dimensionSelect } from './grouping.js';

/** Known categories for the entry form, most used first (see categoryNames). */
function categorySuggestions() {
  return [...categoryNames().values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'de')).map(c => c.name);
}

export async function entryDialog(e = null) {
  const accs = activeAccounts();
  if (!accs.length) { toast('Bitte zuerst ein Konto anlegen', true); return; }
  const accOpts = accs.map(a => ({ value: a.id, label: a.name }));
  const values = e ? { ...e, type: entryType(e), amount: toInput(Math.abs(e.amount)), to_account_id: e.to_account_id ?? '', end_date: e.end_date ?? '' }
    : { type: 'expense', kind: 'recurring', interval_months: 1, start_date: today(), account_id: accs[0].id };
  values.estimated = e?.estimated ? '1' : '0';
  const ok = await formDialog({
    title: e ? `Buchung „${e.name}“ bearbeiten` : 'Neue Buchung', values,
    intro: e ? html`<p class="small muted">Änderungen am Grundbetrag wirken rückwirkend auf alle Termine. Für eine Änderung <i>ab einem Datum</i> (z. B. Gehaltserhöhung) nutze stattdessen „Anpassungen“.</p>` : '',
    fields: [
      { name: 'name', label: 'Bezeichnung', required: true },
      { name: 'type', label: 'Typ', type: 'select', options: [{ value: 'income', label: 'Einnahme' }, { value: 'expense', label: 'Ausgabe' }, { value: 'transfer', label: 'Umbuchung zwischen Konten' }] },
      { name: 'account_id', label: 'Konto', type: 'select', options: accOpts },
      { name: 'to_account_id', label: 'Zielkonto', type: 'select', options: accOpts, showIf: v => v.type === 'transfer' },
      { name: 'amount', label: 'Betrag (positiv eingeben)', type: 'money', required: true },
      { name: 'estimated', label: 'Art', type: 'select', options: [{ value: '0', label: 'Fest (z. B. Miete, Abo)' }, { value: '1', label: 'Geschätzt (z. B. Lebensmittel)' }],
        hint: 'Geschätzte Beträge werden mit „≈“ angezeigt. Die Abweichung zur Wirklichkeit zeigt der nächste Ist-Stand.' },
      { name: 'kind', label: 'Häufigkeit', type: 'select', options: [{ value: 'recurring', label: 'Wiederkehrend' }, { value: 'once', label: 'Einmalig' }] },
      { name: 'interval_months', label: 'Rhythmus', type: 'select', options: Object.entries(RHYTHM).map(([k, l]) => ({ value: k, label: l })), showIf: v => v.kind === 'recurring' },
      { name: 'start_date', label: 'Datum der (ersten) Fälligkeit', type: 'date', required: true, hint: 'Der Tag wird für alle Folgetermine übernommen (bei kürzeren Monaten der Monatsletzte).' },
      { name: 'end_date', label: 'Letzte Fälligkeit (optional)', type: 'date', showIf: v => v.kind === 'recurring', hint: 'Leer lassen = unbegrenzt' },
      { name: 'category', label: 'Kategorie (optional)', type: 'text', suggestions: categorySuggestions() },
      { name: 'note', label: 'Notiz (optional)', type: 'textarea' },
    ],
    onSubmit: v => {
      const abs = Math.abs(v.amount);
      const body = {
        name: v.name, account_id: +v.account_id, to_account_id: v.type === 'transfer' ? +v.to_account_id : null,
        amount: v.type === 'expense' ? -abs : abs, kind: v.kind, interval_months: +(v.interval_months || 1),
        start_date: v.start_date, end_date: v.end_date || null, category: v.category || '', note: v.note || '',
        estimated: v.estimated === '1',
      };
      return e ? api('PUT', `/api/entries/${e.id}`, { ...body, expected_updated_at: e.updated_at }) : api('POST', '/api/entries', body);
    },
  });
  if (ok) { toast('Gespeichert'); refresh(); }
}

/** Monthly equivalent of a group's active recurring bookings; transfers shown separately, one-time bookings left out.
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
  const entries = S.data.entries.filter(e => S.showArchived || !e.archived);
  const adjCount = id => S.data.adjustments.filter(a => a.entry_id === id && !a.archived).length;
  const typeLabel = { income: 'Einnahme', expense: 'Ausgabe', transfer: 'Umbuchung' };
  const dim = getDimension('buchungen');
  const sorted = entries.slice().sort((a, b) => a.archived - b.archived || b.kind.localeCompare(a.kind) || a.name.localeCompare(b.name, 'de'));
  const rowTpl = e => html`<tr class="${e.archived ? 'archived' : ''}">
      <td><b>${e.name}</b>${e.category ? html`<span class="tag">${e.category}</span>` : ''}${e.note ? html`<div class="small muted">${e.note}</div>` : ''}</td>
      <td>${typeLabel[entryType(e)]}</td>
      <td>${accName(e.account_id)}${e.to_account_id ? html` → ${accName(e.to_account_id)}` : ''}</td>
      <td class="num">${approx(e.estimated)}${entryType(e) === 'transfer' ? eur(e.amount) : signed(e.amount)}</td>
      <td>${e.kind === 'once' ? 'einmalig' : rhythm(e.interval_months)}</td>
      <td>${e.kind === 'once' ? fDate(e.start_date) : `ab ${fDate(e.start_date)}${e.end_date ? ` bis ${fDate(e.end_date)}` : ''}`}</td>
      <td><button class="small" @click=${() => adjustmentsDialog(e)}>${adjCount(e.id)} Anpassung${adjCount(e.id) === 1 ? '' : 'en'}</button></td>
      <td style="white-space:nowrap">${e.archived
        ? html`<button class="small" @click=${() => restoreRow('entries', e)}>Wiederherstellen</button>`
        : html`<button class="small" @click=${() => entryDialog(e)}>Bearbeiten</button> <button class="small" @click=${() => archiveDialog('entries', e, e.name)}>Archivieren</button>`}
        <button class="small" title="Änderungsverlauf" @click=${() => historyDialog('entries', e.id)}>Verlauf</button></td></tr>`;
  renderLit(html`<div class="toolbar"><h2 style="margin:0">Buchungen</h2><span class="spacer"></span>
    <label><input type="checkbox" .checked=${S.showArchived} @change=${ev => { S.showArchived = ev.target.checked; renderEntries(main); }}> Archivierte zeigen</label>
    ${dimensionSelect('buchungen', () => renderEntries(main))}
    <button class="primary" @click=${() => entryDialog()}>+ Neue Buchung</button></div>
    <div class="panel table-wrap"><table><thead><tr><th>Bezeichnung</th><th>Typ</th><th>Konto</th><th class="num">Grundbetrag</th><th>Rhythmus</th><th>Zeitraum</th><th>Anpassungen</th><th></th></tr></thead><tbody>
    ${!sorted.length ? html`<tr><td colspan="8" class="muted">Noch keine Buchungen.</td></tr>`
      : dim === 'none' ? sorted.map(rowTpl)
      : groupItems(sorted, e => DIMENSIONS[dim].key(e)).map(g => {
        const open = isOpen('buchungen', dim, g.key, true);
        const toggle = () => { toggleGroup('buchungen', dim, g.key); renderEntries(main); };
        return html`<tr class="group-head"><td colspan="8"><button class="link" aria-expanded=${open} @click=${toggle}>${open ? '▾' : '▸'} ${g.label}</button>
          <span class="muted">· ${g.items.length} Buchung${g.items.length === 1 ? '' : 'en'}</span>${groupSumTpl(g.items)}</td></tr>
          ${open ? g.items.map(rowTpl) : ''}`;
      })}
    </tbody></table></div>`, main);
}

function adjLabel(a) {
  if (a.mode === 'set') return `neuer Betrag ${eur(a.amount)}`;
  return `${a.percent > 0 ? '+' : ''}${String(a.percent).replace('.', ',')} %${a.repeat_yearly ? ' jährlich wiederkehrend' : ''}`;
}

async function adjustmentsDialog(entry) {
  const dlg = document.createElement('dialog');
  const draw = () => {
    const list = S.data.adjustments.filter(a => a.entry_id === entry.id).sort((a, b) => a.effective_date.localeCompare(b.effective_date));
    const rowTpl = a => html`<tr class="${a.archived ? 'archived' : ''}"><td>${fDate(a.effective_date)}</td><td>${adjLabel(a)}</td><td class="small">${a.note}</td>
        <td style="white-space:nowrap">${a.archived
          ? html`<button class="small" @click=${() => restoreAdj(a)}>Wiederherstellen</button>`
          : html`<button class="small" @click=${() => edit(a)}>Bearbeiten</button> <button class="small" @click=${() => archiveAdj(a)}>Archivieren</button>`}</td></tr>`;
    renderLit(html`<div class="body"><h3>Anpassungen: ${entry.name}</h3>
      <p class="small muted">Grundbetrag ${eur(entry.amount)}. Anpassungen gelten ab ihrem Datum und werden in zeitlicher Reihenfolge angewendet. Ein neuer fester Betrag ersetzt alle früheren Anpassungen.</p>
      <table><thead><tr><th>Gültig ab</th><th>Änderung</th><th>Notiz</th><th></th></tr></thead><tbody>
      ${list.length ? list.map(rowTpl) : html`<tr><td colspan="4" class="muted">Keine Anpassungen.</td></tr>`}
      </tbody></table><div class="actions"><button @click=${() => dlg.close()}>Schließen</button><button class="primary" @click=${() => edit(null)}>+ Anpassung</button></div></div>`, dlg);
  };
  const reload = async () => { await load(); draw(); toast('Gespeichert'); };
  const archiveAdj = async a => { if (await setArchived('adjustments', a, true)) await reload(); else { await load(); draw(); } };
  const restoreAdj = async a => { if (await setArchived('adjustments', a, false)) await reload(); else { await load(); draw(); } };
  const sign = entry.to_account_id ? 1 : Math.sign(entry.amount);
  const edit = async a => {
    const ok = await formDialog({
      title: a ? 'Anpassung bearbeiten' : 'Neue Anpassung',
      values: a ? { ...a, amount: a.amount != null ? toInput(Math.abs(a.amount)) : '', percent: a.percent ?? '' } : { effective_date: today(), mode: 'set' },
      fields: [
        { name: 'effective_date', label: 'Gültig ab', type: 'date', required: true },
        { name: 'mode', label: 'Art der Änderung', type: 'select', options: [{ value: 'set', label: 'Neuer fester Betrag' }, { value: 'percent', label: 'Prozentuale Änderung' }] },
        { name: 'amount', label: 'Neuer Betrag (positiv eingeben)', type: 'money', required: true, showIf: v => v.mode === 'set' },
        { name: 'percent', label: 'Änderung in %', type: 'number', step: 'any', required: true, showIf: v => v.mode === 'percent', hint: 'z. B. 3 für +3 %, -10 für −10 %' },
        { name: 'repeat_yearly', label: 'Jedes Jahr erneut anwenden (z. B. Inflation, jährliche Erhöhung)', type: 'checkbox', showIf: v => v.mode === 'percent' },
        { name: 'note', label: 'Notiz (optional)', type: 'text', hint: 'z. B. „Gehaltserhöhung lt. Vertrag“' },
      ],
      onSubmit: v => {
        const body = { entry_id: entry.id, effective_date: v.effective_date, mode: v.mode, amount: v.mode === 'set' ? sign * Math.abs(v.amount) : null, percent: v.mode === 'percent' ? v.percent : null, repeat_yearly: !!v.repeat_yearly, note: v.note || '' };
        return a ? api('PUT', `/api/adjustments/${a.id}`, { ...body, expected_updated_at: a.updated_at }) : api('POST', '/api/adjustments', body);
      },
    });
    if (ok) await reload();
  };
  dlg.addEventListener('close', () => { dlg.remove(); refresh(); });
  draw(); document.body.append(dlg); dlg.showModal();
}
