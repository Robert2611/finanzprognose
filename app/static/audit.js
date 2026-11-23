// ------------------------------------------------------------ Verlauf
import { html, render as renderLit } from './vendor/lit-html.js';
import { eur, fDate, fTs, accName, rhythm, KINDS, FIELD, ENTITY, ACTION, S, api, formDialog, toast, load, refresh } from './core.js';

function fmtVal(k, v) {
  if (v == null || v === '') return '—';
  if (k === 'amount' || k === 'balance') return eur(v);
  if (k === 'account_id' || k === 'to_account_id') return accName(v);
  if (k === 'entry_id') return S.data.entries.find(e => e.id === v)?.name ?? `#${v}`;
  if (k.endsWith('date')) return fDate(v);
  if (k === 'estimated') return v ? 'geschätzt' : 'fest';
  if (k === 'repeat_yearly' || k === 'archived') return v ? 'ja' : 'nein';
  if (k === 'interval_months') return rhythm(v);
  if (k === 'mode') return v === 'set' ? 'fester Betrag' : 'Prozent';
  if (k === 'kind') return { recurring: 'wiederkehrend', once: 'einmalig', ...KINDS }[v] ?? v;
  return String(v);
}
function objLabel(a) {
  const o = a.after || a.before || {};
  if (a.entity === 'checkpoints') return `${accName(o.account_id)}, ${fDate(o.date)}`;
  if (a.entity === 'adjustments') return `${fmtVal('entry_id', o.entry_id)}, ab ${fDate(o.effective_date)}`;
  return o.name ?? `#${a.entity_id}`;
}
function diffTpl(a) {
  const skip = new Set(['id', 'created_at', 'updated_at']);
  if (!a.before) {
    const entries = Object.entries(a.after).filter(([k, v]) => !skip.has(k) && k !== 'archived' && v !== null && v !== '');
    return html`<div class="diff">${entries.map(([k, v], i) => html`${i ? ' · ' : ''}<b>${FIELD[k] || k}:</b> ${fmtVal(k, v)}`)}</div>`;
  }
  const keys = Object.keys(a.after).filter(k => !skip.has(k) && JSON.stringify(a.before[k]) !== JSON.stringify(a.after[k]));
  return html`<div class="diff">${keys.map((k, i) => html`${i ? html`<br>` : ''}<b>${FIELD[k] || k}:</b> <del>${fmtVal(k, a.before[k])}</del> → <ins>${fmtVal(k, a.after[k])}</ins>`)}</div>`;
}
async function doRevert(a, onDone) {
  // Undoing an undo restores the change it undid (a redo, B-019), so it is worded that way.
  const redo = a.action === 'revert';
  const ok = await formDialog({
    title: redo ? `Änderung #${a.reverts_id} wiederherstellen` : `Änderung #${a.id} rückgängig machen`,
    submitLabel: redo ? 'Wiederherstellen' : 'Rückgängig machen',
    intro: redo
      ? html`<p class="muted">Die rückgängig gemachte Änderung #${a.reverts_id} wird wiederhergestellt. Auch das wird als neue Änderung protokolliert – es geht also nichts verloren.</p>`
      : html`<p class="muted">Der Datensatz wird auf den Zustand vor dieser Änderung zurückgesetzt. Das Zurücksetzen wird selbst als neue Änderung protokolliert – es geht also nichts verloren.</p>`,
    fields: [],
    onSubmit: () => api('POST', `/api/audit/${a.id}/revert`),
  });
  if (ok) { toast(redo ? 'Wiederhergestellt' : 'Rückgängig gemacht'); await load(); onDone(); }
}
function auditRowTpl(a, onDone) {
  return html`<tr><td class="small" style="white-space:nowrap">${fTs(a.ts)}<div class="muted">#${a.id}</div></td><td>${ACTION[a.action] || a.action}</td>
    <td>${ENTITY[a.entity] || a.entity}<div class="small"><b>${objLabel(a)}</b></div></td>
    <td>${diffTpl(a)}${a.comment ? html`<div class="small muted">„${a.comment}“</div>` : ''}${a.reverts_id ? html`<div class="small muted">Rückgängig gemacht: ${ENTITY.audit_log} #${a.reverts_id}</div>` : ''}</td>
    <td><button class="small" title="Diese Änderung rückgängig machen" @click=${() => doRevert(a, onDone)}>Rückgängig</button></td></tr>`;
}

export async function renderAudit(main) {
  let rows = await api('GET', '/api/audit?limit=200');
  if (S.view !== 'verlauf') return; // navigated away while loading
  let hasMore = rows.length === 200;
  const draw = () => renderLit(html`<div class="toolbar"><h2 style="margin:0">Änderungsverlauf</h2><span class="muted small">Jede Änderung wird unveränderlich protokolliert – mit Vorher- und Nachher-Zustand.</span></div>
    <div class="panel table-wrap page-scroll"><table><thead><tr><th>Zeitpunkt</th><th>Aktion</th><th>Objekt</th><th>Änderung</th><th></th></tr></thead>
    <tbody>${rows.map(a => auditRowTpl(a, () => renderAudit(main)))}</tbody></table>
    ${hasMore ? html`<div class="toolbar" style="margin-top:10px"><button @click=${loadMore}>Ältere laden</button></div>` : ''}
    </div>`, main);
  async function loadMore() {
    const last = rows.at(-1)?.id;
    const r = await api('GET', `/api/audit?limit=200&before_id=${last}`);
    rows = rows.concat(r);
    hasMore = r.length === 200;
    draw();
  }
  draw();
}

export async function historyDialog(entity, id) {
  const rows = await api('GET', `/api/audit?entity=${entity}&entity_id=${id}&limit=500`);
  const dlg = document.createElement('dialog'); dlg.style.width = 'min(900px,96vw)';
  renderLit(html`<div class="body"><h3>Verlauf</h3><div class="table-wrap"><table><tbody>${rows.map(a => auditRowTpl(a, () => dlg.close()))}</tbody></table></div>
    <div class="actions"><button @click=${() => dlg.close()}>Schließen</button></div></div>`, dlg);
  dlg.addEventListener('close', () => { dlg.remove(); refresh(); });
  document.body.append(dlg); dlg.showModal();
}
