import { html, render as renderLit, nothing } from './vendor/lit-html.js';

// ------------------------------------------------------------ Hilfsfunktionen
export const $ = (s, el = document) => el.querySelector(s);
export const eur = c => c == null ? '–' : (c / 100).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });
export const eurCls = c => c == null ? '' : c < 0 ? 'neg' : '';
export const signed = c => html`<span class="${c < 0 ? 'neg' : 'pos'}">${c > 0 ? '+' : ''}${eur(c)}</span>`;
/** The "≈" mark in front of an estimated amount (B-015); empty for a fixed one. */
export const approx = estimated => estimated ? html`<span class="approx" title="geschätzter Betrag">≈ </span>` : '';
export const ESTIMATE_NOTE = 'Geschätzter Betrag – die Abweichung zur Wirklichkeit zeigt der nächste Ist-Stand.';
export const fDate = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE') : '';
export const fShort = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) : '';
export const fFull = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '';
export const fTs = ts => new Date(ts).toLocaleString('de-DE');
export const fMonth = ym => { const [y, m] = ym.split('-'); return new Date(y, m - 1, 1).toLocaleDateString('de-DE', { month: 'short', year: 'numeric' }); };
export const today = () => new Date().toLocaleDateString('sv-SE');
export const thisMonth = () => today().slice(0, 7);
export const toInput = c => c == null ? '' : (c / 100).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });

export function parseEUR(s) {
  s = String(s ?? '').trim().replace(/\s|€/g, '');
  if (!s) return NaN;
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
  const v = Number(s);
  return Number.isFinite(v) ? Math.round(v * 100) : NaN;
}

export function toast(msg, isErr = false) {
  const d = document.createElement('div');
  d.textContent = msg; if (isErr) d.className = 'e';
  $('#toast').append(d); setTimeout(() => d.remove(), isErr ? 7000 : 3000);
}

export async function api(method, url, body) {
  const r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  let data = null; try { data = await r.json(); } catch { }
  if (!r.ok) {
    throw new Error(errMsg(data) || data?.detail || `Fehler ${r.status}`);
  }
  return data;
}

export const KINDS = { checking: 'Girokonto', savings: 'Tagesgeld', custody: 'Depot', credit_card: 'Kreditkarte', cash: 'Bargeld', other: 'Sonstiges' };
export const RHYTHM = { 1: 'monatlich', 2: 'alle 2 Monate', 3: 'quartalsweise', 6: 'halbjährlich', 12: 'jährlich' };
export const rhythm = n => RHYTHM[n] || `alle ${n} Monate`;
export const ENTITY = { accounts: 'Konto', entries: 'Buchung', adjustments: 'Anpassung', checkpoints: 'Ist-Stand', audit_log: 'Protokolleintrag' };
export const ACTION = { create: 'Angelegt', update: 'Geändert', archive: 'Archiviert', restore: 'Wiederhergestellt', revert: 'Rückgängig' };
export const FIELD = {
  name: 'Name', kind: 'Art', note: 'Notiz', account_id: 'Konto', to_account_id: 'Zielkonto', category: 'Kategorie',
  amount: 'Betrag', start_date: 'Start', end_date: 'Ende', interval_months: 'Rhythmus (Monate)', entry_id: 'Buchung',
  effective_date: 'Gültig ab', mode: 'Art', percent: 'Prozent', repeat_yearly: 'Jährlich wiederholen', date: 'Datum',
  balance: 'Kontostand', archived: 'Archiviert', estimated: 'Fest/geschätzt',
};
export const COLORS = ['#2f6fdb', '#1a9e77', '#d9822b', '#8e5bd9', '#c94f6d', '#2aa1b3', '#7a8b2b'];

