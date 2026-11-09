// ------------------------------------------------------------ Buchungen
import { $, esc, eur, signed, fDate, toInput, today, toast, api, RHYTHM, rhythm, accName, activeAccounts, S, formDialog, refresh, load, archiveDialog, restoreRow } from './core.js';
import { historyDialog } from './audit.js';

function entryType(e) { return e.to_account_id ? 'transfer' : e.amount < 0 ? 'expense' : 'income'; }

export async function entryDialog(e = null) {
  const accs = activeAccounts();
  if (!accs.length) { toast('Bitte zuerst ein Konto anlegen', true); return; }
  const accOpts = accs.map(a => ({ value: a.id, label: a.name }));
  const values = e ? { ...e, type: entryType(e), amount: toInput(Math.abs(e.amount)), to_account_id: e.to_account_id ?? '', end_date: e.end_date ?? '' }
    : { type: 'expense', kind: 'recurring', interval_months: 1, start_date: today(), account_id: accs[0].id };
  const ok = await formDialog({
    title: e ? `Buchung „${e.name}“ bearbeiten` : 'Neue Buchung', values,
    intro: e ? `<p class="small muted">Änderungen am Grundbetrag wirken rückwirkend auf alle Termine. Für eine Änderung <i>ab einem Datum</i> (z. B. Gehaltserhöhung) nutze stattdessen „Anpassungen“.</p>` : '',
    fields: [
      { name: 'name', label: 'Bezeichnung', required: true },
      { name: 'type', label: 'Typ', type: 'select', options: [{ value: 'income', label: 'Einnahme' }, { value: 'expense', label: 'Ausgabe' }, { value: 'transfer', label: 'Umbuchung zwischen Konten' }] },
      { name: 'account_id', label: 'Konto', type: 'select', options: accOpts },
      { name: 'to_account_id', label: 'Zielkonto', type: 'select', options: accOpts, showIf: v => v.type === 'transfer' },
      { name: 'amount', label: 'Betrag (positiv eingeben)', type: 'money', required: true },
      { name: 'kind', label: 'Häufigkeit', type: 'select', options: [{ value: 'recurring', label: 'Wiederkehrend' }, { value: 'once', label: 'Einmalig' }] },
      { name: 'interval_months', label: 'Rhythmus', type: 'select', options: Object.entries(RHYTHM).map(([k, l]) => ({ value: k, label: l })), showIf: v => v.kind === 'recurring' },
      { name: 'start_date', label: 'Datum der (ersten) Fälligkeit', type: 'date', required: true, hint: 'Der Tag wird für alle Folgetermine übernommen (bei kürzeren Monaten der Monatsletzte).' },
      { name: 'end_date', label: 'Letzte Fälligkeit (optional)', type: 'date', showIf: v => v.kind === 'recurring', hint: 'Leer lassen = unbegrenzt' },
      { name: 'category', label: 'Kategorie (optional)', type: 'text' },
      { name: 'note', label: 'Notiz (optional)', type: 'textarea' },
    ],
    onSubmit: v => {
      const abs = Math.abs(v.amount);
      const body = {
        name: v.name, account_id: +v.account_id, to_account_id: v.type === 'transfer' ? +v.to_account_id : null,
        amount: v.type === 'expense' ? -abs : abs, kind: v.kind, interval_months: +(v.interval_months || 1),
        start_date: v.start_date, end_date: v.end_date || null, category: v.category || '', note: v.note || '',
      };
      return e ? api('PUT', `/api/entries/${e.id}`, { ...body, expected_updated_at: e.updated_at }) : api('POST', '/api/entries', body);
    },
  });
  if (ok) { toast('Gespeichert'); refresh(); }
}

