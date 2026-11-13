// App shell: sidebar nav, router (one URL and one module per page in pages/), status polling, theme.
import {$, h, api, ago, SRC, toast, link, go} from './core.js';

const PAGES = {market: 'Market', watch: 'Watchlist', ledger: 'Ledger', settings: 'Settings'};
const HIDDEN = {setup: 'Setup'}; // pages with a URL but no sidebar link
const main = $('#main');
let page = null;

// Loading state: dims the page and shows a moving bar plus a label. Normal page loads only show it after
// 150 ms (no flicker on fast loads); an auction house switch shows it at once.
function setBusy(on, msg) {
  main.classList.toggle('busy', on);
  main.dataset.loading = msg || 'Loading…';
}

async function route(msg) {
  msg = typeof msg === 'string' ? msg : null; // event listeners pass an Event
  const name = location.pathname.slice(1).split('/')[0];
  page = PAGES[name] || HIDDEN[name] ? name : 'market'; // '/', and the old /deals and /search, open Market
  for (const a of $('#nav').children) a.className = a.dataset.p === page ? 'on' : '';
  document.title = `${PAGES[page] || HIDDEN[page]} · ahflip`;
  const t = setTimeout(() => setBusy(true, msg), msg ? 0 : 150);
  try {
    const m = await import(`./pages/${page}.js`);
    await m.render(main, new URLSearchParams(location.search), poll);
  } catch (e) { toast(e.message); }
  finally { clearTimeout(t); setBusy(false); }
}

$('#nav').append(...Object.entries(PAGES).map(([k, name]) => { const a = link('/' + k, name); a.dataset.p = k; return a; }));
addEventListener('popstate', route);
addEventListener('ahflip:route', route);

$('#snapBtn').onclick = async () => {
  try { const r = await api('/api/snap', {}); if (!r.started) toast('Busy: ' + r.job); poll(); } catch (e) { toast(e.message); }
};

function setTheme(t) {
  if (t === 'light') document.documentElement.dataset.theme = 'light'; else delete document.documentElement.dataset.theme;
  $('#themeBtn').textContent = t === 'light' ? 'Dark theme' : 'Light theme';
  try { localStorage.setItem('theme', t); } catch { /* storage blocked: the theme just isn't remembered */ }
}
let theme = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
setTheme(theme);
$('#themeBtn').onclick = () => setTheme(theme = theme === 'light' ? 'dark' : 'light');

// Auction house selector (bottom of the sidebar): switches the site and API snapshots to that house.
const SIDES = {horde: 'Global', goblin: 'Goblin'}; // Horde and Alliance share the global auction house
function drawHouses(s) {
  $('#ahSel').replaceChildren(...Object.entries(SIDES).map(([side, name]) => {
    const on = s.houses[side] === s.house;
    return h('button', {class: on ? 'on' : '', 'aria-pressed': String(on), title: `${name} auction house (#${s.houses[side]})`,
      onclick: async e => {
        if (on) return;
        for (const b of $('#ahSel').children) b.className = b === e.currentTarget ? 'on' : ''; // switch the highlight at once
        setBusy(true, `Loading the ${name} auction house…`);
        try {
          await api('/api/settings', {house: s.houses[side]});
          lastTs = undefined;
          await route(`Loading the ${name} auction house…`);
          poll();
        } catch (err) { setBusy(false); toast(err.message); poll(); }
      }}, name);
  }));
}

let lastTs, lastN;
async function poll() {
  try {
    const s = await api('/api/status');
    const lines = [
      h('div', {}, s.latest ? `Prices: ${SRC[s.src] || s.src}, ${ago(s.latest)}` : 'No prices yet'),
      h('div', {}, `In-game scan ${ago(s.scan_ts)}`),
      h('div', {}, s.job ? `Running: ${s.job}…` : !s.api ? 'API off (no keys): in-game scans only' :
        `API checked ${ago(s.attempt)}` + (s.next ? `, next in ${Math.max(0, Math.round((s.next - Date.now() / 1000) / 60))} min` : ', auto off')),
    ];
    if (s.error) lines.push(h('div', {class: 'err'}, s.error));
    $('#status').replaceChildren(...lines);
    $('#snapBtn').disabled = !!s.job;
    $('#snapBtn').hidden = !s.api;
    drawHouses(s);
    if (!s.setup_done && page !== 'setup') go('/setup'); // first run
    // new data: refresh the pages that show it
    const newScan = lastTs !== undefined && s.latest !== lastTs;
    const newTrades = lastN !== undefined && s.ledger_n !== lastN;
    if ((newScan && (page === 'market' || page === 'watch')) || (newTrades && page === 'ledger')) route();
    lastTs = s.latest; lastN = s.ledger_n;
  } catch { $('#status').replaceChildren(h('div', {class: 'err'}, 'Server not reachable. Is `ah.py web` running?')); }
}

route(); poll(); setInterval(poll, 5000);
