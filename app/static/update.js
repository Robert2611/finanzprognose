// ------------------------------------------------------------ Version (B-026)
// Shows what the update service on the server reports (GET /api/update/status) and asks it for an
// update (POST /api/update/request). The app never updates itself: the host's auto-update.sh does,
// so the page loses the server for a moment and reloads once the update has finished.
import { html, render as renderLit } from './vendor/lit-html.js';
import { $, fTs, api, toast, S, updateResult, updateMode, updaterErrMsg } from './core.js';

const POLL_MS = 3000;
const WATCH_MS = 15 * 60 * 1000;
let watching = false;

/** The header pill for a status, or null to hide it: an update running, failed or available. */
export function updatePillState(st) {
  const h = st?.host;
  if (!st?.enabled || !h) return null;
  if (h.state === 'updating' || st.request_pending) return { cls: 'warn', text: 'Update läuft …' };
  if (h.failed_version && h.failed_version === h.latest && h.latest !== st.running_version) return { cls: 'err', text: `Update auf ${h.latest} fehlgeschlagen` };
  if (st.update_available) return { cls: 'warn', text: `Update verfügbar: ${h.latest}` };
  return null;
}

export async function refreshUpdatePill() {
  const pill = $('#updatePill');
  let st = null;
  try { st = await api('GET', '/api/update/status'); } catch { }
  const p = updatePillState(st);
  pill.hidden = !p;
  if (p) { pill.className = `pill ${p.cls}`; pill.textContent = p.text; }
  return st;
}

/** Polls until the host has handled the request (new version running, or the run finished), then reloads. */
async function watchUpdate(before) {
  if (watching) return;
  watching = true;
  const deadline = Date.now() + WATCH_MS;
  while (Date.now() < deadline) {
    await new Promise(r => setTimeout(r, POLL_MS));
    let st;
    try { st = await api('GET', '/api/update/status'); } catch { continue; } // the app restarts during the update
    const h = st.host;
    if (st.running_version !== before.running_version
      || (!st.request_pending && h?.state === 'idle' && h.checked_at !== before.checked_at)) {
      location.reload();
      return;
    }
  }
  watching = false;
  toast('Das Update hat nach 15 Minuten noch nicht geantwortet. Bitte den Server prüfen.', true);
}

function confirmDialog(version) {
  return new Promise(resolve => {
    const dlg = document.createElement('dialog');
    let ok = false;
    dlg.addEventListener('close', () => { dlg.remove(); resolve(ok); });
    renderLit(html`<div class="body"><h3>Jetzt aktualisieren?</h3>
      <p>Die App wird auf <b>${version}</b> umgestellt und ist dafür etwa eine Minute nicht erreichbar.
      Vorher wird die Datenbank kopiert; startet die neue Version nicht, kehrt der Server automatisch zur jetzigen zurück.</p>
      <div class="actions"><button @click=${() => dlg.close()}>Abbrechen</button>
      <button class="primary" @click=${() => { ok = true; dlg.close(); }}>Aktualisieren</button></div></div>`, dlg);
    document.body.append(dlg); dlg.showModal();
  });
}

export async function renderUpdate(main) {
  const st = await api('GET', '/api/update/status');
  if (S.view !== 'version') return; // navigated away while loading
  const h = st.host;
  const before = { running_version: st.running_version, checked_at: h?.checked_at ?? null };
  const busy = watching || st.request_pending || h?.state === 'updating';
  const retry = h?.failed_version && h.failed_version === h.latest;
  const start = async () => {
    if (!(await confirmDialog(h.latest))) return;
    try { await api('POST', '/api/update/request', { version: h.latest }); }
    catch (ex) { toast('Update nicht angefordert: ' + ex.message, true); return; }
    watchUpdate(before);
    renderUpdate(main); refreshUpdatePill();
  };
  if (busy) watchUpdate(before);
  const last = h?.last_update;
  renderLit(html`<h2>Version</h2>
    ${!st.enabled ? html`<div class="banner warn">Die automatische Aktualisierung ist auf diesem System nicht eingerichtet (siehe README, „Updates“).</div>` : ''}
    ${st.host_error ? html`<div class="banner warn">${updaterErrMsg(st.host_error)}</div>` : ''}
    ${h?.check_error ? html`<div class="banner warn">${updaterErrMsg(h.check_error)}</div>` : ''}
    ${last && last.result !== 'success' ? html`<div class="banner err"><b>Update auf ${last.to} ${updateResult(last.result)}.</b> Details unten unter „Ausgabe des letzten Updates“.</div>` : ''}
    ${busy ? html`<div class="banner warn update-busy">Update läuft … Die Seite lädt neu, sobald es fertig ist.</div>` : ''}
    <div class="cards"><div class="panel"><div class="kv">
      <span class="muted">Laufende Version</span><span class="running-version">${st.running_version}</span>
      ${h ? html`
        <span class="muted">Neueste Version</span><span>${h.latest ?? '—'}${h.checked_at ? html` <span class="small muted">(geprüft ${fTs(h.checked_at)})</span>` : ''}</span>
        <span class="muted">Aktualisierung</span><span>${updateMode(h.mode)}</span>
        <span class="muted">Letztes Update</span><span>${last ? html`${last.from ?? '?'} → ${last.to ?? '?'}, ${updateResult(last.result)}${last.at ? ` (${fTs(last.at)})` : ''}` : '—'}</span>` : ''}
    </div>
    ${h && st.update_available && !busy ? html`<div class="actions" style="justify-content:flex-start">
      <button class="primary" @click=${start}>${retry ? `Erneut versuchen: ${h.latest}` : `Jetzt auf ${h.latest} aktualisieren`}</button></div>` : ''}
    ${h && !st.update_available && !busy && h.latest ? html`<p class="small muted">Die App ist auf dem neuesten Stand.</p>` : ''}
    </div>
    ${st.log_tail.length ? html`<div class="panel"><details><summary>Ausgabe des letzten Updates</summary>
      <pre class="update-log">${st.log_tail.join('\n')}</pre></details></div>` : ''}
    </div>`, main);
}