export async function renderEntries(main) {
  const entries = S.data.entries.filter(e => S.showArchived || !e.archived);
  const adjCount = id => S.data.adjustments.filter(a => a.entry_id === id && !a.archived).length;
  const typeLabel = { income: 'Einnahme', expense: 'Ausgabe', transfer: 'Umbuchung' };
  const sorted = entries.slice().sort((a, b) => a.archived - b.archived || b.kind.localeCompare(a.kind) || a.name.localeCompare(b.name, 'de'));
  main.innerHTML = `<div class="toolbar"><h2 style="margin:0">Buchungen</h2><span class="spacer"></span>
    <label><input type="checkbox" id="arch" ${S.showArchived ? 'checked' : ''}> Archivierte zeigen</label>
    <button class="primary" id="new">+ Neue Buchung</button></div>
    <div class="panel table-wrap"><table><thead><tr><th>Bezeichnung</th><th>Typ</th><th>Konto</th><th class="num">Grundbetrag</th><th>Rhythmus</th><th>Zeitraum</th><th>Anpassungen</th><th></th></tr></thead><tbody>
    ${sorted.map(e => `<tr class="${e.archived ? 'archived' : ''}">
      <td><b>${esc(e.name)}</b>${e.category ? `<span class="tag">${esc(e.category)}</span>` : ''}${e.note ? `<div class="small muted">${esc(e.note)}</div>` : ''}</td>
      <td>${typeLabel[entryType(e)]}</td>
      <td>${esc(accName(e.account_id))}${e.to_account_id ? ` → ${esc(accName(e.to_account_id))}` : ''}</td>
      <td class="num">${entryType(e) === 'transfer' ? eur(e.amount) : signed(e.amount)}</td>
      <td>${e.kind === 'once' ? 'einmalig' : rhythm(e.interval_months)}</td>
      <td>${e.kind === 'once' ? fDate(e.start_date) : `ab ${fDate(e.start_date)}${e.end_date ? ` bis ${fDate(e.end_date)}` : ''}`}</td>
      <td><button class="small" data-adj="${e.id}">${adjCount(e.id)} Anpassung${adjCount(e.id) === 1 ? '' : 'en'}</button></td>
      <td style="white-space:nowrap">${e.archived ? `<button class="small" data-restore="${e.id}">Wiederherstellen</button>` : `<button class="small" data-edit="${e.id}">Bearbeiten</button> <button class="small" data-arch="${e.id}">Archivieren</button>`}
        <button class="small" data-hist="${e.id}" title="Änderungsverlauf">Verlauf</button></td></tr>`).join('') || `<tr><td colspan="8" class="muted">Noch keine Buchungen.</td></tr>`}
    </tbody></table></div>`;
  const find = id => S.data.entries.find(e => e.id === +id);
  $('#arch').onchange = ev => { S.showArchived = ev.target.checked; renderEntries(main); };
  $('#new').onclick = () => entryDialog();
  main.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => entryDialog(find(b.dataset.edit)));
  main.querySelectorAll('[data-arch]').forEach(b => b.onclick = () => archiveDialog('entries', find(b.dataset.arch), find(b.dataset.arch).name));
  main.querySelectorAll('[data-restore]').forEach(b => b.onclick = () => restoreRow('entries', find(b.dataset.restore)));
  main.querySelectorAll('[data-adj]').forEach(b => b.onclick = () => adjustmentsDialog(find(b.dataset.adj)));
  main.querySelectorAll('[data-hist]').forEach(b => b.onclick = () => historyDialog('entries', +b.dataset.hist));
}

function adjLabel(a) {
  if (a.mode === 'set') return `neuer Betrag ${eur(a.amount)}`;
  return `${a.percent > 0 ? '+' : ''}${String(a.percent).replace('.', ',')} %${a.repeat_yearly ? ' jährlich wiederkehrend' : ''}`;
}

async function adjustmentsDialog(entry) {
  const dlg = document.createElement('dialog');
  const draw = () => {
    const list = S.data.adjustments.filter(a => a.entry_id === entry.id).sort((a, b) => a.effective_date.localeCompare(b.effective_date));
    dlg.innerHTML = `<div class="body"><h3>Anpassungen: ${esc(entry.name)}</h3>
      <p class="small muted">Grundbetrag ${eur(entry.amount)}. Anpassungen gelten ab ihrem Datum und werden in zeitlicher Reihenfolge angewendet. Ein neuer fester Betrag ersetzt alle früheren Anpassungen.</p>
      <table><thead><tr><th>Gültig ab</th><th>Änderung</th><th>Notiz</th><th></th></tr></thead><tbody>
      ${list.map(a => `<tr class="${a.archived ? 'archived' : ''}"><td>${fDate(a.effective_date)}</td><td>${esc(adjLabel(a))}</td><td class="small">${esc(a.note)}</td>
        <td style="white-space:nowrap">${a.archived ? `<button class="small" data-r="${a.id}">Wiederherstellen</button>` : `<button class="small" data-e="${a.id}">Bearbeiten</button> <button class="small" data-a="${a.id}">Archivieren</button>`}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">Keine Anpassungen.</td></tr>'}
      </tbody></table><div class="actions"><button data-close>Schließen</button><button class="primary" data-new>+ Anpassung</button></div></div>`;
    $('[data-close]', dlg).onclick = () => dlg.close();
    $('[data-new]', dlg).onclick = () => edit(null);
    const find = id => S.data.adjustments.find(a => a.id === +id);
    dlg.querySelectorAll('[data-e]').forEach(b => b.onclick = () => edit(find(b.dataset.e)));
    dlg.querySelectorAll('[data-a]').forEach(b => b.onclick = async () => { await api('POST', `/api/adjustments/${b.dataset.a}/archive`, {}); await reload(); });
    dlg.querySelectorAll('[data-r]').forEach(b => b.onclick = async () => { await api('POST', `/api/adjustments/${b.dataset.r}/restore`, {}); await reload(); });
  };
  const reload = async () => { await load(); draw(); toast('Gespeichert'); };
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
