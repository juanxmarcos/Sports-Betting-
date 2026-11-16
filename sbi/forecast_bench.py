"""Shadow benchmark of independently published soccer 1X2 forecasts (issue #23, phase 1).

`python -m sbi forecast-bench --openmodel-repo PATH --football-analytics-repo PATH`

reads LOCAL git clones of the public repositories in which two third-party forecasters publish
their predictions, and compares them, fixture by fixture, with the de-vigged market consensus and
with Doyen's own walk-forward model. It writes

  reports/forecast_benchmark.md             the measured comparison
  data/forecast_bench/summary.json          the same numbers, machine readable
  data/forecast_bench/shadow_benchmark.csv  one row per matched fixture (attributed, CC BY 4.0)

This is RESEARCH ONLY. Nothing here reaches the database, the model, the selection rules, the
public site or any pick. External forecasts are never presented as Doyen's. The legal and
methodological audit of each source is in docs/FORECAST_SOURCES.md.

Rules the code enforces:
  * No network call to a forecast source. Inputs are files in a clone the operator made. The only
    download is the football-data.co.uk season files the daily pipeline already uses (cached).
  * Leagues and teams are matched through the EXACT alias tables below. An unknown name, a
    kick-off more than 36 hours apart or a different final score leaves the row unmatched and
    counted. Nothing is matched by similarity.
  * A forecast is "verified pre-kick-off" only if a public git commit containing it is dated
    before the kick-off. Otherwise it is "claimed": the source says it predates the match, and
    nothing public proves it.
  * A paired difference is called better or worse only when its 95% interval excludes zero AND
    the sample has at least MIN_N fixtures. Everything else is reported as inconclusive.
"""
from __future__ import annotations

import csv
import io
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from . import config

MIN_N = 300                        # fixed before any score was computed; below it: inconclusive
KICKOFF_TOLERANCE = timedelta(hours=36)
PROMPT_HOURS = 72                  # a settled row first made public this soon after kick-off
SEASON = "2627"
HISTORY = ["2122", "2223", "2324", "2425", "2526", "2627"]
OUTCOMES = ("H", "D", "A")
VERIFIED, CLAIMED, UNVERIFIED = "verified_pre_kickoff", "claimed_pre_kickoff", "not_before_kickoff"

# status: "measured" = free, licensed and scored below; "blocked" = not used, with the reason.
SOURCES = {
    "openmodel": {
        "name": "The Open Model", "url": "https://theopenmodel.com/data/",
        "repository": "https://github.com/Hicruben/theopenmodel",
        "licence": "CC BY 4.0 (data), MIT (code)",
        "attribution": "Data: The Open Model (theopenmodel.com), CC BY 4.0.",
        "status": "measured",
        "method": "ClubElo ratings -> Dixon-Coles bivariate Poisson",
    },
    "football-analytics": {
        "name": "Football Analytics", "url": "https://footballanalytics.pro/en/data",
        "repository": "https://github.com/serayd61/football-predictions-open-data",
        "licence": "CC BY 4.0",
        "attribution": "Data: Football Analytics open data (footballanalytics.pro/data), CC BY 4.0.",
        "status": "measured",
        "method": "Dixon-Coles / Poisson attack-defence model, refitted daily (dc-1.0)",
    },
    "skorbot": {
        "name": "Skorbot", "url": "https://skorbot.live/en/api/", "repository": None,
        "licence": "none published (site terms: content belongs to Skorbot)",
        "attribution": "Skorbot (skorbot.live)",
        "status": "blocked",
        "method": "undisclosed AI model",
        "blocker": "no open licence; the archive and the change feed needed to prove a pre-kick-off "
                   "version are in the paid Pro tier; the free feed held 86 finished predictions and "
                   "was last refreshed on 2026-11-05",
    },
}

# source league slug -> football-data division. Only divisions in config.FOOTBALL_LEAGUES.
LEAGUES = {
    "openmodel": {"premier-league": "E0", "la-liga": "SP1", "bundesliga": "D1", "serie-a": "I1", "ligue-1": "F1"},
    "football-analytics": {"premier-league": "E0", "championship": "E1", "la-liga": "SP1", "bundesliga": "D1",
                           "serie-a": "I1", "ligue-1": "F1", "eredivisie": "N1", "liga-portugal": "P1"},
}

