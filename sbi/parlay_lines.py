"""NBA and NFL point spreads and game totals as estimated-parlay legs (issue #83).

Model (documented in docs/METHODOLOGY.md, "Spreads and totals"):
- home margin  ~ Normal(mean = expected margin, sd = sport-specific margin sd)
- game total   ~ Normal(mean = expected total,  sd = sport-specific total sd)
Expected margin and total come from the existing points ratings (`sbi.models.ratings`, the team
offence/defence fit already used for NBA/NFL moneylines). A second margin variant reads the
expected margin off the de-vigged moneyline (mean = sd x Phi^-1(P(home win))), and a second total
variant blends the ratings total 50/50 with the market total. Both standard deviations are fitted
on stored historical results (walk-forward residuals), see `backtest`.

Line conventions follow the odds table: a SPREAD line is from the HOME team's perspective for both
selections (home -4.5 = home must win by 5+; the away selection at the same row is away +4.5); a
TOTAL line is the points total. Whole-number lines can push: the leg is then void.

Leg probability: the backtest (data/backtest/parlay_lines.json) compares each model with the
market's de-vigged probability on stored history. Where the model is not better than the market,
the leg uses the de-vigged market consensus (as tennis does) and the card says so
("Probability: market consensus"). `use_model` reads that decision; nothing here changes a
single-pick threshold, and no network request or API credit is used at parlay-build time.
"""
from __future__ import annotations

import json
from math import isfinite

import numpy as np
from scipy.stats import norm

from . import config

SPORTS = ("nba", "nfl")
MARKETS = ("SPREAD", "TOTAL")
SELECTIONS = {"SPREAD": ["home", "away"], "TOTAL": ["over", "under"]}
DEFAULT_SD = {"nba": {"margin": 12.0, "total": 18.0}, "nfl": {"margin": 13.5, "total": 13.5}}
MARKET_LABEL = {"ML": "Moneyline", "1X2": "Match result", "SPREAD": "Point spread", "TOTAL": "Game total"}
PROB_NOTE_MARKET = "Probability: market consensus"
BACKTEST_FILE = "parlay_lines.json"


# ---------- probabilities (pure) ----------
def _is_whole(x: float) -> bool:
    return abs(x - round(x)) < 1e-9


def line_probs(mean: float, sd: float, threshold: float) -> tuple[float, float, float]:
    """(win, push, lose) for "X > threshold" with X ~ Normal(mean, sd) on integer points.
    Whole-number thresholds can push; a continuity correction of 0.5 point is used."""
    if sd <= 0 or not isfinite(mean):
        raise ValueError("invalid normal parameters")
    if _is_whole(threshold):
        lose = float(norm.cdf((threshold - 0.5 - mean) / sd))
        win = float(norm.sf((threshold + 0.5 - mean) / sd))
        return win, max(0.0, 1.0 - win - lose), lose
    win = float(norm.sf((threshold - mean) / sd))
    return win, 0.0, 1.0 - win


def cover_probs(mean_margin: float, sd: float, line: float, selection: str) -> tuple[float, float, float]:
    """(win, push, lose) of a SPREAD selection. `line` is the home line (home -4.5 -> -4.5);
    the home side covers when margin + line > 0, the away side when margin + line < 0."""
    if selection == "home":
        return line_probs(mean_margin, sd, -line)
    if selection == "away":
        return line_probs(-mean_margin, sd, line)
    raise ValueError(selection)


def total_probs(mean_total: float, sd: float, line: float, selection: str) -> tuple[float, float, float]:
    """(win, push, lose) of a TOTAL selection (over: total > line; under: total < line)."""
    if selection == "over":
        return line_probs(mean_total, sd, line)
    if selection == "under":
        return line_probs(-mean_total, sd, -line)
    raise ValueError(selection)


