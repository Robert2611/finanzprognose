'use strict';
// ------------------------------------------------------------ Hilfsfunktionen
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const eur = c => c == null ? '–' : (c / 100).toLocaleString('de-DE', { style: 'currency', currency: 'EUR' });
const eurCls = c => c == null ? '' : c < 0 ? 'neg' : '';
const signed = c => `<span class="${c < 0 ? 'neg' : 'pos'}">${c > 0 ? '+' : ''}${eur(c)}</span>`;
const fDate = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE') : '';
const fShort = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) : '';
const fFull = iso => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '';
const fTs = ts => new Date(ts).toLocaleString('de-DE');
const fMonth = ym => { const [y, m] = ym.split('-'); return new Date(y, m - 1, 1).toLocaleDateString('de-DE', { month: 'short', year: 'numeric' }); };
const today = () => new Date().toLocaleDateString('sv-SE');
const thisMonth = () => today().slice(0, 7);
const toInput = c => c == null ? '' : (c / 100).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false });

function parseEUR(s) {
  s = String(s ?? '').trim().replace(/\s|€/g, '');
  if (!s) return NaN;
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
  const v = Number(s);
  return Number.isFinite(v) ? Math.round(v * 100) : NaN;
}

function toast(msg, isErr = false) {
  const d = document.createElement('div');
  d.textContent = msg; if (isErr) d.className = 'e';
  $('#toast').append(d); setTimeout(() => d.remove(), isErr ? 7000 : 3000);
}