# (source, division) -> {source team name: football-data team name}. Exact strings only.
# A name equal to football-data's needs no entry. Anything else stays unmatched and is reported.
TEAM_ALIASES = {
    ("openmodel", "E0"): {"Forest": "Nott'm Forest"},
    ("openmodel", "SP1"): {"Atletico": "Ath Madrid", "Bilbao": "Ath Bilbao", "Depor": "La Coruna",
                           "Espanyol": "Espanol", "Rayo Vallecano": "Vallecano"},
    ("openmodel", "D1"): {"Bayern": "Bayern Munich", "Frankfurt": "Ein Frankfurt", "Gladbach": "M'gladbach",
                          "Koeln": "FC Koln", "Schalke": "Schalke 04", "Werder": "Werder Bremen"},
    ("football-analytics", "E0"): {
        "AFC Bournemouth": "Bournemouth", "Brighton & Hove Albion": "Brighton", "Coventry City": "Coventry",
        "Hull City": "Hull", "Ipswich Town": "Ipswich", "Leeds United": "Leeds", "Manchester City": "Man City",
        "Manchester United": "Man United", "Newcastle United": "Newcastle",
        "Nottingham Forest": "Nott'm Forest", "Tottenham Hotspur": "Tottenham"},
    ("football-analytics", "E1"): {
        "Birmingham City": "Birmingham", "Blackburn Rovers": "Blackburn", "Bolton Wanderers": "Bolton",
        "Cardiff City": "Cardiff", "Charlton Athletic": "Charlton", "Derby County": "Derby",
        "Lincoln City": "Lincoln", "Norwich City": "Norwich", "Preston North End": "Preston",
        "Queens Park Rangers": "QPR", "Stoke City": "Stoke", "Swansea City": "Swansea",
        "West Bromwich Albion": "West Brom", "West Ham United": "West Ham",
        "Wolverhampton Wanderers": "Wolves"},
    ("football-analytics", "SP1"): {
        "Athletic Club": "Ath Bilbao", "Atletico Madrid": "Ath Madrid", "Atlético Madrid": "Ath Madrid",
        "Celta Vigo": "Celta", "Deportivo A Coruña": "La Coruna", "Deportivo Alaves": "Alaves",
        "Deportivo Alavés": "Alaves", "Espanyol": "Espanol", "Málaga": "Malaga",
        "Racing Santander": "Santander", "Rayo Vallecano": "Vallecano", "Real Betis": "Betis",
        "Real Sociedad": "Sociedad"},
    ("football-analytics", "D1"): {
        "1. FC Köln": "FC Koln", "Bayer Leverkusen": "Leverkusen", "Bayern München": "Bayern Munich",
        "Borussia Dortmund": "Dortmund", "Borussia Mönchengladbach": "M'gladbach",
        "Eintracht Frankfurt": "Ein Frankfurt", "Hamburger SV": "Hamburg", "Mainz 05": "Mainz",
        "VfB Stuttgart": "Stuttgart"},
    ("football-analytics", "F1"): {"Paris Saint-Germain": "Paris SG"},
    ("football-analytics", "N1"): {
        "ADO Den Haag": "Den Haag", "FC Groningen": "Groningen", "FC Twente": "Twente", "FC Utrecht": "Utrecht",
        "Fortuna Sittard": "For Sittard", "NEC Nijmegen": "Nijmegen", "PEC Zwolle": "Zwolle",
        "SC Heerenveen": "Heerenveen"},
    ("football-analytics", "P1"): {
        "Académico Viseu": "Academico Viseu", "Braga": "Sp Braga", "Casa Pia AC": "Casa Pia",
        "Estrela da Amadora": "Estrela", "FC Porto": "Porto", "Famalicão": "Famalicao",
        "Marítimo": "Maritimo", "Sporting CP": "Sp Lisbon", "Vitoria de Guimaraes": "Guimaraes",
        "Vitória de Guimarães": "Guimaraes"},
}

FORECAST_COLUMNS = ["source", "source_fixture_id", "league_slug", "kickoff_utc", "home", "away",
                    "p_H", "p_D", "p_A", "src_hg", "src_ag", "evidence", "evidence_at", "first_public_at",
                    "n_versions", "revised_after_publication", "prompt"]


# ------------------------------------------------------------------ reading the public repositories

def _git(repo, *args) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _ts(s: str) -> datetime:
    t = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def file_versions(repo, path: str) -> list[tuple[datetime, str]]:
    """Every committed version of `path`, oldest first, with its commit time (UTC).

    The commit time is the public evidence of when the content existed. A shallow clone that cuts
    the history makes content look YOUNGER than it is, which can only weaken a pre-kick-off claim.
    """
    out = []
    for line in _git(repo, "log", "--reverse", "--format=%H %cI", "--", path).splitlines():
        h, t = line.split(" ", 1)
        try:
            out.append((_ts(t), _git(repo, "show", f"{h}:{path}")))
        except subprocess.CalledProcessError:      # the commit deleted the file
            continue
    return out


def repo_head(repo) -> dict:
    h, t = _git(repo, "log", "-1", "--format=%H %cI").strip().split(" ", 1)
    return {"commit": h, "committed_at": _ts(t).isoformat()}


def valid_probs(p) -> bool:
    try:
        p = [float(x) for x in p]
    except (TypeError, ValueError):
        return False
    return all(np.isfinite(x) and 0.0 < x < 1.0 for x in p) and abs(sum(p) - 1.0) <= 0.01