def no_push(p: tuple[float, float, float]) -> float:
    """Win probability given the leg is not void (a pushed leg is void, stake returned)."""
    w, _, l = p
    return w / (w + l) if w + l > 0 else 0.5


def leg_prob(market: str, selection: str, line: float, mean: float, sd: float) -> float:
    fn = cover_probs if market == "SPREAD" else total_probs
    return no_push(fn(mean, sd, line, selection))


def ml_implied_margin(p_home: float, sd: float) -> float:
    """Expected home margin implied by a de-vigged moneyline: P(margin > 0) = p_home."""
    p = min(max(float(p_home), 1e-4), 1 - 1e-4)
    return float(sd * norm.ppf(p))


# ---------- display ----------
def _num(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".") if not _is_whole(x) else str(int(round(x)))


def signed_line(x: float) -> str:
    """'−4.5', '+3', 'PK' (a typographic minus, as on the cards)."""
    if abs(x) < 1e-9:
        return "PK"
    return ("+" if x > 0 else "−") + _num(abs(x))


def selection_text(market: str, selection: str, line, home: str, away: str) -> str | None:
    """'Lakers −4.5', 'Celtics +4.5', 'Over 228.5 points', 'Under 44 points'; None if unknown."""
    try:
        line = float(line)
    except (TypeError, ValueError):
        return None
    if market == "SPREAD":
        if selection == "home":
            return f"{home} {signed_line(line)}"
        if selection == "away":
            return f"{away} {signed_line(-line)}"
    if market == "TOTAL" and selection in ("over", "under"):
        return f"{selection.capitalize()} {_num(line)} points"
    return None


def market_label(market: str) -> str:
    return MARKET_LABEL.get(market, str(market))


# ---------- backtest decision ----------
def backtest_path():
    return config.DATA_DIR / "backtest" / BACKTEST_FILE


def use_model(sport: str, market: str, report: dict | None = None) -> bool:
    """True only when the stored backtest shows the model beating the de-vigged market (lower log
    loss, with the bootstrap 95% interval of model minus market entirely below 0). Missing or
    unreadable reports mean the market consensus is used."""
    if report is None:
        try:
            report = json.loads(backtest_path().read_text())
        except (OSError, ValueError):
            return False
    d = (report.get("decision") or {}).get(sport, {}).get(market)
    return bool(d and d.get("use_model"))


# ---------- backtest (network on first run; cached by sbi.sources.http) ----------
def _ll(p, y):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def _brier(p, y):
    return (np.asarray(p, float) - np.asarray(y, float)) ** 2


def _score(df, col, ycol):
    d = df.dropna(subset=[col, ycol])
    return {"log_loss": round(float(_ll(d[col], d[ycol]).mean()), 5),
            "brier": round(float(_brier(d[col], d[ycol]).mean()), 5)} if len(d) else None


def _compare(df, ycol, market_col, model_cols) -> dict:
    from .backtest import bootstrap_ci
    d = df.dropna(subset=[ycol, market_col] + model_cols)
    out = {"n": int(len(d)), "market_devig": _score(d, market_col, ycol)}
    for c in model_cols:
        diff = _ll(d[c], d[ycol]) - _ll(d[market_col], d[ycol])
        lo, hi = bootstrap_ci(np.asarray(diff)) if len(d) else (float("nan"), float("nan"))
        out[c] = {**(_score(d, c, ycol) or {}), "logloss_minus_market": round(float(diff.mean()), 5) if len(d) else None,
                  "ci95": [round(lo, 5), round(hi, 5)]}
    return out


def _decide(cmp: dict, model_cols: list[str]) -> dict:
    best = None
    for c in model_cols:
        r = cmp.get(c) or {}
        ci = r.get("ci95") or [float("nan")] * 2
        if cmp.get("n", 0) >= 100 and isfinite(ci[1]) and ci[1] < 0 and (best is None or r["log_loss"] < cmp[best]["log_loss"]):
            best = c
    return {"use_model": best is not None, "model": best,
            "reason": (f"{best} beats the de-vigged market out of sample" if best else
                       "no model beats the de-vigged market (95% interval of the log-loss difference not below 0, "
                       "or fewer than 100 games): legs use the market consensus")}


