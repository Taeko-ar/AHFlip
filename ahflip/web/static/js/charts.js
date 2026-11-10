// Small SVG charts (no library). Colors come from CSS variables, so they follow the theme.
import {goldText} from './core.js';

const NS = 'http://www.w3.org/2000/svg', W = 800, H = 240, L = 72, R = 20, T = 16, B = 30;
const s = (tag, a, text) => {
  const e = document.createElementNS(NS, tag);
  for (const k in a) e.setAttribute(k, a[k]);
  if (text != null) e.textContent = text;
  return e;
};

function frame(y0, y1, Y) {
  const svg = s('svg', {viewBox: `0 0 ${W} ${H}`, class: 'chart'});
  for (const v of [y0, (y0 + y1) / 2, y1]) {
    svg.append(s('line', {x1: L, x2: W - R, y1: Y(v), y2: Y(v), stroke: 'var(--line)'}));
    svg.append(s('text', {x: L - 6, y: Y(v) + 4, 'text-anchor': 'end', class: 'lbl'}, goldText(v)));
  }
  if (y0 < 0) svg.append(s('line', {x1: L, x2: W - R, y1: Y(0), y2: Y(0), stroke: 'var(--muted)'}));
  return svg;
}

// pts: [{x, y, title, color}] in x order. opts: {ref, refLabel, xLabel(x)}
export function lineChart(pts, opts = {}) {
  const xs = pts.map(p => p.x), ys = pts.map(p => p.y).concat(opts.ref ?? []);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(0, ...ys), y1 = Math.max(0, ...ys) * 1.1 || 1;
  const X = t => L + (t - x0) / (x1 - x0 || 1) * (W - L - R), Y = v => H - B - (v - y0) / (y1 - y0 || 1) * (H - T - B);
  const svg = frame(y0, y1, Y);
  const xl = opts.xLabel || String;
  svg.append(s('text', {x: L, y: H - 8, class: 'lbl'}, xl(x0)));
  svg.append(s('text', {x: W - R, y: H - 8, 'text-anchor': 'end', class: 'lbl'}, xl(x1)));
  if (opts.ref) {
    svg.append(s('line', {x1: L, x2: W - R, y1: Y(opts.ref), y2: Y(opts.ref), stroke: 'var(--muted)', 'stroke-dasharray': '4 4'}));
    svg.append(s('text', {x: W - R, y: Y(opts.ref) - 5, 'text-anchor': 'end', class: 'lbl'}, `${opts.refLabel || ''} ${goldText(opts.ref)}`));
  }
  svg.append(s('polyline', {points: pts.map(p => X(p.x) + ',' + Y(p.y)).join(' '), fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2}));
  for (const p of pts) {
    const c = s('circle', {cx: X(p.x), cy: Y(p.y), r: 4, fill: p.color || 'var(--accent)'});
    if (p.title) c.append(s('title', {}, p.title));
    svg.append(c);
  }
  return svg;
}

// Grouped bars. rows: [{label, bars: [{v, color, title}]}]
export function barChart(rows) {
  const vals = rows.flatMap(r => r.bars.map(b => b.v));
  const y1 = Math.max(0, ...vals) * 1.1 || 1, y0 = 0;
  const Y = v => H - B - (v - y0) / (y1 - y0) * (H - T - B);
  const svg = frame(y0, y1, Y);
  const slot = (W - L - R) / Math.max(rows.length, 1), n = Math.max(...rows.map(r => r.bars.length), 1);
  const bw = Math.min(28, slot * 0.8 / n);
  const every = Math.ceil(rows.length / 10); // at most ~10 x labels
  rows.forEach((r, i) => {
    const x = L + i * slot + (slot - bw * r.bars.length) / 2;
    r.bars.forEach((b, j) => {
      const rect = s('rect', {x: x + j * bw, y: Y(b.v), width: bw - 2, height: Math.max(0, Y(0) - Y(b.v)), fill: b.color, rx: 2});
      if (b.title) rect.append(s('title', {}, b.title));
      svg.append(rect);
    });
    if (i % every === 0) svg.append(s('text', {x: L + i * slot + slot / 2, y: H - 8, 'text-anchor': 'middle', class: 'lbl'}, r.label));
  });
  return svg;
}
