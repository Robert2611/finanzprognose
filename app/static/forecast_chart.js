// ------------------------------------------------------------ Prognose-Diagramm (B-030)
// Two views of the forecast, switched by the „Überschuss pro Monat“ / „Kontostand“ buttons:
//  - flow (default): one bar per month with the month's bookings, split by how routine they are,
//    a marker for the month's surplus, and markers for the month's events;
//  - balance: the month-end balances as lines (the chart before B-030).
// Nested sub-templates that produce bare SVG elements must use the svg tag, not html - otherwise the
// HTML parser creates them in the wrong namespace and the browser silently fails to render them.
import { html, svg, nothing } from './vendor/lit-html.js';
import { eur, fMonth, COLORS, S } from './core.js';
import { eventsByMonth } from './events.js';

// B-028: with reserve accounts, the page is about the available money (all other accounts);
// without any, that is simply the total, and the page looks as before.
export const hasReserve = fc => fc.accounts.some(a => a.reserve);
/** The month-end amount the page is about: the available money, or the total without reserve accounts. */
export const mainClosing = (fc, m) => hasReserve(fc) ? m.available_closing : m.closing;
export const mainOpening = (fc, m) => hasReserve(fc) ? m.available_opening : m.opening;
export const mainLabel = fc => hasReserve(fc) ? 'Verfügbar' : 'Gesamt';
/** B-029: the main month-end amount with every optional booking counted. */
export const withOptional = (fc, m) => hasReserve(fc) ? m.with_optional.available_closing : m.with_optional.closing;

// ---- chart mode (remembered in the browser; without storage it lasts until reload)
const MODE_KEY = 'finanzprognose.chartMode';
let mode = null;
function getMode() {
  if (mode == null) {
    try { mode = localStorage.getItem(MODE_KEY); } catch { /* storage unavailable */ }
    if (mode !== 'balance') mode = 'flow';
  }
  return mode;
}
function setMode(m) { mode = m; try { localStorage.setItem(MODE_KEY, m); } catch { /* storage unavailable */ } }

const W = 1000, H = 250, L = 70, R = 10, B = 26;
const axisLabel = v => `${Math.round(v / 100).toLocaleString('de-DE')} €`;
const scale = (vals, T) => {
  let min = Math.min(0, ...vals), max = Math.max(0, ...vals); if (min === max) max = min + 100;
  const pad = (max - min) * .08; min -= pad; max += pad;
  return { min, max, y: v => T + (max - v) * (H - T - B) / (max - min) };
};

/** The chart with its mode buttons; `onSelect(month)` selects a month, `redraw()` re-renders the chart. */
export function chartTpl(fc, onSelect, redraw) {
  const m = getMode();
  const btn = (key, label) => html`<button class="small ${m === key ? 'active' : ''}" aria-pressed=${m === key} data-mode=${key}
    @click=${() => { setMode(key); redraw(); }}>${label}</button>`;
  return html`<div class="chart-mode">${btn('flow', 'Überschuss pro Monat')}${btn('balance', 'Kontostand')}</div>
    ${m === 'balance' ? balanceTpl(fc, onSelect) : flowTpl(fc, onSelect)}`;
}