def backtest_nfl(test=(2023, 2026), fit_sd=(2018, 2022)) -> dict:
    """Walk-forward on nflverse closing lines (1999-present, free): weekly ratings refits."""
    import pandas as pd
    from . import ev as evm
    from . import us
    from .sources.international import american_to_decimal as a2d
    p = us.params("nfl")
    df = us.nfl_history()
    df = df[df.hs.notna()].reset_index(drop=True)
    df["as_"] = df["as"]
    raw = pd.read_csv(__import__("io").BytesIO(us.fetch(us.NFLVERSE, max_age_hours=24 * 7)[0]))
    raw = raw.set_index("espn")[["away_spread_odds", "home_spread_odds", "under_odds", "over_odds"]]
    df = df.join(raw, on="espn")
    rows = []
    for (season, week), g in df[(df.season >= fit_sd[0]) & (df.season <= test[1])].groupby(["season", "week"], sort=True):
        cut = g.kickoff_utc.min() - pd.Timedelta(hours=1)
        tr = df[(df.kickoff_utc < cut) & (df.kickoff_utc >= cut - pd.Timedelta(days=us.CFG["nfl"]["lookback"]))]
        if len(tr) < 200:
            continue
        m = us._fit("nfl", tr, cut, p["xi"], p["ridge"])
        for r in g.itertuples():
            if not (m.has(r.home) and m.has(r.away)):
                continue
            ph, pa = m.expected(r.home, r.away, bool(r.neutral))
            rec = {"season": season, "margin": r.hs - r.as_, "total": r.hs + r.as_, "mu_m": ph - pa, "mu_t": ph + pa,
                   "home_line": None if pd.isna(r.spread_line) else -float(r.spread_line),
                   "total_line": None if pd.isna(r.total_line) else float(r.total_line)}
            oh, oa = a2d(r.home_ml), a2d(r.away_ml)
            if oh and oa:
                rec["p_ml"] = float(evm.devig_power([oh, oa])[0])
            sh, sa = a2d(r.home_spread_odds), a2d(r.away_spread_odds)
            if sh and sa:
                rec["mkt_cover"] = float(evm.devig_power([sh, sa])[0])
            so, su = a2d(r.over_odds), a2d(r.under_odds)
            if so and su:
                rec["mkt_over"] = float(evm.devig_power([so, su])[0])
            rows.append(rec)
    return _evaluate("nfl", pd.DataFrame(rows), lambda d: d.season <= fit_sd[1], lambda d: d.season >= test[0],
                     {"fit_sd_seasons": list(fit_sd), "test_seasons": list(test),
                      "market": "nflverse closing spread and total with their prices, de-vigged (power method)"})