def read_openmodel(repo) -> tuple[pd.DataFrame, dict]:
    """The Open Model: one dated JSON file per day under data/snapshots/, each committed by a
    scheduled job. For a match, the forecast scored is the LAST version committed before its
    kick-off; `n_versions` counts the distinct probability triples committed before kick-off."""
    names = sorted(n for n in _git(repo, "ls-tree", "--name-only", "HEAD", "data/snapshots/").split()
                   if n.endswith(".json"))
    seen: dict = {}
    info = {"snapshot_files": len(names), "snapshot_files_revised": 0, "invalid_rows": 0}
    for name in names:
        vers = file_versions(repo, name)
        if not vers:
            continue
        if len(vers) > 1:
            info["snapshot_files_revised"] += 1
        at, text = vers[0]                         # the content as first committed
        for m in json.loads(text).get("matches") or []:
            p = m.get("p") or {}
            triple = (p.get("h"), p.get("d"), p.get("a"))
            if not valid_probs(triple) or not m.get("date"):
                info["invalid_rows"] += 1
                continue
            seen.setdefault(str(m["id"]), []).append((at, m, tuple(float(x) for x in triple)))
    rows = []
    for fid, vs in seen.items():
        vs.sort(key=lambda v: v[0])
        before = [v for v in vs if v[0] < _ts(v[1]["date"])]
        at, m, p = (before or vs)[-1]
        rows.append({"source": "openmodel", "source_fixture_id": fid, "league_slug": m.get("league"),
                     "kickoff_utc": _ts(m["date"]), "home": m.get("home"), "away": m.get("away"),
                     "p_H": p[0], "p_D": p[1], "p_A": p[2], "src_hg": np.nan, "src_ag": np.nan,
                     "evidence": VERIFIED if before else UNVERIFIED, "evidence_at": at,
                     "first_public_at": vs[0][0], "n_versions": len({v[2] for v in (before or vs)}),
                     "revised_after_publication": False, "prompt": bool(before)})
    info["last_snapshot_commit"] = max((v[0] for vs in seen.values() for v in vs), default=None)
    return pd.DataFrame(rows, columns=FORECAST_COLUMNS), info


def read_football_analytics(repo, paths=("data/all.csv", "all.csv")) -> tuple[pd.DataFrame, dict]:
    """Football Analytics: a CSV of SETTLED matches. Probabilities enter the file only after the
    final whistle, so no commit can show that a probability existed before kick-off: every row is
    `claimed`. What the history does show is when a row first became public, whether it was part
    of a bulk backfill, and whether it was edited afterwards.

    `prompt` marks a row first published within PROMPT_HOURS of its kick-off, the part of the file
    least exposed to hindsight selection."""
    vers = []
    for p in paths:
        vers += file_versions(repo, p)
    vers.sort(key=lambda v: v[0])
    first: dict = {}
    latest: dict = {}
    revised: set = set()
    removed: set = set()
    prev: set = set()
    info = {"file_versions": len(vers), "invalid_rows": 0, "mirror_started": vers[0][0] if vers else None}
    for at, text in vers:
        cur = set()
        for r in csv.DictReader(io.StringIO(text)):
            fid = r.get("fixture_id")
            if not fid:
                continue
            cur.add(fid)
            key = (r.get("p_home"), r.get("p_draw"), r.get("p_away"))
            if fid not in first:
                first[fid] = (at, key)
            elif first[fid][1] != key:
                revised.add(fid)
            latest[fid] = r
        removed |= prev - cur
        prev = cur
    rows = []
    for fid, r in latest.items():
        p = (r.get("p_home"), r.get("p_draw"), r.get("p_away"))
        if not valid_probs(p) or not r.get("kickoff_utc"):
            info["invalid_rows"] += 1
            continue
        ko, at = _ts(r["kickoff_utc"]), first[fid][0]
        rows.append({"source": "football-analytics", "source_fixture_id": fid, "league_slug": r.get("league_slug"),
                     "kickoff_utc": ko, "home": r.get("home_team"), "away": r.get("away_team"),
                     "p_H": float(first[fid][1][0]), "p_D": float(first[fid][1][1]), "p_A": float(first[fid][1][2]),
                     "src_hg": pd.to_numeric(r.get("home_score"), errors="coerce"),
                     "src_ag": pd.to_numeric(r.get("away_score"), errors="coerce"),
                     "evidence": CLAIMED if at >= ko else VERIFIED, "evidence_at": at, "first_public_at": at,
                     "n_versions": 1, "revised_after_publication": fid in revised,
                     "prompt": timedelta(0) <= at - ko <= timedelta(hours=PROMPT_HOURS)})
    info.update(rows_revised=len(revised), rows_removed=len(removed),
                rows_in_first_version=sum(1 for v in first.values() if vers and v[0] == vers[0][0]))
    return pd.DataFrame(rows, columns=FORECAST_COLUMNS), info


READERS = {"openmodel": read_openmodel, "football-analytics": read_football_analytics}


# ------------------------------------------------------------------ matching (exact, never fuzzy)

