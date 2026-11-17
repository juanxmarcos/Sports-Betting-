"""Third-party forecast shadow benchmark: tiny local git repositories and hand-made frames only.
No network, no database, no walk-forward fit."""
import json
import os
import subprocess
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from sbi import forecast_bench as fb


def T(s):
    return pd.Timestamp(s, tz="UTC")


def _commit(repo, when, files):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "x"], check=True, env=env)


def _repo(tmp_path, name):
    r = tmp_path / name
    r.mkdir()
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    return r


def _snap(*matches):
    return json.dumps({"matches": [{"id": i, "league": lg, "date": ko, "home": h, "away": a,
                                    "p": {"h": p[0], "d": p[1], "a": p[2]}} for i, lg, ko, h, a, p in matches]})


FA_HEAD = ("fixture_id,kickoff_utc,league,league_slug,country,home_team,away_team,home_score,away_score,result,"
           "p_home,p_draw,p_away,lambda_home,lambda_away,pick,pick_correct,model_version,match_url\n")


def _fa(fid, ko, slug, h, a, hs, as_, p):
    return f"{fid},{ko},L,{slug},C,{h},{a},{hs},{as_},1,{p[0]},{p[1]},{p[2]},1.5,1.0,1,1,dc-1.0,u\n"


@pytest.fixture
def fixtures():
    return pd.DataFrame([
        ("E0", T("2026-08-22 14:00"), "Arsenal", "Nott'm Forest", 2, 0),
        ("E0", T("2026-08-23 15:30"), "Man United", "Chelsea", 1, 1),
        ("E0", T("2026-08-29 14:00"), "Chelsea", "Arsenal", 0, 1),
        ("SP1", T("2026-08-22 19:00"), "Ath Madrid", "Malaga", 3, 0),
    ], columns=["div", "kickoff_utc", "home", "away", "hg", "ag"])


# ------------------------------------------------------------------ evidence from git history

def test_openmodel_scores_the_last_version_committed_before_kickoff(tmp_path):
    r = _repo(tmp_path, "tom")
    m = ("premier-league", "2026-08-22T14:00:00+00:00", "Arsenal", "Forest")
    _commit(r, "2026-08-20T08:00:00+00:00", {"data/snapshots/2026-08-20.json": _snap((1, *m, (0.60, 0.25, 0.15)))})
    _commit(r, "2026-08-22T08:00:00+00:00", {"data/snapshots/2026-08-22.json": _snap((1, *m, (0.62, 0.24, 0.14)))})
    # a version written after the match started must never be the one that is scored
    _commit(r, "2026-08-23T08:00:00+00:00", {"data/snapshots/2026-08-23.json": _snap((1, *m, (0.99, 0.005, 0.005)))})
    fc, info = fb.read_openmodel(r)
    row = fc.iloc[0]
    assert len(fc) == 1 and (row.p_H, row.p_D, row.p_A) == (0.62, 0.24, 0.14)
    assert row.evidence == fb.VERIFIED and row.evidence_at == T("2026-08-22 08:00")
    assert row.n_versions == 2 and info["snapshot_files"] == 3


def test_openmodel_forecast_first_committed_after_kickoff_is_not_verified(tmp_path):
    r = _repo(tmp_path, "tom")
    _commit(r, "2026-08-22T18:00:00+00:00", {"data/snapshots/2026-08-22.json": _snap(
        (1, "premier-league", "2026-08-22T14:00:00+00:00", "Arsenal", "Forest", (0.6, 0.25, 0.15)),
        (2, "premier-league", "2026-08-23T15:30:00+00:00", "Man United", "Chelsea", (0.5, 0.5, 0.5)),   # not a distribution
    )})
    fc, info = fb.read_openmodel(r)
    assert list(fc.evidence) == [fb.UNVERIFIED] and info["invalid_rows"] == 1


def test_openmodel_uses_first_committed_content_and_reports_edited_files(tmp_path):
    r = _repo(tmp_path, "tom")
    m = ("premier-league", "2026-08-22T14:00:00+00:00", "Arsenal", "Forest")
    _commit(r, "2026-08-20T08:00:00+00:00", {"data/snapshots/2026-08-20.json": _snap((1, *m, (0.60, 0.25, 0.15)))})
    _commit(r, "2026-08-25T08:00:00+00:00", {"data/snapshots/2026-08-20.json": _snap((1, *m, (0.90, 0.05, 0.05)))})
    fc, info = fb.read_openmodel(r)
    assert fc.iloc[0].p_H == 0.60 and info["snapshot_files_revised"] == 1


