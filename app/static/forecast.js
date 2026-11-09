// ------------------------------------------------------------ Prognose
import { $, esc, eur, eurCls, signed, fShort, fMonth, thisMonth, api, KINDS, COLORS, warnMsg, explLine, S } from './core.js';
import { entryDialog } from './entries.js';
import { accountDialog, checkpointDialog } from './accounts.js';

export async function renderForecast(main) {
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