async function api(method, url, body) {
  const r = await fetch(url, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  let data = null; try { data = await r.json(); } catch { }
  if (!r.ok) {
    throw new Error(errMsg(data) || data?.detail || `Fehler ${r.status}`);
  }
  return data;
}

const KINDS = { checking: 'Girokonto', savings: 'Tagesgeld', custody: 'Depot', credit_card: 'Kreditkarte', cash: 'Bargeld', other: 'Sonstiges' };
const RHYTHM = { 1: 'monatlich', 2: 'alle 2 Monate', 3: 'quartalsweise', 6: 'halbjährlich', 12: 'jährlich' };
const rhythm = n => RHYTHM[n] || `alle ${n} Monate`;
const ENTITY = { accounts: 'Konto', entries: 'Buchung', adjustments: 'Anpassung', checkpoints: 'Ist-Stand', audit_log: 'Protokolleintrag' };
const ACTION = { create: 'Angelegt', update: 'Geändert', archive: 'Archiviert', restore: 'Wiederhergestellt', revert: 'Rückgängig' };
const FIELD = {
  name: 'Name', kind: 'Art', note: 'Notiz', account_id: 'Konto', to_account_id: 'Zielkonto', category: 'Kategorie',
  amount: 'Betrag', start_date: 'Start', end_date: 'Ende', interval_months: 'Rhythmus (Monate)', entry_id: 'Buchung',
  effective_date: 'Gültig ab', mode: 'Art', percent: 'Prozent', repeat_yearly: 'Jährlich wiederholen', date: 'Datum',
  balance: 'Kontostand', archived: 'Archiviert',
};
const COLORS = ['#2f6fdb', '#1a9e77', '#d9822b', '#8e5bd9', '#c94f6d', '#2aa1b3', '#7a8b2b'];

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
  conflict: () => 'Der Datensatz wurde inzwischen geändert. Bitte Seite neu laden und erneut versuchen.',
  unknown_table: () => 'Unbekannter Datentyp',
  ref_not_found: p => `Verweis ${p.field}=${p.id} existiert nicht.`,
  validation_error: p => p.errors.map(e => {
    const fn = VALIDATION_CODES[e.code];
    const msg = fn ? fn(e.params) : e.code;
    return e.field ? `${FIELD[e.field] || e.field}: ${msg}` : msg;
  }).join('; '),
};
const errMsg = data => {
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
const explLine = e => EXPLANATION_CODES[e.code]?.(e) ?? e.code;
const WARNING_CODES = {
  transfer_target_archived: p => `Umbuchung „${entryName(p.entry_id)}“ ignoriert: Zielkonto „${accName(p.account_id)}“ ist archiviert.`,
  no_checkpoint: p => `Konto „${accName(p.account_id)}“ hat keinen Ist-Stand und kann nicht berechnet werden.`,
};
const warnMsg = w => WARNING_CODES[w.code]?.(w) ?? w.code;

// ------------------------------------------------------------ Zustand
const S = { view: location.hash.slice(1) || 'prognose', data: null, from: thisMonth(), months: 24, sel: null, showArchived: false, fc: null };
const accName = id => S.data.accounts.find(a => a.id === id)?.name ?? `#${id}`;
const entryName = id => S.data.entries.find(e => e.id === id)?.name ?? `#${id}`;
const activeAccounts = () => S.data.accounts.filter(a => !a.archived);

async function load() { S.data = await api('GET', '/api/state'); }
async function refresh() { await load(); await render(); refreshBackupPill(); }

// ------------------------------------------------------------ Formular-Dialog
function formDialog({ title, fields, values = {}, submitLabel = 'Speichern', onSubmit, intro = '' }) {
  return new Promise(resolve => {
    let done = false;
    const dlg = document.createElement('dialog');
    dlg.innerHTML = `<form><h3>${esc(title)}</h3>${intro}<div class="fields"></div><div class="err"></div>
      <div class="actions"><button type="button" data-cancel>Abbrechen</button><button type="submit" class="primary">${esc(submitLabel)}</button></div></form>`;
    const box = $('.fields', dlg);
    for (const f of fields) {
      const w = document.createElement('label');
      w.className = 'field' + (f.type === 'checkbox' ? ' check' : ''); w.dataset.name = f.name;
      let input;
      if (f.type === 'select') input = `<select name="${f.name}">${f.options.map(o => `<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('')}</select>`;
      else if (f.type === 'textarea') input = `<textarea name="${f.name}" rows="2"></textarea>`;
      else if (f.type === 'checkbox') input = `<input type="checkbox" name="${f.name}">`;
      else input = `<input name="${f.name}" type="${f.type === 'money' ? 'text' : f.type || 'text'}" ${f.type === 'money' ? 'inputmode="decimal" placeholder="0,00"' : ''} ${f.step ? `step="${f.step}"` : ''} autocomplete="off">`;
      w.innerHTML = `<span>${esc(f.label)}${f.required ? ' *' : ''}</span>${input}${f.hint ? `<small class="muted">${esc(f.hint)}</small>` : ''}`;
      box.append(w);
      const el = w.querySelector('[name]'); const v = values[f.name];
      if (f.type === 'checkbox') el.checked = !!v; else if (v != null) el.value = v;
    }
    const read = () => { const o = {}; for (const f of fields) { const el = box.querySelector(`[name="${f.name}"]`); o[f.name] = f.type === 'checkbox' ? el.checked : el.value; } return o; };
    const visible = (f, v) => !f.showIf || f.showIf(v);
    const upd = () => { const v = read(); for (const f of fields) box.querySelector(`[data-name="${f.name}"]`).hidden = !visible(f, v); };
    dlg.addEventListener('input', upd); dlg.addEventListener('change', upd); upd();
    const finish = r => { if (!done) { done = true; resolve(r); } dlg.close(); };
    $('[data-cancel]', dlg).onclick = () => finish(null);
    dlg.addEventListener('close', () => { if (!done) { done = true; resolve(null); } dlg.remove(); });
    $('form', dlg).addEventListener('submit', async e => {
      e.preventDefault();
      const err = $('.err', dlg); err.textContent = '';
      const v = read();
      for (const f of fields) {
        if (!visible(f, v)) { v[f.name] = null; continue; }
        if (f.required && (v[f.name] === '' || v[f.name] == null)) { err.textContent = `Bitte „${f.label}“ ausfüllen.`; return; }
        if (f.type === 'money' && v[f.name] !== '') {
          const c = parseEUR(v[f.name]); if (Number.isNaN(c)) { err.textContent = `„${f.label}“ ist kein gültiger Betrag.`; return; } v[f.name] = c;
        } else if (f.type === 'money') v[f.name] = null;
        if (f.type === 'number') v[f.name] = v[f.name] === '' ? null : Number(String(v[f.name]).replace(',', '.'));
        if ((f.type === 'date' || f.type === 'text' || f.type === 'select') && v[f.name] === '' && !f.keepEmpty) v[f.name] = f.type === 'text' ? '' : null;
      }
      const btn = $('button[type=submit]', dlg); btn.disabled = true;
      try { const r = onSubmit ? await onSubmit(v) : v; finish(r ?? true); }
      catch (ex) { err.textContent = ex.message; }
      finally { btn.disabled = false; }
    });
    document.body.append(dlg); dlg.showModal();
  });
}

async function archiveDialog(table, row, label) {
  const ok = await formDialog({
    title: `${ENTITY[table]} archivieren`, submitLabel: 'Archivieren',
    intro: `<p class="muted">„${esc(label)}“ wird archiviert und fließt nicht mehr in die Prognose ein. Nichts wird gelöscht – du kannst es jederzeit wiederherstellen.</p>`,
    fields: [{ name: 'comment', label: 'Grund (optional)', type: 'textarea' }],
    onSubmit: v => api('POST', `/api/${table}/${row.id}/archive`, { comment: v.comment || '' }),
  });
  if (ok) { toast('Archiviert'); refresh(); }
}
async function restoreRow(table, row) { await api('POST', `/api/${table}/${row.id}/restore`, {}); toast('Wiederhergestellt'); refresh(); }

// ------------------------------------------------------------ Navigation
function setView(v) { S.view = v; location.hash = v; render(); }
document.addEventListener('click', e => { const b = e.target.closest('[data-view]'); if (b) setView(b.dataset.view); });
window.addEventListener('hashchange', () => { const v = location.hash.slice(1); if (v && v !== S.view) { S.view = v; render(); } });

async function render() {
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.view === S.view));
  const main = $('#main');
  try {
    await ({ prognose: renderForecast, buchungen: renderEntries, konten: renderAccounts, verlauf: renderAudit, sicherung: renderBackup }[S.view] || renderForecast)(main);
  } catch (ex) { main.innerHTML = `<div class="banner err">${esc(ex.message)}</div>`; }
}

// ------------------------------------------------------------ Prognose
async function renderForecast(main) {
  if (!S.data.accounts.length) {
    main.innerHTML = `<div class="panel"><h2>Willkommen</h2><p>Lege zuerst ein Konto mit seinem aktuellen Kontostand an. Danach trägst du wiederkehrende und einmalige Buchungen ein – die Prognose entsteht automatisch.</p><button class="primary" id="first">Erstes Konto anlegen</button></div>`;
    $('#first').onclick = () => accountDialog(); return;
  }
  main.innerHTML = `<div class="toolbar">
      <label>Ab <input type="month" id="from" value="${S.from}"></label>
      <label>Zeitraum <select id="months">${[12, 24, 36, 60, 120].map(n => `<option value="${n}" ${n == S.months ? 'selected' : ''}>${n} Monate</option>`).join('')}</select></label>
      <button id="todayBtn">Heute</button><span class="spacer"></span>
      <button class="primary" id="newEntry">+ Buchung</button><button id="newCp">+ Ist-Stand</button></div>
    <div id="warn"></div><div class="panel" style="margin-bottom:16px"><div id="chart"></div></div>
    <div class="fc-layout"><div class="panel table-wrap" id="ftable"></div><div class="panel detail" id="fdetail"></div></div>`;
  $('#from').onchange = e => { S.from = e.target.value || thisMonth(); S.sel = null; renderForecast(main); };
  $('#months').onchange = e => { S.months = +e.target.value; renderForecast(main); };
  $('#todayBtn').onclick = () => { S.from = thisMonth(); S.sel = null; renderForecast(main); };
  $('#newEntry').onclick = () => entryDialog();
  $('#newCp').onclick = () => checkpointDialog();
  const fc = S.fc = await api('GET', `/api/forecast?start=${S.from}&months=${S.months}`);
  if (!S.sel || !fc.months.some(m => m.month === S.sel)) S.sel = fc.months[0].month;
  const neg = fc.months.find(m => m.closing < 0);
  $('#warn').innerHTML = fc.warnings.map(w => `<div class="banner warn">${esc(warnMsg(w))}</div>`).join('') +
    (neg ? `<div class="banner err">Achtung: Im ${fMonth(neg.month)} wird der Gesamtstand voraussichtlich negativ (${eur(neg.closing)}).</div>` : '');
  drawChart(fc);
  drawTable(fc);
  drawDetail(fc);
}

function drawChart(fc) {
  const W = 1000, H = 250, L = 70, R = 10, T = 10, B = 26;
  const series = [{ name: 'Gesamt', color: 'var(--ink)', vals: fc.months.map(m => m.closing), w: 2.5 }];
  if (fc.accounts.length > 1) fc.accounts.forEach((a, i) => series.push({ name: a.name, color: COLORS[i % COLORS.length], vals: fc.months.map(m => m.accounts[a.id]?.closing ?? null), w: 1.5 }));
  const all = series.flatMap(s => s.vals).filter(v => v != null).concat([0]);
  let min = Math.min(...all), max = Math.max(...all); if (min === max) max = min + 100;
  const pad = (max - min) * .08; min -= pad; max += pad;
  const n = fc.months.length, x = i => L + (n === 1 ? 0 : i * (W - L - R) / (n - 1)), y = v => T + (max - v) * (H - T - B) / (max - min);
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let k = 0; k <= 4; k++) { const v = min + (max - min) * k / 4; svg += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${Math.round(v / 100).toLocaleString('de-DE')} €</text>`; }
  svg += `<line x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}" stroke="var(--neg)" stroke-dasharray="4 3" opacity=".6"/>`;
  const step = Math.ceil(n / 12);
  fc.months.forEach((m, i) => { if (i % step === 0) svg += `<text x="${x(i)}" y="${H - 6}" text-anchor="middle">${fMonth(m.month)}</text>`; });
  const si = fc.months.findIndex(m => m.month === S.sel);
  if (si >= 0) svg += `<line x1="${x(si)}" x2="${x(si)}" y1="${T}" y2="${H - B}" stroke="var(--accent)" opacity=".5"/>`;
  for (const s of series.slice().reverse()) {
    let d = '', pen = false;
    s.vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; });
    svg += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w}" vector-effect="non-scaling-stroke"/>`;
  }
  const cw = (W - L - R) / Math.max(n - 1, 1);
  fc.months.forEach((m, i) => { svg += `<rect data-m="${m.month}" x="${x(i) - cw / 2}" y="${T}" width="${cw}" height="${H - T - B}" fill="transparent" style="cursor:pointer"><title>${fMonth(m.month)}: ${eur(m.closing)}</title></rect>`; });
  svg += '</svg>';
  $('#chart').innerHTML = svg + `<div class="legend">${series.map(s => `<span style="--c:${s.color}">${esc(s.name)}</span>`).join('')}</div>`;
  $('#chart').querySelectorAll('rect[data-m]').forEach(r => r.onclick = () => selectMonth(r.dataset.m));
}

