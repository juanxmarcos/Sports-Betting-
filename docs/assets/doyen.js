/* Sports Betting Doyen — static front end. Reads data/doyen.json. No tracking, no secrets. */
(function () {
  "use strict";
  const $app = document.getElementById("app");
  const store = {
    get(k, d) { try { const v = localStorage.getItem("doyen." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("doyen." + k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
  };
  const S = { data: null, lite: null, sport: store.get("sport", "all"), range: "today", hrange: "all", hsport: "all",
              tz: store.get("tz", null), hday: "0", watch: new Set(store.get("watch", [])) };

  const SPORTS = [["all", "All Sports"], ["soccer", "Soccer"], ["nfl", "NFL"], ["nba", "NBA"], ["tennis", "Tennis"]];
  const ICON = {
    soccer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5l3.6 2.6-1.4 4.2H9.8l-1.4-4.2z"/><path d="M12 3.5v4M15.6 10.1l4.2-1.3M14.2 14.3l2.6 3.6M9.8 14.3l-2.6 3.6M8.4 10.1L4.2 8.8"/></svg>',
    nfl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="12" rx="9" ry="5.6" transform="rotate(-35 12 12)"/><path d="M9.5 14.5l5-5M10.6 11.4l2 2M12 10l2 2M9.2 12.8l2 2"/></svg>',
    nba: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5v17M6 6c2.5 2.2 2.5 9.8 0 12M18 6c-2.5 2.2-2.5 9.8 0 12"/></svg>',
    tennis: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M5.2 6.6c3.4 2.8 3.4 8 0 10.8M18.8 6.6c-3.4 2.8-3.4 8 0 10.8"/></svg>',
    all: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/></svg>',
  };
  const STAR = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.4"><path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8L3.5 9.7l5.9-.9z"/></svg>';
  const STAR_O = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3.5l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.9l-5.3 2.7 1-5.8L3.5 9.7l5.9-.9z"/></svg>';
  const WARN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 4l9 16H3z"/><path d="M12 10v4.5M12 17.2v.3"/></svg>';

  // ---------- helpers ----------
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pct = (x, d = 0) => (x == null || isNaN(x) ? "—" : (x * 100).toFixed(d) + "%");
  const dec = (x) => (x == null ? "—" : Number(x).toFixed(2));
  const D0 = () => S.data || S.lite;
  const tz = () => S.tz || (D0() && D0().default_timezone) || "America/New_York";
  const dkey = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: tz(), year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const addDays = (key, n) => { const [y, m, d] = key.split("-").map(Number); const t = new Date(Date.UTC(y, m - 1, d + n)); return t.toISOString().slice(0, 10); };
  const when = (x) => fmtTime(x.start_utc);
  const fmtTime = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(iso));
  const fmtClock = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), hour: "numeric", minute: "2-digit" }).format(new Date(iso));
  const fmtDay = (key) => { const [y, m, d] = key.split("-").map(Number); return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "long", month: "long", day: "numeric" }).format(new Date(Date.UTC(y, m - 1, d, 12))); };
  const fmtDate = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), month: "short", day: "numeric", year: "numeric" }).format(new Date(iso));
  const ago = (iso) => { if (!iso) return "unknown"; const h = (Date.now() - new Date(iso)) / 36e5; if (h < 1) return Math.max(1, Math.round(h * 60)) + " min ago"; if (h < 48) return Math.round(h) + " h ago"; return Math.round(h / 24) + " days ago"; };
  const sportName = (k) => (SPORTS.find((s) => s[0] === k) || [k, k])[1];

  function inRange(startIso, endIso, range) {
    // Periods (identical in diagnostics and reports): Today/Tomorrow = local calendar days;
    // This Week = the next 7 x 24 hours from now.
    if (range === "week") { const t = new Date(startIso).getTime(), n = Date.now(); return t > n - 3 * 36e5 && t <= n + 7 * 864e5; }
    const today = dkey(new Date());
    const s = dkey(new Date(startIso)), e = endIso ? dkey(new Date(endIso)) : s;
    let lo = today, hi = today;
    if (range === "tomorrow") { lo = hi = addDays(today, 1); }
    if (range === "week") { hi = addDays(today, 6); }
    return s <= hi && e >= lo;
  }
  const sportOk = (s, f) => f === "all" || s === f;

  function toggleWatch(id) {
    if (S.watch.has(id)) S.watch.delete(id); else S.watch.add(id);
    store.set("watch", [...S.watch]);
    render();
  }
  window.__doyenWatch = toggleWatch;
  const starBtn = (id) => `<button class="star ${S.watch.has(id) ? "on" : ""}" onclick="event.stopPropagation();__doyenWatch('${esc(id)}')" aria-label="${S.watch.has(id) ? "Remove from" : "Add to"} watchlist" title="Watchlist">${S.watch.has(id) ? STAR : STAR_O}</button>`;

  // ---------- filters ----------
  function filters(withDate = true, key = "sport", rangeKey = "range", ranges = [["today", "Today"], ["tomorrow", "Tomorrow"], ["week", "This Week"]]) {
    const cur = S[key];
    const chips = SPORTS.map(([k, l]) => {
      const st = k !== "all" && S.data.sports[k];
      const off = st && !st.operational;
      return `<button class="chip ${cur === k ? "on" : ""}" data-f="${key}" data-v="${k}" aria-pressed="${cur === k}">${ICON[k]}${l}${off ? '<span class="dot" title="In development"></span>' : ""}</button>`;
    }).join("");
    const seg = withDate ? `<div class="seg" role="group" aria-label="Date">${ranges.map(([k, l]) => `<button class="${S[rangeKey] === k ? "on" : ""}" data-f="${rangeKey}" data-v="${k}">${l}</button>`).join("")}</div>` : "";
    return `<div class="filters"><div class="chips" role="group" aria-label="Sport">${chips}</div>${seg}</div>`;
  }
  $app.addEventListener("click", (e) => {
    const b = e.target.closest("[data-f]");
    if (b) { S[b.dataset.f] = b.dataset.v; if (b.dataset.f === "sport") store.set("sport", b.dataset.v); render(); return; }
    const go = e.target.closest("[data-go]");
    if (go) { location.hash = go.dataset.go; }
  });

  function sportNotice(sport) {
    if (sport === "all") return "";
    const st = S.data.sports[sport];
    if (!st) return "";
    if (!st.operational) return `<div class="banner">${WARN.replace("<svg", '<svg width="16" height="16"')}<span><b>${esc(st.name)} modelling is still in development.</b> No ${esc(st.name)} picks can be produced yet. This is different from "no qualifying picks". ${esc(st.note || "")}</span></div>`;
    if (st.picks_possible === false) return `<div class="banner">${WARN.replace("<svg", '<svg width="16" height="16"')}<span><b>${esc(st.name)}: model-only monitoring.</b> ${esc(st.note || "Picks need multi-bookmaker odds, which are not currently available for free.")}</span></div>`;
    return "";
  }

  // ---------- cards ----------
  function statusPill(st) {
    if (!st) return "";
    const cls = st.state === "settled" ? st.result.replace("half_", "") : st.state;
    return `<span class="pill ${esc(cls)}" title="${esc(st.note || "")}">${esc(st.label)}</span>`;
  }
  const fmtMon = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), month: "short", day: "numeric" }).format(new Date(iso)).toUpperCase();
  function topline(x, withDate) {
    const today = dkey(new Date()) === dkey(new Date(x.start_utc));
    const parts = [sportName(x.sport).toUpperCase()];
    if (withDate || !today) parts.push(fmtMon(x.start_utc));
    parts.push(fmtClock(x.start_utc));
    return `<div class="tl">${ICON[x.sport] || ""}<span>${esc(parts.join(" · "))}</span></div>`;
  }
  const vs = (t) => esc(String(t || "").replace(/ at /, " @ ").replace(/ v /, " vs. "));

  // ---------- compact cards ----------
  // Every pick card is a peer: same size, same facts. No card is elevated above another.
  // A pick that changed since publication ("updated") keeps its original odds and EV, but they are
  // labelled as publication values and the card says it is not a current recommendation.
  function pickCard(p) {
    const st = p.status || {};
    const changed = st.state && st.state !== "active";
    const flag = changed ? statusPill(st) : (p.stale ? '<span class="pill stale">Price may be stale</span>' : "");
    const ev = `${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}`;
    return `<article class="card cc pick${changed ? " changed" : ""}" data-go="#/pick/${esc(p.id)}" role="link" tabindex="0">
      <div class="cc-top">${topline(p)}${starBtn(p.event_id)}</div>
      <div class="cc-title">${vs(p.title)}</div>
      <div class="cc-main">
        <div><div class="k">${esc(p.market)}</div><div class="sel">${esc(p.selection)}</div></div>
        <div class="odds">${changed ? '<div class="k">Odds at publication</div>' : ""}<div class="o">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")}</div></div>
      </div>
      <div class="cc-facts"><span>Estimated chance <b>${pct(p.prob)}</b></span>${changed ? `<span>EV at publication <b>${ev}</b></span>` : `<span>Expected value <b class="pos">${ev}</b></span>`}</div>
      <div class="cc-why"><span>Why</span> ${esc(p.why_short || "")}</div>
      ${changed ? `<div class="cc-why wait"><b>Not a current recommendation.</b>${st.note ? " " + esc(st.note) : ""}</div>` : ""}
      <div class="cc-foot"><span>${flag}</span><span class="link">Details →</span></div>
    </article>`;
  }
  function watchCard(r) {
    const c = r.closest;
    return `<article class="card cc watch" data-go="#/event/${esc(r.event_id)}" role="link" tabindex="0">
      <div class="cc-top">${topline(r, true)}${starBtn(r.event_id)}</div>
      <div class="cc-title">${vs(r.title)}</div>
      <div class="cc-main">
        <div><div class="k">Watching${c ? " · " + esc(c.market_label) : ""}</div><div class="sel">${c ? esc(c.selection_text) : "—"}</div></div>
        <div class="odds"><div class="o ${c ? "" : "na"}">${c ? dec(c.odds) : "Odds unavailable"}</div><div class="bk">${c ? "current odds" : ""}</div></div>
      </div>
      <div class="cc-why wait">${esc(r.short || "")}</div>
      <div class="cc-foot"><span class="faint">${r.odds_updated ? "Updated " + esc(ago(r.odds_updated)) : "No odds yet"}</span><span class="link">Details →</span></div>
    </article>`;
  }

  function closeCard(r) {
    const c = r.closest;
    return `<article class="card cc close" data-go="#/event/${esc(r.event_id)}" role="link" tabindex="0">
      <div class="cc-top">${topline(r, true)}${starBtn(r.event_id)}</div>
      <div class="cc-title">${vs(r.title)}</div>
      <div class="cc-main">
        <div><div class="k">${esc(c.market_label)}</div><div class="sel">${esc(c.selection_text)}</div></div>
        <div class="odds"><div class="o">${dec(c.odds)}</div><div class="bk">${esc(c.bookmaker || "")}</div></div>
      </div>
      <div class="cc-why close-r">${esc(r.short || "")}</div>
      <div class="cc-foot"><span class="faint">Not a recommendation · updated ${esc(ago(r.odds_updated))}</span><span class="link">Details →</span></div>
    </article>`;
  }

  // ---------- views ----------
  function briefing(D, picks, nEvents) {
    const s = D.briefing || {};
    const f = D.funnel_7d || {};
    const sp = S.sport === "all" ? Object.keys(f) : [S.sport];
    const markets = sp.reduce((a, k) => a + ((f[k] || {})["6_markets_evaluated"] || 0), 0);
    return `<div class="brief"><span><b>${nEvents}</b> events</span><span class="dot"></span><span><b>${markets.toLocaleString()}</b> markets priced this week</span><span class="dot"></span><span><b>${picks.length || "No"}</b> pick${picks.length === 1 ? "" : "s"} ${picks.length ? (picks.length === 1 ? "qualifies" : "qualify") : "qualify yet"}</span>${s.sentence ? `<span class="brief-s">${esc(s.sentence)}</span>` : ""}</div>`;
  }
  // Heading and date context for the selected period. Future periods are never called today's picks.
  const fmtShort = (key) => { const [y, m, d] = key.split("-").map(Number); return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", month: "short", day: "numeric" }).format(new Date(Date.UTC(y, m - 1, d, 12))); };
  function period(range) {
    const today = dkey(new Date());
    if (range === "tomorrow") return { h: "Tomorrow's Picks", when: fmtDay(addDays(today, 1)), none: "for tomorrow" };
    if (range === "week") return { h: "This Week's Picks", when: `Next 7 days · ${fmtShort(today)} – ${fmtShort(dkey(new Date(Date.now() + 7 * 864e5)))}`, none: "this week" };
    return { h: "Picks of the Day", when: fmtDay(today), none: "today" };
  }
  // Picks for the selected period that are still open and have not started, in start-time order.
  // "active" = still clears every rule. "updated" = still open, but the price or information changed
  // since publication. Withdrawn, in-play and settled picks are never listed here (they stay in Pick History).
  function livePicks(D) {
    const now = Date.now();
    const live = D.picks.filter((p) => sportOk(p.sport, S.sport) && inRange(p.start_utc, null, S.range) && new Date(p.start_utc).getTime() > now)
      .sort((a, b) => new Date(a.start_utc) - new Date(b.start_utc) || String(a.title).localeCompare(String(b.title)));
    const state = (p) => (p.status || {}).state;
    return { qualifying: live.filter((p) => state(p) === "active"), changed: live.filter((p) => state(p) === "updated") };
  }
  // Single picks (secondary route since issue #27; the homepage shows parlays only).
  function picksView() {
    const D = S.data;
    const P = period(S.range);
    const { qualifying, changed } = livePicks(D);
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const allWatch = D.watching.map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
    const watching = allWatch.filter((r) => inRange(r.start_utc, r.end_utc, S.range));
    const shown = (watching.length ? watching : allWatch).slice(0, 3);
    const nEvents = D.events.filter((r) => sportOk(r.sport, S.sport) && inRange(r.start_utc, r.end_utc, S.range)).length;
    let h = `<div class="eyebrow">${esc(P.when)}</div><h1 style="margin-top:6px">${esc(P.h)}</h1>
      ${briefing(D, qualifying, nEvents)}${filters()}${staleBanner()}${sportNotice(S.sport)}`;
    h += `<section class="section first" id="picks">`;
    if (qualifying.length) h += `<div class="grid picks">${qualifying.map(pickCard).join("")}</div>`;
    else h += `<div class="card empty-cc"><h3>No picks qualify ${esc(P.none)} ${changed.length ? "right now" : "yet"}.</h3><p>${changed.length
      ? `${changed.length} published pick${changed.length === 1 ? " has" : "s have"} changed since publication and ${changed.length === 1 ? "is" : "are"} listed below with the latest status.`
      : "Every priced market is checked against the sharp consensus; none clears the bar right now."}</p></div>`;
    h += `</section>`;
    if (changed.length) h += `<section class="section" id="changed"><div class="section-h"><h2>Changed since publication</h2><span class="count">${changed.length}</span></div><p class="muted small" style="margin:-6px 0 12px">Still open, but the price or information has moved. Check the latest status before relying on these.</p><div class="grid picks">${changed.map(pickCard).join("")}</div></section>`;
    const closeAll = (D.close_to_value || []).map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
    const closeIn = closeAll.filter((r) => inRange(r.start_utc, r.end_utc, S.range));
    const closeShown = (closeIn.length ? closeIn : closeAll).slice(0, 3);
    h += `<section class="section"><div class="section-h"><h2>Close to Value</h2>${closeAll.length > 3 ? `<a class="link" href="#/close">View all (${closeAll.length}) →</a>` : ""}</div>`;
    h += closeShown.length ? `${!closeIn.length ? `<p class="muted small">None ${esc({ today: "today", tomorrow: "tomorrow", week: "this week" }[S.range])}. Next up:</p>` : ""}<div class="grid">${closeShown.map(closeCard).join("")}</div>`
      : `<div class="card empty-cc"><p>No prices are close to Doyen's value threshold right now.</p></div>`;
    h += `</section>`;
    h += `<section class="section"><div class="section-h"><h2>Matches Doyen Is Watching</h2>${allWatch.length > 3 ? `<a class="link" href="#/watching">View all (${allWatch.length}) →</a>` : ""}</div>`;
    h += shown.length ? `${!watching.length ? `<p class="muted small">Nothing left ${esc({ today: "today", tomorrow: "tomorrow", week: "this week" }[S.range])}. Coming up next:</p>` : ""}<div class="grid">${shown.map(watchCard).join("")}</div>`
      : `<div class="card empty-cc"><h3>Nothing on the radar</h3><p>No matches are close to qualifying. See <a href="#/upcoming">Upcoming</a> for everything Doyen tracks.</p></div>`;
    return h + `</section>`;
  }
  // ---------- daily parlay homepage (issue #27) ----------
  // The homepage shows ONLY today's recommended parlay cards. A card is rendered only for a
  // recommendation that passes every check in parlayProblem() (mirrors sbi/parlays.py card_problem):
  // a published block with no open blockers, dated today in New York, 2-6 active legs on distinct
  // events that all start later today, and ONE bookmaker's own combined quote with a source and a
  // fresh timestamp. Anything missing or unknown is rejected. Stage 0 publishes none, so production
  // shows the one-line empty state. Mock fixtures render only when a test sets __DOYEN_ALLOW_MOCK.
  const PARLAY_URL = "https://github.com/juanxmarcos/Sports-Betting-/blob/main/docs/PARLAYS.md";
  const PARLAY_BLOCKERS = [
    { text: "No bookmaker-quoted parlay price. Doyen's odds feeds return single-market prices only, so it cannot verify that any bookmaker offers a given combination, or at what price." },
    { text: "No validated joint-probability estimate. Multiplying leg probabilities assumes the legs are independent and each leg is well calibrated; Doyen has no settled multi-leg record to support that." },
  ];
  const PDAY_TZ = "America/New_York";             // the site's authoritative publishing day
  const PC = { minLegs: 2, maxLegs: 6, maxCards: 5, stake: 10, quoteRule: "same_ny_day", kind: "bookmaker_combined",
               sports: ["soccer", "nfl", "nba", "tennis"] };
  // "9:47 AM EST": the time a price was taken, always in New York time with the zone shown (issue #53).
  const fmtAsOf = (t, zone = true) => new Intl.DateTimeFormat("en-US", { timeZone: PDAY_TZ, hour: "numeric", minute: "2-digit", ...(zone ? { timeZoneName: "short" } : {}) }).format(new Date(t));
  const nyKey = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: PDAY_TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  const isoT = (x) => { if (typeof x !== "string" || !/(Z|[+-]\d\d:?\d\d)$/.test(x)) return null; const t = new Date(x).getTime(); return isNaN(t) ? null : t; };
  const str = (x) => typeof x === "string" && x.trim() !== "";
  const allowMock = () => typeof window !== "undefined" && window.__DOYEN_ALLOW_MOCK === true;
  function parlayProblem(rec, now, day) {
    if (!rec || typeof rec !== "object") return "not an object";
    if ((rec.mock || rec.test) && !allowMock()) return "mock or test data";
    if (!str(rec.parlay_id)) return "missing parlay_id";
    if (rec.date !== day) return "not today's parlay";
    if (rec.status !== "active") return "parlay is not active";
    if (!str(rec.bookmaker)) return "missing bookmaker";
    const legs = rec.legs;
    if (!Array.isArray(legs) || legs.length < PC.minLegs || legs.length > PC.maxLegs) return "needs 2-6 legs";
    const seen = new Set();
    for (const l of legs) {
      if (!l || typeof l !== "object") return "leg is not an object";
      if (!str(l.event_id) || !str(l.title) || !str(l.selection)) return "leg missing identity";
      if (seen.has(l.event_id)) return "two legs on the same event";
      seen.add(l.event_id);
      if (!PC.sports.includes(l.sport)) return "unsupported sport";
      if (l.status !== "active") return "leg is not active";
      const t = isoT(l.start_utc);
      if (t == null) return "leg has no valid start time";
      if (nyKey(new Date(t)) !== day) return "leg is not on today's date";
      if (t <= now) return "leg has started";
    }
    const q = rec.quote;
    if (!q || q.kind !== PC.kind) return "no single-bookmaker combined quote";
    if (q.bookmaker !== rec.bookmaker) return "quote is from a different bookmaker";
    if (!str(q.source)) return "quote has no provenance";
    if (typeof q.decimal_odds !== "number" || !isFinite(q.decimal_odds) || q.decimal_odds <= 1) return "invalid combined odds";
    const at = isoT(q.quoted_at);
    if (at == null || at > now) return "quote has no valid time";
    if (nyKey(new Date(at)) !== day) return "quote is stale";     // issue #53: today's quote counts until the first leg starts
    return null;
  }
  function shownParlays(P) {
    if (!P || P.status !== "published" || !Array.isArray(P.blockers) || P.blockers.length) return [];
    const now = Date.now(), day = nyKey(new Date(now));
    if (P.date !== day) return [];
    const first = (r) => Math.min(...r.legs.map((l) => isoT(l.start_utc)));
    return (Array.isArray(P.recommendations) ? P.recommendations : []).filter((r) => parlayProblem(r, now, day) === null)
      .sort((a, b) => first(a) - first(b) || String(a.parlay_id).localeCompare(String(b.parlay_id))).slice(0, PC.maxCards);
  }
  // Gross potential payout INCLUDING the stake = stake x quoted combined decimal odds, to the cent.
  // Not expected value and not a probability. Null when the stake is not a usable amount.
  function grossPayout(stake, odds) {
    const s = Number(stake);
    if (stake === "" || stake == null || !isFinite(s) || s < 0 || !(odds > 1)) return null;
    return Math.round(s * odds * 100 + 1e-7) / 100;
  }
  const usd = (x) => (x == null ? "—" : "$" + x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  // ---------- estimated parlays (issue #47) ----------
  // Owner-approved estimates shown alongside the strict path. Mirrors sbi/parlay_estimated.py
  // card_problem: kind "estimated_product" (never a bookmaker quote), today in New York, 2-6 active
  // legs on distinct games that start later today, every leg priced by the card's bookmaker earlier
  // today in New York (issue #51; before the game starts), and estimated odds equal to the product
  // of those prices. A verified
  // bookmaker-quote card always wins: an estimate never reuses one of its games.
  const EC = { kind: "estimated_product",
               empty: "No parlays today: no verified quotes, and no games later today meet the estimate rules.",
               previewBadge: "Preview: may change at the next daily update", previewEmpty: "No preview yet for this day" };
  // Issue #58: with `preview` the day is a later New York date, the card must carry preview: true,
  // and its prices need only be read before each game starts (today's same-day rule is relaxed).
  function estProblem(rec, now, day, preview) {
    preview = preview === true;
    if (!rec || typeof rec !== "object") return "not an object";
    if ((rec.mock || rec.test) && !allowMock()) return "mock or test data";
    if (rec.kind !== EC.kind) return "not an estimate";
    if (!str(rec.parlay_id)) return "missing parlay_id";
    if ((rec.preview === true) !== preview) return "preview flag does not match the day";
    if (rec.date !== day) return preview ? "not this day's preview" : "not today's parlay";
    if (rec.status !== "active") return "parlay is not active";
    if (!str(rec.bookmaker)) return "missing bookmaker";
    const legs = rec.legs;
    if (!Array.isArray(legs) || legs.length < PC.minLegs || legs.length > PC.maxLegs) return "needs 2-6 legs";
    const seen = new Set();
    let product = 1, weak = 0;
    for (const l of legs) {
      if (!l || typeof l !== "object") return "leg is not an object";
      if (!str(l.event_id) || !str(l.title) || !str(l.selection)) return "leg missing identity";
      if (seen.has(l.event_id)) return "two legs on the same event";
      seen.add(l.event_id);
      if (!PC.sports.includes(l.sport)) return "unsupported sport";
      if (l.status !== "active") return "leg is not active";
      const t = isoT(l.start_utc);
      if (t == null) return "leg has no valid start time";
      if (nyKey(new Date(t)) !== day) return preview ? "leg is not on the preview's date" : "leg is not on today's date";
      if (t <= now) return "leg has started";
      if (typeof l.price !== "number" || !isFinite(l.price) || l.price <= 1) return "leg has no valid price";
      const at = isoT(l.price_at);
      if (at == null || at > now) return "leg price has no valid time";
      if (!preview && nyKey(new Date(at)) !== day) return "leg price is stale";
      if (at >= t) return "leg price read after the start";
      if (typeof l.prob === "number" && isFinite(l.prob) && l.prob * l.price < 1 - 0.0005 * l.price) weak += 1;
      product *= l.price;
    }
    if (weak > 1) return "more than one leg below its probability";
    const o = rec.estimated_odds;
    if (typeof o !== "number" || !isFinite(o) || o <= 1) return "invalid estimated odds";
    if (Math.abs(o - product) > 0.005 * o) return "estimated odds are not the product of the leg prices";
    return null;
  }
  function shownEstimates(E, blocked, limit) {
    if (!E || E.status !== "estimated") return [];
    const now = Date.now(), day = nyKey(new Date(now));
    if (E.date !== day) return [];
    const first = (r) => Math.min(...r.legs.map((l) => isoT(l.start_utc)));
    const used = new Set(blocked), out = [];
    (Array.isArray(E.recommendations) ? E.recommendations : []).filter((r) => estProblem(r, now, day) === null)
      .sort((a, b) => first(a) - first(b) || String(a.parlay_id).localeCompare(String(b.parlay_id)))
      .forEach((r) => { if (r.legs.some((l) => used.has(l.event_id))) return; r.legs.forEach((l) => used.add(l.event_id)); out.push(r); });
    return out.slice(0, Math.max(0, limit));
  }
  // Preview cards for one later New York date (issue #58): the block for that date, valid cards only.
  function previewDays() {
    const today = nyKey(new Date());
    return [1, 2, 3].map((n) => addDays(today, n));
  }
  function shownPreview(E, day) {
    const B = E && Array.isArray(E.previews) ? E.previews.find((b) => b && b.date === day && b.preview === true) : null;
    if (!B || B.status !== "preview") return [];
    const now = Date.now();
    const first = (r) => Math.min(...r.legs.map((l) => isoT(l.start_utc)));
    const used = new Set(), out = [];
    (Array.isArray(B.recommendations) ? B.recommendations : []).filter((r) => estProblem(r, now, day, true) === null)
      .sort((a, b) => first(a) - first(b) || String(a.parlay_id).localeCompare(String(b.parlay_id)))
      .forEach((r) => { if (r.legs.some((l) => used.has(l.event_id))) return; r.legs.forEach((l) => used.add(l.event_id)); out.push(r); });
    return out.slice(0, PC.maxCards);
  }
  const shortDay = (key) => { const [y, m, d] = key.split("-").map(Number); return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "short", month: "short", day: "numeric" }).format(new Date(Date.UTC(y, m - 1, d, 12))); };
  function estRecordLine(E) {
    const s = E && E.record;
    if (!s || typeof s.won !== "number" || typeof s.lost !== "number") return "";
    const pl = Number(s.paper_pl);
    if (!isFinite(pl)) return "";
    const sign = pl > 0 ? "+" : (pl < 0 ? "−" : "");
    return `Estimated parlays record: ${s.won}–${s.lost}, paper P/L ${sign}${usd(Math.abs(pl))}`;
  }
  function pricesRead(r) {
    const ts = r.legs.map((l) => isoT(l.price_at)).filter((t) => t != null);
    if (ts.length !== r.legs.length) return "";
    // Preview prices (issue #58) can be from an earlier day, so their time also shows the date.
    const fmt = r.preview === true ? (t, zone = true) => `${shortDay(nyKey(new Date(t)))}, ${fmtAsOf(t, zone)}` : fmtAsOf;
    const lo = fmt(Math.min(...ts), false), hi = fmt(Math.max(...ts));
    const one = fmt(Math.min(...ts)) === hi;
    return `<div class="pc-note" data-prices-read>${one ? `Price as of ${esc(hi)}` : `Prices as of ${esc(lo)} – ${esc(hi)}`} — check your book.</div>`;
  }
  function estCard(r, i) {
    const odds = r.estimated_odds;
    // Issue #68: an open injury/lineup note is shown on the leg (muted), never used to hide it.
    const note = (l) => str(l.risk_note) ? `<div class="lg-n" data-risk-note>${esc(l.risk_note)}</div>` : "";
    const legs = r.legs.map((l) => `<li><div class="lg-t">${vs(l.title)}</div><div class="lg-s">${esc(l.selection_text || l.selection)}</div><div class="lg-when">${esc(fmtClock(l.start_utc))}</div>${note(l)}</li>`).join("");
    const hit = typeof r.est_hit_chance === "number" && r.est_hit_chance > 0 && r.est_hit_chance < 1
      ? `<div class="pc-note">Estimated hit chance ${esc(pct(r.est_hit_chance))} (model estimate, unvalidated).</div>` : "";
    return `<article class="card parlay est" data-parlay="${esc(r.parlay_id)}" data-odds="${esc(odds)}" data-kind="estimate">
      <div class="pc-h"><span class="pc-n">Parlay ${i + 1} · ${r.legs.length} legs</span><span class="pill estimate">Estimate</span>${r.mock ? '<span class="pill mock">Mock data · testing only</span>' : ""}</div>
      ${r.preview === true ? `<div class="pc-note preview-note" data-preview><span class="pill preview">${esc(EC.previewBadge)}</span></div>` : ""}
      <ol class="legs">${legs}</ol>
      <div class="pc-foot">
        <div><div class="k">Bookmaker</div><div class="v">${esc(r.bookmaker)}</div></div>
        <div><div class="k">Estimated combined odds</div><div class="v">${dec(odds)}</div></div>
        <label><span class="k">Bet amount</span><span class="stake">$<input type="number" inputmode="decimal" min="0" step="1" value="${PC.stake}" data-stake aria-label="Bet amount in dollars for parlay ${i + 1}"></span></label>
        <div><div class="k">Potential payout</div><div class="v pay" data-payout>${usd(grossPayout(PC.stake, odds))}</div></div>
      </div>
      <div class="pc-note" data-pays10><b>$${PC.stake} bet pays ${usd(grossPayout(PC.stake, odds))}</b> (estimated, ${r.legs.length} legs, if every leg wins).</div>
      ${pricesRead(r)}
      <div class="pc-note">Estimated price: product of ${esc(r.bookmaker)}'s single-game odds, not a bet-slip quote. Your slip may pay less. Payout includes the stake and is paid only if every leg wins. $${PC.stake} is illustrative, not advice to bet.</div>
      ${hit}
    </article>`;
  }
  // ---------- today's recorded parlays (issue #57) ----------
  // Every estimate the scheduled run recorded for today's New York date (estimated_parlays.ledger_today,
  // read from ledger/estimated_parlays.csv) stays on the homepage after its games start. These cards are
  // shown exactly as first published, never rebuilt or repriced, and never look bettable once a leg starts.
  function ledgerOk(r, day) {
    if (!r || typeof r !== "object") return false;
    if ((r.mock || r.test) && !allowMock()) return false;
    if (r.kind !== EC.kind || !str(r.parlay_id) || r.date !== day || !str(r.bookmaker)) return false;
    if (typeof r.estimated_odds !== "number" || !isFinite(r.estimated_odds) || r.estimated_odds <= 1) return false;
    if (!Array.isArray(r.legs) || r.legs.length < PC.minLegs || r.legs.length > PC.maxLegs) return false;
    return r.legs.every((l) => l && typeof l === "object" && str(l.title) && str(l.selection) && isoT(l.start_utc) != null);
  }
  function recordedToday(E, skip) {
    if (!E || typeof E !== "object" || !Array.isArray(E.ledger_today)) return [];
    const day = nyKey(new Date()), seen = new Set(skip);
    const first = (r) => Math.min(...r.legs.map((l) => isoT(l.start_utc)));
    return E.ledger_today.filter((r) => ledgerOk(r, day) && !seen.has(r.parlay_id) && (seen.add(r.parlay_id), true))
      .sort((a, b) => first(a) - first(b) || String(a.parlay_id).localeCompare(String(b.parlay_id)));
  }
  const FINAL = { won: "Won", lost: "Lost", void: "Void" };
  function ledgerCard(r, i) {
    const now = Date.now();
    const first = Math.min(...r.legs.map((l) => isoT(l.start_utc)));
    const started = first <= now;
    const stake = Number(r.stake) > 0 ? Number(r.stake) : PC.stake;
    const pays = grossPayout(stake, r.estimated_odds);
    const pl = Number(r.paper_pl), plTxt = isFinite(pl) ? (pl > 0 ? "+" : (pl < 0 ? "−" : "")) + usd(Math.abs(pl)) : "–";
    let state, cls;
    if (r.result === "won") { state = `Won: paid ${usd(pays)}`; cls = "won"; }
    else if (r.result === "lost") { state = `Lost: lost ${usd(stake)}`; cls = "lost"; }
    else if (r.result === "void") { state = "Void: stake returned"; cls = "void"; }
    else if (started) { state = "Started, betting closed"; cls = "closed"; }
    else { state = `Open: first game at ${fmtClock(first)}`; cls = "open"; }
    const mark = (l) => {
      if (l.result === "won") return '<span class="lg-r won" title="Leg won">✓</span>';
      if (l.result === "lost") return '<span class="lg-r lost" title="Leg lost">✗</span>';
      if (l.result === "void") return '<span class="lg-r void">void</span>';
      return isoT(l.start_utc) <= now ? '<span class="lg-r">pending</span>' : "";
    };
    const legs = r.legs.map((l) => `<li><div class="lg-t">${vs(l.title)}</div><div class="lg-s">${esc(l.selection_text || l.selection)}</div><div class="lg-when">${esc(fmtClock(l.start_utc))} ${mark(l)}</div></li>`).join("");
    const pub = isoT(r.first_seen);
    const at = pub != null ? ` (published ${esc(fmtAsOf(pub))})` : "";
    const gone = !started && !FINAL[r.result]
      ? `<div class="pc-note">Recorded at publication; the price shown is from then and may have moved.</div>` : "";
    const closed = started || FINAL[r.result] ? `<div class="pc-note">Betting closed: a game in this parlay has started.</div>` : "";
    return `<article class="card parlay est recorded" data-parlay="${esc(r.parlay_id)}" data-kind="recorded" data-state="${esc(cls)}">
      <div class="pc-h"><span class="pc-n">Parlay ${i + 1} · ${r.legs.length} legs</span><span class="pill estimate">Estimate</span>${r.mock ? '<span class="pill mock">Mock data · testing only</span>' : ""}</div>
      <div class="pc-state ${esc(cls)}" data-state-line>${esc(state)}</div>
      <ol class="legs">${legs}</ol>
      <div class="pc-foot">
        <div><div class="k">Bookmaker</div><div class="v">${esc(r.bookmaker)}</div></div>
        <div><div class="k">Estimated odds at publication</div><div class="v">${dec(r.estimated_odds)}</div></div>
        <div><div class="k">$${esc(stake)} bet pays</div><div class="v">${usd(pays)}</div></div>
        ${FINAL[r.result] ? `<div><div class="k">Paper P/L</div><div class="v">${esc(plTxt)}</div></div>` : ""}
      </div>
      ${closed}${gone}
      <div class="pc-note">Price at publication time${at}: product of ${esc(r.bookmaker)}'s single-game odds, not a bet-slip quote. Results come from final scores; paper results only.</div>
    </article>`;
  }
  function parlayCard(r, i) {
    const odds = r.quote.decimal_odds;
    const legs = r.legs.map((l) => `<li><div class="lg-t">${vs(l.title)}</div><div class="lg-s">${l.market ? `<span class="lg-m">${esc(l.market)}</span> ` : ""}${esc(l.selection)}</div><div class="lg-when">${esc(fmtClock(l.start_utc))}</div></li>`).join("");
    return `<article class="card parlay" data-parlay="${esc(r.parlay_id)}" data-odds="${esc(odds)}">
      <div class="pc-h"><span class="pc-n">Parlay ${i + 1} · ${r.legs.length} legs</span><span class="pill active">Verified bookmaker quote</span>${r.mock ? '<span class="pill mock">Mock data · testing only</span>' : ""}</div>
      <ol class="legs">${legs}</ol>
      <div class="pc-foot">
        <div><div class="k">Bookmaker</div><div class="v">${esc(r.bookmaker)}</div></div>
        <div><div class="k">Combined odds</div><div class="v">${dec(odds)}</div></div>
        <label><span class="k">Bet amount</span><span class="stake">$<input type="number" inputmode="decimal" min="0" step="1" value="${PC.stake}" data-stake aria-label="Bet amount in dollars for parlay ${i + 1}"></span></label>
        <div><div class="k">Potential payout</div><div class="v pay" data-payout>${usd(grossPayout(PC.stake, odds))}</div></div>
      </div>
      <div class="pc-note" data-prices-read>Price as of ${esc(fmtAsOf(isoT(r.quote.quoted_at)))} — check your book.</div>
      <div class="pc-note">${esc(r.bookmaker)} combined price from the bet slip. Payout includes the stake and is paid only if every leg wins. $${PC.stake} is illustrative, not advice to bet.</div>
    </article>`;
  }
  function home() {
    const P = (D0() || {}).parlays;
    const E = (D0() || {}).estimated_parlays;
    const cards = shownParlays(P);
    const blocked = cards.flatMap((r) => r.legs.map((l) => l.event_id));
    const est = shownEstimates(E, blocked, PC.maxCards - cards.length);
    const today = nyKey(new Date()), future = previewDays();
    const sel = ["1", "2", "3"].includes(S.hday) ? Number(S.hday) : 0;
    const label = (n) => (n === 0 ? "Today" : (n === 1 ? "Tomorrow" : "+" + n));
    const seg = `<div class="seg days" role="group" aria-label="Day">${[today, ...future].map((k, n) =>
      `<button class="${sel === n ? "on" : ""}" data-f="hday" data-v="${n}" aria-pressed="${sel === n}" data-day="${esc(k)}">${label(n)} · ${esc(shortDay(k))}</button>`).join("")}</div>
      <p class="small muted daynav"><a href="#/history">Past days: History</a></p>`;
    if (sel > 0) {
      const day = future[sel - 1], prev = shownPreview(E, day);
      let p = `<div class="eyebrow">${esc(fmtDay(day))}</div><h1 style="margin-top:6px">Preview Parlays</h1>${seg}`;
      p += `<section class="section first" id="parlays" data-preview-day="${esc(day)}">`;
      if (prev.length) p += `<p class="small muted">Estimates for ${esc(fmtDay(day))}, built from the latest stored prices. Previews are replaced at every daily update and are not recorded; this day's parlays become final on the day itself.</p><div class="grid parlays">${prev.map((r, i) => estCard(r, i)).join("")}</div>`;
      else p += `<p class="zero" data-preview-empty>${esc(EC.previewEmpty)}</p>`;
      return p + `</section>`;
    }
    const rec = recordedToday(E, est.map((r) => r.parlay_id));     // issue #57: started and settled cards stay
    let h = `<div class="eyebrow">${esc(fmtDay(today))}</div><h1 style="margin-top:6px">Recommended Parlays of the Day</h1>${seg}`;
    h += `<section class="section first" id="parlays">`;
    if (cards.length) h += `<div class="grid parlays">${cards.map(parlayCard).join("")}</div>`;
    if (est.length || rec.length) h += `<h2 class="est-h"${cards.length ? "" : ' style="margin-top:0"'}>Estimated parlays of the day</h2><div class="grid parlays">${est.map((r, i) => estCard(r, cards.length + i)).join("")}${rec.map((r, i) => ledgerCard(r, cards.length + est.length + i)).join("")}</div>`;
    if (!cards.length && !est.length && !rec.length) {
      h += E && typeof E === "object" ? `<p class="zero">${esc(EC.empty)} <a href="#/parlays">Why?</a></p>`
        : `<p class="zero">No verified parlays today. <a href="#/parlays">Why?</a></p>`;
    }
    return h + `</section>`;
  }
  $app.addEventListener("input", (e) => {
    const inp = e.target && e.target.closest ? e.target.closest("[data-stake]") : null;
    if (!inp) return;
    const card = inp.closest("[data-parlay]");
    const out = card && card.querySelector("[data-payout]");
    if (out) out.textContent = usd(grossPayout(inp.value, Number(card.dataset.odds)));
  });
  function parlaysDetail() {
    const P = S.data.parlays || {};
    const a = P.audit;
    const today = dkey(new Date());
    const current = a && P.date === today;
    const n = (x, one, many) => `${esc(x)} ${x === 1 ? one : many}`;
    const check = current
      ? `<div class="kv">
          <div class="stat"><div class="k">Straight picks open</div><div class="v">${esc(a.straight_picks_seen)}</div></div>
          <div class="stat"><div class="k">Usable as legs today</div><div class="v">${esc(a.usable_legs_today)}</div></div>
          <div class="stat"><div class="k">Combinations checked</div><div class="v">${esc(a.combinations_checked)}</div></div>
          <div class="stat"><div class="k">Published</div><div class="v">0</div></div></div>
        ${Object.keys(a.excluded || {}).length ? `<div class="k" style="margin-top:12px">Excluded</div><ul class="small muted">${Object.entries(a.excluded).map(([why, c]) => `<li>${n(c, "time", "times")}: ${esc(why.replace(/^(leg|combination): /, ""))}</li>`).join("")}</ul>` : ""}
        ${a.passed_leg_screens ? `<p class="small muted">${n(a.passed_leg_screens, "combination", "combinations")} passed the leg checks but ${a.passed_leg_screens === 1 ? "is" : "are"} not published, for the reasons below.</p>` : ""}
        <p class="note">Checked ${esc(ago(P.generated))} for ${esc(fmtDay(P.date))}.</p>`
      : `<p class="small muted">No parlay check has been recorded for ${esc(fmtDay(today))} yet. Nothing is published either way.</p>`;
    const why = `<ul class="small">${(P.blockers && P.blockers.length ? P.blockers : PARLAY_BLOCKERS).map((b) => `<li>${esc(b.text)}</li>`).join("")}</ul>
      <p class="small muted">Until both exist, any parlay card would show a price nobody quoted and a probability nobody tested.</p>`;
    const needs = `<ul class="small">
        <li>Two to six legs, all on games starting later today (New York date). No extra or weaker legs are added to build one, or to raise the payout.</li>
        <li>Different games, no shared team or player, and different competitions. Same-game parlays are out.</li>
        <li>One bookmaker's own quoted price for the whole combination, with the time it was quoted. Best prices from different bookmakers are never multiplied together and shown as one quote.</li>
        <li>A joint probability with evidence behind it, not just leg probabilities multiplied on trust.</li>
        <li>A permanent snapshot at publication: legs, bookmaker, each quote, the parlay quote, times and method. Later changes are added to the record, never written over it.</li></ul>`;
    const math = `<ul class="small">
        <li>Combined odds = the leg odds multiplied together, only for unrelated legs at one bookmaker.</li>
        <li>Chance all legs win = the leg chances multiplied together, only if the legs are truly independent.</li>
        <li>Expected value = chance all legs win × parlay odds − 1. The expected values of the legs are never multiplied or added.</li></ul>
      <p class="small muted">High combined odds are not a reason to recommend anything.</p>`;
    const risk = `<div class="risk">${WARN}<span>${esc(P.disclosure || "Parlays are higher-variance and win less often than single picks. Any parlay shown here would be paper-traded research, never a guarantee.")}</span></div>
      <p class="small muted">Every leg has to win. A small error in each leg's probability compounds across legs, and the bookmaker's margin is paid on every leg.</p>`;
    return `<div class="sheet"><button class="back" data-go="#/">← Back</button>
      <div class="eyebrow">${esc(fmtDay(today))}</div><h1 style="margin-top:6px">Recommended Parlays of the Day</h1>
      <div style="margin:10px 0 4px"><span class="pill monitor">No verified parlays today</span></div>
      ${estSection()}${sec("Today's check", check)}${sec("Why none is published", why)}${sec("What a parlay would need", needs)}
      ${sec("How the numbers work", math, false)}${sec("Risk", risk)}
      <p class="note"><a href="${PARLAY_URL}" target="_blank" rel="noopener">Full parlay methodology and staged plan</a></p></div>`;
  }
  function estSection() {
    const E = S.data.estimated_parlays;
    if (!E || typeof E !== "object") return "";
    const r = E.record || {};
    const line = estRecordLine(E);
    const groups = r.by_legs && typeof r.by_legs === "object" ? Object.entries(r.by_legs) : [];
    const rows = groups.filter(([, g]) => g && typeof g.won === "number" && typeof g.lost === "number").map(([n, g]) => {
      const pl = Number(g.paper_pl), sign = pl > 0 ? "+" : (pl < 0 ? "−" : "");
      return `<tr><td>${esc(n)} legs</td><td>${esc(g.won)}–${esc(g.lost)}</td><td>${esc(g.open || 0)}</td><td>${esc(g.void || 0)}</td><td>${isFinite(pl) ? sign + usd(Math.abs(pl)) : "–"}</td></tr>`;
    }).join("");
    const byLegs = rows ? `<table class="small" data-by-legs><thead><tr><th>Size</th><th>Won–lost</th><th>Open</th><th>Void</th><th>Paper P/L</th></tr></thead><tbody>${rows}</tbody></table>` : "";
    const body = `<p class="small">Up to five estimated parlays a day for today's games (New York date), shown with an <b>Estimate</b> badge. Each uses one bookmaker that priced every leg earlier today, before the game starts; the estimated price is the product of that bookmaker's single-game odds, not a bet-slip quote, so your slip may pay less.</p>
      <ul class="small">
        <li>Two to five legs (cards of 2, 3 and 4–5 legs), one per game, all on games that haven't started. Different games in one competition are allowed; same-game combinations and legs sharing a team or player are not.</li>
        <li>Each leg uses Doyen's model probability. Where Doyen has no model (tennis) it uses a de-vigged market consensus of at least two bookmakers; a leg with neither is skipped.</li>
        <li>The whole parlay must have positive estimated value (estimated hit chance × estimated odds above 1). At most one leg may be priced below Doyen's probability, and only inside a positive pair; no further leg may lower the parlay's value.</li>
        <li>Picked per size: the best 4–5 leg, 3-leg and 2-leg parlay, then a second of each while room remains. A size with nothing qualifying is skipped, never padded.</li>
        <li>Within a size, ranked by estimated hit chance × estimated value. The hit chance multiplies leg probabilities as if the legs were independent; it is unvalidated.</li>
        <li>A verified bookmaker quote always replaces an estimate on the same games.</li></ul>
      ${line ? `<p class="small"><b>${esc(line)}</b>${typeof r.open === "number" ? ` · ${esc(r.open)} open, ${esc(r.void || 0)} void` : ""}. Paper results at the $${PC.stake} display stake and the estimated price, settled from final scores; a void leg voids the whole parlay here.</p>${byLegs}` : ""}`;
    return sec("Estimated parlays", body);
  }
  function closeAllView() {
    const D = S.data;
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const list = (D.close_to_value || []).map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
    return `<button class="back" data-go="#/">← Today's Picks</button><h1>Close to Value</h1>
      <p class="lead">Real, current prices near Doyen's threshold. Not recommendations.</p>${filters(false)}
      <div class="grid" style="margin-top:16px">${list.map(closeCard).join("") || `<div class="card empty-cc"><h3>Nothing close right now</h3></div>`}</div>`;
  }
  function watchingAll() {
    const D = S.data;
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const list = D.watching.map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
    return `<button class="back" data-go="#/">← Today's Picks</button><h1>Matches Doyen Is Watching</h1>
      <p class="lead">Monitoring only, not recommendations. Ranked by data completeness, price quality, pending information, then start time.</p>${filters(false)}
      <div class="grid" style="margin-top:16px">${list.map(watchCard).join("") || `<div class="card empty-cc"><h3>Nothing on the radar</h3></div>`}</div>`;
  }

  function staleBanner() {
    const hrs = (Date.now() - new Date(S.data.generated)) / 36e5;
    return hrs > 26 ? `<div class="banner">${WARN.replace("<svg", '<svg width="16" height="16"')}<span>Data last refreshed ${esc(ago(S.data.generated))}. Prices may have moved.</span></div>` : "";
  }
  function eventStatus(r) {
    if (r.has_pick) return '<span class="pill active">Pick</span>';
    if (S.data.watching.includes(r.event_id)) return '<span class="pill monitor">Watching</span>';
    if (!r.n_books) return '<span class="pill">No odds yet</span>';
    return '<span class="pill">Analysed</span>';
  }
  function eventRow(r) {
    const brief = r.has_pick || S.data.watching.includes(r.event_id) ? r.short : "";
    return `<div class="row" data-go="#/event/${esc(r.event_id)}" role="link" tabindex="0">
      <div class="t">${esc(fmtClock(r.start_utc))}</div>
      <div class="ev"><b>${vs(r.title)}</b><span>${ICON[r.sport] || ""}${esc(sportName(r.sport))} · ${esc(r.competition)}</span>${brief ? `<em>${esc(brief)}</em>` : ""}</div>
      ${eventStatus(r)}</div>`;
  }
  function upcoming() {
    const ev = S.data.events.filter((r) => sportOk(r.sport, S.sport) && inRange(r.start_utc, r.end_utc, S.range));
    let h = `<h1>Upcoming</h1>${filters()}${sportNotice(S.sport)}`;
    if (!ev.length) return h + `<div class="card empty-cc" style="margin-top:16px"><h3>No events in this window</h3><p>Try a wider date range.</p></div>`;
    const days = {};
    ev.forEach((r) => { const k = dkey(new Date(r.start_utc)); (days[k] = days[k] || []).push(r); });
    Object.keys(days).sort().forEach((k) => { h += `<div class="day"><h3>${esc(fmtDay(k))}</h3><div class="rows">${days[k].map(eventRow).join("")}</div></div>`; });
    return h;
  }

  // Issue #57: every recorded parlay (ledger/estimated_parlays.csv), newest first, with its result.
  function parlayHistory() {
    const rows = (Array.isArray(S.data.parlay_history) ? S.data.parlay_history : [])
      .filter((r) => r && typeof r === "object" && str(r.parlay_id) && Array.isArray(r.legs) && ((!r.mock && !r.test) || allowMock()));
    const E = S.data.estimated_parlays || {};
    const R = E.record || {};
    const line = estRecordLine(E);
    const groups = R.by_legs && typeof R.by_legs === "object" ? Object.entries(R.by_legs) : [];
    const signed = (x) => { const v = Number(x); return isFinite(v) ? (v > 0 ? "+" : (v < 0 ? "−" : "")) + usd(Math.abs(v)) : "–"; };
    // Issue #65: styled record-by-size table. Display only; every number comes from E.record as published.
    const plCls = (x) => { const v = Number(x); return !isFinite(v) || v === 0 ? "zero" : (v > 0 ? "pos" : "neg"); };
    const hit = (g) => { const n = (Number(g.won) || 0) + (Number(g.lost) || 0); return n ? Math.round((Number(g.won) || 0) / n * 100) + "%" : "–"; };
    const sizeRow = (label, g, cls) => `<tr${cls ? ` class="${cls}"` : ""}><th scope="row">${esc(label)}</th><td>${esc(g.won)}–${esc(g.lost)}</td><td>${hit(g)}</td><td>${esc(g.void || 0)}</td><td>${esc(g.open || 0)}</td><td class="pl ${plCls(g.paper_pl)}">${signed(g.paper_pl)}</td></tr>`;
    const byLegs = groups.filter(([, g]) => g && typeof g.won === "number").map(([n, g]) => sizeRow(`${n} legs`, g)).join("");
    const total = byLegs && typeof R.won === "number" && typeof R.lost === "number" ? sizeRow("Total", R, "total") : "";
    const RES = { won: "Won", lost: "Lost", void: "Void", open: "Open" };
    const mk = { won: " ✓", lost: " ✗", void: " (void)" };
    const list = rows.map((r) => {
      const legs = r.legs.map((l) => `<li>${vs(l.title)}: ${esc(l.selection_text || l.selection)}${mk[l.result] || ""}</li>`).join("");
      const res = RES[r.result] || "Open";
      return `<div class="card ph" data-ph="${esc(r.parlay_id)}" data-result="${esc(r.result || "open")}">
        <div class="ph-h"><span class="t">${esc(fmtDay(r.date))}</span><span>${esc(r.bookmaker)} · ${esc(r.n_legs || r.legs.length)} legs</span><span class="pill ${esc(r.result || "open")}">${esc(res)}</span></div>
        <ul class="ph-legs small">${legs}</ul>
        <div class="ph-f small"><span>Estimated odds <b>${dec(r.estimated_odds)}</b></span><span>$${esc(Number(r.stake) || PC.stake)} bet pays <b>${usd(Number(r.gross_payout))}</b></span><span>Paper P/L <b>${r.result === "open" ? "–" : signed(r.paper_pl)}</b></span></div></div>`;
    }).join("");
    const table = byLegs ? `<div class="card ph-rec"><table data-ph-by-legs><caption class="sr">Estimated parlay record by number of legs</caption><thead><tr><th scope="col">Size</th><th scope="col">Won–lost</th><th scope="col" title="Won ÷ (won + lost); voids and open parlays excluded">Hit rate</th><th scope="col">Void</th><th scope="col">Open</th><th scope="col">Paper P/L</th></tr></thead><tbody>${byLegs}</tbody>${total ? `<tfoot>${total}</tfoot>` : ""}</table></div>` : "";
    return `<section class="section" id="parlay-history"><div class="section-h"><h2>Parlays</h2></div>
      <p class="small muted">Every estimated parlay Doyen recorded, newest first, at the estimated price first shown (product of one bookmaker's single-game odds, not a bet-slip quote). Results come from final scores; paper P/L at the stake shown. A void leg voids the whole parlay here. Nothing is edited or removed.</p>
      ${line ? `<div class="brief"><span><b>${esc(line.replace(/^Estimated parlays record: /, "Record "))}</b></span><span class="dot"></span><span><b>${esc(R.open || 0)}</b> open · ${esc(R.void || 0)} void</span></div>` : ""}
      ${table}
      ${list ? `<div class="ph-list">${list}</div>` : `<p class="small muted">No parlays recorded yet.</p>`}</section>`;
  }

  function history() {
    const now = Date.now();
    const H = S.data.history.filter((p) => sportOk(p.sport, S.hsport) && (S.hrange === "all" || (now - new Date(p.published_at)) / 864e5 <= (S.hrange === "7" ? 7 : 30)));
    const settled = H.filter((p) => p.status.state === "settled");
    const W = settled.filter((p) => ["won", "half_won"].includes(p.status.result)).length;
    const L = settled.filter((p) => ["lost", "half_lost"].includes(p.status.result)).length;
    const P = settled.length - W - L;
    // Issue #63: Parlays come first on History; single picks follow under their own heading.
    let h = `<h1>Pick History</h1><p class="lead">Every published parlay and pick at its original odds. Nothing is edited or removed.</p>`
      + parlayHistory()
      + `<section class="section" id="pick-history"><div class="section-h"><h2>Single picks</h2></div>
      ${filters(true, "hsport", "hrange", [["7", "7 days"], ["30", "30 days"], ["all", "All time"]])}
      <div class="brief"><span>Record <b>${W}–${L}${P ? "–" + P : ""}</b></span><span class="dot"></span><span><b>${H.length - settled.length}</b> awaiting result</span></div>`;
    if (!H.length) return h + `<div class="card empty-cc" style="margin-top:16px"><h3>No picks in this period</h3><p>Quiet periods are normal: Doyen only publishes when the evidence clears its bar.</p></div></section>`;
    const res = (p) => p.status.state === "settled" ? statusPill(p.status) : `<span class="pill">${p.status.state === "withdrawn" ? "Withdrawn" : "Pending"}</span>`;
    return h + `<div class="rows hist" style="margin-top:14px">` + H.map((p) => `<div class="row" data-go="#/pick/${esc(p.id)}" role="link" tabindex="0">
        <div class="t">${esc(fmtMon(p.published_at))}</div>
        <div class="ev"><b>${vs(p.title)}</b><span>${esc(p.selection)}</span></div>
        <div class="t r">${dec(p.odds)}</div>${res(p)}</div>`).join("") + `</div></section>`;
  }

  function watchlist() {
    const D = S.data;
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const picksByEv = {}; D.history.forEach((p) => { (picksByEv[p.event_id] = picksByEv[p.event_id] || []).push(p); });
    const ids = [...S.watch];
    let h = `<h1>Watchlist</h1><p class="lead">Saved in this browser only. It won't sync to other devices.</p>`;
    if (!ids.length) return h + `<div class="card empty-cc" style="margin-top:16px"><h3>Your watchlist is empty</h3><p>Tap ☆ on any pick or match to follow it here.</p></div>`;
    return h + `<div class="rows" style="margin-top:16px">` + ids.map((id) => {
      const r = evById[id], pk = (picksByEv[id] || [])[0];
      if (!r && !pk) return `<div class="row"><div class="t">—</div><div class="ev"><b>No longer listed</b><span>Finished or outside the data window.</span></div>${starBtn(id)}</div>`;
      const x = r || pk;
      const status = pk ? statusPill(pk.status) : eventStatus(r);
      const line = pk ? `${pk.selection} @ ${dec(pk.odds)}` : (r.closest ? `${r.closest.selection_text} @ ${dec(r.closest.odds)}` : "Odds unavailable");
      return `<div class="row" data-go="${pk ? "#/pick/" + esc(pk.id) : "#/event/" + esc(id)}" role="link" tabindex="0">
        <div class="t">${esc(fmtMon(x.start_utc))}<small>${esc(fmtClock(x.start_utc))}</small></div>
        <div class="ev"><b>${vs(x.title)}</b><span>${esc(line)}</span></div>${status}${starBtn(id)}</div>`;
    }).join("") + `</div>`;
  }

  // ---------- details ----------
  function cmpBars(mv, bv) {
    const keys = Object.keys(mv || {});
    if (!keys.length) return "";
    return keys.map((k) => `<div class="cmp"><span class="muted">${esc(k)}</span><div><div class="bar" title="Doyen model"><i style="width:${(mv[k] * 100).toFixed(1)}%"></i></div>${bv && bv[k] != null ? `<div class="bar b2" title="Bookmakers (no-vig)"><i style="width:${(bv[k] * 100).toFixed(1)}%"></i></div>` : ""}</div><span>${pct(mv[k])}${bv && bv[k] != null ? `<br><span class="faint">${pct(bv[k])}</span>` : ""}</span></div>`).join("") +
      (bv && Object.keys(bv).length ? `<p class="note">Gold: Doyen's model · Blue: bookmakers' consensus (margin removed)</p>` : "");
  }
  function formBlock(form) {
    if (!form) return "";
    return `<div class="kv">` + Object.entries(form).map(([t, f]) => `<div class="stat"><div class="k">${esc(t)}</div><div class="v">${esc(f.last || "—")}</div><div class="faint small">${f.gf}–${f.ga}${f.xg_for_avg != null ? ` · xG ${f.xg_for_avg}/${f.xg_against_avg}` : ""}</div></div>`).join("") + `</div>`;
  }
  const sec = (title, body, open = true) => body ? `<details class="card sec" ${open ? "open" : ""}><summary>${esc(title)}</summary><div class="sec-b">${body}</div></details>` : "";
  function injuriesBlock(inj) {
    if (!inj || !Object.keys(inj).length) return "";
    return Object.entries(inj).map(([team, list]) => `<div class="small"><b>${esc(team)}</b>: ${list.length ? list.map((i) => `${esc(i.player)} (${esc(i.status)}${i.key ? ", key player" : ""})`).join(", ") : "no reported absences"}</div>`).join("") ;
  }
  function weatherBlock(w) {
    if (!w) return "";
    return `<div class="small">Weather: ${esc(w.temperature_f)}°F · gusts ${esc(w.gust_mph ?? "—")} mph · precipitation ${esc(w.precip_pct ?? "—")}%${w.notable ? ' <span class="pill stale">notable</span>' : ""}</div>`;
  }
  function disagreementBlock(d) {
    if (!d || !d.category || d.category === "none") return "";
    const lab = { explained: "Explained", unexplained: "Unexplained · held for review", technical_suspect: "Possible data fault · held" }[d.category] || d.category;
    return `<div class="k" style="margin-top:10px">Model vs market check</div><div class="small">${pct(d.gap)} gap · ${esc(lab)}${(d.flags || []).length ? ": " + esc(d.flags.join("; ")) : ""}</div>`;
  }
  function extForecast(f) {
    if (!f) return "";
    return `<div class="small">${esc(f.source)}: ${Object.entries(f.probs).map(([k, v]) => `${esc(k)} ${pct(v)}`).join(" · ")} <span class="faint">(${esc(ago(f.retrieved_at))})</span></div>`;
  }

  function pickDetail(id) {
    const p = S.data.history.find((x) => x.id === id);
    if (!p) return `<button class="back" data-go="#/">← Back</button><div class="card empty-cc"><h3>Pick not found</h3></div>`;
    const d = p.detail || {};
    const prices = d.prices || {};
    const sel = `<div class="kv">
        <div class="stat"><div class="k">Best odds</div><div class="v">${dec(p.odds)} <span class="faint small">${esc(p.bookmaker)}</span></div></div>
        <div class="stat"><div class="k">Estimated chance</div><div class="v">${pct(p.prob, 1)}</div></div>
        <div class="stat"><div class="k">Fair odds</div><div class="v">${dec(p.fair_odds)}</div></div>
        <div class="stat"><div class="k">Expected value</div><div class="v pos">${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}</div></div></div>
        <p class="note">${esc(p.ev_plain)}</p>`;
    const stats = [
      d.expected_goals ? `<div class="small muted">Expected goals ${esc(d.expected_goals.home)}–${esc(d.expected_goals.away)}</div>` : "",
      d.model_markets && d.model_markets["1X2:H"] != null ? cmpBars({ Home: d.model_markets["1X2:H"], Draw: d.model_markets["1X2:D"], Away: d.model_markets["1X2:A"] }, null) : "",
      `<div class="kv"><div class="stat"><div class="k">Estimated chance (used)</div><div class="v">${pct(p.prob, 1)}</div><div class="faint small">${p.detail.blend_weight > 0 ? "model + market blend" : "from the sharp market, margin removed"}</div></div>
        <div class="stat"><div class="k">Sharp market</div><div class="v">${pct(p.market_prob, 1)}</div><div class="faint small">${esc(d.consensus_source || "")}, excl. ${esc(p.bookmaker)}</div></div>
        <div class="stat"><div class="k">Doyen's model</div><div class="v">${pct(p.model_prob, 1)}</div><div class="faint small">independent · context only</div></div></div>`,
      d.context ? `<p class="small">${esc(d.context)}</p>` : "",
      formBlock(d.form), injuriesBlock(d.injuries), weatherBlock(d.weather), extForecast(d.external_forecast),
      Object.keys(prices).length ? `<div class="k" style="margin-top:10px">Prices · ${esc(d.n_bookmakers || "")} bookmakers · reference ${esc(d.consensus_source || "—")}</div><div class="prices">${Object.entries(prices).map(([bk, q]) => `<div class="${bk === p.bookmaker ? "best" : ""}"><span>${esc(bk)}</span><span>${Object.entries(q || {}).map(([s, v]) => `${esc(s)} ${dec(v)}`).join(" · ")}</span></div>`).join("")}</div>` : "",
    ].join("");
    const risks = `<div class="risk">${WARN}<span>${esc(p.risk)}</span></div>${(p.risks || []).length ? `<ul class="small muted">${p.risks.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${(p.notes || []).length ? `<div class="k">Research notes</div><ul class="small">${p.notes.map((n) => `<li><span class="pill">${esc(n.evidence_type.replace("_", " "))}</span> ${esc(n.claim)} ${n.source_url ? `<a href="${esc(n.source_url)}" target="_blank" rel="noopener">source</a>` : ""}</li>`).join("")}</ul>` : ""}`;
    const srcs = `<ul class="timeline small">
        <li><span class="pill">Published</span><span>${esc(fmtTime(p.published_at))} at ${dec(p.odds)} (${esc(p.bookmaker)}). Permanent record.</span></li>
        ${(p.updates || []).map((u) => `<li><span class="pill ${esc(u.status)}">${esc(u.status)}</span><span>${esc(fmtTime(u.checked_at))}: ${esc(u.note || "")}</span></li>`).join("")}
        ${p.status.state === "settled" ? `<li><span class="pill ${esc(p.status.result.replace("half_", ""))}">${esc(p.status.label)}</span><span>Paper result ${p.status.pnl >= 0 ? "+" : ""}${Number(p.status.pnl).toFixed(2)} units.</span></li>` : ""}
      </ul><p class="note">Odds updated ${esc(ago(p.odds_updated))} · Sources: ${(d.sources || []).map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").split("/")[0])}</a>`).join(" · ") || "—"} · model ${esc(p.model_version)}</p>`;
    return `<div class="sheet"><button class="back" data-go="#/">← Back</button>
      ${topline(p, true)}<h1 style="margin-top:6px">${vs(p.title)}</h1>
      <div class="cc-main" style="margin-top:12px"><div><div class="k">${esc(p.market)}</div><div class="sel big">${esc(p.selection)}</div></div><div class="odds"><div class="o">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")}</div></div></div>
      <div style="margin:8px 0 4px">${statusPill(p.status)} ${p.status.note ? `<span class="faint small">${esc(p.status.note)}</span>` : ""}</div>
      ${sec("The selection", sel)}${sec("Why Doyen is interested", `<p class="why">${esc(p.why)}</p>`)}${sec("Supporting statistics", stats, false)}
      ${sec("What could go wrong", risks)}${sec("Sources and updates", srcs, false)}
      <div class="actions">${starBtn(p.event_id).replace('class="star', 'class="ibtn')}<a class="btn ghost" href="#/ask/pick/${esc(p.id)}">Ask Doyen</a></div></div>`;
  }

  function eventDetail(id) {
    const r = S.data.events.find((x) => x.event_id === id);
    if (!r) return `<button class="back" data-go="#/upcoming">← Back</button><div class="card empty-cc"><h3>Event not found</h3><p>It may have finished or left the data window.</p></div>`;
    const pk = S.data.picks.find((p) => p.event_id === id);
    const c = r.closest;
    const watch = c ? `<div class="kv">
        <div class="stat"><div class="k">${esc(c.market_label)}</div><div class="v">${esc(c.selection_text)}</div></div>
        <div class="stat"><div class="k">Current odds</div><div class="v">${dec(c.odds)} <span class="faint small">${esc(c.bookmaker || "")}</span></div></div>
        <div class="stat"><div class="k">Fair odds (sharp market)</div><div class="v">${c.market_prob ? dec(1 / c.market_prob) : "—"}</div></div>
        <div class="stat"><div class="k">Value vs fair</div><div class="v">${c.ev == null ? "—" : (c.ev >= 0 ? "+" : "") + pct(c.ev, 1)}</div></div></div>
        <p class="small" style="margin-top:10px"><b>${esc(r.short)}</b></p><p class="note">Not a pick because: ${esc(({ "EV below threshold": "the price isn't far enough above fair value", "too few bookmakers": "fewer than 3 bookmakers price this market", "too few verified independent bookmakers": "fewer than 3 verified, independent bookmakers price this market", "odds outside range": "the value is only at odds outside Doyen's range", "insufficient team history": "one side has too little history", "no market consensus": "there is no sharp reference price" })[c.reason] || c.reason || "below thresholds")}. ${c.n_books != null ? esc(c.n_books) + " bookmaker(s) quote this market." : ""}</p>` : `<p class="small">Odds unavailable. ${esc(r.short || "")}</p>`;
    const stats = [cmpBars(r.model_view, r.book_view), r.expected_goals ? `<div class="small muted">Expected goals ${esc(r.expected_goals.home)}–${esc(r.expected_goals.away)}</div>` : "",
      r.extra_text ? `<p class="small">${esc(r.extra_text)}</p>` : "", formBlock(r.form), injuriesBlock(r.injuries), weatherBlock(r.weather), extForecast(r.external_forecast), disagreementBlock(r.disagreement),
      r.model_weight === 0 ? `<p class="note">The model has not beaten the market out of sample, so its view is context only.</p>` : ""].join("");
    const why = `<p class="why">${esc(r.why_interesting || "Routine analysis.")}</p>${r.rank_basis ? `<p class="note">Watch ranking: ${esc(r.rank_basis)}</p>` : ""}`;
    const srcs = `<p class="small">${r.odds_updated ? "Odds updated " + esc(ago(r.odds_updated)) + " · " : ""}${r.n_books || 0} bookmaker(s) · ${esc(r.competition)}${r.neutral ? " · neutral venue" : ""}</p>${(r.notes || []).length ? `<ul class="small muted">${r.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}${(r.discrepancies || []).length ? `<div class="k">Source discrepancies</div><ul class="small">${r.discrepancies.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : ""}`;
    return `<div class="sheet"><button class="back" data-go="#/upcoming">← Back</button>
      ${topline(r, true)}<h1 style="margin-top:6px">${vs(r.title)}</h1>
      <div style="margin:10px 0">${pk ? `<a class="btn" href="#/pick/${esc(pk.id)}">View Doyen's pick →</a>` : `<span class="pill monitor">${S.data.watching.includes(id) ? "Watching · not a recommendation" : "Analysed · no pick"}</span>`}</div>
      ${sec("What Doyen is watching", watch)}${sec("Why it's interesting", why)}${sec("Supporting statistics", stats, false)}${sec("Sources and updates", srcs, false)}
      <div class="actions">${starBtn(id).replace('class="star', 'class="ibtn')}<a class="btn ghost" href="#/ask/event/${esc(id)}">Ask Doyen</a></div></div>`;
  }

  // ---------- Ask Doyen (handoff to Claude; no embedded AI, no secrets) ----------
  function askContext(kind, id) {
    const D = S.data;
    const lines = [`Sports Betting Doyen data snapshot generated ${D.generated} (times UTC).`];
    const pk = (p) => `- [${sportName(p.sport)} · ${p.competition}] ${p.title}, ${p.start_utc}: ${p.market} — ${p.selection} @ ${p.odds} (${p.bookmaker}); Doyen probability ${pct(p.prob, 1)}, fair odds ${dec(p.fair_odds)}, EV ${pct(p.ev, 1)}; model's own view ${pct(p.model_prob, 1)}; status ${p.status.label}. Why: ${p.why} Main risk: ${p.risk}`;
    if (kind === "pick") { const p = D.history.find((x) => x.id === id); if (p) { lines.push("Selected pick:", pk(p)); if (p.detail && p.detail.prices) lines.push("Prices: " + JSON.stringify(p.detail.prices)); } }
    else if (kind === "event") { const r = D.events.find((x) => x.event_id === id); if (r) lines.push(`Selected event: [${sportName(r.sport)} · ${r.competition}] ${r.title} at ${r.start_utc}. Model view ${JSON.stringify(r.model_view)}; bookmakers ${JSON.stringify(r.book_view)}; closest candidate ${JSON.stringify(r.closest || null)}; waiting for: ${r.waiting_for}.`); }
    lines.push(`Current picks (${D.picks.length}):`); D.picks.slice(0, 8).forEach((p) => lines.push(pk(p)));
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    lines.push("Watching (not recommendations):"); D.watching.slice(0, 6).forEach((wid) => { const r = evById[wid]; if (r) lines.push(`- [${sportName(r.sport)}] ${r.title} ${r.start_utc}: ${r.why_interesting} Waiting for: ${r.waiting_for}`); });
    lines.push(`Paper record: ${D.record.won}W-${D.record.lost}L-${D.record.push}P, ${D.record.profit_units} units, ${D.record.open} open.`);
    lines.push("Sports status: " + Object.values(D.sports).map((s) => `${s.name}: ${s.operational ? (s.picks_possible === false ? "model-only monitoring" : "operational") : "in development"}`).join("; "));
    return lines.join("\n");
  }
  function ask(kind, id) {
    const sugg = ["Why do you like this selection?", "What's your strongest opportunity today?", "What are the biggest risks in today's selections?",
      "Do you see any value in the NFL games this weekend?", "What changed in the odds for this match?", "How have your soccer recommendations performed this month?",
      "What does your tennis model think about this matchup?"];
    const ctx = askContext(kind, id);
    const subject = kind === "pick" ? (S.data.history.find((x) => x.id === id) || {}).selection : kind === "event" ? (S.data.events.find((x) => x.event_id === id) || {}).title : null;
    setTimeout(() => {
      const q = document.getElementById("q"), go = document.getElementById("go"), cp = document.getElementById("cp");
      document.querySelectorAll(".sugg button").forEach((b) => b.addEventListener("click", () => { q.value = b.textContent; q.focus(); }));
      const prompt = () => `You are the research assistant for "Sports Betting Doyen", my personal sports betting research site. Answer my question using ONLY the data snapshot below, plus any web research you do yourself, labelled clearly as such. If the snapshot doesn't contain what's needed, say so plainly rather than guessing. Never describe a bet as safe or guaranteed. Express uncertainty honestly.\n\nQUESTION: ${q.value.trim() || "Give me a short briefing on today's picks and risks."}\n\nDATA SNAPSHOT:\n${ctx}`.slice(0, 7000);
      go.addEventListener("click", () => { window.open("https://claude.ai/new?q=" + encodeURIComponent(prompt()), "_blank", "noopener"); });
      cp.addEventListener("click", async () => { try { await navigator.clipboard.writeText(prompt()); cp.textContent = "Copied ✓"; } catch (e) { q.select(); cp.textContent = "Copy failed — select manually"; } });
    }, 0);
    return `<div class="sheet ask"><div class="eyebrow">Conversation</div><h1 style="margin-top:8px">Ask Doyen</h1>
      <p class="lead">${subject ? `About: <b style="color:var(--ivory)">${esc(subject)}</b>. ` : ""}Ask anything about today's research. Doyen packages its current picks, prices and risks into your question and opens it in Claude.</p>
      <div class="card block"><label for="q" class="sr">Your question</label><textarea id="q" placeholder="e.g. What are the biggest risks in today's selections?"></textarea>
      <div class="sugg">${sugg.map((s) => `<button type="button">${esc(s)}</button>`).join("")}</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn" id="go">Ask in Claude ↗</button><button class="btn ghost" id="cp">Copy question with data</button></div>
      <p class="note"><b>How this works:</b> this site is static, so it doesn't run an AI model or hold any API keys. "Ask in Claude" opens a new Claude conversation in your own account, pre-filled with your question and Doyen's latest data, so nothing is answered by this page. Claude only knows what's in that snapshot, plus anything it researches itself. For questions about long-term performance or model diagnostics, ask the Doyen agent in Claude Code, which has the full database.</p></div></div>`;
  }

  // ---------- router ----------
  const TITLES = { picks: "Single Picks", close: "Close to Value", upcoming: "Upcoming", history: "Pick History", watchlist: "Watchlist", ask: "Ask Doyen", pick: "Pick analysis", event: "Match", watching: "Watching", parlays: "Parlays" };
  function render() {
    const parts = (location.hash.replace(/^#\/?/, "") || "").split("/");
    const r = parts[0] || "home";
    document.querySelectorAll("[data-r]").forEach((a) => a.classList.toggle("on", a.dataset.r === (r === "parlays" ? "home" : (r === "watching" || r === "close" ? "picks" : (r === "pick" || r === "event" ? "" : r)))));
    let html;
    if (r === "home") {
      if (!D0()) return;
      html = home();
    } else if (!S.data) { loadFull(); return; }
    else if (r === "picks") html = picksView();
    else if (r === "upcoming") html = upcoming();
    else if (r === "history") html = history();
    else if (r === "watchlist") html = watchlist();
    else if (r === "ask") html = ask(parts[1], parts[2]);
    else if (r === "watching") html = watchingAll();
    else if (r === "close") html = closeAllView();
    else if (r === "parlays") html = parlaysDetail();
    else if (r === "pick") html = pickDetail(parts[1]);
    else if (r === "event") html = eventDetail(parts[1]);
    else html = picksView();
    $app.innerHTML = html;
    document.title = (TITLES[r] ? TITLES[r] + " · " : "") + "Sports Betting Doyen";
  }
  window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
  $app.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-go]")) { e.preventDefault(); location.hash = e.target.dataset.go; } });

  function tzSelect() {
    const sel = document.getElementById("tz");
    const zones = ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix", "America/Anchorage", "Pacific/Honolulu", "America/Toronto", "America/Mexico_City", "America/Sao_Paulo", "Europe/London", "Europe/Madrid", "Europe/Paris", "Europe/Berlin", "Africa/Johannesburg", "Asia/Dubai", "Asia/Kolkata", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney", "UTC"];
    const cur = tz();
    if (!zones.includes(cur)) zones.unshift(cur);
    sel.innerHTML = zones.map((z) => `<option value="${z}" ${z === cur ? "selected" : ""}>${z.replace("_", " ")}</option>`).join("");
    sel.addEventListener("change", () => { S.tz = sel.value; store.set("tz", sel.value); render(); });
  }

  // The homepage needs only the small parlay file; every other route loads the full research file.
  const getJSON = (u) => fetch(u, { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
  let tzReady = false;
  function ready(d) {
    if (!tzReady) { tzReady = true; tzSelect(); }
    document.getElementById("updated").textContent = "· Updated " + ago(d.generated);
    const rec = document.getElementById("estrec");      // issue #47: one-line estimated-parlay record in the footer
    if (rec) { const line = estRecordLine(d.estimated_parlays); rec.textContent = line; rec.hidden = !line; }
  }
  const fail = (e) => { $app.innerHTML = `<div class="card empty" style="margin-top:24px"><h3>Doyen couldn't load today's research</h3><p>${esc(e.message)}. Please try again in a minute.</p></div>`; };
  let fullP = null;
  function loadFull() {
    if (!fullP) {
      $app.innerHTML = '<div class="skeleton" style="margin-top:24px"></div>';
      fullP = getJSON("data/doyen.json").then((d) => {
        S.data = d;
        d.history.forEach((p) => { p._sel = null; });
        ready(d);
        render();
      }).catch((e) => { fullP = null; fail(e); });
    }
    return fullP;
  }
  const r0 = (location.hash.replace(/^#\/?/, "") || "").split("/")[0];
  if (!r0 || r0 === "home") {
    getJSON("data/parlays.json").then((d) => { if (!d || typeof d !== "object" || !("parlays" in d)) throw new Error("bad parlay file"); S.lite = d; ready(d); render(); })
      .catch(() => loadFull());
  } else loadFull();
})();