def test_football_analytics_rows_are_claims_and_backfills_and_edits_are_flagged(tmp_path):
    r = _repo(tmp_path, "fa")
    old = _fa(1, "2026-08-22T14:00:00.000Z", "premier-league", "Arsenal", "Nottingham Forest", 2, 0, (0.6, 0.25, 0.15))
    _commit(r, "2026-10-17T12:00:00+00:00", {"data/all.csv": FA_HEAD + old})                      # bulk backfill
    new = _fa(2, "2026-10-18T14:00:00.000Z", "premier-league", "Chelsea", "Arsenal", 0, 1, (0.3, 0.3, 0.4))
    edited = old.replace("0.6,0.25,0.15", "0.7,0.2,0.1")
    _commit(r, "2026-10-19T09:00:00+00:00", {"data/all.csv": FA_HEAD + edited + new})
    fc, info = fb.read_football_analytics(r)
    by = fc.set_index("source_fixture_id")
    assert set(fc.evidence) == {fb.CLAIMED}                 # settled-only file: nothing is provably pre-kick-off
    assert not by.loc["1"].prompt and by.loc["2"].prompt    # 8 weeks late vs 19 hours after kick-off
    assert by.loc["1"].revised_after_publication and by.loc["1"].p_H == 0.6     # first published value is kept
    assert info["rows_revised"] == 1 and info["rows_in_first_version"] == 1 and info["file_versions"] == 2


# ------------------------------------------------------------------ matching

def _fc(source, slug, ko, home, away, score=(np.nan, np.nan), p=(0.5, 0.3, 0.2), fid="1"):
    return dict(source=source, source_fixture_id=fid, league_slug=slug, kickoff_utc=T(ko), home=home, away=away,
                p_H=p[0], p_D=p[1], p_A=p[2], src_hg=score[0], src_ag=score[1], evidence=fb.VERIFIED,
                evidence_at=T(ko) - pd.Timedelta(hours=5), first_public_at=T(ko) - pd.Timedelta(hours=5),
                n_versions=1, revised_after_publication=False, prompt=True)


def test_match_uses_exact_aliases_only(fixtures):
    fc = pd.DataFrame([
        _fc("football-analytics", "premier-league", "2026-08-22 14:00", "Arsenal", "Nottingham Forest", (2, 0)),
        _fc("football-analytics", "premier-league", "2026-08-23 15:30", "Man Utd", "Chelsea", (1, 1)),      # not in the table
        _fc("football-analytics", "premier-league", "2026-08-23 15:30", "Manchester Utd.", "Chelsea", (1, 1)),
        _fc("football-analytics", "la-liga", "2026-08-22 19:00", "Atlético Madrid", "Málaga", (3, 0)),
        _fc("football-analytics", "super-lig", "2026-08-22 19:00", "Galatasaray", "Fenerbahçe", (1, 0)),
        _fc("openmodel", "premier-league", "2026-08-22 14:00", "Arsenal", "Forest"),
        _fc("openmodel", "premier-league", "2026-08-22 14:00", "Arsenal", "Nottingham Forest"),   # the other source's alias
    ])
    m = fb.match(fc, fixtures)
    assert list(m.match_status) == ["matched", "unmapped_team", "unmapped_team", "matched", "league_not_in_doyen",
                                    "matched", "unmapped_team"]
    assert m.iloc[3].fd_home == "Ath Madrid" and m.iloc[3].fd_away == "Malaga"


def test_match_refuses_uncertain_fixtures(fixtures):
    fc = pd.DataFrame([
        _fc("football-analytics", "premier-league", "2026-08-25 14:00", "Arsenal", "Nottingham Forest", (2, 0)),  # 3 days off
        _fc("football-analytics", "premier-league", "2026-08-23 15:30", "Manchester United", "Chelsea", (2, 1)),  # other score
        _fc("football-analytics", "premier-league", "2026-08-29 14:00", "Arsenal", "Chelsea", (1, 0)),            # reversed
        _fc("football-analytics", "premier-league", "2026-08-29 14:00", "Chelsea", "Arsenal", (0, 1), fid="7"),
        _fc("football-analytics", "premier-league", "2026-08-29 14:00", "Chelsea", "Arsenal", (0, 1), fid="8"),   # same match twice
        _fc("football-analytics", "premier-league", "2026-08-23 13:30", "Manchester United", "Chelsea", (1, 1)),  # 2h off: fine
    ])
    assert list(fb.match(fc, fixtures).match_status) == [
        "kickoff_mismatch", "score_conflict", "no_doyen_fixture", "matched", "duplicate_source_row", "matched"]