function selectMonth(m) { S.sel = m; drawChart(S.fc); drawTable(S.fc); drawDetail(S.fc); }

function drawTable(fc) {
  const multi = fc.accounts.length > 1;
  let h = `<table><thead><tr><th>Monat (Monatsende)</th>${multi ? fc.accounts.map(a => `<th class="num">${esc(a.name)}</th>`).join('') : ''}<th class="num">Gesamt</th><th class="num">Veränderung</th></tr></thead><tbody>`;
  for (const m of fc.months) {
    const delta = m.closing - m.opening;
    h += `<tr class="clickable ${m.month === S.sel ? 'selected' : ''}" data-m="${m.month}"><td>${fMonth(m.month)}</td>`;
    if (multi) h += fc.accounts.map(a => { const c = m.accounts[a.id]?.closing; return `<td class="num ${eurCls(c)}">${eur(c)}</td>`; }).join('');
    h += `<td class="num ${eurCls(m.closing)}"><b>${eur(m.closing)}</b></td><td class="num">${signed(delta)}</td></tr>`;
  }
  $('#ftable').innerHTML = h + '</tbody></table>';
  $('#ftable').querySelectorAll('tr[data-m]').forEach(r => r.onclick = () => selectMonth(r.dataset.m));
}

function drawDetail(fc) {
  const m = fc.months.find(x => x.month === S.sel); if (!m) return;
  let h = `<h2>${fMonth(m.month)}</h2><div class="kv" style="margin-bottom:12px">
    <span class="muted">Einnahmen</span><span class="num pos" style="text-align:left">${eur(m.income)}</span>
    <span class="muted">Ausgaben</span><span class="num neg" style="text-align:left">${eur(m.expense)}</span>
    <span class="muted">Gesamtstand Monatsende</span><b class="${eurCls(m.closing)}">${eur(m.closing)}</b></div>`;
  for (const a of fc.accounts) {
    const am = m.accounts[a.id]; if (!am) continue;
    h += `<div class="acc-card"><div class="head"><span>${esc(a.name)}</span><span class="muted small">${KINDS[a.kind] || ''}</span></div>
      <div class="row sum"><span></span><span>Anfangsstand</span><span class="num ${eurCls(am.opening)}">${eur(am.opening)}</span></div>`;
    if (!am.items.length) h += `<div class="row"><span></span><span class="muted">Keine Buchungen in diesem Monat</span><span></span></div>`;
    for (const it of am.items) {
      if (it.type === 'checkpoint') {
        const label = it.deviation != null ? 'Ist-Stand eingetragen' : 'Startstand (Ist-Stand)';
        h += `<div class="row cp"><span>${fShort(it.date)}</span><span>${esc(label)}${it.note ? ` <span class="muted small">(${esc(it.note)})</span>` : ''}</span><span class="num"><b>${eur(it.balance)}</b></span>`;
        if (it.deviation != null) h += `<div class="expl"><div>Prognose war ${eur(it.expected)}, tatsächlich ${eur(it.balance)} → Abweichung ${it.deviation > 0 ? '+' : ''}${eur(it.deviation)}</div><div>Ab hier rechnet die Prognose mit dem echten Kontostand weiter.</div></div>`;
        else h += `<div class="expl"><div>Ausgangspunkt der Berechnung für dieses Konto</div></div>`;
        h += `</div>`;
      } else {
        h += `<div class="row"><span>${fShort(it.date)}</span><span><button class="link" data-entry="${it.entry_id}" title="Buchung bearbeiten">${esc(it.label)}</button>${it.category ? `<span class="tag">${esc(it.category)}</span>` : ''}</span><span class="num">${signed(it.amount)}</span>
          <div class="expl">${it.explanation.map(e => `<div>${esc(explLine(e))}</div>`).join('')}<div>Kontostand danach: ${eur(it.balance)}</div></div></div>`;
      }
    }
    h += `<div class="row sum"><span></span><span>Endstand</span><span class="num ${eurCls(am.closing)}">${eur(am.closing)}</span></div></div>`;
  }
  $('#fdetail').innerHTML = h;
  $('#fdetail').querySelectorAll('[data-entry]').forEach(b => b.onclick = () => entryDialog(S.data.entries.find(e => e.id === +b.dataset.entry)));
}

