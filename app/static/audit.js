// ------------------------------------------------------------ Verlauf
import { $, esc, eur, fDate, fTs, accName, rhythm, KINDS, FIELD, ENTITY, ACTION, S, api, formDialog, toast, load, refresh } from './core.js';

function fmtVal(k, v) {
  if (v == null || v === '') return '—';
  if (k === 'amount' || k === 'balance') return eur(v);
  if (k === 'account_id' || k === 'to_account_id') return accName(v);
  if (k === 'entry_id') return S.data.entries.find(e => e.id === v)?.name ?? `#${v}`;
  if (k.endsWith('date')) return fDate(v);
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
function diffHtml(a) {
  const skip = new Set(['id', 'created_at', 'updated_at']);
  if (!a.before) return `<div class="diff">${Object.entries(a.after).filter(([k, v]) => !skip.has(k) && k !== 'archived' && v !== null && v !== '').map(([k, v]) => `<b>${FIELD[k] || k}:</b> ${esc(fmtVal(k, v))}`).join(' · ')}</div>`;
  return `<div class="diff">${Object.keys(a.after).filter(k => !skip.has(k) && JSON.stringify(a.before[k]) !== JSON.stringify(a.after[k]))
    .map(k => `<b>${FIELD[k] || k}:</b> <del>${esc(fmtVal(k, a.before[k]))}</del> → <ins>${esc(fmtVal(k, a.after[k]))}</ins>`).join('<br>')}</div>`;
}
function auditRows(rows) {
  return rows.map(a => `<tr><td class="small" style="white-space:nowrap">${fTs(a.ts)}<div class="muted">#${a.id}</div></td><td>${ACTION[a.action] || a.action}</td>
    <td>${ENTITY[a.entity] || a.entity}<div class="small"><b>${esc(objLabel(a))}</b></div></td><td>${diffHtml(a)}${a.comment ? `<div class="small muted">„${esc(a.comment)}“</div>` : ''}${a.reverts_id ? `<div class="small muted">Rückgängig gemacht: ${ENTITY.audit_log} #${a.reverts_id}</div>` : ''}</td>
    <td><button class="small" data-revert="${a.id}" title="Diese Änderung rückgängig machen">Rückgängig</button></td></tr>`).join('');
}
async function bindRevert(root, after) {
  root.querySelectorAll('[data-revert]').forEach(b => b.onclick = async () => {
    const ok = await formDialog({
      title: `Änderung #${b.dataset.revert} rückgängig machen`, submitLabel: 'Rückgängig machen',
      intro: '<p class="muted">Der Datensatz wird auf den Zustand vor dieser Änderung zurückgesetzt. Das Zurücksetzen wird selbst als neue Änderung protokolliert – es geht also nichts verloren.</p>', fields: [],
      onSubmit: () => api('POST', `/api/audit/${b.dataset.revert}/revert`),
    });
    if (ok) { toast('Rückgängig gemacht'); await load(); after(); }
  });
}
export async function renderAudit(main) {
  const rows = await api('GET', '/api/audit?limit=200');
  main.innerHTML = `<div class="toolbar"><h2 style="margin:0">Änderungsverlauf</h2><span class="muted small">Jede Änderung wird unveränderlich protokolliert – mit Vorher- und Nachher-Zustand.</span></div>
    <div class="panel table-wrap" style="max-height:none"><table><thead><tr><th>Zeitpunkt</th><th>Aktion</th><th>Objekt</th><th>Änderung</th><th></th></tr></thead><tbody id="arows">${auditRows(rows)}</tbody></table>
    ${rows.length === 200 ? '<div class="toolbar" style="margin-top:10px"><button id="more">Ältere laden</button></div>' : ''}</div>`;
  let last = rows.at(-1)?.id;
  bindRevert(main, () => renderAudit(main));
  const more = $('#more'); if (more) more.onclick = async () => {
    const r = await api('GET', `/api/audit?limit=200&before_id=${last}`); last = r.at(-1)?.id ?? last;
    $('#arows').insertAdjacentHTML('beforeend', auditRows(r)); bindRevert(main, () => renderAudit(main)); if (r.length < 200) more.remove();
  };
}
export async function historyDialog(entity, id) {
  const rows = await api('GET', `/api/audit?entity=${entity}&entity_id=${id}&limit=500`);
  const dlg = document.createElement('dialog'); dlg.style.width = 'min(900px,96vw)';
  dlg.innerHTML = `<div class="body"><h3>Verlauf</h3><div class="table-wrap"><table><tbody>${auditRows(rows)}</tbody></table></div><div class="actions"><button data-close>Schließen</button></div></div>`;
  $('[data-close]', dlg).onclick = () => dlg.close();
  dlg.addEventListener('close', () => { dlg.remove(); refresh(); });
  bindRevert(dlg, () => dlg.close());
  document.body.append(dlg); dlg.showModal();
}
