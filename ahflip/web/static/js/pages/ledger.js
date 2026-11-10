// /ledger: your trades (logged in game by the AHFlip addon). All numbers are computed here from the raw
// entries, so the period / type / item filters apply to everything on the page.
import {h, api, gold, goldText, signed, label, when, table, toast, muted, go} from '../core.js';
import {lineChart, barChart} from '../charts.js';
import {showItem} from './market.js';

const itemName = (_, r) => h('b', {style: 'font-weight:500'}, label(r));

const DAY = 86400;
const PERIODS = {today: 'Today', 7: '7 days', 30: '30 days', all: 'All'};
const KINDS = {all: 'Buys and sells', buy: 'Buys', sell: 'Sells'};
const TABLES = {items: 'Items', days: 'Days', trades: 'Trades'};
const dayKey = ts => new Date(ts * 1000).toLocaleDateString('sv'); // YYYY-MM-DD, local time
const state = {period: 'all', kind: 'all', tab: 'items', q: ''}; // kept while the page is re-rendered

function seg(options, key, redraw) {
  const box = h('div', {class: 'seg', role: 'group'});
  const draw = () => box.replaceChildren(...Object.entries(options).map(([k, name]) =>
    h('button', {class: k === state[key] ? 'on' : '', 'aria-pressed': String(k === state[key]), onclick: () => { state[key] = k; draw(); redraw(); }}, name)));
  draw();
  return box;
}