def match(fc: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Attach a Doyen fixture to each forecast row, or the reason it has none.

    `fixtures`: finished football-data matches with columns div, kickoff_utc, home, away, hg, ag.
    Returns `fc` plus div, fd_home, fd_away, fd_kickoff, hg, ag and `match_status`."""
    by_pair: dict = {}
    teams: dict = {}
    for r in fixtures.itertuples():
        by_pair.setdefault((r.div, r.home, r.away), []).append(r)
        teams.setdefault(r.div, set()).update((r.home, r.away))
    out = []
    used: set = set()
    for r in fc.itertuples():
        rec = r._asdict()
        rec.pop("Index", None)
        rec.update(div=None, fd_home=None, fd_away=None, fd_kickoff=pd.NaT, hg=np.nan, ag=np.nan)
        div = LEAGUES.get(r.source, {}).get(r.league_slug)
        if div is None:
            rec["match_status"] = "league_not_in_doyen"
            out.append(rec)
            continue
        al = TEAM_ALIASES.get((r.source, div), {})
        h, a = al.get(r.home, r.home), al.get(r.away, r.away)
        rec.update(div=div, fd_home=h, fd_away=a)
        if h not in teams.get(div, ()) or a not in teams.get(div, ()):
            rec["match_status"] = "unmapped_team"
        else:
            near = [f for f in by_pair.get((div, h, a), ())
                    if abs(f.kickoff_utc - r.kickoff_utc) <= KICKOFF_TOLERANCE]
            if not by_pair.get((div, h, a)):
                rec["match_status"] = "no_doyen_fixture"
            elif len(near) != 1:
                rec["match_status"] = "kickoff_mismatch" if not near else "ambiguous_fixture"
            else:
                f = near[0]
                rec.update(fd_kickoff=f.kickoff_utc, hg=f.hg, ag=f.ag)
                if pd.notna(r.src_hg) and (int(r.src_hg), int(r.src_ag)) != (int(f.hg), int(f.ag)):
                    rec["match_status"] = "score_conflict"
                elif (r.source, div, h, a, f.kickoff_utc) in used:
                    rec["match_status"] = "duplicate_source_row"
                else:
                    used.add((r.source, div, h, a, f.kickoff_utc))
                    rec["match_status"] = "matched"
        out.append(rec)
    return pd.DataFrame(out)


# ------------------------------------------------------------------ Doyen and the market

def doyen_frame(divs, seasons=None, season: str = SEASON) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(fixtures, predictions) for the current season, with strict chronology.

    Predictions are Doyen's walk-forward RECONSTRUCTION (backtest.walk_forward: weekly refit on
    matches before the cut only, Elo computed sequentially), with the tuned hyperparameters and the
    live DC/Elo ensemble weight. They are not stored live predictions: on 2026-11-16 the database
    held none for a finished club match. Market columns are de-vigged consensus probabilities from
    the pre-match and closing odds in the same football-data files."""
    from . import backtest
    config.load_tuned()
    tuned_p = config.DATA_DIR / "tuned.json"
    w = json.loads(tuned_p.read_text()).get("dc_elo_weight", 1.0) if tuned_p.exists() else 1.0
    fx, pr = [], []
    for div in divs:
        m, o = backtest.load_league(div, seasons or HISTORY)
        cur = m[m.season == season]
        fx.append(cur[["div", "kickoff_utc", "home", "away", "hg", "ag"]])
        df, _ = backtest.walk_forward(div, m, o, season, config.MODEL.xi, config.MODEL.ridge)
        if len(df):
            pr.append(df)
    preds = pd.concat(pr) if pr else pd.DataFrame()
    if len(preds):
        for i, s in enumerate(OUTCOMES):
            preds[f"doyen_{s}"] = w * preds[f"dc_{s}"] + (1 - w) * preds[f"elo_{s}"]
    return pd.concat(fx).reset_index(drop=True), preds


def attach(matched: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """Join Doyen and market probabilities to matched rows. Rows Doyen could not price (a team
    with no history, for example a promoted club) keep NaN and are counted, not dropped silently."""
    keep = ["div", "home", "away", "date"] + [f"{k}_{s}" for k in ("doyen", "dc", "elo", "mkt", "close")
                                               for s in OUTCOMES] + ["mkt_src"]
    p = preds[[c for c in keep if c in preds.columns]].rename(
        columns={"home": "fd_home", "away": "fd_away", "date": "fd_kickoff"})
    return matched.merge(p, how="left", on=["div", "fd_home", "fd_away", "fd_kickoff"])


# ------------------------------------------------------------------ scoring

def outcome_index(hg, ag) -> np.ndarray:
    hg, ag = np.asarray(hg, float), np.asarray(ag, float)
    return np.where(hg > ag, 0, np.where(hg == ag, 1, 2))


def _P(df, prefix) -> np.ndarray:
    return df[[f"{prefix}_{s}" for s in OUTCOMES]].to_numpy(float)


def per_match_logloss(P, y) -> np.ndarray:
    return -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1.0))