// ------------------------------------------------------------ Kontostand (lines)
function balanceTpl(fc, onSelect) {
  const T = 10;
  const series = [{ name: mainLabel(fc), color: 'var(--ink)', vals: fc.months.map(m => mainClosing(fc, m)), w: 2.5 }];
  // B-029: what the main line would be with every optional booking, dashed
  if (fc.months.some(m => m.with_optional)) series.push({ name: 'mit optionalen Posten', color: 'var(--ink)', dash: '6 4', w: 1.5,
    vals: fc.months.map(m => m.with_optional ? withOptional(fc, m) : mainClosing(fc, m)) });
  if (fc.accounts.length > 1) fc.accounts.forEach((a, i) => series.push({ name: a.name, color: COLORS[i % COLORS.length], vals: fc.months.map(m => m.accounts[a.id]?.closing ?? null), w: 1.5 }));
  const { min, max, y } = scale(series.flatMap(s => s.vals).filter(v => v != null), T);
  const n = fc.months.length, x = i => L + (n === 1 ? 0 : i * (W - L - R) / (n - 1));
  const gridLevels = [0, 1, 2, 3, 4].map(k => min + (max - min) * k / 4);
  const step = Math.ceil(n / 12);
  const si = fc.months.findIndex(m => m.month === S.sel);
  const cw = (W - L - R) / Math.max(n - 1, 1);
  const pathD = s => { let d = '', pen = false; s.vals.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`; pen = true; }); return d; };
  return html`<svg class="chart" data-mode="balance" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      ${gridLevels.map(v => svg`<line x1=${L} x2=${W - R} y1=${y(v)} y2=${y(v)} stroke="var(--line)"></line><text x=${L - 6} y=${y(v) + 4} text-anchor="end">${axisLabel(v)}</text>`)}
      <line x1=${L} x2=${W - R} y1=${y(0)} y2=${y(0)} stroke="var(--neg)" stroke-dasharray="4 3" opacity=".6"></line>
      ${fc.months.map((m, i) => i % step === 0 ? svg`<text x=${x(i)} y=${H - 6} text-anchor="middle">${fMonth(m.month)}</text>` : nothing)}
      ${si >= 0 ? svg`<line x1=${x(si)} x2=${x(si)} y1=${T} y2=${H - B} stroke="var(--accent)" opacity=".5"></line>` : nothing}
      ${series.slice().reverse().map(s => svg`<path d=${pathD(s)} fill="none" stroke=${s.color} stroke-width=${s.w} stroke-dasharray=${s.dash ?? nothing} vector-effect="non-scaling-stroke"></path>`)}
      ${fc.months.map((m, i) => svg`<rect x=${x(i) - cw / 2} y=${T} width=${cw} height=${H - T - B} fill="transparent" style="cursor:pointer" @click=${() => onSelect(m.month)}><title>${fMonth(m.month)}: ${eur(mainClosing(fc, m))}</title></rect>`)}
    </svg>
    <div class="legend">${series.map(s => html`<span class=${s.dash ? 'dashed' : ''} style="--c:${s.color}">${s.name}</span>`)}</div>`;
}

// ------------------------------------------------------------ Überschuss pro Monat (bars)
/** Bar segment classes, bottom-up from zero, with label and color. */
export const FLOW_CLASSES = {
  monthly: { label: 'Monatlich wiederkehrend', color: '#8a96a8' },
  irregular: { label: 'Seltener wiederkehrend (z. B. jährlich)', color: '#d9822b' },
  once: { label: 'Einmalig', color: '#8e5bd9' },
  reserve: { label: 'Rücklage', color: '#1a9e77' },
};
const CLASS_ORDER = Object.keys(FLOW_CLASSES);

/** The month's cash flow of the money the page is about: its bookings (on the available accounts
 *  when there are reserve accounts) by class, estimated and optional kept apart, plus the reserve
 *  flow. Transfers between counted accounts cancel out and are left out. */
export function monthFlow(fc, m) {
  const res = hasReserve(fc);
  const entries = new Map(S.data.entries.map(e => [e.id, e]));
  const segs = new Map();
  const add = (cls, est, opt, amount) => {
    const k = `${cls}|${est}|${opt}|${amount > 0}`;
    const s = segs.get(k) ?? { cls, est, opt, amount: 0 };
    s.amount += amount; segs.set(k, s);
  };
  for (const a of fc.accounts) {
    if (res && a.reserve) continue;
    for (const it of m.accounts[a.id]?.items ?? []) {
      if (it.type !== 'booking') continue;
      const e = entries.get(it.entry_id);
      const cls = !e || e.kind === 'once' ? 'once' : e.interval_months === 1 ? 'monthly' : 'irregular';
      add(cls, !!it.estimated, !!it.optional, it.amount);
    }
  }
  if (res && m.to_reserve) add('reserve', false, false, -m.to_reserve);
  const order = s => CLASS_ORDER.indexOf(s.cls) * 4 + s.est * 2 + s.opt;
  const list = [...segs.values()].filter(s => s.amount).sort((x, y) => order(x) - order(y));
  return {
    up: list.filter(s => s.amount > 0), down: list.filter(s => s.amount < 0),
    net: list.reduce((t, s) => t + s.amount, 0),
    income: list.filter(s => s.amount > 0).reduce((t, s) => t + s.amount, 0),
    expense: list.filter(s => s.amount < 0).reduce((t, s) => t + s.amount, 0),
  };
}

function flowTpl(fc, onSelect) {
  const T = 24;
  const flows = fc.months.map(m => monthFlow(fc, m));
  const events = eventsByMonth(fc);
  const { min, max, y } = scale(flows.flatMap(f => [f.income, f.expense, f.net]), T);
  const n = fc.months.length, cw = (W - L - R) / n, x = i => L + cw * (i + .5), bw = Math.max(cw * .62, 2);
  const gridLevels = [0, 1, 2, 3, 4].map(k => min + (max - min) * k / 4);
  const step = Math.ceil(n / 12);
  const signedEur = v => `${v > 0 ? '+' : ''}${eur(v)}`;
  const segRects = (i, list) => {
    let acc = 0;
    return list.map(s => {
      const y0 = y(acc), y1 = y(acc + s.amount); acc += s.amount;
      return svg`<rect class="seg" data-cls=${s.cls} data-est=${s.est ? '1' : '0'} data-opt=${s.opt ? '1' : '0'} data-amount=${s.amount}
        x=${x(i) - bw / 2} y=${Math.min(y0, y1)} width=${bw} height=${Math.max(Math.abs(y1 - y0), .5)}
        fill=${FLOW_CLASSES[s.cls].color} fill-opacity=${s.opt ? .25 : s.est ? .45 : .9}
        stroke=${s.opt ? FLOW_CLASSES[s.cls].color : nothing} stroke-dasharray=${s.opt ? '4 3' : nothing} vector-effect="non-scaling-stroke"></rect>`;
    });
  };
  const anyEst = flows.some(f => [...f.up, ...f.down].some(s => s.est));
  const anyOpt = flows.some(f => [...f.up, ...f.down].some(s => s.opt));
  const used = new Set(flows.flatMap(f => [...f.up, ...f.down].map(s => s.cls)));
  return html`<svg class="chart" data-mode="flow" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      ${gridLevels.map(v => svg`<line x1=${L} x2=${W - R} y1=${y(v)} y2=${y(v)} stroke="var(--line)"></line><text x=${L - 6} y=${y(v) + 4} text-anchor="end">${axisLabel(v)}</text>`)}
      ${fc.months.map((m, i) => m.month === S.sel ? svg`<rect x=${x(i) - cw / 2} y=${T} width=${cw} height=${H - T - B} fill="var(--accent)" opacity=".08"></rect>` : nothing)}
      ${fc.months.map((m, i) => i % step === 0 ? svg`<text x=${x(i)} y=${H - 6} text-anchor="middle">${fMonth(m.month)}</text>` : nothing)}
      ${flows.map((f, i) => svg`<g class="bar" data-month=${fc.months[i].month}>${segRects(i, f.up)}${segRects(i, f.down)}
        <line class="net" data-amount=${f.net} x1=${x(i) - bw / 2 - 2} x2=${x(i) + bw / 2 + 2} y1=${y(f.net)} y2=${y(f.net)} stroke="var(--ink)" stroke-width="2.5" vector-effect="non-scaling-stroke"></line></g>`)}
      <line x1=${L} x2=${W - R} y1=${y(0)} y2=${y(0)} stroke="var(--ink)" opacity=".5"></line>
      ${fc.months.map((m, i) => events.has(m.month) ? svg`<circle class="event-mark" data-month=${m.month} data-count=${events.get(m.month).length}
        cx=${x(i)} cy=${T - 12} r="4.5" fill="var(--accent)" vector-effect="non-scaling-stroke"></circle>` : nothing)}
      ${fc.months.map((m, i) => svg`<rect x=${x(i) - cw / 2} y="0" width=${cw} height=${H - B} fill="transparent" style="cursor:pointer" @click=${() => onSelect(m.month)}><title>${[
        `${fMonth(m.month)}: Überschuss ${signedEur(flows[i].net)}`, `Einnahmen ${eur(flows[i].income)}, Ausgaben ${eur(flows[i].expense)}`,
        ...(events.get(m.month) ?? []).map(ev => `• ${ev.text}`)].join('\n')}</title></rect>`)}
    </svg>
    <div class="legend">${CLASS_ORDER.filter(c => used.has(c)).map(c => html`<span style="--c:${FLOW_CLASSES[c].color}">${FLOW_CLASSES[c].label}</span>`)}
      <span class="net-key" style="--c:var(--ink)">Überschuss des Monats</span>
      ${events.size ? html`<span class="event-key" style="--c:var(--accent)">Ereignis (Einmaliges, Anpassung, Beginn/Ende)</span>` : nothing}
      ${anyEst || anyOpt ? html`<span class="legend-note muted">${[anyEst && 'heller = geschätzt', anyOpt && 'gestrichelt = optional'].filter(Boolean).join(' · ')}</span>` : nothing}</div>`;
}
