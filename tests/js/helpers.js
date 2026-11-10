// Shared test helpers: a fake JSON API on fetch, promise flushing, and the page shell.
import {vi} from 'vitest';

// routes: {'/api/x': data | Error | (url, body) => data | Error}. Unknown paths answer 404.
export function fakeApi(routes) {
  const fetch = vi.fn(async (url, opts = {}) => {
    const path = url.split('?')[0];
    let res = routes[path];
    if (typeof res === 'function') res = await res(url, opts.body ? JSON.parse(opts.body) : undefined);
    if (res === undefined) return {ok: false, status: 404, json: async () => ({})};
    if (res instanceof Error) return {ok: false, status: 400, json: async () => ({error: res.message})};
    return {ok: true, status: 200, json: async () => structuredClone(res)};
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

// Lets pending fetches, awaits and dynamic imports finish (setImmediate is not faked in these tests).
export async function flush() {
  await vi.dynamicImportSettled();
  for (let i = 0; i < 10; i++) await new Promise(r => setImmediate(r));
}

// Last POST body sent to a path.
export const posted = (fetch, path) => {
  const c = fetch.mock.calls.filter(([u, o]) => u.startsWith(path) && o?.method === 'POST').at(-1);
  return c && JSON.parse(c[1].body);
};

// A page container plus the #toast element core.toast() writes to.
export function pageShell() {
  document.body.innerHTML = '<div id="main"></div><div id="toast"></div>';
  return document.getElementById('main');
}

export const toastText = () => document.getElementById('toast').textContent;