// ------------------------------------------------------------ API-Fehlercodes -> Deutsch
// The backend never sends German text; every error response is {code, params}. This maps
// codes raised in app/main.py and app/db.py to the German text the UI shows.
const VALIDATION_CODES = {
  missing: () => 'ist erforderlich',
  string_too_short: p => `muss mindestens ${p.min_length} Zeichen haben`,
  string_too_long: p => `darf höchstens ${p.max_length} Zeichen haben`,
  string_type: () => 'muss Text sein',
  literal_error: p => `ungültiger Wert (erlaubt: ${p.expected})`,
  int_type: () => 'muss eine Zahl sein',
  int_parsing: () => 'muss eine Zahl sein',
  float_type: () => 'muss eine Zahl sein',
  float_parsing: () => 'muss eine Zahl sein',
  bool_type: () => 'muss ja/nein sein',
  bool_parsing: () => 'muss ja/nein sein',
  date_type: () => 'muss ein gültiges Datum sein',
  date_parsing: () => 'muss ein gültiges Datum sein',
  date_from_datetime_parsing: () => 'muss ein gültiges Datum sein',
  greater_than: p => `muss größer als ${p.gt} sein`,
  less_than: p => `muss kleiner als ${p.lt} sein`,
  greater_than_equal: p => `muss mindestens ${p.ge} sein`,
  less_than_equal: p => `muss höchstens ${p.le} sein`,
  end_before_start: () => 'Das Enddatum liegt vor dem Startdatum.',
  transfer_same_account: () => 'Quell- und Zielkonto müssen verschieden sein.',
  transfer_amount_not_positive: () => 'Der Umbuchungsbetrag muss positiv sein.',
  amount_zero: () => 'Der Betrag darf nicht 0 sein.',
  amount_required: () => 'Bitte den neuen Betrag angeben.',
  percent_required: () => 'Bitte die prozentuale Änderung angeben.',
};
const ERROR_CODES = {
  not_found: p => `${ENTITY[p.entity] || p.entity} #${p.id} nicht gefunden`,
  backup_not_found: p => `Sicherung „${p.name}“ nicht gefunden.`,
  updater_not_configured: () => 'Die automatische Aktualisierung ist auf diesem System nicht eingerichtet.',
  update_in_progress: () => 'Es läuft bereits ein Update.',
  updater_unavailable: () => 'Die Update-Anfrage konnte nicht abgelegt werden (Ordner /updater nicht beschreibbar).',
  conflict: () => 'Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen.',
  unknown_table: () => 'Unbekannter Datentyp',
  ref_not_found: p => `Verweis ${p.field}=${p.id} existiert nicht.`,
  validation_error: p => p.errors.map(e => {
    const fn = VALIDATION_CODES[e.code];
    const msg = fn ? fn(e.params) : e.code;
    return e.field ? `${FIELD[e.field] || e.field}: ${msg}` : msg;
  }).join('; '),
};
export const errMsg = data => {
  const fn = data?.code && ERROR_CODES[data.code];
  return fn ? fn(data.params || {}) : null;
};

// ------------------------------------------------------------ Prognose-Codes -> Deutsch
// forecast.compute() never sends German text either; warnings and explanation steps are
// {code, params} objects that this maps to the German text the UI shows.
const noteSuffix = note => note ? ` (${note})` : '';
const EXPLANATION_CODES = {
  base_amount: p => `Grundbetrag ${eur(p.amount)}`,
  set_amount: p => `ab ${fFull(p.date)}: neuer Betrag ${eur(p.amount)}${noteSuffix(p.note)}`,
  percent_change: p => {
    const pct = `${p.percent > 0 ? '+' : ''}${String(p.percent).replace('.', ',')} %`;
    const times = p.repeat_yearly ? `, jährlich – hier ${p.years}× angewendet` : '';
    return `ab ${fFull(p.date)}: ${pct}${times} → ${eur(p.amount)}${noteSuffix(p.note)}`;
  },
};
export const explLine = e => EXPLANATION_CODES[e.code]?.(e) ?? e.code;
const WARNING_CODES = {
  transfer_target_archived: p => `Umbuchung „${entryName(p.entry_id)}“: Zielkonto „${accName(p.account_id)}“ ist archiviert – berücksichtigt wird nur die Abbuchung vom Quellkonto.`,
  no_checkpoint: p => `Konto „${accName(p.account_id)}“ hat keinen Ist-Stand und kann nicht berechnet werden.`,
};
export const warnMsg = w => WARNING_CODES[w.code]?.(w) ?? w.code;

