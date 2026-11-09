// ------------------------------------------------------------ Sicherung
import { $, esc, eur, fTs, api, toast } from './core.js';

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
  const res = { ok: '<span class="pos">erfolgreich</span>', unchanged: 'keine Änderungen – nichts zu sichern', error: '<span class="neg">FEHLER</span>' }[st.last_result] || '—';
  main.innerHTML = `<h2>Sicherung</h2>${st.last_result === 'error' ? `<div class="banner err"><b>Letzte Sicherung fehlgeschlagen:</b> ${esc(st.last_error)}</div>` : ''}
    <div class="cards"><div class="panel"><div class="kv">
      <span class="muted">Ziel</span><code>${esc(st.backup_dir)}</code>
      <span class="muted">Zeitplan</span><span>täglich um ${esc(st.backup_time)} Uhr, nur bei Änderungen</span>
      <span class="muted">Letzte erfolgreiche</span><span>${st.last_success ? fTs(st.last_success) : '—'}</span>
      <span class="muted">Letzte Datei</span><span class="small">${esc(st.last_file || '—')}</span>
      <span class="muted">Letzter Versuch</span><span>${st.last_attempt ? fTs(st.last_attempt) : '—'} · ${res}</span>
      <span class="muted">Datenstand</span><span>Version ${st.current_version}${st.pending_changes ? ' – <b>ungesicherte Änderungen</b>' : ' – gesichert'}</span>
    </div><div class="actions" style="justify-content:flex-start"><button class="primary" id="run">Jetzt sichern</button><a class="btn" href="/api/export">Export als JSON herunterladen</a></div></div>
    <div class="panel"><h3>Vorhandene Sicherungen (neueste 30)</h3><table><tbody>${(st.files || []).map(f => `<tr><td class="small">${esc(f.name)}</td><td class="num small">${(f.size / 1024).toFixed(0)} KB</td></tr>`).join('') || '<tr><td class="muted">Keine Sicherungen gefunden.</td></tr>'}</tbody></table>
    <p class="small muted">Alte Stände werden nie gelöscht. Zu jeder SQLite-Datei gibt es eine gleichnamige, lesbare JSON-Datei.</p></div></div>`;
  $('#run').onclick = async () => {
    const r = await api('POST', '/api/backup/run');
    if (r.last_result === 'error') toast('Sicherung fehlgeschlagen: ' + r.last_error, true);
    else toast(r.last_result === 'unchanged' ? 'Keine Änderungen seit der letzten Sicherung' : 'Sicherung erstellt');
    renderBackup(main); refreshBackupPill();
  };
}
