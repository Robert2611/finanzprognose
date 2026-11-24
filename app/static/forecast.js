// ------------------------------------------------------------ Prognose
import { html, svg, render as renderLit, nothing } from './vendor/lit-html.js';
import { $, eur, eurCls, signed, approx, ESTIMATE_NOTE, fShort, fMonth, thisMonth, api, KINDS, COLORS, warnMsg, explLine, S } from './core.js';
import { entryDialog, recurringDialog, onceDialog } from './entry_dialogs.js';
import { accountDialog, checkpointDialog } from './accounts.js';
import { DIMENSIONS, groupItems, getDimension, isOpen, toggleGroup, dimensionSelect } from './grouping.js';
import { optionalPanelTpl, includeQuery } from './optional.js';

export async function renderForecast(main) {
  if (!S.data.accounts.length) {
    renderLit(html`<div class="panel"><h2>Willkommen</h2><p>Lege zuerst ein Konto mit seinem aktuellen Kontostand an. Danach trägst du wiederkehrende und einmalige Buchungen ein – die Prognose entsteht automatisch.</p><button class="primary" @click=${() => accountDialog()}>Erstes Konto anlegen</button></div>`, main);
    return;
  }
  renderLit(html`<div class="toolbar">
      <label>Ab <input type="month" .value=${S.from} @change=${e => { S.from = e.target.value || thisMonth(); S.sel = null; renderForecast(main); }}></label>
      <label>Zeitraum <select @change=${e => { S.months = +e.target.value; renderForecast(main); }}>${[12, 24, 36, 60, 120].map(n => html`<option value=${n} ?selected=${n == S.months}>${n} Monate</option>`)}</select></label>
      <button @click=${() => { S.from = thisMonth(); S.sel = null; renderForecast(main); }}>Heute</button>
      ${dimensionSelect('prognose', () => S.fc && drawDetail(S.fc))}<span class="spacer"></span>
      <button class="primary" @click=${() => recurringDialog()}>+ Wiederkehrend</button><button @click=${() => onceDialog()}>+ Einmalig</button><button @click=${() => checkpointDialog()}>+ Ist-Stand</button></div>
    <div id="warn"></div>${optionalPanelTpl(() => renderForecast(main))}<div class="panel" style="margin-bottom:16px"><div id="chart"></div></div>
    <div class="fc-layout"><div class="panel table-wrap" id="ftable"></div><div class="panel detail" id="fdetail"></div></div>`, main);
  const fc = S.fc = await api('GET', `/api/forecast?start=${S.from}&months=${S.months}${includeQuery()}`);
  if (S.view !== 'prognose') return; // navigated away while loading: #chart etc. are gone, don't clobber the new view
  if (!S.sel || !fc.months.some(m => m.month === S.sel)) S.sel = fc.months[0].month;
  const neg = fc.months.find(m => mainClosing(fc, m) < 0);
  const what = hasReserve(fc) ? 'das verfügbare Geld (ohne Rücklagen)' : 'der Gesamtstand';
  renderLit(html`${fc.warnings.map(w => html`<div class="banner warn">${warnMsg(w)}</div>`)}
    ${neg ? html`<div class="banner err">Achtung: Im ${fMonth(neg.month)} wird ${what} voraussichtlich negativ (${eur(mainClosing(fc, neg))}).</div>` : ''}`, $('#warn'));
  drawChart(fc);
  drawTable(fc);
  drawDetail(fc);
}

// B-028: with reserve accounts, the page is about the available money (all other accounts);
// without any, that is simply the total, and the page looks as before.
const hasReserve = fc => fc.accounts.some(a => a.reserve);
/** The month-end amount the page is about: the available money, or the total without reserve accounts. */
const mainClosing = (fc, m) => hasReserve(fc) ? m.available_closing : m.closing;
const mainOpening = (fc, m) => hasReserve(fc) ? m.available_opening : m.opening;
const mainLabel = fc => hasReserve(fc) ? 'Verfügbar' : 'Gesamt';
/** B-029: the main month-end amount with every optional booking counted. */
const withOptional = (fc, m) => hasReserve(fc) ? m.with_optional.available_closing : m.with_optional.closing;
const optTag = it => it.optional ? html`<span class="tag optional">optional</span>` : nothing;
const reserveTag = a => a.reserve ? html`<span class="tag reserve" title="nicht zum Verplanen">Rücklage</span>` : nothing;