// ------------------------------------------------------------ Sicherung: Codes -> Deutsch (B-020, B-022)
const BACKUP_ERROR_CODES = {
  backup_dir_missing: p => `Backup-Ziel ${p.dir} existiert nicht.`,
  marker_missing: p => `Datei ${p.marker} fehlt im Backup-Ziel – ist das NAS eingebunden? Es wurde nichts gesichert.`,
  integrity_failed: p => `Integritätsprüfung der Sicherung fehlgeschlagen: ${p.result}`,
  backup_failed: p => `Unerwarteter Fehler: ${p.detail}`,
};
/** German text of a backup last_error: {code, params}, or a plain string from a status file written before B-020. */
export const backupErrMsg = e => e == null ? '' : typeof e === 'string' ? e : BACKUP_ERROR_CODES[e.code]?.(e.params || {}) ?? e.code;
const BACKUP_REASONS = { scheduled: 'Zeitplan', manual: 'manuell', retry: 'Wiederholung nach Fehler' };
/** German label of a backup run reason; older status files hold German text already and show as-is. */
export const backupReason = r => r ? BACKUP_REASONS[r] ?? r : '';
const VERIFY_PROBLEMS = {
  checksum_mismatch: () => 'Die Prüfsumme weicht vom Eintrag in backups.log ab – die Datei wurde nach dem Sichern verändert.',
  integrity_failed: p => `Die Integritätsprüfung ist fehlgeschlagen: ${p.result}`,
  not_a_database: p => `Die Datei ist keine lesbare SQLite-Datenbank (${p.detail}).`,
  tables_missing: p => `Es fehlen Tabellen: ${p.tables}`,
  version_mismatch: p => `Der Datenstand der Datei (Version ${p.data_version}) passt nicht zum Dateinamen (v${p.file_version}).`,
};
export const verifyProblemMsg = p => VERIFY_PROBLEMS[p.code]?.(p.params || {}) ?? p.code;

// ------------------------------------------------------------ Version/Update: Codes -> Deutsch (B-026)
const UPDATE_RESULTS = {
  success: 'erfolgreich',
  rolled_back: 'fehlgeschlagen – die vorherige Version läuft wieder',
  rollback_failed: 'fehlgeschlagen – auch das Zurückrollen ist fehlgeschlagen, bitte auf dem Server prüfen',
  failed: 'fehlgeschlagen – nichts wurde umgestellt',
};
export const updateResult = r => UPDATE_RESULTS[r] ?? r;
const UPDATE_MODES = { auto: 'automatisch – neue Versionen werden alle 15 Minuten gesucht und installiert', notify: 'nur anzeigen – installiert wird erst nach „Jetzt aktualisieren“' };
export const updateMode = m => UPDATE_MODES[m] ?? m;
const UPDATER_ERRORS = {
  pull_failed: () => 'Die neueste Version konnte nicht abgefragt werden (ghcr.io nicht erreichbar oder Token abgelaufen).',
  bad_version_label: () => 'Das neueste Image hat keine gültige Versionsangabe.',
  updater_status_missing: () => 'Vom Update-Dienst auf dem Server liegt noch kein Status vor. Läuft der Timer finanzprognose-update.timer?',
  updater_status_unreadable: () => 'Der Status des Update-Dienstes ist nicht lesbar.',
};
/** German text of an updater code: a host check_error (string) or a host_error {code, params}. */
export const updaterErrMsg = e => { const c = typeof e === 'string' ? e : e?.code; return c ? UPDATER_ERRORS[c]?.(e?.params || {}) ?? c : ''; };