def backtest_nba(con=None) -> dict:
    """Standard deviations from walk-forward ratings residuals on ESPN results (2024-25 season);
    model vs market only on games with stored pre-game quotes in data/sbi.sqlite (the only free
    NBA odds history Doyen has), so that sample is small."""
    import pandas as pd
    from datetime import datetime, timezone
    from . import db
    from . import ev as evm
    from . import us
    con = con or db.connect()
    now = datetime.now(timezone.utc)
    p = us.params("nba")
    hist = us.nba_history(now)
    hist["as_"] = hist["as"]
    stored = _stored_nba_lines(con, now)
    rows = []
    days = sorted({d.normalize() for d in hist.kickoff_utc})
    fits = {}
    for day in days:
        if day < pd.Timestamp("2024-12-01", tz="UTC"):
            continue
        tr = hist[(hist.kickoff_utc < day) & (hist.kickoff_utc >= day - pd.Timedelta(days=us.CFG["nba"]["lookback"]))]
        if len(tr) < 300:
            continue
        g = hist[(hist.kickoff_utc >= day) & (hist.kickoff_utc < day + pd.Timedelta(days=1))]
        m = fits.setdefault(day, us._fit("nba", tr, day, p["xi"], p["ridge"]))
        for r in g.itertuples():
            if not (m.has(r.home) and m.has(r.away)):
                continue
            ph, pa = m.expected(r.home, r.away, bool(r.neutral))
            rec = {"kickoff": r.kickoff_utc, "espn": str(r.espn), "margin": r.hs - r.as_, "total": r.hs + r.as_,
                   "mu_m": ph - pa, "mu_t": ph + pa}
            rec.update(stored.get(str(r.espn), {}))
            rows.append(rec)
    df = pd.DataFrame(rows)
    cut = pd.Timestamp("2025-07-01", tz="UTC")
    return _evaluate("nba", df, lambda d: d.kickoff < cut, lambda d: d.kickoff >= pd.Timestamp("2026-10-01", tz="UTC"),
                     {"fit_sd_period": "2024-12-01 to 2025-06-30 (walk-forward, ESPN results)",
                      "test_period": "games from 2026-10-01 with stored pre-game quotes",
                      "market": "latest stored pre-game quote per bookmaker at the most-quoted line, de-vigged consensus "
                                "(sbi.ev.consensus); moneyline consensus for the ML-implied margin"})


def _stored_nba_lines(con, now) -> dict:
    """espn id -> {home_line, total_line, mkt_cover, mkt_over, p_ml} from stored pre-game quotes."""
    from collections import Counter
    from . import ev as evm
    from .engine import books_from_rows
    from .sources.books import normalize_book
    out = {}
    evs = con.execute("""SELECT event_id, kickoff_utc FROM events WHERE sport='nba' AND status='finished'
                         AND home_score IS NOT NULL""").fetchall()
    for e in evs:
        latest = {}
        for r in con.execute("SELECT bookmaker, market, selection, line, price, retrieved_at FROM odds WHERE event_id=? "
                             "AND kind='pre' AND retrieved_at < ?", (e["event_id"], e["kickoff_utc"])):
            bk = normalize_book(r["bookmaker"])
            if not bk:
                continue
            k = (bk, r["market"], r["selection"], r["line"])
            if k not in latest or r["retrieved_at"] > latest[k][1]:
                latest[k] = (r["price"], r["retrieved_at"])
        # one line per bookmaker and market: its latest quote
        last_line = {}
        for (bk, mk, sel, ln), (px, t) in latest.items():
            if (bk, mk) not in last_line or t > last_line[(bk, mk)][1]:
                last_line[(bk, mk)] = (ln, t)
        books = books_from_rows([(mk, ln, bk, sel, px) for (bk, mk, sel, ln), (px, t) in latest.items()
                                 if last_line[(bk, mk)][0] == ln])
        rec = {}
        ml, _ = evm.consensus(evm.clean(books.get(("ML", None)) or {}, ["home", "away"]), ["home", "away"])
        if ml:
            rec["p_ml"] = float(ml["home"])
        for mk, sels, key, pk in (("SPREAD", ["home", "away"], "home_line", "mkt_cover"),
                                  ("TOTAL", ["over", "under"], "total_line", "mkt_over")):
            lines = Counter({ln: evm.n_books(evm.clean(b, sels), sels) for (m, ln), b in books.items() if m == mk})
            if not lines:
                continue
            ln = max(lines, key=lambda x: (lines[x], -abs(x)))
            c, _ = evm.consensus(evm.clean(books[(mk, ln)], sels), sels)
            if c:
                rec[key], rec[pk] = float(ln), float(c[sels[0]])
        out[e["event_id"].rsplit(":", 1)[-1]] = rec
    return out


