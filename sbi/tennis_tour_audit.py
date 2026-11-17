"""Tennis tour-label audit (issue #49): how many matches changed label, and what it did to the model.

Before #49 every match took its tour from the ESPN scoreboard it was first read from (``atp`` is read
first), and that scoreboard returns women's draws at combined events too. The fix takes the tour from
the draw (``sbi/tennis.py: tour_of``). Each parsed match keeps both labels (``feed_tour`` = old,
``tour`` = new), so this audit compares them on exactly the same matches:

- counts of completed matches since 2024 whose label changed, by Grand Slam / tour / rule used;
- stored database events whose league differs from the corrected tour, and published picks among them
  (listed, never edited);
- walk-forward of the live model (same Elo, same test matches from ``TEST_FROM``) with old vs new labels:
  log loss and Brier, paired 95% bootstrap intervals; optionally the #46 mirror warm start as well.

Elo ratings are keyed by player name, not by tour, so the label never changed whose rating a match
updates; what it changed is the best-of-five conversion (women's Slam matches) and the league a stored
event is filed under (which decides which odds feed can match it).

Read-only: writes ``data/backtest/tennis_tour_labels.json`` and ``reports/tennis_tour_labels.md``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

from . import config
from .tennis import Elo, match_prob

TEST_FROM = "2025-07-01"      # same as data/backtest/tennis.json and the #46 walk-forward
MIN_HISTORY = 10
OUT = config.DATA_DIR / "backtest" / "tennis_tour_labels.json"
REPORT = config.REPORTS_DIR / "tennis_tour_labels.md"


def _ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _ci(x, seed=0):
    from .backtest import bootstrap_ci
    lo, hi = bootstrap_ci(np.asarray(x, float), seed=seed)
    return [round(lo, 5), round(hi, 5)]


def completed(espn: list[dict]) -> list[dict]:
    return sorted([m for m in espn if m["completed"] and m["winner"] and not m.get("walkover")], key=lambda x: x["date"])


def label_counts(espn: list[dict]) -> dict:
    done = completed(espn)
    changed = [m for m in done if m.get("feed_tour", m["tour"]) != m["tour"]]
    src = {}
    for m in done:
        src[m.get("tour_source", "unknown")] = src.get(m.get("tour_source", "unknown"), 0) + 1
    by_dir = {}
    for m in changed:
        k = f"{m['feed_tour']}->{m['tour']}"
        by_dir[k] = by_dir.get(k, 0) + 1
    up = [m for m in espn if not m["completed"]]
    return {"completed_matches": len(done), "completed_label_changed": len(changed),
            "completed_label_changed_by_direction": by_dir,
            "completed_label_changed_grand_slam": sum(1 for m in changed if m["slam"]),
            "grand_slam_matches_no_longer_best_of_five": sum(1 for m in changed if m["slam"] and m["tour"] == "wta"),
            "tour_rule_used": dict(sorted(src.items())),
            "not_completed_matches_in_window": len(up),
            "not_completed_label_changed": sum(1 for m in up if m.get("feed_tour", m["tour"]) != m["tour"])}


def stored_rows(con, espn: list[dict]) -> dict:
    """Stored tennis events whose league differs from the corrected tour (matched on the ESPN match ID)."""
    tour_by_id = {str(m["id"]): m["tour"] for m in espn}
    picks = {r[0] for r in con.execute("SELECT DISTINCT event_id FROM recommendations WHERE sport='tennis'")}
    n, unknown, wrong = 0, 0, []
    for eid, league in con.execute("SELECT event_id, league FROM events WHERE sport='tennis'"):
        n += 1
        t = tour_by_id.get(eid.split(":")[-1])
        if t is None:
            unknown += 1
        elif league != f"TENNIS:{t.upper()}":
            wrong.append({"event_id": eid, "league": league, "correct": f"TENNIS:{t.upper()}", "has_pick": eid in picks})
    return {"stored_events": n, "not_in_espn_window": unknown, "mislabelled": len(wrong),
            "mislabelled_with_published_pick": [w["event_id"] for w in wrong if w["has_pick"]], "rows": wrong}


def _walk(hist, label_key, elo=None, test_from=TEST_FROM):
    elo = elo or Elo()
    cut = datetime.fromisoformat(test_from).replace(tzinfo=timezone.utc)
    out = {}
    for m in hist:
        if m["date"] >= cut:
            mm = {**m, "tour": m[label_key]}
            n = min(elo.matches_played(m["p1"]), elo.matches_played(m["p2"]))
            out[str(m["id"])] = (match_prob(elo, mm), 1.0 if m["winner"] == m["p1"] else 0.0, n)
        loser = m["p2"] if m["winner"] == m["p1"] else m["p1"]
        elo.update(m["winner"], loser, m["surface"])
    return out


def _compare(before: dict, after: dict, ids: list[str]) -> dict:
    if not ids:
        return {"n": 0}
    pb = np.array([before[i][0] for i in ids]); pa = np.array([after[i][0] for i in ids])
    y = np.array([after[i][1] for i in ids])
    lb, la, bb, ba = _ll(pb, y), _ll(pa, y), (pb - y) ** 2, (pa - y) ** 2
    return {"n": len(ids),
            "logloss": {"before": round(float(lb.mean()), 5), "after": round(float(la.mean()), 5),
                        "after_minus_before": round(float((la - lb).mean()), 5), "ci95": _ci(la - lb)},
            "brier": {"before": round(float(bb.mean()), 5), "after": round(float(ba.mean()), 5),
                      "after_minus_before": round(float((ba - bb).mean()), 5), "ci95": _ci(ba - bb, seed=1)}}


def walk_forward(espn: list[dict], warm=None) -> dict:
    """Old vs new labels on identical test matches. ``warm``: callable returning a pre-trained Elo (mirror arm)."""
    hist = completed(espn)
    before = _walk(hist, "feed_tour", warm() if warm else None)
    after = _walk(hist, "tour", warm() if warm else None)
    meta = {str(m["id"]): m for m in hist}
    main = [i for i, v in after.items() if v[2] >= MIN_HISTORY]
    changed = [i for i in main if meta[i]["feed_tour"] != meta[i]["tour"]]
    return {"test_from": TEST_FROM, "min_history": MIN_HISTORY,
            "main": _compare(before, after, main),
            "main_wta": _compare(before, after, [i for i in main if meta[i]["tour"] == "wta"]),
            "main_label_changed": _compare(before, after, changed),
            "main_label_changed_grand_slam": _compare(before, after, [i for i in changed if meta[i]["slam"]]),
            "all_test_matches": _compare(before, after, list(after))}


def mirror_warm(espn: list[dict]):
    """Elo factory warm-started with the #46 mirror (2010-2023), or None if the local mirror files are absent."""
    from .sources import sackmann
    from .tennis_history import ESPN_FROM
    if not sackmann.verify(sackmann.LOCAL_DIR, sackmann.load_manifest()).get("ok"):
        return None
    sack, _ = sackmann.load(sackmann.LOCAL_DIR)
    names = {}
    for m in espn:
        names.setdefault(m["tour"], set()).update((m["p1"], m["p2"]))
    pm, _ = sackmann.build_player_map(sack, names)

    def make():
        e = Elo()
        for m in sack:
            if m.tourney_date < ESPN_FROM and not m.walkover:
                e.update(pm.key(m.tour, m.winner_id), pm.key(m.tour, m.loser_id), m.surface)
        return e
    return make