def per_match_brier(P, y) -> np.ndarray:
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1.0
    return ((P - Y) ** 2).sum(axis=1)


def cluster_ci(x, clusters, n: int = 4000, seed: int = 0) -> tuple[float, float]:
    """95% interval for the mean of x, resampling whole match days (same-day matches share news
    and conditions, so treating them as independent would make the interval too narrow)."""
    x = np.asarray(x, float)
    if len(x) == 0:
        return (float("nan"), float("nan"))
    _, inv = np.unique(np.asarray(clusters), return_inverse=True)
    sums = np.bincount(inv, weights=x)
    cnts = np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sums), size=(n, len(sums)))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def verdict(n: int, lo: float, hi: float) -> str:
    """'better' = the first forecast has the lower loss. Short samples are never a result."""
    if n < MIN_N or not (np.isfinite(lo) and np.isfinite(hi)) or lo <= 0.0 <= hi:
        return "inconclusive"
    return "better" if hi < 0 else "worse"


def calibration(P, y, bins: int = 5) -> dict:
    """Reliability over all three outcomes pooled, and the expected calibration error."""
    p = P.ravel()
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1.0
    o = Y.ravel()
    edges = np.linspace(0, 1, bins + 1)
    rows, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mk = (p >= lo) & ((p < hi) | (hi == 1.0))
        if mk.sum():
            ece += mk.sum() / len(p) * abs(p[mk].mean() - o[mk].mean())
            rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mk.sum()),
                         "predicted": round(float(p[mk].mean()), 4), "observed": round(float(o[mk].mean()), 4)})
    return {"ece": round(float(ece), 4), "bins": rows}


def pool_weight(S, M, y) -> float:
    """In-sample log-loss-optimal weight on S in the linear pool w*S + (1-w)*M. Descriptive only:
    it is fitted on the same matches it is reported for, so it flatters S."""
    r = minimize_scalar(lambda w: per_match_logloss(w * S + (1 - w) * M, y).mean(), bounds=(0, 1), method="bounded")
    return float(r.x)


def _corr(a, b) -> float | None:
    a, b = np.ravel(a), np.ravel(b)
    if a.std() < 1e-12 or b.std() < 1e-12:      # identical forecasts: correlation is undefined
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 3)


MODELS = (("source", "p"), ("market_pre", "mkt"), ("market_closing", "close"), ("doyen", "doyen"),
          ("doyen_dixon_coles", "dc"), ("doyen_elo", "elo"))
PAIRS = (("source", "market_pre"), ("source", "market_closing"), ("source", "doyen"), ("doyen", "market_pre"))


def score(df: pd.DataFrame) -> dict:
    """Paired scores on the rows where the source, both markets and Doyen all have a forecast."""
    need = [f"{pre}_{s}" for _, pre in MODELS for s in OUTCOMES]
    d = df.dropna(subset=need)
    out = {"n": int(len(d)), "min_n_for_a_verdict": MIN_N}
    if not len(d):
        return out
    y = outcome_index(d.hg, d.ag)
    days = pd.to_datetime(d.fd_kickoff, utc=True).dt.strftime("%Y-%m-%d").to_numpy()
    out["match_days"] = int(len(set(days)))
    out["kickoff_from"], out["kickoff_to"] = min(days), max(days)
    P = {name: _P(d, pre) for name, pre in MODELS}
    P["uniform"] = np.full((len(d), 3), 1 / 3)
    ll = {k: per_match_logloss(v, y) for k, v in P.items()}
    br = {k: per_match_brier(v, y) for k, v in P.items()}
    out["models"] = {k: {"logloss": round(float(ll[k].mean()), 4), "brier": round(float(br[k].mean()), 4)} for k in P}
    out["paired"] = {}
    for a, b in PAIRS:
        dl, db_ = ll[a] - ll[b], br[a] - br[b]
        lo, hi = cluster_ci(dl, days)
        blo, bhi = cluster_ci(db_, days)
        out["paired"][f"{a}_minus_{b}"] = {
            "logloss_diff": round(float(dl.mean()), 4), "logloss_ci95": [round(lo, 4), round(hi, 4)],
            "brier_diff": round(float(db_.mean()), 4), "brier_ci95": [round(blo, 4), round(bhi, 4)],
            "verdict": verdict(len(d), lo, hi)}
    out["calibration"] = {k: calibration(P[k], y) for k in ("source", "market_pre", "doyen")}
    S, M, D = P["source"], P["market_pre"], P["doyen"]
    dep = {"mean_abs_diff_source_vs_doyen": round(float(np.abs(S - D).mean()), 4),
           "mean_abs_diff_source_vs_market": round(float(np.abs(S - M).mean()), 4),
           "mean_abs_diff_doyen_vs_market": round(float(np.abs(D - M).mean()), 4)}
    if len(d) > 2:
        ha = [0, 2]                                 # home and away; the draw is the remainder
        dep["corr_probabilities_source_vs_doyen"] = _corr(S[:, ha], D[:, ha])
        dep["corr_deviation_from_market_source_vs_doyen"] = _corr((S - M)[:, ha], (D - M)[:, ha])
        dep["in_sample_pool_weight_on_source_vs_market"] = round(pool_weight(S, M, y), 3)
        dep["in_sample_pool_weight_on_doyen_vs_market"] = round(pool_weight(D, M, y), 3)
    out["dependency"] = dep
    return out