// ------------------------------------------------------------ Zustand
export const S = { view: location.hash.slice(1) || 'prognose', data: null, from: thisMonth(), months: 24, sel: null, showArchived: false, fc: null };
export const accName = id => S.data.accounts.find(a => a.id === id)?.name ?? `#${id}`;
export const entryName = id => S.data.entries.find(e => e.id === id)?.name ?? `#${id}`;
export const activeAccounts = () => S.data.accounts.filter(a => !a.archived);

export async function load() { S.data = await api('GET', '/api/state'); }
export async function refresh() { await load(); await render(); refreshBackupPill(); }

// ------------------------------------------------------------ Formular-Dialog
export function formDialog({ title, fields, values = {}, submitLabel = 'Speichern', onSubmit, intro = '' }) {
  return new Promise(resolve => {
    let done = false;
    const dlg = document.createElement('dialog');
    const state = { values: { ...values }, error: '', busy: false };
    const finish = r => { if (!done) { done = true; resolve(r); } dlg.close(); };

    const fieldTpl = f => {
      if (f.showIf && !f.showIf(state.values)) return nothing;
      const v = state.values[f.name];
      let input;
      if (f.type === 'select') {
        input = html`<select name=${f.name}>${f.options.map(o => html`<option value=${o.value} ?selected=${String(o.value) === String(v)}>${o.label}</option>`)}</select>`;
      } else if (f.type === 'textarea') {
        input = html`<textarea name=${f.name} rows="2" .value=${v ?? ''}></textarea>`;
      } else if (f.type === 'checkbox') {
        input = html`<input type="checkbox" name=${f.name} .checked=${!!v}>`;
      } else {
        input = html`<input name=${f.name} type=${f.type === 'money' ? 'text' : f.type || 'text'}
          inputmode=${f.type === 'money' ? 'decimal' : nothing} placeholder=${f.type === 'money' ? '0,00' : nothing}
          step=${f.step ?? nothing} autocomplete="off" list=${f.suggestions ? `fd-list-${f.name}` : nothing} .value=${v ?? ''}>`;
        // Free text with a pick list: the browser offers matching suggestions while typing.
        if (f.suggestions) input = html`${input}<datalist id=${`fd-list-${f.name}`}>${f.suggestions.map(s => html`<option value=${s}></option>`)}</datalist>`;
      }
      return html`<label class="field ${f.type === 'checkbox' ? 'check' : ''}" data-name=${f.name}>
        <span>${f.label}${f.required ? ' *' : ''}</span>${input}${f.hint ? html`<small class="muted">${f.hint}</small>` : ''}
      </label>`;
    };

    const onFormChange = e => {
      const name = e.target.name; if (!name) return;
      const f = fields.find(x => x.name === name); if (!f) return;
      state.values[name] = f.type === 'checkbox' ? e.target.checked : e.target.value;
      draw();
    };

    const onSubmitForm = async e => {
      e.preventDefault();
      state.error = '';
      const v = { ...state.values };
      for (const f of fields) {
        if (f.showIf && !f.showIf(v)) { v[f.name] = null; continue; }
        if (f.required && (v[f.name] === '' || v[f.name] == null)) { state.error = `Bitte „${f.label}“ ausfüllen.`; draw(); return; }
        if (f.type === 'money' && v[f.name] !== '') {
          const c = parseEUR(v[f.name]); if (Number.isNaN(c)) { state.error = `„${f.label}“ ist kein gültiger Betrag.`; draw(); return; } v[f.name] = c;
        } else if (f.type === 'money') v[f.name] = null;
        if (f.type === 'number') v[f.name] = v[f.name] === '' ? null : Number(String(v[f.name]).replace(',', '.'));
        if ((f.type === 'date' || f.type === 'text' || f.type === 'select') && v[f.name] === '' && !f.keepEmpty) v[f.name] = f.type === 'text' ? '' : null;
      }
      state.busy = true; draw();
      try { const r = onSubmit ? await onSubmit(v) : v; finish(r ?? true); }
      catch (ex) { state.error = ex.message; state.busy = false; draw(); }
    };

    const tpl = () => html`<form @input=${onFormChange} @change=${onFormChange} @submit=${onSubmitForm}>
      <h3>${title}</h3>${intro}
      <div class="fields">${fields.map(fieldTpl)}</div>
      <div class="err">${state.error}</div>
      <div class="actions">
        <button type="button" @click=${() => finish(null)}>Abbrechen</button>
        <button type="submit" class="primary" ?disabled=${state.busy}>${submitLabel}</button>
      </div>
    </form>`;
    const draw = () => renderLit(tpl(), dlg);

    dlg.addEventListener('close', () => { if (!done) { done = true; resolve(null); } dlg.remove(); });
    draw();
    document.body.append(dlg); dlg.showModal();
  });
}

