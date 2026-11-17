"""Quote-source audit (issue #24): where could more independent price quotes come from at zero
recurring cost, and what does the existing The Odds API quota actually buy?

`python -m sbi quote-sources` reads the database READ-ONLY, makes no network call and writes
  reports/quote_sources.md and data/coverage/quote_sources_latest.json
(developer reports; nothing here is shown on the public site, and no pick rule reads them).

Three parts:
  1. CANDIDATES: the budget and licensing matrix. Every row was checked against the provider's own
     pages on the date given, carries the links, and has one of five statuses. A source may only get
     a connector when its status is "verified"; tests enforce the invariants.
  2. Measured economics of the existing The Odds API subscription, from the job log: credits spent,
     what each credit bought, and credits that bought nothing (no returned event could be matched).
  3. Operator yield of the stored quotes: bookmaker NAMES versus known OPERATORS per event, and the
     smallest set of stored bookmakers that keeps today's known-operator coverage. That number says
     how many of the ten slots of a one-region `bookmakers=` request would be free for operators
     the `eu` region does not carry. What those other bookmakers would actually return is NOT
     measured here: it needs the owner's key (see `probe`, one credit, stores nothing).

Prediction-market prices (Polymarket, Kalshi) are not bookmaker odds. This module never treats them
as such; they appear only as matrix rows.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from . import config, coverage
from .sources import odds_api
from .sources.books import GROUPS, normalize_book

CHECKED = "2026-11-16"
SOURCE = odds_api.SOURCE
STATUSES = {
    "verified": "free, permitted and working; may have a connector",
    "owner_opt_in": "free, but needs an owner action (account, key or setting) before any use",
    "blocked": "reachable, but the right to store or publish the data is not confirmed",
    "unavailable": "could not be verified, or does not offer what is needed",
    "paid": "needs a paid plan, a commercial licence or a funded account",
}


@dataclass(frozen=True)
class Candidate:
    key: str
    name: str
    kind: str                 # bookmaker aggregator | betting exchange | prediction market | bookmaker
    status: str               # one of STATUSES
    recurring_cost: str
    credential: str
    sports: str               # of Soccer / NFL / NBA / Tennis
    store: str                # may we keep the data?
    publish: str              # may raw quotes sit in a public file or page?
    independence: str         # what it adds beyond the operators already stored
    finding: str
    links: tuple[str, ...]
    checked: str = CHECKED


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        key="the-odds-api", name="The Odds API (the-odds-api.com), in use", kind="bookmaker aggregator",
        status="verified", recurring_cost="$0 (Starter, 500 credits/month)", credential="ODDS_API_KEY (already set by the owner)",
        sports="Soccer, NFL, NBA, Tennis",
        store="Yes: \"Storing our data and retaining it indefinitely\" is permitted",
        publish="Display in a site or app: yes. Offering the data as \"downloadable files\" or a feed: no. "
                "The raw quotes in the public data/sbi.sqlite are therefore still an open owner decision",
        independence="The only source of 3+ operators and of a sharp reference today",
        finding="Terms last updated 31 August 2026. Cost is markets x regions; /sports and /events are free.",
        links=("https://the-odds-api.com/liveapi/guides/v4/", "https://the-odds-api.com/terms-and-conditions.html")),
    Candidate(
        key="the-odds-api-bookmakers", name="The Odds API: `bookmakers` parameter (same key, same quota)",
        kind="bookmaker aggregator", status="owner_opt_in", recurring_cost="$0 (up to 10 named bookmakers are billed as one region)",
        credential="none new; owner sets SBI_ODDS_API_BOOKMAKERS",
        sports="Soccer, NFL, NBA, Tennis", store="As above", publish="As above",
        independence="Could swap repeated brands of one operator for operators the eu region lacks (for example "
                     "DraftKings, FanDuel, BetMGM, Smarkets). Not measured: needs one call with the owner's key",
        finding="Guide: \"Every group of 10 bookmakers is the equivalent of 1 region\"; `bookmakers` takes priority over "
                "`regions`. The bookmaker list marks some keys \"paid subscriptions only\" (for example Caesars, Fanatics). "
                "Whether the free plan returns every other key is unconfirmed until probed.",
        links=("https://the-odds-api.com/liveapi/guides/v4/", "https://the-odds-api.com/sports-odds-data/bookmaker-apis.html")),
    Candidate(
        key="the-odds-api-us-ex", name="The Odds API: `us_ex` keys (Polymarket, Kalshi, Novig, ProphetX)",
        kind="prediction market", status="blocked", recurring_cost="$0 if named in a bookmaker list",
        credential="none new", sports="As offered by each exchange; not verified",
        store="As for The Odds API", publish="As for The Odds API",
        independence="A separate reference signal at most; not bookmaker odds",
        finding="These are contract prices, not sportsbook odds: settlement rules, fees, currency and access differ. "
                "The connector refuses these keys and drops them if returned. Using them needs its own design "
                "(separate table, market-definition checks) and its own PR.",
        links=("https://the-odds-api.com/sports-odds-data/bookmaker-apis.html",)),
    Candidate(
        key="betting-data-api", name="Betting Data API (theoddsapi.com, now redirects to bettingdataapi.com)",
        kind="bookmaker aggregator", status="owner_opt_in", recurring_cost="$0 tier: 25 requests/day; paid from $29/month",
        credential="new account and API key (owner only; not created)",
        sports="NBA and NFL moneylines from US books (free tier also lists MLB, not a supported sport). No Soccer, no Tennis",
        store="Not addressed in the terms", publish="Not addressed; reselling or redistributing bulk odds as a feed is prohibited",
        independence="US books only, which The Odds API also lists. Likely the same operators as the `bookmakers` option above",
        finding="A different company from The Odds API: \"operated by TheOddsAPI LLC, a Wyoming limited liability company\". "
                "The free tier is described as \"Evaluate with production data\", moneyline only, no card. "
                "Not proven permanently free or cleared for storage, so no adapter is built.",
        links=("https://bettingdataapi.com/pricing", "https://bettingdataapi.com/terms")),
    Candidate(
        key="polymarket-gamma", name="Polymarket Gamma API (public, keyless)", kind="prediction market",
        status="blocked", recurring_cost="$0", credential="none",
        sports="NBA, NFL, Tennis and club Soccer game markets seen on 2026-11-16",
        store="Unclear: terms section 4.2 prohibits \"data mining tools, robots, crawlers\" on site data and "
              "redistributing or commercially exploiting the data, with exceptions the company may grant",
        publish="Not confirmed",
        independence="Independent of every bookmaker, but it is an exchange contract price, not bookmaker odds",
        finding="Documented public API; limit 500 requests per 10 s on /events. Terms effective 11 August 2026 also bar "
                "trading from restricted jurisdictions. Prices are 0 to 1 per share in USDC with a bid/ask spread and "
                "per-market fees (`feesEnabled`); soccer is three separate Yes/No contracts. No adapter and nothing stored "
                "until the owner confirms the data rights.",
        links=("https://docs.polymarket.com/quickstart/introduction/rate-limits", "https://polymarket.com/tos",
               "https://github.com/Polymarket/agent-skills/blob/main/market-data.md")),
    Candidate(
        key="kalshi", name="Kalshi public market-data endpoints", kind="prediction market", status="blocked",
        recurring_cost="$0", credential="none for public endpoints",
        sports="Not verified", store="Terms not reviewed", publish="Terms not reviewed",
        independence="As for Polymarket: a separate signal, not bookmaker odds",
        finding="Docs: \"several public endpoints that don't require API keys\"; data \"can lag the exchange by several "
                "seconds\". Data terms were not found on the docs page, so nothing is used.",
        links=("https://docs.kalshi.com/getting_started/quick_start_market_data",)),
    Candidate(
        key="betfair-exchange-api", name="Betfair Exchange API (own key)", kind="betting exchange", status="paid",
        recurring_cost="Account required; licence terms apply", credential="KYC-verified Betfair account and app key (not created)",
        sports="Soccer, NFL, NBA, Tennis", store="Not stated for a personal key; the page lists it for personal betting use",
        publish="No: publishing odds needs an Odds Publisher licence, offered to existing affiliates",
        independence="None new: Betfair Exchange prices already arrive through The Odds API",
        finding="\"In all cases, a personal or corporate KYC-verified Betfair account is required\". Operators and companies "
                "wanting Exchange data are sent to data sales. The page does not mention the Delayed App Key. "
                "No account is opened.",
        links=("https://support.developer.betfair.com/hc/en-us/articles/360002464152-Which-API-Licence-Do-I-Require",)),
    Candidate(
        key="pinnacle-api", name="Pinnacle API (direct)", kind="bookmaker", status="paid",
        recurring_cost="\"a variable cost associated with the speed and breadth of access\"", credential="application form",
        sports="Soccer, NFL, NBA, Tennis", store="Case by case", publish="Case by case",
        independence="None new: Pinnacle prices already arrive through The Odds API",
        finding="Access is by application, decided per use case. Not applied for.",
        links=("https://www.pinnacle.com/en/api/",)),
    Candidate(
        key="smarkets-api", name="Smarkets API (direct)", kind="betting exchange", status="unavailable",
        recurring_cost="Not verifiable", credential="Not verifiable", sports="Not verifiable",
        store="Not verifiable", publish="Not verifiable",
        independence="Smarkets is listed in The Odds API `uk` region, so the `bookmakers` option may cover it",
        finding="docs.smarkets.com returned only a page title to an automated read; access rules and data terms could not be read.",
        links=("https://docs.smarkets.com/",)),
)

# One dated observation of what Polymarket listed, taken with the documented public API on
# 2026-11-16 15:00 UTC (18 requests in total, project User-Agent). Counts only: no price was stored.
# It is context for the owner's decision, not a coverage gain.
POLYMARKET_OBSERVATION = {
    "as_of": "2026-11-16T15:00:00+00:00", "window": "games starting in the next 7 days", "requests": 18,
    "rows": [  # competition, games listed, games with a two-sided match-winner market, median resting liquidity (USD), median bid/ask spread
        ("NBA", 51, 51, 23109, 0.03), ("NFL", 14, 13, 33446, 0.01), ("Tennis ATP", 88, 88, 5671, 0.02),
        ("Tennis WTA", 14, 14, 6160, 0.02), ("Soccer: Premier League", 9, 9, 67345, 0.01),
        ("Soccer: La Liga", 9, 9, 54735, 0.01)],
    "caveats": ["Tennis includes lower-tier events and round-robin pairings that may not be played.",
                "Soccer match result is three separate Yes/No contracts per match, not one 1X2 market; "
                "soccer liquidity is the sum over the three contracts.",
                "Only two soccer leagues were examined.",
                "Liquidity is resting order size, not a stake limit at the quoted price.",
                "Every market seen had fees enabled."],
}


def _runs(con):
    if not coverage._has(con, "job_runs"):
        return
    for r in con.execute("SELECT started_at, details FROM job_runs WHERE job='ingest-odds-api' ORDER BY id"):
        try:
            d = json.loads(r["details"] or "{}")
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("fetched"):
            yield r["started_at"], d


def credit_economics(con) -> dict:
    """What the credits bought, from the job log. A fetch 'bought nothing' when none of the events
    it returned for the 7-day window could be matched to a stored event, so no quote was kept."""
    per_fetch = {}
    if coverage._has(con, "odds_api_fetches"):
        for r in con.execute("SELECT sport_key, MAX(credits) c FROM odds_api_fetches GROUP BY 1"):
            per_fetch[r["sport_key"]] = r["c"]
    by_key: dict = defaultdict(lambda: {"fetches": 0, "credits": 0, "events_matched": 0, "fetches_matching_nothing": 0,
                                        "credits_matching_nothing": 0})
    runs = unknown = rows = 0
    first = last = None
    for started, d in _runs(con):
        runs += 1
        first, last = first or started, started
        rows += int(d.get("odds_rows") or 0)
        for sk in d["fetched"]:
            cov = (d.get("coverage") or {}).get(sk)
            cost = per_fetch.get(sk)
            if cov is None or cost is None:
                unknown += 1            # older log format: counted, not guessed
                continue
            k = by_key[sk]
            k["fetches"] += 1
            k["credits"] += cost
            k["events_matched"] += int(cov.get("matched") or 0)
            if not cov.get("matched"):
                k["fetches_matching_nothing"] += 1
                k["credits_matching_nothing"] += cost
    tot = {f: sum(k[f] for k in by_key.values()) for f in ("fetches", "credits", "events_matched",
                                                           "fetches_matching_nothing", "credits_matching_nothing")}
    tot["share_matching_nothing"] = round(tot["credits_matching_nothing"] / tot["credits"], 3) if tot["credits"] else None
    return {"runs_that_fetched": runs, "first_run": first, "last_run": last, "new_quote_rows_stored": rows,
            "fetches_without_detail": unknown, "by_sport_key": dict(sorted(by_key.items())), "total": tot}


def _fresh_books(con, now: datetime, horizon_h: float, fresh_h: float) -> dict:
    """(event, market) -> normalised bookmakers with a fresh The Odds API quote, upcoming events only."""
    end = (now + timedelta(hours=horizon_h)).isoformat()
    out: dict = defaultdict(set)
    for r in con.execute("""SELECT o.event_id, o.market, o.bookmaker, MAX(o.retrieved_at) m
                            FROM odds o JOIN events e ON e.event_id = o.event_id
                            WHERE o.kind='pre' AND o.source=? AND e.status='scheduled' AND e.kickoff_utc > ? AND e.kickoff_utc <= ?
                            GROUP BY 1,2,3""", (SOURCE, now.isoformat(), end)):
        book = normalize_book(r["bookmaker"])
        if book and coverage._age_h(now, r["m"]) <= fresh_h:
            out[(r["event_id"], r["market"])].add(book)
    return out


def _known(books) -> set:
    return {GROUPS[b] for b in books if b in GROUPS}


def _events_3plus(markets: dict, keep: set | None = None) -> set:
    return {e for (e, _), books in markets.items()
            if len(_known(books if keep is None else books & keep)) >= 3}


def _events_sharp(markets: dict, keep: set | None = None) -> set:
    return {e for (e, _), books in markets.items()
            if any(b in coverage.SHARP for b in (books if keep is None else books & keep))}


def minimal_books(markets: dict) -> list[str]:
    """Greedy smallest set of stored bookmakers that keeps, for every event-market, every known
    operator and every sharp reference it has today. Unknown-ownership bookmakers are never
    needed for that, because they do not count toward the lower bound."""
    need = set()                      # (event-market, operator) pairs to keep covered
    for k, books in markets.items():
        need |= {(k, GROUPS[b]) for b in books if b in GROUPS}
    chosen: list[str] = [b for b in coverage.SHARP if any(b in books for books in markets.values())]
    covered = {(k, GROUPS[b]) for k, books in markets.items() for b in books if b in chosen and b in GROUPS}
    candidates = sorted({b for books in markets.values() for b in books if b in GROUPS} - set(chosen))
    while need - covered:
        gain = {b: len({(k, GROUPS[b]) for k, books in markets.items() if b in books} - covered) for b in candidates}
        best = max(candidates, key=lambda b: (gain[b], b))
        if not gain[best]:
            break
        chosen.append(best)
        candidates.remove(best)
        covered |= {(k, GROUPS[best]) for k, books in markets.items() if best in books}
    return chosen


def operator_yield(con, now: datetime, horizon_h: float = 168, fresh_h: float | None = None) -> dict:
    """Names versus known operators in the stored The Odds API quotes, and what a one-region
    bookmaker list would need to keep. Measured from stored quotes only."""
    fresh_h = config.RULES.max_odds_age_hours if fresh_h is None else fresh_h
    markets = _fresh_books(con, now, horizon_h, fresh_h)
    books_all = set().union(*markets.values()) if markets else set()
    per_book = []
    for b in sorted(books_all):
        ev = {e for (e, _), books in markets.items() if b in books}
        per_book.append({"bookmaker": b, "operator": GROUPS.get(b), "events": len(ev)})
    by_operator: dict = defaultdict(list)
    for b in books_all:
        if b in GROUPS:
            by_operator[GROUPS[b]].append(b)
    keep = minimal_books(markets)
    full3, full_sharp = _events_3plus(markets), _events_sharp(markets)
    kept = set(keep)
    names = [len(v) for v in markets.values()]
    known = [len(_known(v)) for v in markets.values()]
    return {
        "event_markets_priced": len(markets), "events_priced": len({e for e, _ in markets}),
        "bookmakers": len(books_all), "known_operators": len(by_operator),
        "unknown_ownership": sorted(b for b in books_all if b not in GROUPS),
        "operators_with_several_brands": {g: sorted(v) for g, v in sorted(by_operator.items()) if len(v) > 1},
        "median_bookmakers_per_event_market": median(names) if names else None,
        "median_known_operators_per_event_market": median(known) if known else None,
        "events_with_3plus_known_operators": len(full3), "events_with_sharp_reference": len(full_sharp),
        "minimal_bookmakers_keeping_known_coverage": keep,
        "check_events_with_3plus_known_operators_after": len(_events_3plus(markets, kept)),
        "check_events_with_sharp_reference_after": len(_events_sharp(markets, kept)),
        "slots_per_region": odds_api.BOOKMAKERS_PER_REGION,
        "slots_left_for_other_operators": max(0, odds_api.BOOKMAKERS_PER_REGION - len(keep)),
        "per_bookmaker": per_book,
    }


def probe(bookmakers: str, sport_key: str = "basketball_nba") -> dict:
    """Owner-run entitlement check: ONE /odds call (h2h only) for a bookmaker list, with the owner's
    key. It stores nothing. It reports which requested bookmakers the plan actually returned and what
    the provider says the call cost. Refused when the list is invalid, when no key is set, or when
    the remaining credits are unknown or at the reserve."""
    keys, problem = odds_api.bookmaker_selection(bookmakers)
    if problem or not keys:
        return {"refused": problem or "no bookmakers given"}
    api_key = odds_api.key()
    if not api_key:
        return {"refused": "ODDS_API_KEY not set"}
    _, usage = odds_api._get("/sports", {}, api_key)                      # free; tells us what is left
    remaining = odds_api._int(usage.get("remaining"))
    expected = odds_api.request_cost("h2h", bookmakers=keys)
    if remaining is None or remaining - expected < odds_api.RESERVE:
        return {"refused": f"remaining credits {remaining}; the {odds_api.RESERVE}-credit reserve is kept"}
    data, usage = odds_api._get(f"/sports/{sport_key}/odds", {"bookmakers": ",".join(keys), "markets": "h2h",
                                                              "oddsFormat": "decimal", "dateFormat": "iso"}, api_key)
    seen: dict = defaultdict(int)
    for e in data:
        for bk in e.get("bookmakers", []):
            seen[bk["key"]] += 1
    return {"sport_key": sport_key, "requested": list(keys), "events_returned": len(data),
            "events_per_bookmaker_returned": dict(sorted(seen.items())),
            "requested_but_not_returned": sorted(set(keys) - set(seen)),
            "returned_but_not_requested": sorted(set(seen) - set(keys)),
            "credits_expected": expected, "credits_charged": odds_api._int(usage.get("last")),
            "credits_remaining": odds_api._int(usage.get("remaining")), "stored": "nothing"}


def build(con, now: datetime, horizon_h: float = 168) -> dict:
    base_p = coverage.latest_baseline()
    base = json.loads(base_p.read_text()) if base_p else None
    return {"as_of": now.isoformat(), "horizon_hours": horizon_h, "checked": CHECKED,
            "baseline": None if not base else {"file": base_p.name, "as_of": base.get("as_of"), "summary": base.get("summary"),
                                                "bookmakers": {k: base["bookmakers"][k] for k in (
                                                    "bookmakers", "known_operators", "operators_lower", "operators_upper")}},
            "now": {"summary": coverage.summary(con, now, horizon_h),
                    "bookmakers": {k: v for k, v in coverage.book_audit(con).items() if k in (
                        "bookmakers", "known_operators", "operators_lower", "operators_upper")}},
            "credit_economics": credit_economics(con), "operator_yield": operator_yield(con, now, horizon_h),
            "candidates": [asdict(c) for c in CANDIDATES], "polymarket_observation": POLYMARKET_OBSERVATION}


def to_markdown(rep: dict) -> str:
    L = [f"# Quote-source audit ({rep['as_of'][:16].replace('T', ' ')} UTC)", "",
         "Generated by `python -m sbi quote-sources` from the stored database (read-only, no network call). "
         f"Provider pages were read on {rep['checked']}; see docs/DATA_SOURCES.md.", "",
         "**How to read this.** Everything here is about stored, delayed quotes used for research. Nothing is a live or "
         "executable price, and no pick rule reads this report. Prediction-market prices are not bookmaker odds.", "",
         "Provider pages were read with an automated fetch tool, so quoted terms are short fragments. Read the linked "
         "page before relying on any of them.", ""]
    L += ["## Operators: baseline and now", ""]
    b, n = rep["baseline"], rep["now"]
    if b:
        L += [f"Baseline: `{b['file']}` ({b['as_of'][:16].replace('T', ' ')} UTC, from PR #16). "
              "Operator counts are a lower bound: only bookmakers with a recorded owner or pricing platform count.", "",
              "| Measure | Baseline | Now | Change |", "|---|---|---|---|"]
        for k, label in (("bookmakers", "Bookmakers stored (after merging name variants)"),
                         ("known_operators", "Known operators"), ("operators_upper", "Upper bound (every unknown counted separately, provisional)")):
            L.append(f"| {label} | {b['bookmakers'][k]} | {n['bookmakers'][k]} | {n['bookmakers'][k] - b['bookmakers'][k]:+d} |")
        L += ["", "| Sport | Measure | Baseline | Now | Change |", "|---|---|---|---|---|"]
        for sport in sorted(set(b["summary"]) | set(n["summary"])):
            for k in ("scheduled_events", "with_fresh_quote_bookmaker_timed", "with_3plus_operators_lower", "with_sharp_reference"):
                x, y = b["summary"].get(sport, {}).get(k, 0), n["summary"].get(sport, {}).get(k, 0)
                L.append(f"| {sport} | {k.replace('_', ' ')} | {x} | {y} | {y - x:+d} |")
        L += ["", "The two dates fall in different fixture weeks, so the per-sport changes mostly reflect the calendar, "
              "not a source change. No new source is connected in this audit.", ""]
    ce = rep["credit_economics"]
    t = ce["total"]
    L += ["## The Odds API: what the credits bought", "",
          f"From the job log, {ce['runs_that_fetched']} runs that fetched odds "
          f"({(ce['first_run'] or '')[:10]} to {(ce['last_run'] or '')[:10]}).", "",
          f"- Credits spent on fetches with a recorded outcome: **{t['credits']}** in {t['fetches']} fetches.",
          f"- Credits spent on fetches where **no returned event matched a stored event** (nothing kept): "
          f"**{t['credits_matching_nothing']}** in {t['fetches_matching_nothing']} fetches"
          + (f" ({t['share_matching_nothing']:.1%} of the credits)." if t["share_matching_nothing"] is not None else "."),
          f"- New quote rows stored by these runs: {ce['new_quote_rows_stored']}.",
          f"- Fetches logged without a per-competition outcome (older log format, not counted above): {ce['fetches_without_detail']}.",
          "", "| Competition key | Fetches | Credits | Events matched | Fetches matching nothing | Credits matching nothing |",
          "|---|---|---|---|---|---|"]
    for sk, k in ce["by_sport_key"].items():
        L.append(f"| {sk} | {k['fetches']} | {k['credits']} | {k['events_matched']} | {k['fetches_matching_nothing']} | "
                 f"{k['credits_matching_nothing']} |")
    L += ["", "Since issue #24 the connector checks the free event list first and does not buy odds for a competition "
          "in which no listed event matches a stored event.", ""]
    oy = rep["operator_yield"]
    L += ["## The Odds API: bookmaker names versus known operators", "",
          f"Fresh stored quotes for events starting in the next {rep['horizon_hours']:g} hours.", "",
          f"- Events priced: {oy['events_priced']} ({oy['event_markets_priced']} event-markets).",
          f"- Bookmakers: {oy['bookmakers']}, of which known operators: **{oy['known_operators']}**; "
          f"unknown ownership: {len(oy['unknown_ownership'])} ({', '.join(oy['unknown_ownership']) or 'none'}).",
          "- Operators quoted under several brands: "
          + ("; ".join(f"{g} ({', '.join(v)})" for g, v in oy["operators_with_several_brands"].items()) or "none") + ".",
          f"- Median per event-market: {oy['median_bookmakers_per_event_market']} bookmakers, "
          f"{oy['median_known_operators_per_event_market']} known operators.",
          f"- Events with 3+ known operators: {oy['events_with_3plus_known_operators']}; with a sharp reference: "
          f"{oy['events_with_sharp_reference']}.", "",
          "### What a one-region bookmaker list would need to keep", "",
          f"The smallest set of stored bookmakers that keeps every known operator and sharp reference on every "
          f"event-market is **{len(oy['minimal_bookmakers_keeping_known_coverage'])}** of {oy['slots_per_region']} slots: "
          + (", ".join(oy["minimal_bookmakers_keeping_known_coverage"]) or "none") + ".",
          f"Recounted with only those: {oy['check_events_with_3plus_known_operators_after']} events with 3+ known operators "
          f"(all bookmakers: {oy['events_with_3plus_known_operators']}) and {oy['check_events_with_sharp_reference_after']} "
          f"with a sharp reference (all bookmakers: {oy['events_with_sharp_reference']}).",
          f"That would leave **{oy['slots_left_for_other_operators']}** slot(s) for operators the `eu` region does not carry.", "",
          "**Limits of this number.** It is measured on stored `eu` quotes only. It does not show what other bookmakers "
          "would return on the free plan, and dropping the unknown-ownership bookmakers removes prices that the "
          "best-price search uses today. Changing the list is an owner decision; the default is unchanged.", "",
          "| Bookmaker | Known operator | Events with a fresh quote |", "|---|---|---|"]
    for r in oy["per_bookmaker"]:
        L.append(f"| {r['bookmaker']} | {r['operator'] or 'unknown'} | {r['events']} |")
    L += ["", "## Budget and licensing matrix", "",
          "Statuses: " + "; ".join(f"**{k}** = {v}" for k, v in STATUSES.items()) + ".", "",
          "| Source | Kind | Status | Recurring cost | Credential | Sports | May store | May publish raw quotes | Adds | Checked |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c in rep["candidates"]:
        L.append("| " + " | ".join(str(c[k]).replace("|", "/") for k in (
            "name", "kind", "status", "recurring_cost", "credential", "sports", "store", "publish", "independence", "checked")) + " |")
    L += ["", "### Findings and links", ""]
    for c in rep["candidates"]:
        L.append(f"- **{c['name']}** ({c['status']}): {c['finding']} " + " ".join(f"<{u}>" for u in c["links"]))
    po = rep["polymarket_observation"]
    L += ["", "## Polymarket: one dated observation (context only)", "",
          f"Taken {po['as_of'][:16].replace('T', ' ')} UTC with the documented public API ({po['requests']} requests). "
          f"Counts only; no price was stored. Window: {po['window']}.", "",
          "| Competition | Games listed | With a two-sided match-winner market | Median resting liquidity (USD) | Median bid/ask spread |",
          "|---|---|---|---|---|"]
    L += [f"| {a} | {g} | {m} | {liq:,} | {s:.2f} |" for a, g, m, liq, s in po["rows"]]
    L += [""] + [f"- {c}" for c in po["caveats"]]
    return "\n".join(L) + "\n"


def write(now: datetime | None = None, db_path: Path | str | None = None) -> dict:
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    con = coverage.connect_ro(db_path)
    try:
        rep = build(con, now)
    finally:
        con.close()
    out_dir = config.DATA_DIR / "coverage"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quote_sources_latest.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "quote_sources.md").write_text(to_markdown(rep))
    return rep
