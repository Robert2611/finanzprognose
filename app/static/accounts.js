// ------------------------------------------------------------ Konten
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, eur, eurCls, fDate, today, toInput, toast, api, KINDS, activeAccounts, S, formDialog, refresh, archiveDialog, restoreRow } from './core.js';

export async function accountDialog(acc = null) {
  const kindOpts = Object.entries(KINDS).map(([value, label]) => ({ value, label }));
  const fields = [{ name: 'name', label: 'Name', required: true }, { name: 'kind', label: 'Kontoart', type: 'select', options: kindOpts }];
  if (!acc) fields.push(
    { name: 'start_balance', label: 'Aktueller Kontostand', type: 'money', required: true, hint: 'Negativ mit Minus, z. B. -250,00' },
    { name: 'start_date', label: 'Stand vom (abends)', type: 'date', required: true });
  fields.push({ name: 'note', label: 'Notiz (optional)', type: 'textarea' });
  const ok = await formDialog({
    title: acc ? `Konto „${acc.name}“ bearbeiten` : 'Neues Konto', fields,
    values: acc ? acc : { kind: 'checking', start_date: today() },
    onSubmit: v => acc ? api('PUT', `/api/accounts/${acc.id}`, { name: v.name, kind: v.kind, note: v.note || '', expected_updated_at: acc.updated_at })
      : api('POST', '/api/accounts', { name: v.name, kind: v.kind, note: v.note || '', start_balance: v.start_balance, start_date: v.start_date }),
  });
  if (ok) { toast('Gespeichert'); refresh(); }
}

export async function checkpointDialog(accountId = null, cp = null) {
  const accs = activeAccounts();
  if (!accs.length) { toast('Bitte zuerst ein Konto anlegen', true); return; }
  const ok = await formDialog({
    title: cp ? 'Ist-Stand bearbeiten' : 'Ist-Stand eintragen',
    intro: html`<p class="small muted">Trage den tatsächlichen Kontostand ein (z. B. aus dem Online-Banking). Die Prognose rechnet ab diesem Tag mit dem echten Wert weiter und zeigt die Abweichung an. Buchungen am selben Tag gelten als bereits enthalten.</p>`,
    values: cp ? { ...cp, balance: toInput(cp.balance) } : { account_id: accountId ?? accs[0].id, date: today() },
    fields: [
      { name: 'account_id', label: 'Konto', type: 'select', options: accs.map(a => ({ value: a.id, label: a.name })) },
      { name: 'date', label: 'Datum (Stand am Abend)', type: 'date', required: true },
      { name: 'balance', label: 'Kontostand', type: 'money', required: true },
      { name: 'note', label: 'Notiz (optional)', type: 'text' },
    ],
    onSubmit: v => {
      const body = { account_id: +v.account_id, date: v.date, balance: v.balance, note: v.note || '' };
      return cp ? api('PUT', `/api/checkpoints/${cp.id}`, { ...body, expected_updated_at: cp.updated_at }) : api('POST', '/api/checkpoints', body);
    },
  });
  if (ok) { toast('Gespeichert'); refresh(); }
}

export async function renderAccounts(main) {
  const accs = S.data.accounts.filter(a => S.showArchived || !a.archived);
  const cpRowTpl = (c, startId) => html`<tr class="${c.archived ? 'archived' : ''}"><td>${fDate(c.date)}${c.id === startId ? html` <span class="tag">Startstand</span>` : ''}</td><td class="num ${eurCls(c.balance)}">${eur(c.balance)}</td><td class="small muted">${c.note}</td>
      <td style="white-space:nowrap;text-align:right">${c.archived
        ? html`<button class="small" @click=${() => restoreRow('checkpoints', c)}>Wiederherstellen</button>`
        : html`<button class="small" @click=${() => checkpointDialog(c.account_id, c)}>Bearbeiten</button> <button class="small" @click=${() => archiveDialog('checkpoints', c, `Ist-Stand vom ${fDate(c.date)}`)}>Archivieren</button>`}</td></tr>`;
  const cardTpl = a => {
    const cps = S.data.checkpoints.filter(c => c.account_id === a.id && (S.showArchived || !c.archived)).sort((x, y) => y.date.localeCompare(x.date));
    const last = cps.find(c => !c.archived);
    const active = cps.filter(c => !c.archived);
    const startId = active.length ? active.reduce((min, c) => c.date < min.date ? c : min).id : null;
    return html`<div class="panel ${a.archived ? 'archived' : ''}" style="${a.archived ? 'opacity:.55' : ''}">
        <div class="toolbar" style="margin-bottom:6px"><h3 style="margin:0">${a.name}</h3><span class="tag">${KINDS[a.kind] || a.kind}</span><span class="spacer"></span>
        ${a.archived
          ? html`<button class="small" @click=${() => restoreRow('accounts', a)}>Wiederherstellen</button>`
          : html`<button class="small" @click=${() => accountDialog(a)}>Bearbeiten</button><button class="small" @click=${() => archiveDialog('accounts', a, a.name)}>Archivieren</button>`}</div>
        ${a.note ? html`<p class="small muted">${a.note}</p>` : ''}
        <div class="kv"><span class="muted">Letzter Ist-Stand</span><span>${last ? html`<b>${eur(last.balance)}</b> am ${fDate(last.date)}` : html`<span class="neg">keiner – Konto wird nicht berechnet</span>`}</span></div>
        <div class="toolbar" style="margin:12px 0 4px"><b class="small">Ist-Stände</b><span class="spacer"></span>${a.archived ? '' : html`<button class="small primary" @click=${() => checkpointDialog(a.id)}>+ Ist-Stand</button>`}</div>
        <table><tbody>${cps.map(c => cpRowTpl(c, startId))}</tbody></table>
      </div>`;
  };
  renderLit(html`<div class="toolbar"><h2 style="margin:0">Konten &amp; Ist-Stände</h2><span class="spacer"></span>
    <label><input type="checkbox" .checked=${S.showArchived} @change=${ev => { S.showArchived = ev.target.checked; renderAccounts(main); }}> Archivierte zeigen</label>
    <button class="primary" @click=${() => accountDialog()}>+ Neues Konto</button></div>
    <div class="cards">${accs.length ? accs.map(cardTpl) : html`<div class="panel muted">Noch keine Konten.</div>`}</div>`, main);
}