function chartTpl(fc) {
  const W = 1000, H = 250, L = 70, R = 10, T = 10, B = 26;
  const series = [{ name: mainLabel(fc), color: 'var(--ink)', vals: fc.months.map(m => mainClosing(fc, m)), w: 2.5 }];
  // B-029: what the main line would be with every optional booking, dashed
  if (fc.months.some(m => m.with_optional)) series.push({ name: 'mit optionalen Posten', color: 'var(--ink)', dash: '6 4', w: 1.5,
    vals: fc.months.map(m => m.with_optional ? (hasReserve(fc) ? m.with_optional.available_closing : m.with_optional.closing) : mainClosing(fc, m)) });
  if (fc.accounts.length > 1) fc.accounts.forEach((a, i) => series.push({ name: a.name, color: COLORS[i % COLORS.length], vals: fc.months.map(m => m.accounts[a.id]?.closing ?? null), w: 1.5 }));
  const all = series.flatMap(s => s.vals).filter(v => v != null).concat([0]);
  let min = Math.min(...all), max = Math.max(...all); if (min === max) max = min + 100;
  const pad = (max - min) * .08; min -= pad; max += pad;
  const n = fc.months.length, x = i => L + (n === 1 ? 0 : i * (W - L - R) / (n - 1)), y = v => T + (max - v) * (H - T - B) / (max - min);
  const gridLevels = [0, 1, 2, 3, 4].map(k => min + (max - min) * k / 4);
  const step = Math.ceil(n / 12);
  const si = fc.months.findIndex(m => m.month === S.sel);
  const cw = (W - L - R) / Math.max(n - 1, 1);
  const pathD = s => { let d = '', pen = false; s.vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; }); return d; };
  // Nested sub-templates that produce bare SVG elements (no <svg> wrapper of their own) must
  // use the svg tag, not html - otherwise the HTML parser creates them in the wrong namespace
  // and the browser silently fails to render them.
  return html`<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      ${gridLevels.map(v => svg`<line x1=${L} x2=${W - R} y1=${y(v)} y2=${y(v)} stroke="var(--line)"></line><text x=${L - 6} y=${y(v) + 4} text-anchor="end">${Math.round(v / 100).toLocaleString('de-DE')} €</text>`)}
      <line x1=${L} x2=${W - R} y1=${y(0)} y2=${y(0)} stroke="var(--neg)" stroke-dasharray="4 3" opacity=".6"></line>
      ${fc.months.map((m, i) => i % step === 0 ? svg`<text x=${x(i)} y=${H - 6} text-anchor="middle">${fMonth(m.month)}</text>` : nothing)}
      ${si >= 0 ? svg`<line x1=${x(si)} x2=${x(si)} y1=${T} y2=${H - B} stroke="var(--accent)" opacity=".5"></line>` : nothing}
      ${series.slice().reverse().map(s => svg`<path d=${pathD(s)} fill="none" stroke=${s.color} stroke-width=${s.w} stroke-dasharray=${s.dash ?? nothing} vector-effect="non-scaling-stroke"></path>`)}
      ${fc.months.map((m, i) => svg`<rect x=${x(i) - cw / 2} y=${T} width=${cw} height=${H - T - B} fill="transparent" style="cursor:pointer" @click=${() => selectMonth(m.month)}><title>${fMonth(m.month)}: ${eur(mainClosing(fc, m))}</title></rect>`)}
    </svg>
    <div class="legend">${series.map(s => html`<span class=${s.dash ? 'dashed' : ''} style="--c:${s.color}">${s.name}</span>`)}</div>`;
}

function drawChart(fc) { renderLit(chartTpl(fc), $('#chart')); }

function selectMonth(m) { S.sel = m; drawChart(S.fc); drawTable(S.fc); drawDetail(S.fc); }