/** Archive dialog; `notice` is an optional extra template shown below the intro (e.g. what still uses an account).
 *  Sends expected_updated_at, so archiving a record changed elsewhere is refused with a conflict. */
export async function archiveDialog(table, row, label, notice = '') {
  const ok = await formDialog({
    title: `${ENTITY[table]} archivieren`, submitLabel: 'Archivieren',
    intro: html`<p class="muted">„${label}“ wird archiviert und fließt nicht mehr in die Prognose ein. Nichts wird gelöscht – du kannst es jederzeit wiederherstellen.</p>${notice}`,
    fields: [{ name: 'comment', label: 'Grund (optional)', type: 'textarea' }],
    onSubmit: v => api('POST', `/api/${table}/${row.id}/archive`, { comment: v.comment || '', expected_updated_at: row.updated_at }),
  });
  if (ok) { toast('Archiviert'); refresh(); }
}
/** POST archive/restore without a dialog (sends expected_updated_at); returns false and toasts the error on failure. */
export async function setArchived(table, row, archived) {
  try {
    await api('POST', `/api/${table}/${row.id}/${archived ? 'archive' : 'restore'}`, { expected_updated_at: row.updated_at });
    return true;
  } catch (err) { toast(err.message, true); return false; }
}
export async function restoreRow(table, row) { if (await setArchived(table, row, false)) toast('Wiederhergestellt'); refresh(); }

// ------------------------------------------------------------ Navigation
// Importing the view renderers here closes an import cycle (each view module imports
// helpers/state back from core.js). That's safe in native ESM because nothing below runs at
// module-evaluation time - render()/setView() only touch these bindings once the user
// navigates, by which point every module has finished loading.
import { renderForecast } from './forecast.js';
import { renderEntries } from './entries.js';
import { renderOnce } from './once.js';
import { renderAccounts } from './accounts.js';
import { renderAudit } from './audit.js';
import { renderBackup, refreshBackupPill } from './backup.js';
import { renderUpdate } from './update.js';

export function setView(v) { S.view = v; location.hash = v; render(); }
document.addEventListener('click', e => { const b = e.target.closest('[data-view]'); if (b) setView(b.dataset.view); });
window.addEventListener('hashchange', () => { const v = location.hash.slice(1); if (v && v !== S.view) { S.view = v; render(); } });

export async function render() {
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.view === S.view));
  const main = $('#main');
  try {
    await ({ prognose: renderForecast, buchungen: renderEntries, einmalig: renderOnce, konten: renderAccounts, verlauf: renderAudit, sicherung: renderBackup, version: renderUpdate }[S.view] || renderForecast)(main);
  } catch (ex) { renderLit(html`<div class="banner err">${ex.message}</div>`, main); }
}
