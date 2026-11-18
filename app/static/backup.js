// ------------------------------------------------------------ Sicherung
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, eur, fTs, api, toast, S } from './core.js';

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
      if (r.last_result === 'error') toast('Sicherung fehlgeschlagen: ' + r.last_error, true);
      else toast(r.last_result === 'unchanged' ? 'Keine Änderungen seit der letzten Sicherung' : 'Sicherung erstellt');
    } catch (ex) { toast('Sicherung fehlgeschlagen: ' + ex.message, true); }
    renderBackup(main); refreshBackupPill();
  };
  renderLit(html`<h2>Sicherung</h2>${st.last_result === 'error' ? html`<div class="banner err"><b>Letzte Sicherung fehlgeschlagen:</b> ${st.last_error}</div>` : ''}
    <div class="cards"><div class="panel"><div class="kv">
      <span class="muted">Ziel</span><code>${st.backup_dir}</code>
      <span class="muted">Zeitplan</span><span>täglich um ${st.backup_time} Uhr, nur bei Änderungen</span>
      <span class="muted">Letzte erfolgreiche</span><span>${st.last_success ? fTs(st.last_success) : '—'}</span>
      <span class="muted">Letzte Datei</span><span class="small">${st.last_file || '—'}</span>
      <span class="muted">Letzter Versuch</span><span>${st.last_attempt ? fTs(st.last_attempt) : '—'} · ${res}</span>
      <span class="muted">Datenstand</span><span>Version ${st.current_version}${st.pending_changes ? html` – <b>ungesicherte Änderungen</b>` : ' – gesichert'}</span>
    </div><div class="actions" style="justify-content:flex-start"><button class="primary" @click=${run}>Jetzt sichern</button><a class="btn" href="/api/export">Export als JSON herunterladen</a></div></div>
    <div class="panel"><h3>Vorhandene Sicherungen (neueste 30)</h3><table><tbody>${(st.files || []).length
      ? st.files.map(f => html`<tr><td class="small">${f.name}</td><td class="num small">${(f.size / 1024).toFixed(0)} KB</td></tr>`)
      : html`<tr><td class="muted">Keine Sicherungen gefunden.</td></tr>`}</tbody></table>
    <p class="small muted">Alte Stände werden nie gelöscht. Zu jeder SQLite-Datei gibt es eine gleichnamige, lesbare JSON-Datei.</p></div></div>`, main);
}
