// ------------------------------------------------------------ Sicherung
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, eur, fTs, api, toast, S, backupErrMsg, backupReason, verifyProblemMsg } from './core.js';

export async function refreshBackupPill() {
  const pill = $('#backupPill');
  try {
    const st = await api('GET', '/api/backup/status');
    if (st.last_result === 'error') { pill.className = 'pill err'; pill.textContent = 'Sicherung fehlgeschlagen!'; }
    else if (!st.last_success) { pill.className = 'pill warn'; pill.textContent = 'Noch keine Sicherung'; }
    else { pill.className = 'pill ok'; pill.textContent = `Gesichert ${new Date(st.last_success).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}${st.pending_changes ? ' · neue Änderungen' : ''}`; }
    return st;
  } catch { pill.className = 'pill err'; pill.textContent = 'Server nicht erreichbar'; }
}
export async function renderBackup(main) {
  const st = await api('GET', '/api/backup/status');
  if (S.view !== 'sicherung') return; // navigated away while loading
  const res = { ok: html`<span class="pos">erfolgreich</span>`, unchanged: 'keine Änderungen – nichts zu sichern', error: html`<span class="neg">FEHLER</span>` }[st.last_result] ?? '—';
  const run = async () => {
    try {
      const r = await api('POST', '/api/backup/run');
      if (r.last_result === 'error') toast('Sicherung fehlgeschlagen: ' + backupErrMsg(r.last_error), true);
      else toast(r.last_result === 'unchanged' ? 'Keine Änderungen seit der letzten Sicherung' : 'Sicherung erstellt');
    } catch (ex) { toast('Sicherung fehlgeschlagen: ' + ex.message, true); }
    renderBackup(main); refreshBackupPill();
  };
  renderLit(html`<h2>Sicherung</h2>${st.last_result === 'error' ? html`<div class="banner err"><b>Letzte Sicherung fehlgeschlagen:</b> ${backupErrMsg(st.last_error)}</div>` : ''}
    <div class="cards"><div class="panel"><div class="kv">
      <span class="muted">Ziel</span><code>${st.backup_dir}</code>
      <span class="muted">Zeitplan</span><span>täglich um ${st.backup_time} Uhr, nur bei Änderungen</span>
      <span class="muted">Letzte erfolgreiche</span><span>${st.last_success ? fTs(st.last_success) : '—'}</span>
      <span class="muted">Letzte Datei</span><span class="small">${st.last_file || '—'}</span>
      <span class="muted">Letzter Versuch</span><span>${st.last_attempt ? fTs(st.last_attempt) : '—'}${st.last_reason ? ` (${backupReason(st.last_reason)})` : ''} · ${res}</span>
      <span class="muted">Datenstand</span><span>Version ${st.current_version}${st.pending_changes ? html` – <b>ungesicherte Änderungen</b>` : ' – gesichert'}</span>
    </div><div class="actions" style="justify-content:flex-start"><button class="primary" @click=${run}>Jetzt sichern</button><a class="btn" href="/api/export">Export als JSON herunterladen</a></div></div>
    <div class="panel"><h3>Vorhandene Sicherungen (neueste 30)</h3><table><tbody>${(st.files || []).length
      ? st.files.map(f => html`<tr><td class="small">${f.name}</td><td class="num small">${(f.size / 1024).toFixed(0)} KB</td><td style="text-align:right"><button class="small" @click=${() => verifyDialog(f.name)}>Prüfen</button></td></tr>`)
      : html`<tr><td class="muted">Keine Sicherungen gefunden.</td></tr>`}</tbody></table>
    <p class="small muted">Alte Stände werden nie gelöscht. Zu jeder SQLite-Datei gibt es eine gleichnamige, lesbare JSON-Datei.</p></div></div>`, main);
}

const COUNT_LABELS = { accounts: 'Konten', entries: 'Buchungen', adjustments: 'Anpassungen', checkpoints: 'Ist-Stände', audit_log: 'Protokolleinträge' };

/** Read-only check of one backup file (B-022): the server checks a private copy, nothing is changed. */
export async function verifyDialog(name) {
  const dlg = document.createElement('dialog');
  const draw = body => renderLit(html`<div class="body verify"><h3>Sicherung prüfen</h3><p class="small"><code>${name}</code></p>${body}
    <p class="small muted">Geprüft wird eine Kopie: Die Sicherung auf dem NAS und die laufende Datenbank werden nicht verändert. Wie man eine Sicherung zurückspielt, steht im README unter „Wiederherstellen aus einer Sicherung“.</p>
    <div class="actions"><button class="primary" @click=${() => dlg.close()}>Schließen</button></div></div>`, dlg);
  dlg.addEventListener('close', () => dlg.remove());
  draw(html`<p class="muted">Wird geprüft …</p>`);
  document.body.append(dlg); dlg.showModal();
  let r;
  try { r = await api('GET', `/api/backup/verify?name=${encodeURIComponent(name)}`); }
  catch (ex) { draw(html`<div class="banner err">${ex.message}</div>`); return; }
  const checksum = !r.sha256_logged ? 'nicht in backups.log eingetragen'
    : r.sha256_logged === r.sha256 ? 'stimmt mit backups.log überein' : html`<span class="neg">weicht von backups.log ab</span>`;
  draw(html`${r.ok
      ? html`<div class="banner ok">In Ordnung – diese Sicherung ist vollständig lesbar und lässt sich wiederherstellen.</div>`
      : html`<div class="banner err"><b>Probleme gefunden:</b><ul>${r.problems.map(p => html`<li>${verifyProblemMsg(p)}</li>`)}</ul></div>`}
    <div class="kv">
      <span class="muted">Datenstand</span><span>${r.data_version != null ? `Version ${r.data_version}` : '—'} (laut Dateiname v${r.file_version})</span>
      <span class="muted">Schema-Version</span><span>${r.schema_version ?? '—'}</span>
      <span class="muted">Größe</span><span>${(r.size / 1024).toFixed(0)} KB</span>
      <span class="muted">Prüfsumme</span><span>${checksum}</span>
      ${Object.entries(COUNT_LABELS).filter(([t]) => t in r.counts).map(([t, l]) => html`<span class="muted">${l}</span><span class="num count" style="text-align:left" data-table=${t}>${r.counts[t]}</span>`)}
    </div>`);
}
