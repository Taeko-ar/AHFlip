// /watch: starred items with their price now vs their usual price. Click a row: the Market item panel.
// URL: /watch?item=id
import {h, api, gold, table, star, label, pct, muted, copyName} from '../core.js';
import {showItem} from './market.js';

export async function render(main, params) {
  const d = await api('/api/watch');
  const watch = new Set(d.items.map(r => r.item));
  let selected = Number(params.get('item')) || null;
  const panel = h('aside', {class: 'panel', 'aria-label': 'Item details'});

  function select(r) {
    selected = r ? r.item : null;
    history.replaceState(null, '', selected ? '/watch?item=' + selected : '/watch');
    for (const tr of main.querySelectorAll('tbody tr')) tr.classList.toggle('sel', tr.dataset.item == selected);
    if (!r) return panel.remove();
    if (!panel.isConnected) main.append(panel);
    showItem(panel, r, watch, () => select(null));
  }

  main.replaceChildren(h('section', {class: 'page fill'},
    h('h1', {}, 'Watchlist'),
    h('p', {class: 'sub'}, 'Star items on the Market page to follow them here.'),
    d.items.length ? h('div', {class: 'grow', style: 'margin-top:20px'}, table([
      {k: 'name', label: 'Item', fmt: (_, r) => [copyName(r.name), h('b', {style: 'font-weight:500'}, label(r))]},
      {k: 'min', label: 'Now', num: 1, fmt: gold},
      {k: 'median', label: 'Usual', num: 1, fmt: v => h('span', {class: 'muted'}, gold(v))},
      {k: 'vs', label: 'vs usual', num: 1, fmt: (_, r) => pct(r.min, r.median)},
      {k: 'qty', label: 'Listed', num: 1, fmt: v => muted(v ?? '–')},
      {k: 'sell', label: 'Vendor', num: 1, fmt: gold},
      {k: 'item', label: '★', fmt: v => star(v, true)},
    ], d.items.map(r => ({...r, vs: r.min != null && r.median ? r.min / r.median : null})), 'name', 1,
      {onRow: select, selected: r => r.item === selected})) : null));
  if (selected) select({item: selected});
}
