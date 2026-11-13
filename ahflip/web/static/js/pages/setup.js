// /setup: first run (main.js sends new installs here). Ruleset, pre-filled from the AHFlip saved
// file; where the addon goes; whether Blizzard API keys are set up. Everything can be changed later in Settings.
import {h, api, toast, go, muted} from '../core.js';

export async function render(main) {
  const d = await api('/api/setup');
  const rs = h('select', {id: 'setup-rs'}, Object.entries(d.rulesets).map(([id, name]) =>
    h('option', {value: id, selected: Number(id) === (d.detected.rs ?? d.rs)}, name)));

  async function save() {
    try { await api('/api/setup', {rs: Number(rs.value)}); go('/market'); } catch (e) { toast(e.message); }
  }

  const file = ([name, f]) => h('div', {class: 'file'},
    h('span', {class: 'dot ' + (f ? 'ok' : 'no')}), h('span', {}, name), muted(f || 'not found yet'));

  main.replaceChildren(h('section', {class: 'page settings'},
    h('h1', {}, d.done ? 'Setup' : 'Welcome to ahflip'),
    h('p', {class: 'sub'}, 'Three steps. You can change all of it later in Settings.'),
    h('div', {class: 'set-grid'},
      h('section', {class: 'set-group'},
        h('h2', {}, '1. Your realm'),
        h('div', {class: 'set-row'}, h('div', {}, h('label', {for: 'setup-rs'}, 'Ruleset')), h('div', {class: 'ctl'}, rs)),
        d.detected.rs ? h('p', {class: 'muted small'}, 'Filled in from your last AHFlip scan.') : null),
      h('section', {class: 'set-group'},
        h('h2', {}, '2. The AHFlip addon'),
        h('p', {class: 'muted small'}, d.wow ? `Found WoW Forever in ${d.wow}.` :
          'WoW Forever wasn\'t found in the usual places. After setup, set the file paths in Settings › Game files.'),
        h('p', {}, 'Copy the ', h('code', {}, '_addon_/AHFlip'), ' folder into:'),
        h('div', {class: 'code'}, d.addons),
        h('p', {class: 'muted small'}, 'Restart the game. At the auction house click "AHFlip scan", then "Reload to save". Your trades are logged too.'),
        h('div', {class: 'files'}, Object.entries(d.files).map(file))),
      h('section', {class: 'set-group full'},
        h('h2', {}, '3. Blizzard API (optional)'),
        d.api ? h('p', {class: 'muted small'}, 'API keys found: the site also takes background snapshots from the Blizzard API.') : [
          h('p', {class: 'muted small'}, 'No API keys: the site runs on your in-game scans, which is enough. For background snapshots between scans, create a client at develop.battle.net (any name, redirect http://localhost) and put its id and secret in a .env file next to ah.py, then restart ah.py web:'),
          h('div', {class: 'code'}, 'BNET_CLIENT_ID=...\nBNET_CLIENT_SECRET=...')])),
    h('div', {style: 'margin-top:24px'}, h('button', {class: 'btn primary', onclick: save}, d.done ? 'Save' : 'Start'))));
}
