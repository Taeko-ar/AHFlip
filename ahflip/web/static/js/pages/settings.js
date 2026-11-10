// /settings: grouped rows (label + help on the left, control on the right). Changes collect in a
// save bar at the bottom; nothing is stored until Save.
import {h, api, goldText, when, ago, toast, muted, link} from '../core.js';

// [key, label, help, type, unit]. type: int | pct (stored 0..1, shown 0..100) | gold | text
const SECTIONS = [
  ['Deals', 'What counts as a deal on the Market page.', [
    ['flip_discount', 'Flip threshold', '"Below usual" means at most this share of usual.', 'pct', '% of usual'],
    ['min_profit', 'Minimum profit', 'Hide deals below this per unit, e.g. 50c.', 'gold'],
    ['cut', 'AH cut, Horde / Alliance', 'Taken from every sale.', 'pct', '%'],
    ['cut_goblin', 'AH cut, Goblin', 'Not verified; sale mails show the real one.', 'pct', '%'],
  ]],
  ['Usual price', 'Median of earlier scans from the same source.', [
    ['hist_days', 'History window', 'How far back scans count.', 'int', 'days'],
    ['min_snaps', 'Scans needed', 'Fewer: no usual price yet.', 'int', 'scans'],
    ['min_listed', 'Minimum listings', 'Rarer items are hidden from Below usual / Rising.', 'int', 'listed'],
    ['max_spread', 'Maximum price swing', 'Wilder prices are hidden too (10 = 1g to 10g).', 'int', '× lowest'],
  ]],
  ['Blizzard API', 'Background snapshots. They lag the game by hours.', [
    ['snap_minutes', 'Snapshot every', '0 turns it off. At least 5.', 'int', 'min'],
    ['rs', 'Ruleset', '1 PvP, 2 Normal, 3 Roleplay, 15 RP PvP.', 'int'],
  ]],
  ['Auction houses', 'Ids for the Horde / Alliance / Goblin switch.', [
    ['house_horde', 'Horde', 'Checked in game.', 'int'],
    ['house_alliance', 'Alliance', 'From the API, not verified.', 'int'],
    ['house_goblin', 'Blackwater (goblin)', 'From the API, not verified.', 'int'],
  ]],
  ['Game files', 'Written by WoW on /reload or logout. * matches any account.', [
    ['addon_file', 'AHFlip saved file', 'Scans, item names and your trades.', 'text'],
    ['scan_file', 'Auctionator saved file', 'Optional second scan source.', 'text'],
    ['scan_realm', 'Auctionator realm key', 'Its key for this ruleset.', 'text'],
  ]],
];

const shown = (t, v) => t === 'pct' ? +(v * 100).toFixed(2) : t === 'gold' ? goldText(v) : v;
const parsed = (t, v) => t === 'pct' ? Number(v) / 100 : t === 'int' ? Number(v) : v.trim();

export async function render(main, _, poll) {
  const [s, st] = await Promise.all([api('/api/settings'), api('/api/status')]);
  const inputs = {}, types = {};
  const bar = h('div', {class: 'savebar', hidden: true});
  const dirty = () => Object.keys(inputs).filter(k => String(inputs[k].value).trim() !== String(shown(types[k], s[k])));
  function update() {
    const n = dirty().length;
    bar.hidden = !n;
    bar.replaceChildren(h('span', {}, `${n} unsaved change${n === 1 ? '' : 's'}`),
      h('button', {class: 'btn', onclick: discard}, 'Discard'), h('button', {class: 'btn primary', onclick: save}, 'Save'));
  }
  function discard() { for (const k in inputs) inputs[k].value = shown(types[k], s[k]); update(); }
  async function save() {
    const out = {};
    for (const k of dirty()) out[k] = parsed(types[k], inputs[k].value);
    try { Object.assign(s, await api('/api/settings', out)); discard(); toast('Saved', true); poll(); }
    catch (e) { toast(e.message); }
  }

  const row = ([k, label, help, t, unit]) => {
    types[k] = t;
    inputs[k] = h('input', {id: 'set-' + k, value: shown(t, s[k]), oninput: update,
      class: t === 'text' ? 'wide' : 'short', inputmode: t === 'text' || t === 'gold' ? false : 'decimal'});
    return h('div', {class: 'set-row' + (t === 'text' ? ' stack' : '')},
      h('div', {}, h('label', {for: 'set-' + k}, label), h('div', {class: 'help'}, help)),
      h('div', {class: 'ctl'}, inputs[k], unit ? muted(unit) : null));
  };

  const files = Object.entries(st.scan_files).map(([name, f]) => h('div', {class: 'file'},
    h('span', {class: 'dot ' + (f ? 'ok' : 'no')}), h('span', {}, name), muted(f || 'no file found at this path')));

  const group = ([title, sub, rows]) => h('section', {class: 'set-group' + (title === 'Game files' ? ' full' : '')},
    h('h2', {}, title), h('p', {class: 'muted small'}, sub), rows.map(row),
    title === 'Game files' ? h('div', {class: 'files'}, files, muted(`Last scan imported ${ago(st.scan_ts)}.`)) : null);

  const retry = h('button', {class: 'btn', onclick: async () => {
    try { const r = await api('/api/retry', {}); toast(r.started ? 'Retry started' : 'Busy: ' + r.job, r.started); poll(); } catch (e) { toast(e.message); }
  }}, 'Retry now');

  main.replaceChildren(h('section', {class: 'page settings'},
    h('h1', {}, 'Settings'),
    h('p', {class: 'sub'}, 'Stored in ah.db. The addon has its own options in game: /ahflip settings or the minimap button. ',
      link('/setup', 'Run setup again')),
    // three columns on a wide window; Item info sits with the small groups, Game files spans the bottom
    h('div', {class: 'set-grid'},
      SECTIONS.filter(([title]) => title !== 'Game files').map(group),
      h('section', {class: 'set-group'},
        h('h2', {}, 'Item info'),
        h('p', {class: 'muted small'}, 'From the Blizzard API; AHFlip scans fill the rest.'),
        h('div', {class: 'set-row'},
          h('div', {}, h('div', {}, `${st.missing} items without info`),
            h('div', {class: 'help'}, `Retried daily, ~1 s per item. Last: ${when(st.retried)}.`)),
          h('div', {class: 'ctl'}, retry))),
      SECTIONS.filter(([title]) => title === 'Game files').map(group)),
    bar));
  update();
}
