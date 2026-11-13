// /market (home): items vs their usual price, in views; click a row to open the item on the right.
// URL: /market?view=below|vendor|rising|all&q=text&cat=Class[/Subclass]&item=id
import {h, api, gold, goldText, signed, label, when, SRC, table, star, muted, toast, copyName} from '../core.js';
import {lineChart} from '../charts.js';

const VIEWS = {below: 'Below usual price', vendor: 'Below vendor', rising: 'Rising', all: 'All items'};

const pctPill = p => p == null ? muted('–') :
  h('span', {class: 'pill' + (p <= -35 ? ' g' : p <= -20 ? ' g2' : p >= 20 ? ' r' : '')}, (p > 0 ? '+' : '') + p + '%');

function spark(vals) {
  if (vals.length < 2) return muted('–');
  const NS = 'http://www.w3.org/2000/svg', W = 96, H = 24;
  const lo = Math.min(...vals), hi = Math.max(...vals), y = v => 3 + (hi === lo ? 9 : (hi - v) / (hi - lo) * 18);
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', W); svg.setAttribute('height', H); svg.setAttribute('aria-hidden', 'true');
  const pl = document.createElementNS(NS, 'polyline');
  pl.setAttribute('points', vals.map((v, i) => `${(i * (W - 2) / (vals.length - 1)).toFixed(1)},${y(v).toFixed(1)}`).join(' '));
  pl.setAttribute('fill', 'none'); pl.setAttribute('stroke', 'var(--faint)'); pl.setAttribute('stroke-width', '1.5');
  const dot = document.createElementNS(NS, 'circle');
  dot.setAttribute('cx', W - 2); dot.setAttribute('cy', y(vals[vals.length - 1])); dot.setAttribute('r', 2.5); dot.setAttribute('fill', 'var(--text)');
  svg.append(pl, dot);
  return svg;
}

export async function render(main, params) {
  const view = VIEWS[params.get('view')] ? params.get('view') : 'below';
  const q = params.get('q') || '';
  const cat = params.get('cat') || '';
  const d = await api(`/api/market?view=${view}&q=${encodeURIComponent(q)}&cat=${encodeURIComponent(cat)}`);
  const watch = new Set(d.watch);
  let selected = Number(params.get('item')) || null;

  const query = v => {
    const p = new URLSearchParams({view: v});
    if (search.value.trim()) p.set('q', search.value.trim());
    if (catSel.value) p.set('cat', catSel.value);
    return p;
  };
  const setUrl = () => {
    const p = query(view);
    if (selected) p.set('item', selected);
    history.replaceState(null, '', '/market?' + p);
  };
  const go = (v) => { history.pushState(null, '', '/market?' + query(v)); dispatchEvent(new Event('ahflip:route')); };
  const reload = () => { setUrl(); dispatchEvent(new Event('ahflip:route')); };

  const search = h('input', {placeholder: 'Search…', value: q, 'aria-label': 'Search items', size: 18});
  let t;
  search.addEventListener('input', () => { clearTimeout(t); t = setTimeout(reload, 300); });

  // Category filter: classes, each followed by its subclasses (indented). d.cats: [[class, subclass], ...] sorted.
  const subs = new Map();
  for (const [k, s] of d.cats) subs.set(k, [...(subs.get(k) || []), s].filter(Boolean));
  const catSel = h('select', {'aria-label': 'Category', onchange: reload}, h('option', {value: ''}, 'All categories'),
    [...subs].flatMap(([k, list]) => [h('option', {value: k}, k), ...list.map(s => h('option', {value: `${k}/${s}`}, '  ' + s))]));
  catSel.value = cat;

  const nameCol = {k: 'name', label: 'Item', fmt: (_, r) => [copyName(r.name), h('b', {style: 'font-weight:500'}, label(r))]};
  const starCol = {k: 'watched', label: '★', tip: 'Watchlist', fmt: (_, r) => star(r.item, watch.has(r.item))};
  const cols = view === 'vendor' ? [
    nameCol,
    {k: 'now', label: 'Now', num: 1, fmt: gold},
    {k: 'sell', label: 'Vendor', num: 1, fmt: gold},
    {k: 'gain', label: 'Profit / unit', num: 1, fmt: v => h('span', {class: 'good'}, gold(v))},
    {k: 'units', label: 'Units', num: 1, fmt: v => v ?? muted('–'), tip: 'How many you can buy at a profit (AHFlip scans only)'},
    {k: 'total', label: 'Total', num: 1, fmt: v => v == null ? muted('–') : h('span', {class: 'good'}, gold(v))},
    starCol,
  ] : [
    nameCol,
    {k: 'now', label: 'Now', num: 1, fmt: gold},
    {k: 'usual', label: 'Usual', num: 1, fmt: v => h('span', {class: 'muted'}, gold(v)), tip: `Median of the last days' scans and API snapshots`},
    {k: 'pct', label: 'vs usual', fmt: pctPill},
    {k: 'trend', label: 'Trend', fmt: spark, tip: 'Lowest price per day, then now'},
    {k: 'listed', label: 'Listed', num: 1, fmt: v => h('span', {class: 'muted'}, v)},
    starCol,
  ];
  const rows = d.rows.map(r => ({...r, watched: watch.has(r.item) ? 1 : 0, gain: r.sell != null ? r.sell - r.now : null, units: r.deal?.units ?? null, total: r.deal?.total ?? null}));
  const sortKey = {below: 'pct', vendor: 'total', rising: 'pct', all: 'listed'}[view];
  const panel = h('aside', {class: 'panel', 'aria-label': 'Item details'});

  function select(r) {
    selected = r ? r.item : null;
    setUrl();
    for (const tr of main.querySelectorAll('tbody tr')) tr.classList.toggle('sel', tr.dataset.item == selected);
    if (r) showItem(panel, r, watch, () => select(null)); else panel.remove();
    if (r && !panel.isConnected) main.append(panel);
  }

  const tbl = d.ts == null ? h('p', {class: 'muted'}, 'No prices yet. Run an AHFlip scan in game, or "Refresh API now".') :
    rows.length ? table(cols, rows, sortKey, view === 'below' ? 1 : -1, {onRow: select, selected: r => r.item === selected}) :
    h('p', {class: 'muted', style: 'margin-top:16px'}, q || cat ? 'No items match.' : 'Nothing here right now.');

  main.replaceChildren(h('section', {class: 'page fill'},
    h('h1', {}, 'Market'),
    h('p', {class: 'sub'}, d.ts == null ? '' :
      `Prices from ${SRC[d.src] || d.src} at ${when(d.ts)}. Usual price = median of earlier scans and API snapshots.`),
    h('div', {class: 'tabs', role: 'tablist'},
      Object.entries(VIEWS).map(([k, name]) => h('button', {class: 'tab' + (k === view ? ' on' : ''), role: 'tab', 'aria-selected': String(k === view), onclick: () => go(k)},
        name, k !== 'all' ? h('span', {class: 'muted'}, ' · ' + (d.counts[k] ?? 0)) : null)),
      h('div', {class: 'end'}, catSel, search)),
    h('div', {class: 'grow'}, tbl),
    d.more ? h('p', {class: 'muted small'}, `${d.more} more not shown. Search to narrow down.`) : null,
    d.hidden ? h('p', {class: 'muted small'}, `${d.hidden} rarely listed or erratic items hidden (Settings › Usual price).`) : null));
  if (selected) {
    const r = rows.find(x => x.item === selected);
    if (r) select(r); else { main.append(panel); showItem(panel, {item: selected}, watch, () => select(null)); }
  }
}

