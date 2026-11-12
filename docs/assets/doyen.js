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

  const SPORTS = [["all", "All Sports"], ["soccer", "Soccer"], ["nfl", "NFL"], ["nba", "NBA"], ["tennis", "Tennis"], ["golf", "Golf"]];
  const ICON = {
    soccer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5l3.6 2.6-1.4 4.2H9.8l-1.4-4.2z"/><path d="M12 3.5v4M15.6 10.1l4.2-1.3M14.2 14.3l2.6 3.6M9.8 14.3l-2.6 3.6M8.4 10.1L4.2 8.8"/></svg>',
    nfl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="12" rx="9" ry="5.6" transform="rotate(-35 12 12)"/><path d="M9.5 14.5l5-5M10.6 11.4l2 2M12 10l2 2M9.2 12.8l2 2"/></svg>',
    nba: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5v17M6 6c2.5 2.2 2.5 9.8 0 12M18 6c-2.5 2.2-2.5 9.8 0 12"/></svg>',
    tennis: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8.5"/><path d="M5.2 6.6c3.4 2.8 3.4 8 0 10.8M18.8 6.6c-3.4 2.8-3.4 8 0 10.8"/></svg>',
    golf: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 20V3.5l9 3.5-9 3.5"/><ellipse cx="12" cy="20" rx="7" ry="1.6"/></svg>',
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
  const isGolf = (x) => x && x.sport === "golf";
  const when = (x) => isGolf(x) ? `${fmtDate(x.start_utc)}${x.end_utc ? " – " + fmtDate(x.end_utc) : ""}` : fmtTime(x.start_utc);
  const fmtTime = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short" }).format(new Date(iso));
  const fmtClock = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), hour: "numeric", minute: "2-digit" }).format(new Date(iso));
  const fmtDay = (key) => { const [y, m, d] = key.split("-").map(Number); return new Intl.DateTimeFormat("en-US", { timeZone: "UTC", weekday: "long", month: "long", day: "numeric" }).format(new Date(Date.UTC(y, m - 1, d, 12))); };
  const fmtDate = (iso) => new Intl.DateTimeFormat("en-US", { timeZone: tz(), month: "short", day: "numeric", year: "numeric" }).format(new Date(iso));
  const ago = (iso) => { if (!iso) return "unknown"; const h = (Date.now() - new Date(iso)) / 36e5; if (h < 1) return Math.max(1, Math.round(h * 60)) + " min ago"; if (h < 48) return Math.round(h) + " h ago"; return Math.round(h / 24) + " days ago"; };
  const sportName = (k) => (SPORTS.find((s) => s[0] === k) || [k, k])[1];

  function inRange(startIso, endIso, range) {
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
  function pickMeta(p) {
    return `<div class="meta"><span class="sp">${ICON[p.sport] || ""}${esc(sportName(p.sport))}</span><span class="sep"></span><span>${esc(p.competition)}</span><span class="sep"></span><span>${esc(fmtTime(p.start_utc))}</span></div>`;
  }
  function pickCard(p) {
    const st = p.status || {};
    return `<article class="card pick" aria-label="${esc(p.selection)}">
      ${starBtn(p.event_id)}
      ${pickMeta(p)}
      <div class="event">${esc(p.title)}</div>
      <div class="sel-row"><div class="sel"><div class="mk">${esc(p.market)}</div><div class="pickname">${esc(p.selection)}</div></div>
        <div class="odds"><div class="o">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")}</div></div></div>
      <div class="stats">
        <div class="stat"><div class="k">Doyen's chance</div><div class="v">${pct(p.prob, 1)}</div></div>
        <div class="stat"><div class="k">Fair odds</div><div class="v">${dec(p.fair_odds)}</div></div>
        <div class="stat"><div class="k">Expected value</div><div class="v pos">${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}</div></div>
      </div>
      <p class="why">${esc(p.why)}</p>
      <div class="risk">${WARN}<span><b>Main risk:</b> ${esc(p.risk)}</span></div>
      <div class="foot"><span>${statusPill(st)} ${p.stale ? '<span class="pill stale">Price may be stale</span>' : ""} Odds updated ${esc(ago(p.odds_updated))}</span>
        <button class="link" data-go="#/pick/${esc(p.id)}">Full analysis →</button></div>
    </article>`;
  }
  function potdCard(p, title) {
    return `<section class="potd" aria-label="${esc(title)}"><div class="potd-in">
      <div class="crown"><span>${esc(title)}</span><i></i></div>
      ${pickMeta(p)}
      <div class="potd-grid">
        <div>
          <div class="event" style="margin-top:6px">${esc(p.title)}</div>
          <div class="sel" style="margin-top:14px"><div class="mk">${esc(p.market)}</div><div class="pickname">${esc(p.selection)}</div></div>
          <p class="why" style="margin-top:14px">${esc(p.why)}</p>
        </div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <div class="odds" style="text-align:left"><div class="faint" style="font-size:12px;letter-spacing:.1em;text-transform:uppercase">Best price</div><div class="o">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")} · odds updated ${esc(ago(p.odds_updated))}</div></div>
          <div class="stats" style="grid-template-columns:1fr 1fr">
            <div class="stat"><div class="k">Doyen's chance</div><div class="v">${pct(p.prob, 1)}</div></div>
            <div class="stat"><div class="k">Expected value</div><div class="v pos">${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}</div></div>
          </div>
          <div class="faint" style="font-size:12.5px">${esc(p.ev_plain)}</div>
        </div>
      </div>
      <div class="risk" style="margin-top:16px">${WARN}<span><b>Principal risk:</b> ${esc(p.risk)}</span></div>
      <div class="foot" style="margin-top:14px"><span>${statusPill(p.status)} ${p.stale ? '<span class="pill stale">Price may be stale</span>' : ""}</span>
        <span style="display:flex;gap:14px"><button class="link" data-go="#/ask/pick/${esc(p.id)}">Ask Doyen</button><button class="link" data-go="#/pick/${esc(p.id)}">Read the full analysis →</button></span></div>
    </div></section>`;
  }
  function watchCard(r) {
    return `<article class="card watch">
      ${starBtn(r.event_id)}
      <div class="meta"><span class="sp">${ICON[r.sport] || ""}${esc(sportName(r.sport))}</span><span class="sep"></span><span>${esc(r.competition)}</span><span class="sep"></span><span>${esc(when(r))}</span></div>
      <div class="event">${esc(r.title)}</div>
      <div><span class="pill monitor">Monitoring · not a recommendation</span></div>
      <div class="w">${esc(r.why_interesting || "On Doyen's radar.")}</div>
      <div class="wait">Waiting for: <b>${esc(r.waiting_for)}</b></div>
      <div class="foot"><span>${r.odds_updated ? "Odds updated " + esc(ago(r.odds_updated)) : "No odds yet"}</span><button class="link" data-go="#/event/${esc(r.event_id)}">Details →</button></div>
    </article>`;
  }

  // ---------- views ----------
  function home() {
    const D = S.data;
    const picks = D.picks.filter((p) => sportOk(p.sport, S.sport) && inRange(p.start_utc, null, S.range));
    let featured = null, title = "Doyen's Pick of the Day";
    if (S.sport === "all" && S.range === "today") featured = picks.find((p) => p.id === D.pick_of_the_day) || null;
    if (!featured && picks.length && picks[0].status.state === "active") { featured = picks[0]; title = S.sport === "all" ? "Doyen's Top Pick" : `Doyen's Top ${sportName(S.sport)} Pick`; }
    const rest = picks.filter((p) => !featured || p.id !== featured.id);
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const watching = D.watching.map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && inRange(r.start_utc, r.end_utc, S.range));
    const today = dkey(new Date());
    const rangeLabel = { today: "today", tomorrow: "tomorrow", week: "this week" }[S.range];
    let h = `<div class="eyebrow">${esc(fmtDay(today))}</div><h1 style="margin-top:8px">Today's Picks</h1>
      <p class="lead">${picks.length ? `${picks.length} qualifying pick${picks.length > 1 ? "s" : ""} ${rangeLabel}` : `No qualifying picks ${rangeLabel}`} · ${watching.length} match${watching.length === 1 ? "" : "es"} being watched · updated ${esc(ago(D.generated))}</p>
      ${filters()}${staleBanner()}${sportNotice(S.sport)}`;
    if (featured) h += potdCard(featured, title);
    else h += `<section class="potd"><div class="potd-in empty-potd"><div class="crown"><span>Doyen's Pick of the Day</span><i></i></div>
      <h2>No opportunity qualifies right now.</h2>
      <p style="margin-top:10px">Doyen only publishes a pick when a bookmaker's price beats a sharp market estimate by at least ${pct(D.rules.min_ev)} at odds between ${D.rules.min_odds} and ${D.rules.max_odds}, with prices from at least ${D.rules.min_bookmakers} bookmakers. Today nothing clears that bar${S.sport !== "all" ? " for " + esc(sportName(S.sport)) : ""}. No pick is better than a weak pick.</p>
      <p>The matches below are the closest Doyen is watching. They are not recommendations.</p></div></section>`;
    if (rest.length) h += `<section class="section"><div class="section-h"><h2>More picks</h2><span class="count">${rest.length}</span></div><div class="grid">${rest.map(pickCard).join("")}</div></section>`;
    h += `<section class="section"><div class="section-h"><h2>Matches Doyen Is Watching</h2><span class="count">${watching.length}</span></div>`;
    if (watching.length) h += `<div class="grid">${watching.map(watchCard).join("")}</div>`;
    else {
      const next = D.watching.map((id) => evById[id]).filter((r) => r && sportOk(r.sport, S.sport) && new Date(r.start_utc) > new Date());
      h += next.length ? `<p class="muted" style="margin:-4px 0 14px">Nothing left on the radar ${esc(rangeLabel)}. Coming up next:</p><div class="grid">${next.map(watchCard).join("")}</div>`
        : `<div class="card empty"><h3>Nothing on the radar ${esc(rangeLabel)}</h3><p>Try another date or sport, or see everything Doyen is tracking under <a href="#/upcoming">Upcoming</a>.</p></div>`;
    }
    h += `</section>`;
    return h;
  }

  function staleBanner() {
    const hrs = (Date.now() - new Date(S.data.generated)) / 36e5;
    return hrs > 18 ? `<div class="banner">${WARN.replace("<svg", '<svg width="16" height="16"')}<span>Data last refreshed ${esc(ago(S.data.generated))}. Prices may have moved since.</span></div>` : "";
  }

  function eventStatus(r) {
    if (r.has_pick) return '<span class="pill active">Pick</span>';
    if (S.data.watching.includes(r.event_id)) return '<span class="pill monitor">Watching</span>';
    if (!r.n_books) return '<span class="pill">Awaiting odds</span>';
    return '<span class="pill">Analysed</span>';
  }
  function eventRow(r) {
    const multi = r.end_utc && dkey(new Date(r.end_utc)) !== dkey(new Date(r.start_utc));
    return `<div class="row" data-go="#/event/${esc(r.event_id)}" role="link" tabindex="0">
      <div class="t">${isGolf(r) ? "All day" : esc(fmtClock(r.start_utc))}${multi ? `<small>to ${esc(fmtDate(r.end_utc))}</small>` : ""}</div>
      <div class="ev"><b>${esc(r.title)}</b><span>${ICON[r.sport] || ""}${esc(r.competition)}${r.neutral ? " · neutral venue" : ""}</span></div>
      ${eventStatus(r)}${starBtn(r.event_id)}</div>`;
  }
  function upcoming() {
    const ev = S.data.events.filter((r) => sportOk(r.sport, S.sport) && inRange(r.start_utc, r.end_utc, S.range));
    let h = `<div class="eyebrow">Schedule</div><h1 style="margin-top:8px">Upcoming</h1><p class="lead">Every event Doyen is tracking across the five sports. Tap one for the research.</p>${filters()}${sportNotice(S.sport)}`;
    if (!ev.length) return h + `<div class="card empty" style="margin-top:18px"><h3>No events in this window</h3><p>${S.sport !== "all" && !S.data.sports[S.sport].operational ? "This sport's data pipeline isn't live yet." : "Try a wider date range."}</p></div>`;
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
    const pl = settled.reduce((a, p) => a + (p.status.pnl || 0), 0);
    let h = `<div class="eyebrow">Accountability</div><h1 style="margin-top:8px">Pick History</h1><p class="lead">Every pick Doyen has published, at its original odds. Nothing is ever edited or removed.</p>
      ${filters(true, "hsport", "hrange", [["7", "7 days"], ["30", "30 days"], ["all", "All time"]])}
      <div class="record">
        <div class="stat"><div class="k">Record</div><div class="v">${W}–${L}${P ? "–" + P : ""}</div></div>
        <div class="stat"><div class="k">Paper profit</div><div class="v ${pl > 0 ? "pos" : ""}">${pl >= 0 ? "+" : ""}${pl.toFixed(2)}u</div></div>
        <div class="stat"><div class="k">Awaiting result</div><div class="v">${H.length - settled.length}</div></div>
      </div>
      <p class="note">Fixed one-unit paper stakes. A small sample says very little about skill; ask Doyen for the full statistical picture.</p>`;
    if (!H.length) return h + `<div class="card empty" style="margin-top:16px"><h3>No picks in this period</h3><p>Doyen publishes only when the evidence clears its thresholds, so quiet periods are normal.</p></div>`;
    h += `<div class="rows hist" style="margin-top:16px">` + H.map((p) => `<div class="row" data-go="#/pick/${esc(p.id)}" style="cursor:pointer">
        <div class="t">${esc(fmtDate(p.published_at))}</div>
        <div class="ev"><b>${esc(p.selection)} · ${esc(p.title)}</b><span>${ICON[p.sport] || ""}${esc(p.competition)} · ${esc(p.market)}</span></div>
        <div class="t" style="text-align:right">${dec(p.odds)}<small>${esc(p.bookmaker || "")}</small></div>
        ${statusPill(p.status.state === "settled" ? p.status : { state: "expired", label: p.status.state === "withdrawn" ? "Withdrawn · unsettled" : "Unsettled" })}</div>`).join("") + `</div>`;
    return h;
  }

  function watchlist() {
    const D = S.data;
    const evById = Object.fromEntries(D.events.map((e) => [e.event_id, e]));
    const picksByEv = {}; D.history.forEach((p) => { (picksByEv[p.event_id] = picksByEv[p.event_id] || []).push(p); });
    const ids = [...S.watch];
    let h = `<div class="eyebrow">Personal</div><h1 style="margin-top:8px">Watchlist</h1><p class="lead">Events you've starred. Saved in this browser only: it won't sync to other devices, and clearing site data removes it.</p>`;
    if (!ids.length) return h + `<div class="card empty" style="margin-top:18px"><h3>Your watchlist is empty</h3><p>Tap the ☆ on any pick or event to follow it here.</p></div>`;
    h += `<div class="rows" style="margin-top:18px">` + ids.map((id) => {
      const r = evById[id], pk = (picksByEv[id] || [])[0];
      if (!r && !pk) return `<div class="row"><div class="t">—</div><div class="ev"><b>Event no longer listed</b><span>It has finished or dropped out of the data window.</span></div><span></span>${starBtn(id)}</div>`;
      const title = r ? r.title : pk.title, start = r ? r.start_utc : pk.start_utc;
      const status = pk ? statusPill(pk.status) : (r && D.watching.includes(id) ? '<span class="pill monitor">Watching</span>' : '<span class="pill">No pick yet</span>');
      const odds = pk ? `${pk.selection} @ ${dec(pk.odds)}` : (r && r.closest ? `Best: ${r.closest.selection_text} @ ${dec(r.closest.odds)}` : "No odds yet");
      const upd = pk ? (pk.status.note || "Published " + ago(pk.published_at)) : (r && r.odds_updated ? "Odds updated " + ago(r.odds_updated) : "");
      return `<div class="row" data-go="${pk ? "#/pick/" + esc(pk.id) : "#/event/" + esc(id)}">
        <div class="t">${esc(fmtClock(start))}<small>${esc(fmtDate(start))}</small></div>
        <div class="ev"><b>${esc(title)}</b><span>${esc(odds)} · ${esc(upd)}</span></div>${status}${starBtn(id)}</div>`;
    }).join("") + `</div>`;
    return h;
  }

  function cmpBars(mv, bv) {
    const keys = Object.keys(mv || {});
    if (!keys.length) return "";
    return keys.map((k) => `<div class="cmp"><span class="muted">${esc(k)}</span><div><div class="bar" title="Doyen model"><i style="width:${(mv[k] * 100).toFixed(1)}%"></i></div>${bv && bv[k] != null ? `<div class="bar" style="margin-top:4px;opacity:.55" title="Bookmakers (no-vig)"><i style="width:${(bv[k] * 100).toFixed(1)}%;background:var(--info)"></i></div>` : ""}</div><span>${pct(mv[k])}${bv && bv[k] != null ? `<br><span class="faint">${pct(bv[k])}</span>` : ""}</span></div>`).join("") +
      (bv && Object.keys(bv).length ? `<p class="note">Gold: Doyen's model. Blue: bookmakers' consensus with their margin removed.</p>` : "");
  }
  function formBlock(form) {
    if (!form) return "";
    return Object.entries(form).map(([t, f]) => `<div class="stat"><div class="k">${esc(t)}</div><div class="v">${esc(f.last || "—")}</div><div class="faint" style="font-size:12px">${f.gf}–${f.ga} goals${f.xg_for_avg != null ? ` · xG ${f.xg_for_avg}/${f.xg_against_avg}` : ""}</div></div>`).join("");
  }

  function pickDetail(id) {
    const p = S.data.history.find((x) => x.id === id);
    if (!p) return `<div class="sheet"><button class="back" data-go="#/">← Back</button><div class="card empty"><h3>Pick not found</h3></div></div>`;
    const d = p.detail || {};
    const prices = d.prices || {};
    const rows = Object.entries(prices).map(([bk, q]) => [bk, q && q[p._sel]]).filter((x) => x[1]);
    let h = `<div class="sheet"><button class="back" data-go="#/">← Back</button>
      ${pickMeta(p)}<h1 style="margin-top:8px">${esc(p.title)}</h1>
      <div class="sel-row" style="margin-top:14px"><div class="sel"><div class="mk">${esc(p.market)}</div><div class="pickname" style="font-size:22px">${esc(p.selection)}</div></div>
      <div class="odds"><div class="o" style="font-size:40px">${dec(p.odds)}</div><div class="bk">${esc(p.bookmaker || "")}</div></div></div>
      <div style="margin-top:10px">${statusPill(p.status)} ${p.status.note ? `<span class="faint" style="font-size:13px">${esc(p.status.note)}</span>` : ""}</div>
      <div class="kv" style="margin-top:16px">
        <div class="stat"><div class="k">Doyen's chance</div><div class="v">${pct(p.prob, 1)}</div></div>
        <div class="stat"><div class="k">Fair odds</div><div class="v">${dec(p.fair_odds)}</div></div>
        <div class="stat"><div class="k">Expected value</div><div class="v pos">${p.ev >= 0 ? "+" : ""}${pct(p.ev, 1)}</div></div>
        <div class="stat"><div class="k">Model's own view</div><div class="v">${pct(p.model_prob, 1)}</div></div>
      </div>
      <p class="note">${esc(p.ev_plain)}</p>
      <div class="card block"><h3>Why Doyen likes it</h3><p class="why">${esc(p.why)}</p></div>
      <div class="card block"><h3>What could make it wrong</h3><div class="risk">${WARN}<span><b>Main risk:</b> ${esc(p.risk)}</span></div>
        ${(p.risks || []).length ? `<ul style="margin:10px 0 0 18px;padding:0;color:var(--muted);font-size:14px">${p.risks.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>`;
    if (Object.keys(prices).length) {
      const sels = new Set(); Object.values(prices).forEach((q) => Object.keys(q || {}).forEach((s) => sels.add(s)));
      h += `<div class="card block"><h3>Prices across bookmakers</h3><p class="note" style="margin-top:0">Consensus reference: ${esc(d.consensus_source || "—")} · ${esc(d.n_bookmakers || "—")} bookmakers · odds updated ${esc(ago(p.odds_updated))}</p>
        <div class="prices">${Object.entries(prices).map(([bk, q]) => `<div class="${bk === p.bookmaker ? "best" : ""}"><span>${esc(bk)}</span><span>${Object.entries(q || {}).map(([s, v]) => `${esc(s)} ${dec(v)}`).join(" · ")}</span></div>`).join("")}</div></div>`;
    }
    if (d.model_markets || d.form) {
      const mm = d.model_markets || {};
      const mv = mm["1X2:H"] != null ? { Home: mm["1X2:H"], Draw: mm["1X2:D"], Away: mm["1X2:A"], "Over 2.5": mm["OU:over:2.5"], "Both score": mm["BTTS:yes"] } : null;
      h += `<div class="card block"><h3>Model context</h3>${d.expected_goals ? `<p class="muted" style="margin:0 0 8px">Expected goals ${esc(d.expected_goals.home)}–${esc(d.expected_goals.away)}</p>` : ""}${mv ? cmpBars(mv, null) : ""}
        ${d.form ? `<div class="kv" style="margin-top:10px">${formBlock(d.form)}</div>` : ""}</div>`;
    }
    h += `<div class="card block"><h3>Research notes</h3>${(p.notes || []).length ? `<ul class="timeline">${p.notes.map((n) => `<li><span class="pill">${esc(n.evidence_type.replace("_", " "))}</span><span>${esc(n.claim)} ${n.source_url ? `<a href="${esc(n.source_url)}" target="_blank" rel="noopener">source</a>` : ""}</span></li>`).join("")}</ul>` : `<p class="muted" style="margin:0">No contextual research recorded yet. Team news isn't modelled, so check it before acting.</p>`}</div>
      <div class="card block"><h3>Record</h3><ul class="timeline">
        <li><span class="pill">Published</span><span>${esc(fmtTime(p.published_at))} at ${dec(p.odds)} (${esc(p.bookmaker)}). This entry is permanent.</span></li>
        ${p.status.checked_at ? `<li><span class="pill ${esc(p.status.state)}">${esc(p.status.label)}</span><span>${esc(fmtTime(p.status.checked_at))}: ${esc(p.status.note || "")}</span></li>` : ""}
        ${p.status.state === "settled" ? `<li><span class="pill ${esc(p.status.result.replace("half_", ""))}">${esc(p.status.label)}</span><span>Paper result ${p.status.pnl >= 0 ? "+" : ""}${Number(p.status.pnl).toFixed(2)} units.</span></li>` : ""}
      </ul><p class="note">Sources: ${(d.sources || []).map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//, "").split("/")[0])}</a>`).join(" · ") || "—"} · model ${esc(p.model_version)}</p></div>
      <div style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">${starBtn(p.event_id).replace('class="star', 'class="ibtn').replace("star on", "ibtn on")}<a class="btn ghost" href="#/ask/pick/${esc(p.id)}">Ask Doyen about this pick</a></div></div>`;
    return h;
  }

  function eventDetail(id) {
    const r = S.data.events.find((x) => x.event_id === id);
    if (!r) return `<div class="sheet"><button class="back" data-go="#/upcoming">← Back</button><div class="card empty"><h3>Event not found</h3><p>It may have finished or dropped out of the data window.</p></div></div>`;
    const pk = S.data.picks.find((p) => p.event_id === id);
    const c = r.closest;
    let h = `<div class="sheet"><button class="back" data-go="#/upcoming">← Back</button>
      <div class="meta"><span class="sp">${ICON[r.sport] || ""}${esc(sportName(r.sport))}</span><span class="sep"></span><span>${esc(r.competition)}</span><span class="sep"></span><span>${esc(when(r))}</span></div>
      <h1 style="margin-top:8px">${esc(r.title)}</h1>
      <div style="margin-top:10px">${pk ? `<a class="btn" href="#/pick/${esc(pk.id)}">View Doyen's pick →</a>` : `<span class="pill monitor">${S.data.watching.includes(id) ? "Watching · not a recommendation" : "No pick · analysed"}</span>`}</div>
      <div class="card block"><h3>Why it's interesting</h3><p class="why">${esc(r.why_interesting || "Routine analysis.")}</p><p class="muted" style="margin:8px 0 0">Waiting for: <b style="color:var(--info)">${esc(r.waiting_for)}</b></p></div>`;
    if (c) h += `<div class="card block"><h3>Closest to value</h3><p class="why">${esc(c.market_label)} — <b>${esc(c.selection_text)}</b> at ${dec(c.odds)} (${esc(c.bookmaker || "")}). ${c.market_prob != null ? `Sharp market consensus (margin removed): ${pct(c.market_prob, 1)}` : `Doyen's estimate: ${pct(c.prob, 1)}`}${c.model_prob != null && c.market_prob != null ? `; Doyen's model: ${pct(c.model_prob, 1)}` : ""}. Value of this price against fair: ${c.ev >= 0 ? "+" : ""}${pct(c.ev, 1)}.</p><p class="note">Why it isn't a pick: ${esc(c.reason || "below thresholds")}.</p></div>`;
    if (Object.keys(r.model_view || {}).length) h += `<div class="card block"><h3>${r.sport === "golf" ? "Win probability: top of the field" : "Model vs bookmakers"}</h3>${r.expected_goals ? `<p class="muted" style="margin:0 0 8px">Expected goals ${esc(r.expected_goals.home)}–${esc(r.expected_goals.away)}</p>` : ""}${cmpBars(r.model_view, r.book_view)}${r.model_weight === 0 ? '<p class="note">This competition\'s model has not yet earned weight against the market, so its view is context only.</p>' : ""}</div>`;
    if (r.form) h += `<div class="card block"><h3>Recent form</h3><div class="kv">${formBlock(r.form)}</div></div>`;
    if (r.extra_text && r.extra_text !== r.why_interesting && !(r.why_interesting || "").includes(r.extra_text.split(". ")[0])) h += `<div class="card block"><h3>Notes</h3><p class="why">${esc(r.extra_text)}</p></div>`;
    if (r.golf_table) h += `<div class="card block"><h3>Simulated finishing chances</h3><div class="rows">${r.golf_table.slice(0, 15).map((g) => `<div class="golfrow"><b>${esc(g.player)}</b><div class="gnums"><span>${pct(g.win, 1)}<small>win</small></span><span>${pct(g.top5)}<small>top 5</small></span><span>${pct(g.top10)}<small>top 10</small></span><span>${pct(g.top20)}<small>top 20</small></span><span>${pct(g.cut)}<small>cut</small></span></div></div>`).join("")}</div><p class="note">10,000 simulations from strokes-versus-field ratings. Probabilities, not predictions. Doyen has no free golf odds to compare against outside the majors, so these are not picks.</p></div>`;
    h += `<p class="note">${r.odds_updated ? "Odds updated " + esc(ago(r.odds_updated)) + " · " : ""}${r.n_books || 0} bookmaker${r.n_books === 1 ? "" : "s"} quoting.</p>
      <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap">${starBtn(id).replace('class="star', 'class="ibtn')}<a class="btn ghost" href="#/ask/event/${esc(id)}">Ask Doyen about this event</a></div></div>`;
    return h;
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
      "What does your tennis model think about this matchup?", "Which golf markets look interesting this week?"];
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
  function render() {
    if (!S.data) return;
    const parts = (location.hash.replace(/^#\/?/, "") || "").split("/");
    const r = parts[0] || "home";
    document.querySelectorAll("[data-r]").forEach((a) => a.classList.toggle("on", a.dataset.r === (r === "pick" || r === "event" ? "" : r)));
    let html;
    if (r === "upcoming") html = upcoming();
    else if (r === "history") html = history();
    else if (r === "watchlist") html = watchlist();
    else if (r === "ask") html = ask(parts[1], parts[2]);
    else if (r === "pick") html = pickDetail(parts[1]);
    else if (r === "event") html = eventDetail(parts[1]);
    else html = home();
    $app.innerHTML = html;
    document.title = ({ upcoming: "Upcoming", history: "Pick History", watchlist: "Watchlist", ask: "Ask Doyen", pick: "Pick analysis", event: "Event" }[r] ? ({ upcoming: "Upcoming", history: "Pick History", watchlist: "Watchlist", ask: "Ask Doyen", pick: "Pick analysis", event: "Event" }[r] + " · ") : "") + "Sports Betting Doyen";
  }
  window.addEventListener("hashchange", () => { render(); window.scrollTo(0, 0); });
  $app.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-go]")) location.hash = e.target.dataset.go; });

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
