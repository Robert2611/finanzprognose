// ------------------------------------------------------------ Anpassungen (per booking)
import { html, render as renderLit } from './vendor/lit-html.js';
import { eur, fDate, toInput, today, toast, api, S, formDialog, refresh, load, setArchived } from './core.js';

/** German label of an adjustment's change, e.g. "neuer Betrag 3.200,00 €" or "+3 % jährlich wiederkehrend". */
export function adjLabel(a) {
  if (a.mode === 'set') return `neuer Betrag ${eur(a.amount)}`;
  return `${a.percent > 0 ? '+' : ''}${String(a.percent).replace('.', ',')} %${a.repeat_yearly ? ' jährlich wiederkehrend' : ''}`;
}

/** The per-booking adjustments sub-dialog (list + add/edit/archive/restore). */
export async function adjustmentsDialog(entry) {
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