// Item details in the right-hand panel. r: the Market row (range and deal info) or just {item}.
export async function showItem(panel, r, watch, close) {
  panel.replaceChildren(h('p', {class: 'muted'}, 'Loading…'));
  let d;
  try { d = await api('/api/history?item=' + r.item); } catch (e) { toast(e.message); return; }
  const deal = r.deal;
  const pts = d.points.map(([ts, min, qty, src]) => ({x: ts, y: min, color: src === 'api' ? 'var(--faint)' : 'var(--text)',
    title: `${when(ts)} (${SRC[src] || src}): ${goldText(min)}, ${qty} listed`}));
  panel.replaceChildren(
    h('div', {}, h('button', {class: 'x', 'aria-label': 'Close', onclick: close}, '×'),
      h('div', {class: 'muted small'}, '#' + d.item), h('h2', {}, label(d), copyName(d.name))),
    h('dl', {class: 'props'},
      h('dt', {}, 'Now'), h('dd', {}, gold(d.min), d.qty != null ? muted(` · ${d.qty} listed`) : null),
      h('dt', {}, 'Usual'), h('dd', {}, gold(d.median), muted(` · ${d.past} scans`)),
      r.lo != null ? [h('dt', {}, 'Range'), h('dd', {}, gold(r.lo), ' – ', gold(r.hi))] : null,
      h('dt', {}, 'Vendor'), h('dd', {}, gold(d.sell)),
      deal ? [h('dt', {}, deal.kind === 'vendor' ? 'Vendor snipe' : 'If you flip'),
        h('dd', {}, deal.units != null ? [`${deal.units} at a profit · `, h('b', {class: 'good'}, '+', gold(deal.total))] : [h('span', {class: 'good'}, '+', gold(deal.profit)), muted(' per unit')])] : null,
      h('dt', {}, 'You hold'), h('dd', {}, d.held)),
    pts.length > 1 ? lineChart(pts, {ref: d.median, refLabel: 'usual', xLabel: when}) : h('p', {class: 'muted small'}, 'Chart needs 2+ scans with this item.'),
    h('div', {}, h('div', {class: 'muted small', style: 'margin-bottom:4px'}, 'Your trades'),
      d.trades.length ? h('div', {class: 'trades'}, d.trades.map(e => h('div', {},
        h('span', {class: 'muted'}, when(e.ts)), h('span', {}, `${e.kind === 'buy' ? 'Bought' : 'Sold'} ×${e.qty}`),
        signed((e.kind === 'buy' ? -1 : 1) * e.qty * e.price)))) : h('div', {class: 'muted small'}, 'None yet.')));
}