def run(con, espn: list[dict], with_mirror: bool = True) -> dict:
    out = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "rule": "the grouping slug mens-singles/womens-singles, else the competition type slug, "
                   "else the grouping or competition name (Men's/Women's), else the scoreboard endpoint (feed_fallback)",
           "labels": label_counts(espn), "stored": stored_rows(con, espn), "walk_forward_live": walk_forward(espn)}
    warm = mirror_warm(espn) if with_mirror else None
    out["walk_forward_mirror_warm_start"] = walk_forward(espn, warm) if warm else {"skipped": "local mirror files absent"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str) + "\n")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(out))
    return out


def _row(label, r):
    if not r.get("n"):
        return f"| {label} | 0 | | | | | | |"
    L, B = r["logloss"], r["brier"]
    return (f"| {label} | {r['n']:,} | {L['before']:.5f} | {L['after']:.5f} | {L['after_minus_before']:+.5f} "
            f"({L['ci95'][0]:+.5f} to {L['ci95'][1]:+.5f}) | {B['before']:.5f} | {B['after']:.5f} | "
            f"{B['after_minus_before']:+.5f} ({B['ci95'][0]:+.5f} to {B['ci95'][1]:+.5f}) |")


def render(o: dict) -> str:
    L, S = o["labels"], o["stored"]
    s = ["# Tennis tour labels (issue #49)", "",
         f"Generated {o['generated_at']} by `python -m sbi tennis-tour-audit`. Read-only.", "",
         f"**Rule.** The tour of each match is read from the ESPN draw it belongs to: {o['rule']}. "
         "Before this fix the tour came from the scoreboard endpoint, and ESPN's `atp` scoreboard (read first) also "
         "carries the women's draws at combined events.", "",
         "## Matches whose label changed", "",
         f"- Completed ESPN singles matches since 2024: {L['completed_matches']:,}; label changed: "
         f"**{L['completed_label_changed']:,}** ({', '.join(f'{k}: {v:,}' for k, v in L['completed_label_changed_by_direction'].items()) or 'none'}).",
         f"- Of these, Grand Slam matches: **{L['completed_label_changed_grand_slam']:,}**, all now best of three "
         f"({L['grand_slam_matches_no_longer_best_of_five']:,} women's Slam matches no longer get the best-of-five conversion).",
         f"- Rule used per completed match: {', '.join(f'{k} {v:,}' for k, v in L['tour_rule_used'].items())}.",
         f"- Not yet completed matches in the fetched window: {L['not_completed_matches_in_window']:,}; label changed: "
         f"{L['not_completed_label_changed']:,}.", "",
         "## Stored database rows", "",
         f"- Stored tennis events: {S['stored_events']}; with a league different from the corrected tour: **{S['mislabelled']}**"
         f" ({S['not_in_espn_window']} could not be checked because their ESPN match is outside the fetched data).",
         f"- Published picks on a mislabelled event: **{len(S['mislabelled_with_published_pick'])}**"
         + (": " + ", ".join(S["mislabelled_with_published_pick"]) + " (left unchanged)." if S["mislabelled_with_published_pick"] else "."),
         "- From now on `tennis.register` keeps an already stored row's ID (its odds stay linked) and corrects its league, "
         "unless a published pick references it, in which case the row is left exactly as it was.", ""]
    for key, title in (("walk_forward_live", "Walk-forward, live model"),
                       ("walk_forward_mirror_warm_start", "Walk-forward, live model warm-started with the #46 mirror")):
        w = o[key]
        s += [f"## {title}", ""]
        if "skipped" in w:
            s += [f"Skipped: {w['skipped']}.", ""]
            continue
        s += [f"Same Elo and the same test matches from {w['test_from']}; only the tour label differs. "
              "Negative after − before is better after the fix.", "",
              "| Test set | n | Log loss before | after | after − before (95%) | Brier before | after | after − before (95%) |",
              "|---|---|---|---|---|---|---|---|",
              _row(f"Main (both players {w['min_history']}+ matches)", w["main"]),
              _row("Main, WTA (corrected label)", w["main_wta"]),
              _row("Main, label changed", w["main_label_changed"]),
              _row("Main, label changed, Grand Slam", w["main_label_changed_grand_slam"]),
              _row("All test matches", w["all_test_matches"]), ""]
    s += ["Elo ratings are keyed by player, not by tour, so the label never changed whose rating a match updated; "
          "the difference above comes only from dropping the best-of-five conversion on women's Grand Slam matches. "
          "A positive difference means the wrong conversion happened to help: it sharpens probabilities, and the Elo "
          "is under-confident on these matches. That is a calibration question for a separate, measured change; "
          "it is not a reason to keep applying best-of-five maths to best-of-three matches."]
    return "\n".join(s) + "\n"
