/* Sports Betting Doyen — static front end. Reads data/doyen.json. No tracking, no secrets. */
(function () {
  "use strict";
  const $app = document.getElementById("app");
  const store = {
    get(k, d) { try { const v = localStorage.getItem("doyen." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("doyen." + k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
  };
  const S = { data: null, sport: store.get("sport", "all"), range: "today", hrange: "all", hsport: "all",
              tz: store.get("tz", null), watch: new Set(store.get("watch", [])) };

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
  const tz = () => S.tz || (S.data && S.data.default_timezone) || "America/New_York";
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
  function pickCard(p, featured) {
    const st = p.status || {};
    const flag = st.state && st.state !== "active" ? statusPill(st) : (p.stale ? '<span class="pill stale">Price may be stale</span>' : "");
    return `<article class="card cc ${featured ? "feat" : ""}" data-go="#/pick/${esc(p.id)}" role="link" tabindex="0">
      ${featured ? `<div class="crown"><span>Doyen's Pick of the Day</span><i></i></div>` : ""}
      <div class="cc-top">${topline(p)}${starBtn(p.event_id)}</div>
      <div class="cc-title">${vs(p.title)}</div>
      <div class="cc-main">
        <div><div class="k">${esc(p.market)}</div><div class="sel">${esc(p.selection)}</div></div>
        <div class="odds"><div class="o">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")}</div></div>
      </div>
      <div class="cc-facts"><span>Estimated chance <b>${pct(p.prob)}</b></span>${featured ? `<span>Expected value <b class="pos">${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}</b></span>` : ""}</div>
      <div class="cc-why"><span>Why</span> ${esc(p.why_short || "")}</div>
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
    return `<div class="brief"><span><b>${nEvents}</b> events</span><span class="dot"></span><span><b>${markets.toLocaleString()}</b> markets priced this week</span><span class="dot"></span><span><b>${picks.length || "No"}</b> pick${picks.length === 1 ? "" : "s"} ${picks.length ? "qualify" : "qualify yet"}</span>${s.sentence ? `<span class="brief-s">${esc(s.sentence)}</span>` : ""}</div>`;
  }
  function home() {
    const D = S.data;
    const picks = D.picks.filter((p) => sportOk(p.sport, S.sport) && inRange(p.start_utc, null, S.range));
    let featured = null;
    if (S.range === "today") featured = picks.find((p) => p.id === D.pick_of_the_day && sportOk(p.sport, S.sport)) || null;
    if (!featured && picks.length && picks[0].status.state === "active") featured = picks[0];
    const rest = picks.filter((p) => !featured || p.id !== featured.id);
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const allWatch = D.watching.map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
    const watching = allWatch.filter((r) => inRange(r.start_utc, r.end_utc, S.range));
    const shown = (watching.length ? watching : allWatch).slice(0, 3);
    const nEvents = D.events.filter((r) => sportOk(r.sport, S.sport) && inRange(r.start_utc, r.end_utc, S.range)).length;
    let h = `<div class="eyebrow">${esc(fmtDay(dkey(new Date())))}</div><h1 style="margin-top:6px">Today's Picks</h1>
      ${briefing(D, picks, nEvents)}${filters()}${staleBanner()}${sportNotice(S.sport)}`;
    if (featured) h += `<section class="section first">${pickCard(featured, true)}</section>`;
    else h += `<section class="section first"><div class="card empty-cc"><div class="crown"><span>${S.range === "week" ? "This Week's Picks" : "Doyen's Pick of the Day"}</span><i></i></div><h3>No verified pick ${esc({ today: "today", tomorrow: "for tomorrow", week: "this week" }[S.range])} yet.</h3><p>Every priced market is checked against the sharp consensus; none clears the bar right now.</p></div></section>`;
    if (rest.length) h += `<section class="section"><div class="section-h"><h2>More picks</h2><span class="count">${rest.length}</span></div><div class="grid">${rest.map((p) => pickCard(p)).join("")}</div></section>`;
    if (S.range === "today") h += parlaysSection();
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
  // ---------- parlays (issue #7, stage 0) ----------
  // Doyen publishes no parlays yet: it has no bookmaker-quoted parlay price and no validated joint
  // probability (docs/PARLAYS.md). There is deliberately NO parlay card renderer here, so nothing
  // in the data file can make a recommendation appear until that work is done and reviewed.
  const PARLAY_URL = "https://github.com/juanxmarcos/Sports-Betting-/blob/main/docs/PARLAYS.md";
  const PARLAY_BLOCKERS = [
    { text: "No bookmaker-quoted parlay price. Doyen's odds feeds return single-market prices only, so it cannot verify that any bookmaker offers a given combination, or at what price." },
    { text: "No validated joint-probability estimate. Multiplying leg probabilities assumes the legs are independent and each leg is well calibrated; Doyen has no settled multi-leg record to support that." },
  ];
  function parlaysSection() {
    return `<section class="section" id="parlays"><div class="section-h"><h2>Recommended Parlays of the Day</h2><a class="link" href="#/parlays">Details →</a></div>
      <div class="card empty-cc parlay-empty" data-go="#/parlays" role="link" tabindex="0"><h3>No verified parlays today</h3>
      <p>Doyen can't yet confirm a bookmaker's combined price or a reliable joint probability, so it recommends none rather than guess.</p></div></section>`;
  }
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
        <li>Two or three legs, each already a published, active straight pick starting today. No extra or weaker legs are added to build one.</li>
        <li>Different games, no shared team or player, and different competitions. Same-game parlays are out.</li>
        <li>One bookmaker pricing every leg with fresh quotes, and that bookmaker's own price for the combination.</li>
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
      ${sec("Today's check", check)}${sec("Why none is published", why)}${sec("What a parlay would need", needs)}
      ${sec("How the numbers work", math, false)}${sec("Risk", risk)}
      <p class="note"><a href="${PARLAY_URL}" target="_blank" rel="noopener">Full parlay methodology and staged plan</a></p></div>`;
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
    return hrs > 18 ? `<div class="banner">${WARN.replace("<svg", '<svg width="16" height="16"')}<span>Data last refreshed ${esc(ago(S.data.generated))}. Prices may have moved.</span></div>` : "";
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

  function history() {
    const now = Date.now();
    const H = S.data.history.filter((p) => sportOk(p.sport, S.hsport) && (S.hrange === "all" || (now - new Date(p.published_at)) / 864e5 <= (S.hrange === "7" ? 7 : 30)));
    const settled = H.filter((p) => p.status.state === "settled");
    const W = settled.filter((p) => ["won", "half_won"].includes(p.status.result)).length;
    const L = settled.filter((p) => ["lost", "half_lost"].includes(p.status.result)).length;
    const P = settled.length - W - L;
    let h = `<h1>Pick History</h1><p class="lead">Every published pick at its original odds. Nothing is edited or removed.</p>
      ${filters(true, "hsport", "hrange", [["7", "7 days"], ["30", "30 days"], ["all", "All time"]])}
      <div class="brief"><span>Record <b>${W}–${L}${P ? "–" + P : ""}</b></span><span class="dot"></span><span><b>${H.length - settled.length}</b> awaiting result</span></div>`;
    if (!H.length) return h + `<div class="card empty-cc" style="margin-top:16px"><h3>No picks in this period</h3><p>Quiet periods are normal: Doyen only publishes when the evidence clears its bar.</p></div>`;
    const res = (p) => p.status.state === "settled" ? statusPill(p.status) : `<span class="pill">${p.status.state === "withdrawn" ? "Withdrawn" : "Pending"}</span>`;
    return h + `<div class="rows hist" style="margin-top:14px">` + H.map((p) => `<div class="row" data-go="#/pick/${esc(p.id)}" role="link" tabindex="0">
        <div class="t">${esc(fmtMon(p.published_at))}</div>
        <div class="ev"><b>${vs(p.title)}</b><span>${esc(p.selection)}</span></div>
        <div class="t r">${dec(p.odds)}</div>${res(p)}</div>`).join("") + `</div>`;
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
        <p class="small" style="margin-top:10px"><b>${esc(r.short)}</b></p><p class="note">Not a pick because: ${esc(({ "EV below threshold": "the price isn't far enough above fair value", "too few bookmakers": "fewer than 3 bookmakers price this market", "odds outside range": "the value is only at odds outside Doyen's range", "insufficient team history": "one side has too little history", "no market consensus": "there is no sharp reference price" })[c.reason] || c.reason || "below thresholds")}. ${c.n_books != null ? esc(c.n_books) + " bookmaker(s) quote this market." : ""}</p>` : `<p class="small">Odds unavailable. ${esc(r.short || "")}</p>`;
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
  const TITLES = { close: "Close to Value", upcoming: "Upcoming", history: "Pick History", watchlist: "Watchlist", ask: "Ask Doyen", pick: "Pick analysis", event: "Match", watching: "Watching", parlays: "Parlays" };
  function render() {
    if (!S.data) return;
    const parts = (location.hash.replace(/^#\/?/, "") || "").split("/");
    const r = parts[0] || "home";
    document.querySelectorAll("[data-r]").forEach((a) => a.classList.toggle("on", a.dataset.r === (r === "watching" || r === "close" || r === "parlays" ? "home" : (r === "pick" || r === "event" ? "" : r))));
    let html;
    if (r === "upcoming") html = upcoming();
    else if (r === "history") html = history();
    else if (r === "watchlist") html = watchlist();
    else if (r === "ask") html = ask(parts[1], parts[2]);
    else if (r === "watching") html = watchingAll();
    else if (r === "close") html = closeAllView();
    else if (r === "parlays") html = parlaysDetail();
    else if (r === "pick") html = pickDetail(parts[1]);
    else if (r === "event") html = eventDetail(parts[1]);
    else html = home();
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

  fetch("data/doyen.json", { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((d) => {
      S.data = d;
      d.history.forEach((p) => { p._sel = null; });
      tzSelect();
      document.getElementById("updated").textContent = "· Updated " + ago(d.generated);
      render();
    })
    .catch((e) => { $app.innerHTML = `<div class="card empty" style="margin-top:24px"><h3>Doyen couldn't load today's research</h3><p>${esc(e.message)}. Please try again in a minute.</p></div>`; });
})();