def _evaluate(sport, df, sd_mask, test_mask, meta) -> dict:
    fit = df[sd_mask(df)]
    sd_m = float(np.sqrt(((fit.margin - fit.mu_m) ** 2).mean()))
    sd_t = float(np.sqrt(((fit.total - fit.mu_t) ** 2).mean()))
    sd_mkt = None
    if "home_line" in fit and fit.home_line.notna().sum() > 100:
        f2 = fit.dropna(subset=["home_line"])
        sd_mkt = float(np.sqrt(((f2.margin + f2.home_line) ** 2).mean()))
    t = df[test_mask(df)].copy()
    for c in ("home_line", "total_line", "mkt_cover", "mkt_over", "p_ml"):
        if c not in t:
            t[c] = np.nan
    t = t.astype({c: float for c in ("home_line", "total_line", "mkt_cover", "mkt_over", "p_ml")})
    sd_ml = sd_mkt or sd_m

    def cover(r, mu, sd):
        return np.nan if pd_isna(r.home_line) or pd_isna(mu) else leg_prob("SPREAD", "home", r.home_line, mu, sd)

    def over(r, mu, sd):
        return np.nan if pd_isna(r.total_line) else leg_prob("TOTAL", "over", r.total_line, mu, sd)

    t["y_cover"] = [np.nan if pd_isna(r.home_line) or abs(r.margin + r.home_line) < 1e-9 else float(r.margin + r.home_line > 0)
                    for r in t.itertuples()]
    t["y_over"] = [np.nan if pd_isna(r.total_line) or abs(r.total - r.total_line) < 1e-9 else float(r.total > r.total_line)
                   for r in t.itertuples()]
    t["cover_ratings"] = [cover(r, r.mu_m, sd_m) for r in t.itertuples()]
    t["cover_ml_implied"] = [cover(r, np.nan if pd_isna(r.p_ml) else ml_implied_margin(r.p_ml, sd_ml), sd_ml)
                             for r in t.itertuples()]
    t["over_ratings"] = [over(r, r.mu_t, sd_t) for r in t.itertuples()]
    t["over_blend"] = [over(r, 0.5 * r.mu_t + 0.5 * r.total_line, sd_t) if not pd_isna(r.total_line) else np.nan
                       for r in t.itertuples()]
    spread = _compare(t, "y_cover", "mkt_cover", ["cover_ratings", "cover_ml_implied"])
    total = _compare(t, "y_over", "mkt_over", ["over_ratings", "over_blend"])
    return {"sport": sport, **meta,
            "sd": {"margin_ratings": round(sd_m, 2), "total_ratings": round(sd_t, 2),
                   "margin_around_market_line": None if sd_mkt is None else round(sd_mkt, 2),
                   "n_fit": int(len(fit))},
            "pushes_excluded": {"spread": int(((t.margin + t.home_line).abs() < 1e-9).sum()),
                                "total": int(((t.total - t.total_line).abs() < 1e-9).sum())},
            "SPREAD": spread, "TOTAL": total,
            "decision": {"SPREAD": _decide(spread, ["cover_ratings", "cover_ml_implied"]),
                         "TOTAL": _decide(total, ["over_ratings", "over_blend"])}}


def pd_isna(x) -> bool:
    try:
        return x is None or not isfinite(float(x))
    except (TypeError, ValueError):
        return True


def backtest(con=None) -> dict:
    """Run both sports, write data/backtest/parlay_lines.json and return it."""
    from datetime import datetime, timezone
    rep = {"method": "normal-margin-total-v1", "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "metric_note": "Log loss and Brier on home cover and over, pushes excluded; market = de-vigged price; "
                          "ci95 = bootstrap 95% interval of (model log loss - market log loss) per game.",
           "nfl": backtest_nfl(), "nba": backtest_nba(con)}
    rep["decision"] = {s: rep[s]["decision"] for s in SPORTS}
    path = backtest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rep, indent=2, default=str))
    return rep