function tableTpl(fc) {
  const multi = fc.accounts.length > 1, res = hasReserve(fc);
  return html`<table><thead><tr><th>Monat (Monatsende)</th>${multi ? fc.accounts.map(a => html`<th class="num">${a.name}${a.reserve ? html`<div class="small muted">Rücklage</div>` : nothing}</th>`) : nothing}<th class="num">${mainLabel(fc)}</th><th class="num">Veränderung</th>${res ? html`<th class="num">Gesamt</th>` : nothing}</tr></thead><tbody>
      ${fc.months.map(m => {
        const total = mainClosing(fc, m), delta = total - mainOpening(fc, m);
        return html`<tr class="clickable ${m.month === S.sel ? 'selected' : ''}" @click=${() => selectMonth(m.month)}><td>${fMonth(m.month)}</td>
          ${multi ? fc.accounts.map(a => { const c = m.accounts[a.id]?.closing; return html`<td class="num ${eurCls(c)}">${eur(c)}</td>`; }) : nothing}
          <td class="num ${eurCls(total)}"><b>${eur(total)}</b></td><td class="num">${signed(delta)}</td>${res ? html`<td class="num muted ${eurCls(m.closing)}">${eur(m.closing)}</td>` : nothing}</tr>`;
      })}
    </tbody></table>`;
}

function drawTable(fc) { renderLit(tableTpl(fc), $('#ftable')); }

function itemTpl(it) {
  if (it.type === 'checkpoint') {
    const label = it.deviation != null ? 'Ist-Stand eingetragen' : 'Startstand (Ist-Stand)';
    return html`<div class="row cp"><span>${fShort(it.date)}</span><span>${label}${it.note ? html` <span class="muted small">(${it.note})</span>` : ''}</span><span class="num"><b>${eur(it.balance)}</b></span>
        ${it.deviation != null
          ? html`<div class="expl"><div>Prognose war ${eur(it.expected)}, tatsächlich ${eur(it.balance)} → Abweichung ${it.deviation > 0 ? '+' : ''}${eur(it.deviation)}</div><div>Ab hier rechnet die Prognose mit dem echten Kontostand weiter.</div></div>`
          : html`<div class="expl"><div>Ausgangspunkt der Berechnung für dieses Konto</div></div>`}
      </div>`;
  }
  return html`<div class="row"><span>${fShort(it.date)}</span><span><button class="link" title="Buchung bearbeiten" @click=${() => entryDialog(S.data.entries.find(e => e.id === it.entry_id))}>${it.label}</button>${it.category ? html`<span class="tag">${it.category}</span>` : ''}${optTag(it)}</span><span class="num">${approx(it.estimated)}${signed(it.amount)}</span>
      <div class="expl">${explTpl(it)}<div>Kontostand danach: ${eur(it.balance)}</div></div></div>`;
}

/** The explanation lines of a booking/transfer item, plus a note when its amount is an estimate. */
const explTpl = it => html`${it.explanation.map(e => html`<div>${explLine(e)}</div>`)}${it.estimated ? html`<div>${ESTIMATE_NOTE}</div>` : ''}`;

/** The estimated part of the month's income and expense (bookings only, like the totals). */
function estimatedTotals(m) {
  const t = { income: 0, expense: 0 };
  for (const a of Object.values(m.accounts)) for (const it of a.items) {
    if (it.type === 'booking' && it.estimated) t[it.amount > 0 ? 'income' : 'expense'] += it.amount;
  }
  return t;
}