# ------------------------------------------------------------------ orchestration

def benchmark(forecasts: dict, fixtures: pd.DataFrame, preds: pd.DataFrame, infos: dict | None = None) -> tuple[dict, pd.DataFrame]:
    """forecasts: {source_id: DataFrame from a reader}. Pure: no files, no network, no database."""
    summary = {"sources": {}, "min_n_for_a_verdict": MIN_N, "kickoff_tolerance_hours": 36,
               "doyen_fixtures_finished": {k: int(v) for k, v in fixtures.groupby("div").size().items()},
               "doyen_fixtures_priced": {k: int(v) for k, v in preds.groupby("div").size().items()} if len(preds) else {}}
    tables = []
    for sid, fc in forecasts.items():
        m = attach(match(fc, fixtures), preds) if len(fc) else pd.DataFrame(columns=FORECAST_COLUMNS + ["match_status"])
        ok = m[m.match_status == "matched"] if len(m) else m
        s = {"registry": SOURCES[sid], "info": (infos or {}).get(sid, {}), "rows": int(len(fc)),
             "match_status": {k: int(v) for k, v in m.match_status.value_counts().items()} if len(m) else {},
             "evidence": {k: int(v) for k, v in fc.evidence.value_counts().items()} if len(fc) else {},
             "unmapped_teams": sorted({f"{r.div}: {t}" for r in m[m.match_status == "unmapped_team"].itertuples()
                                       for t in (r.fd_home, r.fd_away)
                                       if t not in set(fixtures[fixtures["div"] == r.div].home)
                                       | set(fixtures[fixtures["div"] == r.div].away)}) if len(m) else [],
             "matched_without_doyen_price": int(ok["doyen_H"].isna().sum()) if len(ok) else 0,
             "by_league": {}, "sets": {}}
        if len(m):
            bad = m[~m.match_status.isin(["matched", "league_not_in_doyen"])]
            s["unmatched_rows"] = [f"{r.league_slug} {r.kickoff_utc:%Y-%m-%d} {r.home} v {r.away}: {r.match_status}"
                                   for r in bad.head(25).itertuples()]
            gap = (ok.fd_kickoff - ok.kickoff_utc).dt.total_seconds().abs() / 3600 if len(ok) else pd.Series(dtype=float)
            s["matched_with_identical_kickoff"] = int((gap == 0).sum())
            s["largest_kickoff_gap_hours"] = round(float(gap.max()), 1) if len(gap) else None
        if len(fc):
            s["kickoff_from"], s["kickoff_to"] = fc.kickoff_utc.min().isoformat(), fc.kickoff_utc.max().isoformat()
            lead = (fc.kickoff_utc - fc.evidence_at).dt.total_seconds() / 3600
            s["hours_public_before_kickoff"] = {"min": round(float(lead.min()), 1), "median": round(float(lead.median()), 1),
                                                "max": round(float(lead.max()), 1)}
            s["revised_after_publication"] = int(fc.revised_after_publication.sum())
            s["rows_with_more_than_one_pre_kickoff_version"] = int((fc.n_versions > 1).sum())
        for div, g in (ok.groupby("div") if len(ok) else ()):
            in_window = fixtures[(fixtures["div"] == div) & (fixtures.kickoff_utc >= g.fd_kickoff.min())
                                 & (fixtures.kickoff_utc <= g.fd_kickoff.max())]
            s["by_league"][div] = {"matched": int(len(g)), "doyen_fixtures_in_source_window": int(len(in_window)),
                                   "doyen_fixtures_in_season": int((fixtures["div"] == div).sum()),
                                   "scored": int(g.dropna(subset=["doyen_H", "mkt_H", "close_H"]).shape[0])}
        if len(ok):
            s["sets"]["verified_pre_kickoff"] = score(ok[ok.evidence == VERIFIED])
            s["sets"]["all_matched"] = score(ok)
            s["sets"]["published_promptly"] = score(ok[ok.prompt])
            tables.append(ok)
        summary["sources"][sid] = s
    for sid, reg in SOURCES.items():
        summary["sources"].setdefault(sid, {"registry": reg, "rows": 0, "sets": {}})
    cols = ["source", "source_fixture_id", "div", "fd_kickoff", "fd_home", "fd_away", "hg", "ag", "evidence",
            "evidence_at", "first_public_at", "prompt", "p_H", "p_D", "p_A", "mkt_H", "mkt_D", "mkt_A",
            "close_H", "close_D", "close_A", "doyen_H", "doyen_D", "doyen_A"]
    table = pd.concat(tables)[cols].sort_values(["source", "fd_kickoff", "div", "fd_home"]) if tables \
        else pd.DataFrame(columns=cols)
    return summary, table


