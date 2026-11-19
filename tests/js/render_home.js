// Test harness: runs docs/assets/doyen.js against a JSON fixture with a minimal DOM stub and a fixed
// clock, then prints the rendered HTML (the homepage unless "hash" names another route).
// Input (stdin): {"data": {...}, "now": ISO, "range": "today|tomorrow|week", "hash": "#/parlays",
//   "allowMock": true (render fixtures marked mock), "noLite": true (data/parlays.json missing),
//   "footer": true (print the footer's estimated-parlay record line instead),
//   "stake": {"value": "25", "odds": 6.5, "result": "won"} (simulate typing a bet amount on a card with
//   those data-odds/data-result; prints the payout text, or {"payout", "storage"} with "dump": true),
//   "storage": {"doyen.betAmount": "25"} (seed localStorage; issue #76),
//   "wheel": {"value": "10", "focused": true} (wheel over a bet-amount input; prints {value, blurred,
//   focused}; issue #80),
//   "hday": "1" (click the homepage day switcher: 0 today, 1-3 the preview days; issue #58)}.
"use strict";
const fs = require("fs");
const path = require("path");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const FIXED = new Date(input.now).getTime();
const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { if (a.length) super(...a); else super(FIXED); }
  static now() { return FIXED; }
}
global.Date = FakeDate;

const listeners = {};
const app = { innerHTML: "", addEventListener: (t, f) => { listeners[t] = f; } };
const stub = () => ({ innerHTML: "", textContent: "", addEventListener() {} });
const els = { app, tz: stub(), updated: stub(), estrec: stub() };
global.document = { getElementById: (id) => els[id] || stub(), querySelectorAll: () => [], title: "", activeElement: null,
                    currentScript: input.scriptSrc ? { src: input.scriptSrc } : null };   // "scriptSrc": issue #98 build id
global.window = { addEventListener() {}, scrollTo() {}, __DOYEN_ALLOW_MOCK: input.allowMock === true };
global.location = { hash: input.hash || "" };
const mem = Object.assign({}, input.storage || {});
global.localStorage = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); },
                        removeItem: (k) => { delete mem[k]; } };
const fetched = [];
global.fetch = (url) => {
  fetched.push(url);
  if (/parlays\.json(\?|$)/.test(url)) {
    if (input.noLite) return Promise.resolve({ ok: false, status: 404 });
    const d = input.data || {};
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ generated: d.generated, default_timezone: d.default_timezone, parlays: d.parlays, estimated_parlays: d.estimated_parlays, singles: d.singles }) });
  }
  return Promise.resolve({ ok: true, json: () => Promise.resolve(input.data) });
};

require(path.join(__dirname, "..", "..", "docs", "assets", "doyen.js"));
setTimeout(() => {
  if (input.stake) {
    const out = { textContent: "" };
    const ds = { odds: String(input.stake.odds) };
    if (input.stake.result) ds.result = input.stake.result;
    const card = { dataset: ds, querySelector: () => out };
    const inp = { value: input.stake.value, closest: (sel) => (sel === "[data-parlay]" ? card : inp) };
    listeners.input({ target: inp });
    if (input.stake.rerender) {   // re-render the homepage after typing: same page view keeps the amount
      listeners.click({ target: { closest: (sel) => (sel === "[data-f]" ? { dataset: { f: "hday", v: "0" } } : null) } });
      process.stdout.write(app.innerHTML);
      return;
    }
    process.stdout.write(input.stake.dump ? JSON.stringify({ payout: out.textContent, storage: mem }) : out.textContent);
    return;
  }
  if (input.wheel) {
    let blurred = false;
    const inp = { value: input.wheel.value, closest: (sel) => (sel === "[data-stake]" ? inp : null),
                  blur: () => { blurred = true; if (document.activeElement === inp) document.activeElement = null; } };
    if (input.wheel.focused) document.activeElement = inp;
    // A browser steps a number input on wheel only while it is still focused after dispatch.
    listeners.wheel({ target: inp, deltaY: -1 });
    if (document.activeElement === inp) inp.value = String(Number(inp.value) + 1);
    process.stdout.write(JSON.stringify({ value: inp.value, blurred, focused: document.activeElement === inp }));
    return;
  }
  if (input.footer) { process.stdout.write(JSON.stringify({ estrec: els.estrec.textContent, hidden: els.estrec.hidden })); return; }
  if (input.fetched) { process.stdout.write(JSON.stringify(fetched)); return; }
  if (input.hday != null) {
    listeners.click({ target: { closest: (sel) => (sel === "[data-f]" ? { dataset: { f: "hday", v: String(input.hday) } } : null) } });
  }
  if (input.range && input.range !== "today") {
    listeners.click({ target: { closest: (sel) => (sel === "[data-f]" ? { dataset: { f: "range", v: input.range } } : null) } });
  }
  if (input.dumpStorage) { process.stdout.write(JSON.stringify({ html: app.innerHTML, storage: mem })); return; }
  process.stdout.write(app.innerHTML);
}, 0);