export async function render(main) {
  const d = await api('/api/ledger');
  const box = h('div', {class: 'col'}); // fills the page; only the table at its bottom scrolls
  const q = h('input', {placeholder: 'Filter items…', value: state.q, 'aria-label': 'Filter items', size: 18,
    oninput: () => { state.q = q.value; draw(); }});

  // Cost basis per item from all buys, ignoring filters: realized profit = sold x (sell price - avg buy price).
  const basis = {};
  for (const e of d.entries) {
    const b = basis[e.item] ??= {qty: 0, cost: 0, bought: 0, sold: 0};
    if (e.kind === 'buy') { b.qty += e.qty; b.cost += e.qty * e.price; b.bought += e.qty; } else b.sold += e.qty;
  }
  const avgBuy = i => basis[i]?.qty ? basis[i].cost / basis[i].qty : null;

  function filtered() {
    const now = Date.now() / 1000, f = state.q.toLowerCase();
    const since = state.period === 'all' ? 0 : state.period === 'today' ? new Date().setHours(0, 0, 0, 0) / 1000 : now - state.period * DAY;
    return d.entries.filter(e => e.ts >= since && (state.kind === 'all' || e.kind === state.kind) && label(e).toLowerCase().includes(f));
  }

  function draw() {
    const E = filtered();
    if (!E.length) {
      box.replaceChildren(h('p', {class: 'muted', style: 'margin-top:24px'}, d.entries.length ? 'No trades match.' :
        'No trades yet. Buy or sell something in game with the AHFlip addon, then /reload.'));
      return;
    }
    const per = {};
    let spent = 0, earned = 0, realized = 0;
    for (const e of E) {
      const p = per[e.item] ??= {item: e.item, name: e.name, bought: 0, sold: 0, spent: 0, earned: 0, realized: 0};
      if (e.kind === 'buy') { p.bought += e.qty; p.spent += e.qty * e.price; spent += e.qty * e.price; }
      else {
        p.sold += e.qty; p.earned += e.qty * e.price; earned += e.qty * e.price;
        const a = avgBuy(e.item);
        if (a != null) { p.realized += e.qty * (e.price - a); realized += e.qty * (e.price - a); }
      }
    }
    let stock = 0;
    const items = Object.values(per).map(p => {
      const now = d.now[p.item] || {}, held = Math.max(0, basis[p.item].bought - basis[p.item].sold);
      const ah = now.min != null ? Math.floor(now.min * (1 - d.cut)) : null; // after the AH cut
      const exit = Math.max(now.sell ?? -1, ah ?? -1);
      const value = held && exit >= 0 ? held * exit : null;
      stock += value || 0;
      return {...p, held, avgbuy: p.bought ? p.spent / p.bought : null, avgsell: p.sold ? p.earned / p.sold : null,
        net: p.earned - p.spent, ah, vendor: now.sell, value, where: exit < 0 ? null : exit === now.sell ? 'vendor' : 'AH'};
    });
    const days = {};
    for (const e of E) {
      const k = dayKey(e.ts), x = days[k] ??= {day: k, buys: 0, sells: 0, spent: 0, earned: 0};
      if (e.kind === 'buy') { x.buys++; x.spent += e.qty * e.price; } else { x.sells++; x.earned += e.qty * e.price; }
    }
    const dayRows = Object.values(days).sort((a, b) => a.day < b.day ? -1 : 1).map(x => ({...x, net: x.earned - x.spent}));
    let run = 0;
    const cum = [...E].sort((a, b) => a.ts - b.ts).map(e => {
      run += (e.kind === 'sell' ? 1 : -1) * e.qty * e.price;
      return {x: e.ts, y: run, color: e.kind === 'sell' ? 'var(--good)' : 'var(--bad)',
        title: `${when(e.ts)} ${e.kind} ${e.qty}x ${label(e)}: ${goldText(e.qty * e.price)} (running ${goldText(run)})`};
    });

    const stat = (name, value, tip) => h('div', {class: 'stat', title: tip || false}, h('span', {}, name), h('b', {}, value));
    const tabs = h('div', {class: 'tabs', role: 'tablist'}, Object.entries(TABLES).map(([k, name]) =>
      h('button', {class: 'tab' + (k === state.tab ? ' on' : ''), role: 'tab', 'aria-selected': String(k === state.tab),
        onclick: () => { state.tab = k; draw(); }}, name)));
    const tables = {
      items: () => table([
        {k: 'name', label: 'Item', fmt: itemName},
        {k: 'bought', label: 'Bought', num: 1}, {k: 'avgbuy', label: 'Avg buy', num: 1, fmt: gold},
        {k: 'sold', label: 'Sold', num: 1}, {k: 'avgsell', label: 'Avg sell', num: 1, fmt: gold},
        {k: 'realized', label: 'Realized', num: 1, fmt: signed, tip: 'Sold units vs their average buy price'},
        {k: 'held', label: 'Held', num: 1, tip: 'Bought − sold, all time'},
        {k: 'value', label: 'Held value', num: 1, fmt: (v, r) => v == null ? muted('–') : h('span', {}, gold(v), ' ', muted(r.where)),
          tip: 'At the better of vendor price or lowest AH listing after cut'},
        {k: 'net', label: 'Cash net', num: 1, fmt: signed},
      ], items, 'net', -1, rowOpts),
      days: () => table([
        {k: 'day', label: 'Day'}, {k: 'buys', label: 'Buys', num: 1}, {k: 'sells', label: 'Sells', num: 1},
        {k: 'spent', label: 'Spent', num: 1, fmt: gold}, {k: 'earned', label: 'Received', num: 1, fmt: gold},
        {k: 'net', label: 'Net', num: 1, fmt: signed},
      ], dayRows, 'day'),
      trades: () => table([
        {k: 'ts', label: 'Time', fmt: when},
        {k: 'kind', label: 'Type', fmt: v => h('span', {class: 'pill' + (v === 'sell' ? ' g' : '')}, v === 'sell' ? 'sold' : 'bought')},
        {k: 'name', label: 'Item', fmt: itemName},
        {k: 'qty', label: 'Qty', num: 1}, {k: 'price', label: 'Each', num: 1, fmt: gold},
        {k: 'total', label: 'Total', num: 1, fmt: (v, r) => signed(r.kind === 'sell' ? v : -v)},
        {k: 'note', label: 'Note', fmt: v => muted(v || '')},
        {k: 'id', label: '', fmt: (id, r) => h('span', {style: 'display:flex;gap:4px;justify-content:end'},
          h('button', {class: 'btn sm', onclick: () => edit(r)}, 'Edit'),
          h('button', {class: 'btn sm', 'aria-label': 'Delete', onclick: () => del(id)}, '×'))},
      ], E.map(e => ({...e, total: e.qty * e.price})), 'ts', -1, rowOpts),
    };

    box.replaceChildren(
      h('div', {class: 'stats'},
        stat('Spent', gold(spent)), stat('Received', gold(earned)),
        stat('Net', signed(earned - spent), 'Received − spent'),
        stat('Realized', signed(realized), 'Sold units vs their average buy price'),
        stat('Stock', gold(stock), 'Held items at the better of vendor or AH price (after cut)'),
        stat('Trades', E.length)),
      h('div', {class: 'charts'},
        h('div', {}, h('h3', {}, 'Spent and received per day'), barChart(dayRows.slice(-30).map(x => ({label: x.day.slice(5), bars: [
          {v: x.spent, color: 'var(--bad)', title: `${x.day} spent ${goldText(x.spent)}`},
          {v: x.earned, color: 'var(--good)', title: `${x.day} received ${goldText(x.earned)}`}]})))),
        h('div', {}, h('h3', {}, 'Running net'), cum.length > 1 ? lineChart(cum, {xLabel: when}) : h('p', {class: 'muted small'}, 'Needs 2+ trades.'))),
      tabs, editBox, h('div', {class: 'grow'}, tables[state.tab]()));
  }

  // Click an item or trade row: the Market item panel on the right.
  let selected = null;
  const panel = h('aside', {class: 'panel', 'aria-label': 'Item details'});
  const watchSet = new Set();
  api('/api/watch').then(w => w.items.forEach(r => watchSet.add(r.item))).catch(() => {});
  function select(r) {
    selected = r ? r.item : null;
    for (const tr of main.querySelectorAll('tbody tr')) tr.classList.toggle('sel', tr.dataset.item == selected);
    if (!r) return panel.remove();
    if (!panel.isConnected) main.append(panel);
    showItem(panel, {item: r.item}, watchSet, () => select(null));
  }
  const rowOpts = {onRow: select, selected: r => r.item === selected};

  // Edit a trade: a small bar above the table (trades are logged in game; this only fixes mistakes).
  const editBox = h('div');
  function edit(r) {
    const qty = h('input', {type: 'number', min: 1, value: r.qty, size: 5});
    const price = h('input', {value: goldText(r.price), size: 12});
    const note = h('input', {value: r.note || '', size: 20});
    editBox.replaceChildren(h('form', {class: 'edit', onsubmit: async e => {
      e.preventDefault();
      try { await api('/api/ledger', {edit: r.id, kind: r.kind, item: String(r.item), qty: qty.value, price: price.value, note: note.value}); toast('Saved', true); go('/ledger'); }
      catch (err) { toast(err.message); }
    }}, h('span', {style: 'align-self:center'}, `${r.kind === 'sell' ? 'Sold' : 'Bought'} ${label(r)}, ${when(r.ts)}`),
      h('label', {}, 'Qty', qty), h('label', {}, 'Each', price), h('label', {}, 'Note', note),
      h('button', {class: 'btn primary'}, 'Save'), h('button', {class: 'btn', type: 'button', onclick: () => editBox.replaceChildren()}, 'Cancel')));
    qty.focus();
  }
  async function del(id) {
    if (!confirm('Delete this trade?')) return;
    try { await api('/api/ledger', {delete: id}); go('/ledger'); } catch (e) { toast(e.message); }
  }

  main.replaceChildren(h('section', {class: 'page fill'},
    h('h1', {}, 'Ledger'),
    h('div', {class: 'bar'}, seg(PERIODS, 'period', draw), seg(KINDS, 'kind', draw), q),
    box));
  draw();
}