def _f(v, nd=4) -> str:
    return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def _set_block(title: str, sc: dict, note: str) -> list[str]:
    L = [f"#### {title}", "", note, ""]
    if not sc.get("n"):
        return L + ["No fixture has a forecast from the source, both markets and Doyen.", ""]
    L += [f"{sc['n']} fixtures on {sc['match_days']} match days, {sc['kickoff_from']} to {sc['kickoff_to']}. "
          f"A verdict needs at least {MIN_N} fixtures.", "",
          "| Forecast | Log loss | Brier |", "|---|---|---|"]
    names = {"source": "External source", "market_pre": "Market, pre-match", "market_closing": "Market, closing",
             "doyen": "Doyen (DC/Elo ensemble)", "doyen_dixon_coles": "Doyen Dixon-Coles only",
             "doyen_elo": "Doyen Elo only", "uniform": "Uniform one third"}
    for k, label in names.items():
        L.append(f"| {label} | {_f(sc['models'][k]['logloss'])} | {_f(sc['models'][k]['brier'])} |")
    L += ["", "| Paired difference (negative = first is better) | Log loss (95%) | Brier (95%) | Verdict |", "|---|---|---|---|"]
    for k, p in sc["paired"].items():
        a, b = k.split("_minus_")
        L.append(f"| {names[a]} minus {names[b]} | {p['logloss_diff']:+.4f} ({p['logloss_ci95'][0]:+.4f} to "
                 f"{p['logloss_ci95'][1]:+.4f}) | {p['brier_diff']:+.4f} ({p['brier_ci95'][0]:+.4f} to "
                 f"{p['brier_ci95'][1]:+.4f}) | {p['verdict']} |")
    d = sc["dependency"]
    L += ["", "| Dependency | Value |", "|---|---|",
          f"| Mean absolute probability gap, source vs Doyen | {_f(d['mean_abs_diff_source_vs_doyen'])} |",
          f"| Mean absolute probability gap, source vs market | {_f(d['mean_abs_diff_source_vs_market'])} |",
          f"| Mean absolute probability gap, Doyen vs market | {_f(d['mean_abs_diff_doyen_vs_market'])} |",
          f"| Correlation of probabilities, source vs Doyen | {_f(d.get('corr_probabilities_source_vs_doyen'), 3)} |",
          f"| Correlation of deviations from the market, source vs Doyen | {_f(d.get('corr_deviation_from_market_source_vs_doyen'), 3)} |",
          f"| In-sample best weight on the source when pooled with the market | {_f(d.get('in_sample_pool_weight_on_source_vs_market'), 3)} |",
          f"| In-sample best weight on Doyen when pooled with the market | {_f(d.get('in_sample_pool_weight_on_doyen_vs_market'), 3)} |",
          "", "| Calibration (all outcomes pooled) | ECE | " + " | ".join(b["bin"] for b in sc["calibration"]["source"]["bins"]) + " |",
          "|---|---|" + "---|" * len(sc["calibration"]["source"]["bins"])]
    for k in ("source", "market_pre", "doyen"):
        c = sc["calibration"][k]
        by = {b["bin"]: b for b in c["bins"]}
        cells = [f"{by[b['bin']]['predicted']:.2f} / {by[b['bin']]['observed']:.2f} (n={by[b['bin']]['n']})"
                 if b["bin"] in by else "none" for b in sc["calibration"]["source"]["bins"]]
        L.append(f"| {names[k]}: predicted / observed | {_f(c['ece'])} | " + " | ".join(cells) + " |")
    return L + [""]


