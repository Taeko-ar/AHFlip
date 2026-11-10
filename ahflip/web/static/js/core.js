// Shared helpers for every page: DOM builder, gold formatting, API calls, sortable table, navigation.
export const $ = s => document.querySelector(s);

export function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v === false || v == null) continue;
    else if (k === 'class') e.className = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k instanceof Node ? k : String(k));
  return e;
}

export function gold(c) {
  if (c == null) return h('span', {class: 'muted'}, '–');
  const neg = c < 0; c = Math.abs(Math.round(c));
  const G = Math.floor(c / 10000), S = Math.floor(c / 100) % 100, C = c % 100, out = h('span', {class: 'money'});
  if (neg) out.append('-');
  if (G) out.append(h('span', {class: 'g'}, G + 'g'), ' ');
  if (G || S) out.append(h('span', {class: 's'}, (G ? String(S).padStart(2, '0') : S) + 's'), ' ');
  out.append(h('span', {class: 'c'}, (G || S ? String(C).padStart(2, '0') : C) + 'c'));
  return out;
}
export const goldText = c => gold(c).textContent;
export const signed = c => h('span', {class: c > 0 ? 'good' : c < 0 ? 'bad' : ''}, gold(c));
export const label = r => r.name || ('#' + r.item);
export const when = ts => ts ? new Date(ts * 1000).toLocaleString([], {dateStyle: 'short', timeStyle: 'short'}) : 'never';
export const SRC = {api: 'API', addon: 'AHFlip scan', scan: 'Auctionator scan'};
export function ago(ts) {
  if (!ts) return 'never';
  const m = Math.round((Date.now() / 1000 - ts) / 60);
  return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : m < 48 * 60 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`;
}
export const muted = t => h('span', {class: 'muted'}, t);

export function toast(msg, ok) {
  const t = $('#toast');
  t.textContent = msg; t.className = ok ? 'ok' : ''; t.style.display = 'block';
  clearTimeout(t._h); t._h = setTimeout(() => t.style.display = 'none', 5000);
}

export async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} :
    {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || ('HTTP ' + r.status));
  return d;
}

// Client-side navigation: main.js listens for this event and renders the page for the new URL.
export function go(path) {
  if (path !== location.pathname + location.search) history.pushState(null, '', path);
  dispatchEvent(new Event('ahflip:route'));
}
export const link = (href, ...kids) => h('a', {href, onclick: e => {
  if (e.button || e.ctrlKey || e.metaKey || e.shiftKey) return; // let the browser open new tabs
  e.preventDefault(); go(href);
}}, ...kids);

// Sortable table. cols: [{k, label, num, fmt(value, row), tip}]. opts.onRow(row): rows are clickable;
// opts.selected(row): highlight.
export function table(cols, rows, sortKey, dir = -1, opts = {}) {
  const tb = h('tbody');
  const head = h('tr', {}, cols.map(c => h('th', {class: c.num ? 'num' : '', title: c.tip || false,
    onclick: () => { dir = sortKey === c.k ? -dir : (c.num ? -1 : 1); sortKey = c.k; draw(); }}, c.label)));
  const val = (r, k) => { const v = k === 'name' ? label(r).toLowerCase() : r[k]; return v == null ? -Infinity : v; };
  function draw() {
    const rs = [...rows].sort((a, b) => { const x = val(a, sortKey), y = val(b, sortKey); return (x > y ? 1 : x < y ? -1 : 0) * dir; });
    tb.replaceChildren(...rs.map(r => h('tr', {
      class: [opts.onRow && 'click', opts.selected?.(r) && 'sel'].filter(Boolean).join(' ') || false,
      'data-item': r.item ?? false,
      onclick: opts.onRow ? e => { if (!e.target.closest('a,button,input')) opts.onRow(r); } : null,
    }, cols.map(c =>
      h('td', {class: c.num ? 'num' : ''}, c.fmt ? c.fmt(r[c.k], r) : (r[c.k] ?? ''))))));
  }
  draw();
  return h('div', {class: 'wrap'}, h('table', {}, h('thead', {}, head), tb));
}

export function star(id, on) {
  const b = h('button', {class: 'star' + (on ? ' on' : ''), title: 'watchlist', onclick: async () => {
    try { on = !on; await api('/api/watch', {item: id, on}); b.className = 'star' + (on ? ' on' : ''); b.textContent = on ? '★' : '☆'; }
    catch (e) { toast(e.message); }
  }}, on ? '★' : '☆');
  return b;
}

export const pct = (a, b) => a == null || !b ? muted('–') :
  h('span', {class: a < b ? 'good' : a > b ? 'bad' : ''}, ((a / b - 1) * 100).toFixed(0) + '%');