def test_alias_tables_only_cover_doyen_leagues_and_blocked_sources_have_no_reader():
    from sbi import config
    for (source, div), al in fb.TEAM_ALIASES.items():
        assert div in config.FOOTBALL_LEAGUES and div in fb.LEAGUES[source].values()
        assert all(k != v for k, v in al.items())
    assert fb.SOURCES["skorbot"]["status"] == "blocked" and "skorbot" not in fb.READERS
    with pytest.raises(ValueError, match="blocked"):
        fb.write({"skorbot": "/nowhere"})
    for s in fb.SOURCES.values():       # every source carries its licence and attribution line
        assert s["licence"] and s["attribution"] and s["url"].startswith("https://")


# ------------------------------------------------------------------ scoring

def _scored(n, seed=0, source_noise=0.0):
    """n fixtures with a known truth; the market is the truth, the source is the truth plus noise."""
    rng = np.random.default_rng(seed)
    truth = rng.dirichlet((4, 2.5, 3), n)
    y = np.array([rng.choice(3, p=p) for p in truth])
    src = truth + rng.normal(0, source_noise, truth.shape)
    src = np.clip(src, 0.02, None)
    src /= src.sum(axis=1, keepdims=True)
    d = pd.DataFrame({"fd_kickoff": [T("2026-08-01") + pd.Timedelta(days=int(i // 8)) for i in range(n)],
                      "hg": np.where(y == 0, 1, 0), "ag": np.where(y == 2, 1, 0)})
    for pre, P in (("p", src), ("mkt", truth), ("close", truth), ("doyen", truth), ("dc", truth), ("elo", truth)):
        for i, s in enumerate("HDA"):
            d[f"{pre}_{s}"] = P[:, i]
    return d


def test_scores_match_hand_calculation():
    d = pd.DataFrame({"fd_kickoff": [T("2026-08-01"), T("2026-08-02")], "hg": [1, 0], "ag": [0, 0]})
    for pre, P in (("p", [(0.5, 0.3, 0.2), (0.2, 0.5, 0.3)]), ("mkt", [(0.4, 0.3, 0.3), (0.3, 0.4, 0.3)])):
        for i, s in enumerate("HDA"):
            d[f"{pre}_{s}"] = [P[0][i], P[1][i]]
    for pre in ("close", "doyen", "dc", "elo"):
        for s in "HDA":
            d[f"{pre}_{s}"] = d[f"mkt_{s}"]
    s = fb.score(d)
    assert s["n"] == 2 and s["match_days"] == 2
    assert s["models"]["source"]["logloss"] == pytest.approx(-np.log(0.5), abs=1e-4)          # home win, then draw
    assert s["models"]["market_pre"]["logloss"] == pytest.approx(-np.log(0.4), abs=1e-4)
    assert s["models"]["source"]["brier"] == pytest.approx((0.38 + 0.38) / 2, abs=1e-4)
    assert s["models"]["uniform"]["logloss"] == pytest.approx(np.log(3), abs=1e-4)
    assert s["paired"]["source_minus_market_pre"]["logloss_diff"] == pytest.approx(np.log(0.4) - np.log(0.5), abs=1e-4)


def test_short_samples_are_inconclusive_however_large_the_gap():
    s = fb.score(_scored(120, source_noise=0.25))
    p = s["paired"]["source_minus_market_pre"]
    assert p["logloss_ci95"][0] > 0 and p["verdict"] == "inconclusive"     # clearly worse, yet below MIN_N
    assert fb.verdict(fb.MIN_N - 1, 0.01, 0.02) == "inconclusive"
    assert fb.verdict(fb.MIN_N, -0.01, 0.02) == "inconclusive"
    assert fb.verdict(fb.MIN_N, 0.01, 0.02) == "worse" and fb.verdict(fb.MIN_N, -0.02, -0.01) == "better"


def test_large_sample_detects_a_noisy_source_and_gives_it_no_pool_weight():
    s = fb.score(_scored(1200, source_noise=0.15))
    assert s["paired"]["source_minus_market_pre"]["verdict"] == "worse"
    assert s["paired"]["doyen_minus_market_pre"]["verdict"] == "inconclusive"      # identical forecasts
    assert s["dependency"]["in_sample_pool_weight_on_source_vs_market"] < 0.2
    assert s["calibration"]["market_pre"]["ece"] < 0.03


def test_rows_missing_any_forecast_are_left_out_of_the_paired_scores():
    d = _scored(40)
    d.loc[:9, "doyen_H"] = np.nan
    assert fb.score(d)["n"] == 30
    assert fb.score(d.iloc[0:0]) == {"n": 0, "min_n_for_a_verdict": fb.MIN_N}


def test_cluster_interval_is_wider_than_treating_matches_as_independent():
    rng = np.random.default_rng(1)
    day_effect = np.repeat(rng.normal(0, 1, 30), 10)
    x = day_effect + rng.normal(0, 0.2, 300)
    lo_c, hi_c = fb.cluster_ci(x, np.repeat(np.arange(30), 10))
    lo_i, hi_i = fb.cluster_ci(x, np.arange(300))
    assert hi_c - lo_c > 2 * (hi_i - lo_i)


def test_valid_probs_rejects_bad_triples():
    assert fb.valid_probs((0.5, 0.3, 0.2)) and fb.valid_probs(("0.4527", "0.1736", "0.3737"))
    for bad in ((0.5, 0.5, 0.5), (1.0, 0.0, 0.0), (0.6, 0.5, -0.1), (None, 0.5, 0.5), ("x", 0.5, 0.5), (0.5, 0.3, float("nan"))):
        assert not fb.valid_probs(bad)


# ------------------------------------------------------------------ end to end, research-only outputs

def test_benchmark_end_to_end_without_network_or_database(tmp_path, fixtures, monkeypatch):
    import requests
    import sqlite3

    def boom(*a, **k):
        raise AssertionError("the benchmark must not touch the network or the database")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(sqlite3, "connect", boom)

    tom, fa = _repo(tmp_path, "tom"), _repo(tmp_path, "fa")
    _commit(tom, "2026-08-21T08:00:00+00:00", {"data/snapshots/2026-08-21.json": _snap(
        (1, "premier-league", "2026-08-22T14:00:00+00:00", "Arsenal", "Forest", (0.60, 0.25, 0.15)),
        (2, "premier-league", "2026-08-23T15:30:00+00:00", "Man United", "Chelsea", (0.40, 0.30, 0.30)))})
    _commit(fa, "2026-08-23T09:00:00+00:00", {"data/all.csv": FA_HEAD + _fa(
        9, "2026-08-22T14:00:00.000Z", "premier-league", "Arsenal", "Nottingham Forest", 2, 0, (0.55, 0.25, 0.20))})
    preds = fixtures.rename(columns={"kickoff_utc": "date"}).iloc[:1].copy()      # Doyen priced one fixture only
    for pre in ("doyen", "dc", "elo", "mkt", "close"):
        preds[f"{pre}_H"], preds[f"{pre}_D"], preds[f"{pre}_A"] = 0.5, 0.3, 0.2
    preds["mkt_src"] = "Avg"
    monkeypatch.setattr(fb, "doyen_frame", lambda divs, **k: (fixtures, preds))

    out, rep = tmp_path / "out", tmp_path / "forecast_benchmark.md"
    s = fb.write({"openmodel": tom, "football-analytics": fa, "skorbot": None}, out_dir=out, report_path=rep,
                 now=datetime(2026, 11, 16, tzinfo=timezone.utc))
    om = s["sources"]["openmodel"]
    assert om["match_status"] == {"matched": 2} and om["matched_without_doyen_price"] == 1
    assert om["sets"]["verified_pre_kickoff"]["n"] == 1 and om["by_league"]["E0"]["scored"] == 1
    fa_s = s["sources"]["football-analytics"]
    assert fa_s["evidence"] == {fb.CLAIMED: 1} and fa_s["sets"]["verified_pre_kickoff"]["n"] == 0
    assert fa_s["sets"]["published_promptly"]["n"] == 1
    assert s["sources"]["skorbot"]["rows"] == 0

    table = pd.read_csv(out / "shadow_benchmark.csv")
    assert len(table) == 3 and set(table.source) == {"openmodel", "football-analytics"}
    text = rep.read_text()
    for needle in ("The Open Model (theopenmodel.com), CC BY 4.0", "footballanalytics.pro/data), CC BY 4.0",
                   "Not measured", "inconclusive", "Research only"):
        assert needle in text
    assert json.loads((out / "summary.json").read_text())["min_n_for_a_verdict"] == fb.MIN_N


def test_committed_benchmark_stays_out_of_the_public_site_and_the_model():
    """External forecasts are a shadow table: not in the site data, not imported by the pipeline."""
    from pathlib import Path
    root = Path(fb.__file__).resolve().parent.parent
    for p in (root / "docs" / "data").glob("*.json"):
        t = p.read_text()
        assert "theopenmodel" not in t and "footballanalytics" not in t and "skorbot" not in t
    for name in ("pipeline.py", "engine.py", "ev.py", "site.py", "report.py", "settle.py"):
        assert "forecast_bench" not in (root / "sbi" / name).read_text()