def render(summary: dict) -> str:
    L = ["# Third-party soccer forecasts: shadow benchmark", "",
         f"Generated {summary.get('generated_at', '')} by `python -m sbi forecast-bench`. Research only: "
         "nothing in this file feeds the model, the selection rules, the public site or any pick. "
         "The audit of each source's terms and method is in `docs/FORECAST_SOURCES.md`.", "",
         "External forecasts belong to their publishers and are shown with attribution. They are not Doyen's, "
         "they are not bookmakers, and they are not counted or voted as if they were.", "",
         "## How to read it", "",
         "- **Fixtures** are finished 2026-27 matches in Doyen's football-data leagues. A source row is matched "
         "only through exact league and team alias tables, with kick-offs within 36 hours and the same final score.",
         "- **Market** is the de-vigged consensus of the football-data odds: pre-match (collected one to three days "
         "before) and closing.",
         "- **Doyen** is a walk-forward reconstruction with the live settings (weekly refit on earlier matches only). "
         "It is not a record of live predictions: the database holds none for a finished club match yet.",
         f"- **Verdict**: better or worse only when the 95% interval excludes zero and there are at least {MIN_N} "
         "fixtures. Intervals resample whole match days.",
         "- **Timing is not equal.** The sources, the market snapshots and Doyen's weekly refit see information of "
         "different ages. The closing market is the latest of all.", ""]
    for sid, s in summary["sources"].items():
        reg = s["registry"]
        L += [f"## {reg['name']}", "", f"- Source: {reg['url']}" + (f" (repository: {reg['repository']})" if reg.get("repository") else ""),
              f"- Licence: {reg['licence']}. Attribution: \"{reg['attribution']}\"", f"- Method: {reg['method']}"]
        if reg["status"] == "blocked":
            L += [f"- **Not measured.** {reg['blocker']}.", ""]
            continue
        if not s.get("rows"):
            L += ["- **Not measured in this run**: no clone of the repository was given.", ""]
            continue
        head = s["info"].get("head", {})
        ms = s["match_status"]
        L += [f"- Repository state read: commit `{head.get('commit', '')[:12]}` of {head.get('committed_at', '')}",
              f"- Rows: {s['rows']}, kick-offs {s['kickoff_from'][:10]} to {s['kickoff_to'][:10]}",
              "- Pre-kick-off evidence: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in s["evidence"].items()),
              "- Matching: " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in ms.items()),
              f"- Matched fixtures Doyen could not price (no team history): {s['matched_without_doyen_price']}",
              f"- Matched rows whose kick-off time equals football-data's exactly: {s['matched_with_identical_kickoff']} "
              f"(largest gap {s['largest_kickoff_gap_hours']} hours)",
              f"- Rows edited after first publication: {s['revised_after_publication']}"]
        lead = s["hours_public_before_kickoff"]
        if lead["median"] >= 0:
            L.append(f"- Forecast scored: the last version committed before kick-off, public a median of {lead['median']} hours "
                     f"before it (range {lead['min']} to {lead['max']}). {s['rows_with_more_than_one_pre_kickoff_version']} "
                     "rows changed between daily versions.")
        else:
            L.append(f"- First public a median of {-lead['median']:.0f} hours AFTER kick-off (range {-lead['max']:.0f} to "
                     f"{-lead['min']:.0f}); {s['info'].get('rows_in_first_version', 0)} rows arrived in the first bulk commit.")
        if s.get("unmatched_rows"):
            L.append("- In-scope rows left unmatched: " + "; ".join(s["unmatched_rows"]))
        if s["unmapped_teams"]:
            L.append("- Team names with no alias (left unmatched): " + "; ".join(s["unmapped_teams"]))
        L += ["", "| League | Matched | Doyen fixtures in the source's date range | Doyen fixtures this season | Scored |", "|---|---|---|---|---|"]
        for div, b in sorted(s["by_league"].items()):
            L.append(f"| {div} {config.FOOTBALL_LEAGUES.get(div, '')} | {b['matched']} | {b['doyen_fixtures_in_source_window']} | "
                     f"{b['doyen_fixtures_in_season']} | {b['scored']} |")
        L.append("")
        notes = {"verified_pre_kickoff": "Only forecasts in a public commit dated before kick-off. This is the only set free of hindsight risk.",
                 "all_matched": "Every matched row, whatever its evidence.",
                 "published_promptly": f"Rows first made public within {PROMPT_HOURS} hours after kick-off (or verified before it). "
                                       "Excludes bulk backfills, which could have been selected or changed with the results known."}
        titles = {"verified_pre_kickoff": "Verified before kick-off", "all_matched": "All matched rows",
                  "published_promptly": "Published promptly"}
        for k in ("verified_pre_kickoff", "all_matched", "published_promptly"):
            if k != "all_matched" and s["sets"][k].get("n") == s["sets"]["all_matched"].get("n"):
                L += [f"#### {titles[k]}", "", "Same fixtures as \"All matched rows\".", ""]
                continue
            L += _set_block(titles[k], s["sets"][k], notes[k])
    return "\n".join(L) + "\n"


def write(repos: dict, out_dir: Path | None = None, report_path: Path | None = None, now: datetime | None = None) -> dict:
    """repos: {source_id: path to a local clone}. Sources without a path are skipped and said so."""
    out_dir = out_dir or (config.DATA_DIR / "forecast_bench")
    report_path = report_path or (config.REPORTS_DIR / "forecast_benchmark.md")
    forecasts, infos = {}, {}
    for sid, path in repos.items():
        if not path:
            continue
        if SOURCES[sid]["status"] != "measured":
            raise ValueError(f"{sid} is blocked: {SOURCES[sid].get('blocker')}")
        forecasts[sid], info = READERS[sid](path)
        info["head"] = repo_head(path)
        infos[sid] = info
    divs = sorted({d for sid in forecasts for d in LEAGUES[sid].values()})
    fixtures, preds = doyen_frame(divs)
    summary, table = benchmark(forecasts, fixtures, preds, infos)
    summary["generated_at"] = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    t = table.copy()
    for c in t.columns:
        if t[c].dtype == float:
            t[c] = t[c].round(4)
    t.to_csv(out_dir / "shadow_benchmark.csv", index=False)
    report_path.write_text(render(summary))
    return summary