// ------------------------------------------------------------ Buchungen
function entryType(e) { return e.to_account_id ? 'transfer' : e.amount < 0 ? 'expense' : 'income'; }

async function entryDialog(e = null) {
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

async function renderEntries(main) {
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

// ------------------------------------------------------------ Konten
async function accountDialog(acc = null) {
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

async function checkpointDialog(accountId = null, cp = null) {
  const accs = activeAccounts();
  if (!accs.length) { toast('Bitte zuerst ein Konto anlegen', true); return; }
  const ok = await formDialog({
    title: cp ? 'Ist-Stand bearbeiten' : 'Ist-Stand eintragen',
    intro: '<p class="small muted">Trage den tatsächlichen Kontostand ein (z. B. aus dem Online-Banking). Die Prognose rechnet ab diesem Tag mit dem echten Wert weiter und zeigt die Abweichung an. Buchungen am selben Tag gelten als bereits enthalten.</p>',
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

async function renderAccounts(main) {
  const accs = S.data.accounts.filter(a => S.showArchived || !a.archived);
  main.innerHTML = `<div class="toolbar"><h2 style="margin:0">Konten &amp; Ist-Stände</h2><span class="spacer"></span>
    <label><input type="checkbox" id="arch" ${S.showArchived ? 'checked' : ''}> Archivierte zeigen</label>
    <button class="primary" id="new">+ Neues Konto</button></div>
    <div class="cards">${accs.map(a => {
      const cps = S.data.checkpoints.filter(c => c.account_id === a.id && (S.showArchived || !c.archived)).sort((x, y) => y.date.localeCompare(x.date));
      const last = cps.find(c => !c.archived);
      const active = cps.filter(c => !c.archived);
      const startId = active.length ? active.reduce((min, c) => c.date < min.date ? c : min).id : null;
      return `<div class="panel ${a.archived ? 'archived' : ''}" style="${a.archived ? 'opacity:.55' : ''}">
        <div class="toolbar" style="margin-bottom:6px"><h3 style="margin:0">${esc(a.name)}</h3><span class="tag">${KINDS[a.kind] || a.kind}</span><span class="spacer"></span>
        ${a.archived ? `<button class="small" data-restore="${a.id}">Wiederherstellen</button>` : `<button class="small" data-edit="${a.id}">Bearbeiten</button><button class="small" data-arch="${a.id}">Archivieren</button>`}</div>
        ${a.note ? `<p class="small muted">${esc(a.note)}</p>` : ''}
        <div class="kv"><span class="muted">Letzter Ist-Stand</span><span>${last ? `<b>${eur(last.balance)}</b> am ${fDate(last.date)}` : '<span class="neg">keiner – Konto wird nicht berechnet</span>'}</span></div>
        <div class="toolbar" style="margin:12px 0 4px"><b class="small">Ist-Stände</b><span class="spacer"></span>${a.archived ? '' : `<button class="small primary" data-cp="${a.id}">+ Ist-Stand</button>`}</div>
        <table><tbody>${cps.map(c => `<tr class="${c.archived ? 'archived' : ''}"><td>${fDate(c.date)}${c.id === startId ? ' <span class="tag">Startstand</span>' : ''}</td><td class="num ${eurCls(c.balance)}">${eur(c.balance)}</td><td class="small muted">${esc(c.note)}</td>
          <td style="white-space:nowrap;text-align:right">${c.archived ? `<button class="small" data-cprestore="${c.id}">Wiederherstellen</button>` : `<button class="small" data-cpedit="${c.id}">Bearbeiten</button> <button class="small" data-cparch="${c.id}">Archivieren</button>`}</td></tr>`).join('')}</tbody></table>
      </div>`;
    }).join('') || '<div class="panel muted">Noch keine Konten.</div>'}</div>`;
  const fa = id => S.data.accounts.find(a => a.id === +id), fc = id => S.data.checkpoints.find(c => c.id === +id);
  $('#arch').onchange = ev => { S.showArchived = ev.target.checked; renderAccounts(main); };
  $('#new').onclick = () => accountDialog();
  main.querySelectorAll('[data-edit]').forEach(b => b.onclick = () => accountDialog(fa(b.dataset.edit)));
  main.querySelectorAll('[data-arch]').forEach(b => b.onclick = () => archiveDialog('accounts', fa(b.dataset.arch), fa(b.dataset.arch).name));
  main.querySelectorAll('[data-restore]').forEach(b => b.onclick = () => restoreRow('accounts', fa(b.dataset.restore)));
  main.querySelectorAll('[data-cp]').forEach(b => b.onclick = () => checkpointDialog(+b.dataset.cp));
  main.querySelectorAll('[data-cpedit]').forEach(b => b.onclick = () => { const c = fc(b.dataset.cpedit); checkpointDialog(c.account_id, c); });
  main.querySelectorAll('[data-cparch]').forEach(b => b.onclick = () => { const c = fc(b.dataset.cparch); archiveDialog('checkpoints', c, `Ist-Stand vom ${fDate(c.date)}`); });
  main.querySelectorAll('[data-cprestore]').forEach(b => b.onclick = () => restoreRow('checkpoints', fc(b.dataset.cprestore)));
}

// ------------------------------------------------------------ Verlauf
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
async function renderAudit(main) {
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
async function historyDialog(entity, id) {
  const rows = await api('GET', `/api/audit?entity=${entity}&entity_id=${id}&limit=500`);
  const dlg = document.createElement('dialog'); dlg.style.width = 'min(900px,96vw)';
  dlg.innerHTML = `<div class="body"><h3>Verlauf</h3><div class="table-wrap"><table><tbody>${auditRows(rows)}</tbody></table></div><div class="actions"><button data-close>Schließen</button></div></div>`;
  $('[data-close]', dlg).onclick = () => dlg.close();
  dlg.addEventListener('close', () => { dlg.remove(); refresh(); });
  bindRevert(dlg, () => dlg.close());
  document.body.append(dlg); dlg.showModal();
}

// ------------------------------------------------------------ Sicherung
async function refreshBackupPill() {
  const pill = $('#backupPill');
  try {
    const st = await api('GET', '/api/backup/status');
    if (st.last_result === 'error') { pill.className = 'pill err'; pill.textContent = 'Sicherung fehlgeschlagen!'; }
    else if (!st.last_success) { pill.className = 'pill warn'; pill.textContent = 'Noch keine Sicherung'; }
    else { pill.className = 'pill ok'; pill.textContent = `Gesichert ${new Date(st.last_success).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' })}${st.pending_changes ? ' · neue Änderungen' : ''}`; }
    return st;
  } catch { pill.className = 'pill err'; pill.textContent = 'Server nicht erreichbar'; }
}
async function renderBackup(main) {
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

// ------------------------------------------------------------ Start
(async () => {
  try { await load(); await render(); } catch (ex) { $('#main').innerHTML = `<div class="banner err">${esc(ex.message)}</div>`; }
  refreshBackupPill(); setInterval(refreshBackupPill, 5 * 60 * 1000);
})();