function detailTpl(fc) {
  const m = fc.months.find(x => x.month === S.sel); if (!m) return html``;
  const est = estimatedTotals(m);
  const estRow = (c, cls) => c ? html`<span class="muted est-part">davon geschätzt</span><span class="num ${cls} est-part" style="text-align:left">≈ ${eur(c)}</span>` : nothing;
  return html`<h2>${fMonth(m.month)}</h2><div class="kv" style="margin-bottom:12px">
      <span class="muted">Einnahmen</span><span class="num pos" style="text-align:left">${eur(m.income)}</span>${estRow(est.income, 'pos')}
      <span class="muted">Ausgaben</span><span class="num neg" style="text-align:left">${eur(m.expense)}</span>${estRow(est.expense, 'neg')}
      ${hasReserve(fc) ? html`${m.to_reserve ? html`<span class="muted">${m.to_reserve > 0 ? 'In Rücklage gelegt' : 'Aus Rücklage entnommen'}</span><span class="num to-reserve" style="text-align:left">${eur(Math.abs(m.to_reserve))}</span>` : nothing}
        <span class="muted">Verfügbar Monatsende</span><b class="${eurCls(m.available_closing)}">${eur(m.available_closing)}</b>
        <span class="muted">Gesamtstand Monatsende</span><span class="${eurCls(m.closing)}">${eur(m.closing)}</span>`
      : html`<span class="muted">Gesamtstand Monatsende</span><b class="${eurCls(m.closing)}">${eur(m.closing)}</b>`}
      ${m.with_optional ? html`<span class="muted">mit allen optionalen Posten</span><span class="with-optional ${eurCls(withOptional(fc, m))}">${eur(withOptional(fc, m))}</span>` : nothing}</div>
    ${getDimension('prognose') !== 'none' ? groupedTpl(fc, m) : fc.accounts.map(a => {
      const am = m.accounts[a.id]; if (!am) return nothing;
      return html`<div class="acc-card"><div class="head"><span>${a.name}${reserveTag(a)}</span><span class="muted small">${KINDS[a.kind] || ''}</span></div>
        <div class="row sum"><span></span><span>Anfangsstand</span><span class="num ${eurCls(am.opening)}">${eur(am.opening)}</span></div>
        ${!am.items.length ? html`<div class="row"><span></span><span class="muted">Keine Buchungen in diesem Monat</span><span></span></div>` : nothing}
        ${am.items.map(itemTpl)}
        <div class="row sum"><span></span><span>Endstand</span><span class="num ${eurCls(am.closing)}">${eur(am.closing)}</span></div></div>`;
    })}`;
}

/** The month's bookings grouped by the chosen dimension, with a subtotal per group. A transfer is
 *  counted once (its source side), except under "Konto", where each side belongs to its account.
 *  Transfers are listed but kept out of the subtotal, like in the monthly income/expense totals. */
function groupedTpl(fc, m) {
  const dim = getDimension('prognose');
  const multi = fc.accounts.length > 1;
  const items = fc.accounts.flatMap(a => (m.accounts[a.id]?.items ?? [])
    .filter(it => it.type !== 'checkpoint' && !(it.type === 'transfer' && it.amount > 0 && dim !== 'account'))
    .map(it => ({ ...it, accountId: a.id })));
  if (!items.length) return html`<p class="muted">Keine Buchungen in diesem Monat</p>`;
  const entryOf = it => S.data.entries.find(e => e.id === it.entry_id);
  const groups = groupItems(items, it => DIMENSIONS[dim].key(entryOf(it), it.accountId));
  return groups.map(g => {
    const open = isOpen('prognose', dim, g.key, false);
    const toggle = () => { toggleGroup('prognose', dim, g.key); drawDetail(S.fc); };
    const bookings = g.items.filter(it => it.type === 'booking'), transfers = g.items.filter(it => it.type === 'transfer');
    const sum = bookings.reduce((t, it) => t + it.amount, 0);
    const est = list => approx(list.some(it => it.estimated));
    return html`<div class="acc-card group"><div class="head"><button class="link" aria-expanded=${open} @click=${toggle}>${open ? '▾' : '▸'} ${g.label}</button>
        <span class="num">${bookings.length ? html`<span class="group-sum">${est(bookings)}${signed(sum)}</span>` : ''}${transfers.length
          ? html` <span class="muted small">Umbuchungen</span> <span class="group-transfers">${est(transfers)}${eur(transfers.reduce((t, it) => t + Math.abs(it.amount), 0))}</span>` : ''}</span></div>
      ${open ? g.items.map(it => html`<div class="row"><span>${fShort(it.date)}</span><span><button class="link" title="Buchung bearbeiten" @click=${() => entryDialog(entryOf(it))}>${it.label}</button>${optTag(it)}${multi && dim !== 'account' ? html`<span class="tag">${fc.accounts.find(a => a.id === it.accountId)?.name}</span>` : ''}</span><span class="num">${approx(it.estimated)}${signed(it.amount)}</span>
          <div class="expl">${explTpl(it)}</div></div>`) : ''}</div>`;
  });
}

function drawDetail(fc) { renderLit(detailTpl(fc), $('#fdetail')); }
