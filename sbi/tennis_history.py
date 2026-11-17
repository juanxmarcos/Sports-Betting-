"""Tennis history from the unofficial Sackmann mirror: sanity check, coverage and walk-forward (issue #45).

Research only. It writes reports and mapping files, never the database, and never changes
the live tennis model (``sbi/tennis.py``). Steps:

1. Load the pinned mirror files (checksums verified against ``data/tennis_sackmann/manifest.json``).
2. Map Sackmann players to the names Doyen's ESPN tennis data uses, and link mirror matches to
   Doyen's completed ESPN matches. **If winners disagree on more than 1% of linked matches, stop:**
   the report says so and no evaluation is run.
3. Walk-forward, chronological, same test matches for both arms:
   A = the live model (surface Elo on ESPN history from 2024-01-01, tuned parameters);
   B = the same, warm-started with mirror tour-level matches from 2010 to 2023.
   Log loss and Brier on ESPN results from ``TEST_FROM``, paired 95% bootstrap intervals.
4. Market check: on finished tennis events with stored multi-bookmaker match-winner odds,
   log loss and Brier of A, B and the de-vigged median market.

Decision rule, fixed before any result was seen (``CRITERIA``): B may replace A only if
(a) its paired log-loss gain over A has a 95% interval entirely below zero on the main test set,
and (b) at least ``min_market_events`` priced events exist and B's log loss is no worse than the market.
Otherwise the data stays research-only.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config
from .sources import sackmann
from .tennis import Elo, match_prob

ESPN_FROM = date(2024, 1, 1)          # Doyen's ESPN history starts here (sbi/tennis.py)
TEST_FROM = "2025-07-01"              # same test start as data/backtest/tennis.json
MIN_HISTORY = 10                      # same eligibility as the live backtest
CRITERIA = {"max_disagreement_rate": 0.01, "logloss_gain_ci_upper_below": 0.0, "min_market_events": 200}
OUT_DIR = config.DATA_DIR / "tennis_sackmann"
REPORT = config.REPORTS_DIR / "tennis_history.md"


def _ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _brier(p, y):
    return (np.asarray(p, float) - np.asarray(y, float)) ** 2


def _ci(x, seed=0):
    from .backtest import bootstrap_ci
    lo, hi = bootstrap_ci(np.asarray(x, float), seed=seed)
    return [round(lo, 5), round(hi, 5)]


def _summ(pa, pb, y) -> dict:
    if not len(y):
        return {"n": 0}
    la, lb, ba, bb = _ll(pa, y), _ll(pb, y), _brier(pa, y), _brier(pb, y)
    return {"n": int(len(y)),
            "logloss": {"A_espn_only": round(float(la.mean()), 5), "B_with_mirror": round(float(lb.mean()), 5),
                        "B_minus_A": round(float((lb - la).mean()), 5), "B_minus_A_ci95": _ci(lb - la)},
            "brier": {"A_espn_only": round(float(ba.mean()), 5), "B_with_mirror": round(float(bb.mean()), 5),
                      "B_minus_A": round(float((bb - ba).mean()), 5), "B_minus_A_ci95": _ci(bb - ba, seed=1)}}


def _espn_completed(espn: list[dict]) -> list[dict]:
    return sorted([m for m in espn if m["completed"] and m["winner"] and not m.get("walkover")],
                  key=lambda x: x["date"])


def walk_forward(sack: list[sackmann.Match], espn: list[dict], pm: sackmann.PlayerMap,
                 test_from: str = TEST_FROM, warm_until: date = ESPN_FROM) -> dict:
    hist = _espn_completed(espn)
    a, b = Elo(), Elo()
    warm = 0
    for m in sack:
        if m.tourney_date >= warm_until or m.walkover:
            continue
        b.update(pm.key(m.tour, m.winner_id), pm.key(m.tour, m.loser_id), m.surface)
        warm += 1
    cut = datetime.fromisoformat(test_from).replace(tzinfo=timezone.utc)
    rows, by_id = [], {}
    for m in hist:
        if m["date"] >= cut:
            pa, pb = match_prob(a, m), match_prob(b, m)
            na = min(a.matches_played(m["p1"]), a.matches_played(m["p2"]))
            nb = min(b.matches_played(m["p1"]), b.matches_played(m["p2"]))
            y = 1.0 if m["winner"] == m["p1"] else 0.0
            rows.append((pa, pb, y, na, nb, m["tour"]))
            by_id[str(m["id"])] = (pa, pb)
        loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
        a.update(m["winner"], loser, m["surface"])
        b.update(m["winner"], loser, m["surface"])
    R = np.array(rows, dtype=object) if rows else np.zeros((0, 6), dtype=object)

    def sub(mask):
        return _summ(R[mask, 0].astype(float), R[mask, 1].astype(float), R[mask, 2].astype(float))
    if len(R):
        na, nb, tour = R[:, 3].astype(int), R[:, 4].astype(int), R[:, 5]
        main = na >= MIN_HISTORY
        res = {"main_A_eligible": sub(main), "all_test_matches": sub(np.ones(len(R), bool)),
               "thin_history_in_A": sub(~main), "thin_in_A_but_10plus_in_B": sub((~main) & (nb >= MIN_HISTORY)),
               "atp_main": sub(main & (tour == "atp")), "wta_main": sub(main & (tour == "wta"))}
    else:
        res = {"main_A_eligible": {"n": 0}}
    return {"test_from": test_from, "warm_start_matches": warm, "warm_until": warm_until.isoformat(),
            "espn_history_matches": len(hist), "elo_params": {"w_surface": a.w, "k_scale": a.ks},
            "results": res, "_by_id": by_id}


def market_check(con, by_id: dict) -> dict:
    """De-vigged median market vs A and B on finished tennis events with stored ML odds (latest pre-start quote per book)."""
    q = """SELECT e.event_id, e.kickoff_utc, e.home_score, e.away_score, o.bookmaker, o.selection, o.price, o.retrieved_at
           FROM events e JOIN odds o USING(event_id)
           WHERE e.sport='tennis' AND e.status='finished' AND o.market='ML' AND o.retrieved_at < e.kickoff_utc
           ORDER BY o.retrieved_at"""
    ev = {}
    for eid, ko, hs, as_, book, sel, price, ts in con.execute(q):
        if hs is None or as_ is None or hs == as_:
            continue
        e = ev.setdefault(eid, {"y": 1.0 if hs > as_ else 0.0, "books": {}})
        e["books"].setdefault(book, {})[sel] = price
    rows = []
    for eid, e in sorted(ev.items()):
        ps = [(1 / b["home"]) / (1 / b["home"] + 1 / b["away"]) for b in e["books"].values() if "home" in b and "away" in b]
        espn_id = eid.split(":")[-1]
        if len(ps) < 3 or espn_id not in by_id:
            continue
        pa, pb = by_id[espn_id]
        rows.append((float(np.median(ps)), pa, pb, e["y"], len(ps)))
    if not rows:
        return {"n": 0}
    M = np.array(rows)
    out = {"n": len(rows), "median_bookmakers": float(np.median(M[:, 4]))}
    for name, col in (("market", 0), ("A_espn_only", 1), ("B_with_mirror", 2)):
        out[name] = {"logloss": round(float(_ll(M[:, col], M[:, 3]).mean()), 5),
                     "brier": round(float(_brier(M[:, col], M[:, 3]).mean()), 5)}
    return out


def coverage(sack, stats, espn, pm, names, linked, overlap_end) -> dict:
    seasons = {}
    for m in sack:
        s = seasons.setdefault(f"{m.tour}:{m.tourney_date.year}", {"matches": 0, "walkovers": 0})
        s["matches"] += 1
        s["walkovers"] += int(m.walkover)
    espn_done = _espn_completed(espn)
    in_overlap = [m for m in sack if not m.walkover and ESPN_FROM <= m.tourney_date <= overlap_end]
    espn_end = overlap_end + timedelta(days=14)          # the last mirror tournament (starting overlap_end) runs on
    espn_overlap = [m for m in espn_done if m["date"].date() <= espn_end]
    active = {p for m in espn_done for p in (m["p1"], m["p2"])}
    mapped_espn = {e for (e, _how) in pm.by_id.values()}
    last_seen = {}
    for m in sack:
        for k in ((m.tour, m.winner_id), (m.tour, m.loser_id)):
            last_seen[k] = max(last_seen.get(k, m.tourney_date), m.tourney_date)
    unmatched_recent = sum(1 for k in pm.unmatched if last_seen.get(k, ESPN_FROM) >= ESPN_FROM)
    methods = {}
    for (_t, _pid), (_e, how) in pm.by_id.items():
        methods[how] = methods.get(how, 0) + 1
    n_links = len(linked["links"])
    tour_of = {e: t for (t, _pid), (e, _how) in pm.by_id.items()}
    women_as_atp = [m for m in espn_done if m["tour"] == "atp" and tour_of.get(m["p1"]) == "wta" and tour_of.get(m["p2"]) == "wta"]
    return {
        "mirror": {"files": stats["files"], "rows_dropped": stats["dropped"], "matches": len(sack),
                   "first_date": min(m.tourney_date for m in sack).isoformat() if sack else None,
                   "last_date": max(m.tourney_date for m in sack).isoformat() if sack else None,
                   "seasons": dict(sorted(seasons.items()))},
        "players": {"mirror_players": len(names), "matched": len(pm.by_id), "unmatched": len(pm.unmatched),
                    "match_methods": methods,
                    "unmatched_with_a_mirror_match_since_2024": unmatched_recent,
                    "espn_players_2024_on": len(active),
                    "espn_players_with_mirror_id": len(active & mapped_espn)},
        "links": {"overlap_window": [ESPN_FROM.isoformat(), overlap_end.isoformat()], "espn_window_end": espn_end.isoformat(),
                  "mirror_matches_in_overlap": len(in_overlap), "espn_matches_in_overlap": len(espn_overlap),
                  "linked": n_links,
                  "share_of_mirror_matches_linked": round(n_links / len(in_overlap), 4) if in_overlap else None,
                  "share_of_espn_matches_linked": round(n_links / len(espn_overlap), 4) if espn_overlap else None,
                  "candidates": linked.get("candidates"),
                  "rejected_other_tournament": linked.get("rejected_other_tournament"),
                  "winner_disagreements": len(linked["disagreements"]),
                  "disagreement_rate": round(len(linked["disagreements"]) / n_links, 5) if n_links else None,
                  "disagreement_examples": linked["disagreements"][:30]},
        "espn_tour_labels": {"completed_matches_labelled_atp_between_two_wta_players": len(women_as_atp),
                             "of_which_grand_slam_treated_as_best_of_five": sum(1 for m in women_as_atp if m["slam"])},
    }


def doyen_event_players(con) -> dict:
    out = {}
    for league, home, away in con.execute("SELECT league, home, away FROM events WHERE sport='tennis'"):
        t = league.split(":")[-1].lower()
        out.setdefault(t, set()).update((home, away))
    return out


def decide(wf: dict, mk: dict) -> dict:
    main = wf["results"].get("main_A_eligible", {})
    gain = main.get("n", 0) > 0 and main["logloss"]["B_minus_A_ci95"][1] < CRITERIA["logloss_gain_ci_upper_below"]
    market_ok = (mk.get("n", 0) >= CRITERIA["min_market_events"]
                 and mk["B_with_mirror"]["logloss"] <= mk["market"]["logloss"])
    reasons = []
    if not gain:
        reasons.append("B's log-loss gain over the live model is not significant (95% interval reaches 0 or above)")
    if not market_ok:
        reasons.append(f"only {mk.get('n', 0)} finished events have stored multi-bookmaker tennis odds "
                       f"(criterion: {CRITERIA['min_market_events']}), so no gain against the market can be shown")
    return {"criteria": CRITERIA, "gain_vs_live_model": bool(gain), "market_criterion_met": bool(market_ok),
            "adopt_in_live_model": bool(gain and market_ok), "reasons_not_adopted": reasons}


def _write_csv(path: Path, rows: list[dict], header: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def run(con, espn: list[dict], mirror_dir: Path = sackmann.LOCAL_DIR, manifest: dict | None = None,
        out_dir: Path = OUT_DIR, report: Path = REPORT, verify_checksums: bool = True) -> dict:
    manifest = manifest if manifest is not None else sackmann.load_manifest()
    chk = sackmann.verify(mirror_dir, manifest) if verify_checksums else {"ok": True, "skipped": True}
    if not chk["ok"]:
        raise SystemExit(f"mirror files do not match the manifest: {chk}")
    sack, stats = sackmann.load(mirror_dir)
    espn_names = {}
    for m in espn:
        espn_names.setdefault(m["tour"], set()).update((m["p1"], m["p2"]))
    pm, names = sackmann.build_player_map(sack, espn_names)
    linked = sackmann.link_matches(sack, espn, pm)
    overlap_end = max((m.tourney_date for m in sack), default=ESPN_FROM)
    cov = coverage(sack, stats, espn, pm, names, linked, overlap_end)
    dp = doyen_event_players(con)
    cov["players"]["doyen_db_event_players"] = {t: len(v) for t, v in dp.items()}
    mapped = {e for (e, _h) in pm.by_id.values()}
    cov["players"]["doyen_db_event_players_with_mirror_id"] = {t: len(v & mapped) for t, v in dp.items()}
    out = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "provenance": {k: manifest[k] for k in ("mirror", "revision", "downloaded_at", "licence", "label", "attribution")},
           "checksums_verified": chk, "coverage": cov}
    rate = cov["links"]["disagreement_rate"]
    if rate is None or rate > CRITERIA["max_disagreement_rate"]:
        out["stopped"] = (f"winner disagreement rate {rate} exceeds {CRITERIA['max_disagreement_rate']} "
                          "(or no linked matches): mirror conflicts with known results, evaluation not run")
    else:
        wf = walk_forward(sack, espn, pm)
        mk = market_check(con, wf.pop("_by_id"))
        out.update({"walk_forward": wf, "market_check": mk, "decision": decide(wf, mk)})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "coverage.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    _write_csv(out_dir / "player_map.csv", pm.rows(names), ["tour", "sackmann_id", "sackmann_name", "espn_name", "method"])
    _write_csv(out_dir / "tournament_map.csv", sackmann.tournament_map(linked["links"]),
               ["tour", "sackmann_tournament", "espn_tournament", "linked_matches", "share"])
    _write_csv(out_dir / "match_links.csv", sorted(linked["links"], key=lambda r: (r["date"], r["sackmann_id"])),
               ["tour", "sackmann_id", "espn_id", "date"])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render(out))
    return out


def _fmt_ci(c):
    return f"{c[0]:+.5f} to {c[1]:+.5f}"


def render(o: dict) -> str:
    p, c = o["provenance"], o["coverage"]
    L, P, M = c["links"], c["players"], c["mirror"]
    s = ["# Tennis history from the Sackmann mirror (issue #45)", "",
         f"Generated {o['generated_at']} by `python -m sbi tennis-history`. Research only: the database and the live "
         "tennis model are not changed.", "",
         "## Provenance", "",
         f"- **Label: {p['label']}.**",
         f"- Mirror: {p['mirror']} (revision `{p['revision']}`), downloaded {p['downloaded_at']}.",
         f"- Licence: {p['licence']}. {p['attribution']}",
         f"- Checksums (SHA-256, per file, in `data/tennis_sackmann/manifest.json`): "
         f"{'verified' if o['checksums_verified'].get('ok') else 'NOT verified'}"
         f" ({o['checksums_verified'].get('checked', 0)} files).", "",
         "## Coverage", "",
         f"- Mirror: {M['files']} files, {M['matches']:,} tour-level singles matches, {M['first_date']} to {M['last_date']} "
         f"(rows dropped as unreadable: {M['rows_dropped']}).",
         f"- Players: {P['mirror_players']:,} in the mirror; {P['matched']:,} matched to an ESPN name used by Doyen "
         f"({', '.join(f'{k}: {v}' for k, v in P['match_methods'].items())}); {P['unmatched']:,} unmatched, of whom "
         f"{P['unmatched_with_a_mirror_match_since_2024']:,} played a mirror match since 2024 (the rest last appear earlier). "
         "Ambiguous names are left unmatched, never guessed.",
         f"- ESPN players seen since 2024: {P['espn_players_with_mirror_id']:,} of {P['espn_players_2024_on']:,} have a mirror ID. "
         "ESPN also carries Challenger and WTA 125 events, which the tour-level mirror files do not.",
         f"- Players in Doyen's stored tennis events (by Doyen's ESPN tour label) with a mirror ID: "
         + ", ".join(f"{t.upper()} {P['doyen_db_event_players_with_mirror_id'].get(t, 0)} of {n}"
                     for t, n in P['doyen_db_event_players'].items()) + ".", "",
         "| Season | ATP matches | WTA matches |", "|---|---|---|"]
    years = sorted({k.split(":")[1] for k in M["seasons"]})
    for y in years:
        s.append(f"| {y} | {M['seasons'].get(f'atp:{y}', {}).get('matches', 0):,} | {M['seasons'].get(f'wta:{y}', {}).get('matches', 0):,} |")
    pct = lambda x: "n/a" if x is None else f"{x:.1%}"  # noqa: E731
    s += ["", "## Sanity check against Doyen's ESPN results", "",
          f"Mirror tournaments starting {L['overlap_window'][0]} to {L['overlap_window'][1]} (the mirror's last week), "
          f"against ESPN matches up to {L['espn_window_end']}.", "",
          f"- Mirror matches in the window (walkovers excluded): {L['mirror_matches_in_overlap']:,}; ESPN completed matches: "
          f"{L['espn_matches_in_overlap']:,}.",
          f"- Linked (same two players, ESPN date within the tournament window, same tournament as the rest of that "
          f"tournament's links): **{L['linked']:,}**, i.e. {pct(L['share_of_mirror_matches_linked'])} of mirror matches and "
          f"{pct(L['share_of_espn_matches_linked'])} of ESPN matches (ESPN includes lower-tier events the mirror files omit).",
          f"- {L['rejected_other_tournament']} candidate pairings were dropped because the ESPN match belonged to a "
          "different tournament from the rest of that mirror tournament's links (the same two players met in two nearby events).",
          f"- Winner disagreements: **{L['winner_disagreements']}** ({(L['disagreement_rate'] or 0):.3%} of linked; "
          f"stop threshold {CRITERIA['max_disagreement_rate']:.0%}). Listed below. Which source is right was not checked, and neither was corrected."]
    T = c["espn_tour_labels"]
    if T["completed_matches_labelled_atp_between_two_wta_players"]:
        s += ["", f"**Found in Doyen's own data (not changed here):** {T['completed_matches_labelled_atp_between_two_wta_players']:,} "
              "completed ESPN matches labelled `atp` are between two WTA players (women's draws at combined events such as the "
              f"Slams, Indian Wells, Miami and Madrid). {T['of_which_grand_slam_treated_as_best_of_five']:,} of them are Grand Slam "
              "matches, which the live model converts to best of five sets although women play best of three. "
              "This affects the live model, so it needs its own issue."]
    if L["disagreement_examples"]:
        s += ["", "| Date | Tour | Mirror tournament | Mirror winner | ESPN winner | Retired |", "|---|---|---|---|---|---|"]
        s += [f"| {d['date']} | {d['tour'].upper()} | {d['sackmann_tournament']} | {d['winner_sackmann']} | {d['winner_espn']} | "
              f"{'yes' if d['retired'] else 'no'} |" for d in L["disagreement_examples"]]
    if "stopped" in o:
        s += ["", f"## STOPPED", "", o["stopped"]]
        return "\n".join(s) + "\n"
    wf, mk, dc = o["walk_forward"], o["market_check"], o["decision"]
    s += ["", "## Walk-forward evaluation", "",
          f"A = live model (surface Elo, w_surface {wf['elo_params']['w_surface']}, K scale {wf['elo_params']['k_scale']}) "
          f"on {wf['espn_history_matches']:,} ESPN matches from 2024. B = the same, warm-started with "
          f"{wf['warm_start_matches']:,} mirror matches before {wf['warm_until']}. Both predict each ESPN match from "
          f"{wf['test_from']} before seeing its result. Negative B − A is better for B.", "",
          "| Test set | n | Log loss A | Log loss B | B − A (95%) | Brier A | Brier B | B − A (95%) |",
          "|---|---|---|---|---|---|---|---|"]
    labels = {"main_A_eligible": "Main: both players 10+ matches in A", "all_test_matches": "All test matches",
              "thin_history_in_A": "Thin history in A", "thin_in_A_but_10plus_in_B": "Thin in A, 10+ in B",
              "atp_main": "Main, ATP", "wta_main": "Main, WTA"}
    for k, lab in labels.items():
        r = wf["results"].get(k, {})
        if r.get("n"):
            s.append(f"| {lab} | {r['n']:,} | {r['logloss']['A_espn_only']:.5f} | {r['logloss']['B_with_mirror']:.5f} | "
                     f"{_fmt_ci(r['logloss']['B_minus_A_ci95'])} | {r['brier']['A_espn_only']:.5f} | "
                     f"{r['brier']['B_with_mirror']:.5f} | {_fmt_ci(r['brier']['B_minus_A_ci95'])} |")
    s += ["", "### Against the market", ""]
    if mk.get("n"):
        s += [f"{mk['n']} finished tennis events have stored match-winner odds from 3+ bookmakers before the start "
              f"(median {mk['median_bookmakers']:.0f} bookmakers). The mirror has no odds, and Doyen has no older tennis odds.", "",
              "| | Log loss | Brier |", "|---|---|---|"]
        for k, lab in (("market", "De-vigged median market"), ("A_espn_only", "A (live model)"), ("B_with_mirror", "B (with mirror)")):
            s.append(f"| {lab} | {mk[k]['logloss']:.5f} | {mk[k]['brier']:.5f} |")
        s += ["", f"With {mk['n']} events this says nothing reliable either way."]
    else:
        s.append("No finished tennis event with stored odds from 3+ bookmakers could be scored.")
    s += ["", "## Decision", "",
          f"Pre-registered rule: adopt B only if its log-loss gain over A has a 95% interval below zero on the main set "
          f"**and** at least {CRITERIA['min_market_events']} priced events show B no worse than the market.", "",
          f"- Gain over the live model: **{'yes' if dc['gain_vs_live_model'] else 'no'}**.",
          f"- Market criterion met: **{'yes' if dc['market_criterion_met'] else 'no'}**.",
          f"- **Live model changed: {'yes' if dc['adopt_in_live_model'] else 'no, the mirror data stays research-only'}.**"]
    s += [f"  - {r}." for r in dc["reasons_not_adopted"]]
    return "\n".join(s) + "\n"
