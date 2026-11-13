// Test harness: runs docs/assets/doyen.js against a JSON fixture with a minimal DOM stub and a fixed
// clock, then prints the rendered homepage HTML. Input (stdin): {"data": {...}, "now": ISO, "range": "today|tomorrow|week"}.
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
const els = { app, tz: stub(), updated: stub() };
global.document = { getElementById: (id) => els[id] || stub(), querySelectorAll: () => [], title: "" };
global.window = { addEventListener() {}, scrollTo() {} };
global.location = { hash: "" };
global.localStorage = { getItem: () => null, setItem() {} };
global.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(input.data) });

require(path.join(__dirname, "..", "..", "docs", "assets", "doyen.js"));
setTimeout(() => {
  if (input.range && input.range !== "today") {
    listeners.click({ target: { closest: (sel) => (sel === "[data-f]" ? { dataset: { f: "range", v: input.range } } : null) } });
  }
  process.stdout.write(app.innerHTML);
}, 0);
