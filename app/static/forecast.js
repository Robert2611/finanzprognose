// ------------------------------------------------------------ Prognose
import { html, render as renderLit, nothing } from './vendor/lit-html.js';
import { $, eur, eurCls, signed, approx, ESTIMATE_NOTE, fShort, fMonth, thisMonth, api, KINDS, warnMsg, explLine, S } from './core.js';
import { entryDialog, recurringDialog, onceDialog } from './entry_dialogs.js';
import { accountDialog, checkpointDialog } from './accounts.js';
import { DIMENSIONS, groupItems, getDimension, isOpen, toggleGroup, dimensionSelect } from './grouping.js';
import { optionalPanelTpl, includeQuery } from './optional.js';
import { chartTpl, hasReserve, mainClosing, mainOpening, mainLabel, withOptional } from './forecast_chart.js';
import { eventsByMonth } from './events.js';

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

const optTag = it => it.optional ? html`<span class="tag optional">optional</span>` : nothing;
const reserveTag = a => a.reserve ? html`<span class="tag reserve" title="nicht zum Verplanen">Rücklage</span>` : nothing;

function drawChart(fc) { renderLit(chartTpl(fc, selectMonth, () => drawChart(S.fc)), $('#chart')); }

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

/** B-030: the month's events (one-time bookings, adjustments, recurring bookings starting or ending). */
function eventsTpl(fc, m) {
  const list = eventsByMonth(fc).get(m.month);
  if (!list) return nothing;
  return html`<div class="events"><b class="small">Ereignisse in diesem Monat</b><ul>${list.map(ev => html`<li class="event" data-kind=${ev.kind}>${ev.text}</li>`)}</ul></div>`;
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
    ${eventsTpl(fc, m)}
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
