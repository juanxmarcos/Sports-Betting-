"""Sackmann mirror adapter and tennis-history evaluation (issue #45). No network: recorded fixtures only."""
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from sbi import tennis_history as th
from sbi.sources import sackmann as s

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).parent / "fixtures" / "sackmann"


def _espn(i, p1, p2, winner, d, tour="atp", tournament="Brisbane International", event="1", completed=True, **kw):
    return {"id": str(i), "tour": tour, "tournament": tournament, "event_id_espn": event,
            "date": datetime.fromisoformat(d).replace(tzinfo=timezone.utc), "round": "", "p1": p1, "p2": p2,
            "completed": completed, "state": "STATUS_FINAL", "winner": winner, "walkover": False,
            "slam": False, "major": False, "surface": "hard", "sets": (2, 0), **kw}


def _espn_brisbane_2024():
    return [
        _espn(1, "Holger Rune", "Roman Safiullin", "Holger Rune", "2024-01-06T08:00:00"),
        _espn(2, "Grigor Dimitrov", "Jordan Thompson", "Grigor Dimitrov", "2024-01-06T10:00:00"),
        _espn(3, "Grigor Dimitrov", "Holger Rune", "Grigor Dimitrov", "2024-01-07T08:00:00"),
        # women's matches carried in the ESPN "atp" feed, as Doyen's data does at combined events
        _espn(4, "Aryna Sabalenka", "Victoria Azarenka", "Aryna Sabalenka", "2024-01-06T06:00:00", event="2"),
        _espn(5, "Elena Rybakina", "Linda Noskova", "Elena Rybakina", "2024-01-06T04:00:00", tour="wta", event="2"),
        _espn(6, "Elena Rybakina", "Aryna Sabalenka", "Elena Rybakina", "2024-01-07T06:00:00", tour="wta", event="2"),
    ]


# ---------------------------------------------------------------- parsing

def test_parse_fixture_rows_and_flags():
    ms, stats = s.load(FIX)
    assert stats == {"files": 3, "dropped": 0}
    assert len(ms) == 11
    wo = [m for m in ms if m.walkover]
    ret = [m for m in ms if m.retired]
    assert [(m.winner_name, m.loser_name) for m in wo] == [("Tallon Griekspoor", "Marin Cilic")]
    assert [(m.winner_name, m.loser_name) for m in ret] == [("Sebastian Korda", "Yoshihito Nishioka"),
                                                            ("Frances Tiafoe", "Lorenzo Musetti")]
    f = next(m for m in ms if m.tour == "atp" and m.tourney_id == "2024-0339" and m.round == "F")
    assert (f.winner_name, f.loser_name, f.surface, f.tourney_date, f.best_of) == \
        ("Grigor Dimitrov", "Holger Rune", "hard", date(2024, 1, 1), 3)
    assert f.source_id == f"atp:2024-0339:{f.match_num}"
    assert ms == sorted(ms, key=lambda m: (m.tourney_date, m.tourney_id, m.match_num))


def test_parse_drops_malformed_rows_and_maps_carpet():
    hdr = (FIX / "atp" / "atp_matches_2024.csv").read_text().splitlines()[0]
    good = (FIX / "atp" / "atp_matches_2024.csv").read_text().splitlines()[1]
    carpet = good.replace(",Hard,", ",Carpet,", 1)
    no_date = good.replace(",20240101,", ",,", 1)
    ms, dropped = s.parse_csv("\n".join([hdr, carpet, no_date]), "atp")
    assert dropped == 1 and len(ms) == 1 and ms[0].surface == "hard"


def test_name_keys():
    assert s.norm_name("Stan Wawrinka") == s.norm_name("  stan   WAWRINKA ")
    assert s.norm_name("Félix Auger-Aliassime") == "felix auger aliassime"
    assert s.norm_name("Jo-Wilfried Tsonga") == s.norm_name("Jo Wilfried Tsonga")
    assert s.short_key("Felix Auger Aliassime") == "f aliassime"


# ---------------------------------------------------------------- player map and links

def test_player_map_exact_initial_and_ambiguous():
    ms, _ = s.load(FIX)
    espn = {"atp": {"Grigor Dimitrov", "Holger Rune", "R. Safiullin", "Jordan Thompson",
                    "Aryna Sabalenka", "Victoria Azarenka"},
            "wta": {"Elena Rybakina", "Linda Noskova"}}
    pm, names = s.build_player_map(ms, espn)
    by_name = {names[k]: v for k, v in pm.by_id.items()}
    assert by_name["Grigor Dimitrov"] == ("Grigor Dimitrov", "exact")
    assert by_name["Roman Safiullin"] == ("R. Safiullin", "initial+surname")
    # women found although Doyen's ESPN data labels them "atp"
    assert by_name["Aryna Sabalenka"][0] == "Aryna Sabalenka"
    assert "Novak Djokovic" not in by_name                       # never seen in ESPN: unmatched, not guessed
    assert any(n == "Novak Djokovic" for n in pm.unmatched.values())
    assert pm.key("atp", "104925") == "sackmann:atp:104925"


def test_player_map_leaves_ambiguous_initials_unmatched():
    ms, _ = s.load(FIX)
    pm, names = s.build_player_map(ms, {"atp": {"H. Rune", "Hugo Rune"}})
    assert not any(names[k] == "Holger Rune" for k in pm.by_id)


def test_player_map_drops_same_name_on_both_tours():
    hdr = (FIX / "atp" / "atp_matches_2024.csv").read_text().splitlines()
    w = (FIX / "wta" / "wta_matches_2024.csv").read_text().splitlines()
    ms_a, _ = s.parse_csv("\n".join(hdr[:2]), "atp")
    ms_w, _ = s.parse_csv("\n".join([w[0], w[1].replace("Elena Rybakina", "Grigor Dimitrov")]), "wta")
    pm, names = s.build_player_map(ms_a + ms_w, {"atp": {"Grigor Dimitrov", "Holger Rune", "Aryna Sabalenka"}})
    assert pm.espn("atp", ms_a[0].winner_id) is None and pm.espn("wta", ms_w[0].winner_id) is None


def test_links_and_disagreements():
    ms, _ = s.load(FIX)
    espn = _espn_brisbane_2024()
    espn[2] = dict(espn[2], winner="Holger Rune")                 # ESPN says Rune won the final
    names = {"atp": {p for e in espn for p in (e["p1"], e["p2"])}}
    pm, _ = s.build_player_map(ms, names)
    L = s.link_matches(ms, espn, pm)
    assert len(L["links"]) == 6
    assert [(d["winner_sackmann"], d["winner_espn"]) for d in L["disagreements"]] == [("Grigor Dimitrov", "Holger Rune")]


def test_link_rejects_pair_from_a_nearby_tournament():
    ms, _ = s.load(FIX)
    espn = _espn_brisbane_2024()
    # the final is missing in ESPN's Brisbane draw, but the pair met again ten days later elsewhere
    espn[2] = _espn(30, "Holger Rune", "Grigor Dimitrov", "Holger Rune", "2024-01-11T08:00:00",
                    tournament="Somewhere Else", event="9")
    pm, _ = s.build_player_map(ms, {"atp": {p for e in espn for p in (e["p1"], e["p2"])}})
    L = s.link_matches(ms, espn, pm)
    assert L["rejected_other_tournament"] == 1 and L["disagreements"] == []
    assert all(r["espn_event"] in ("1", "2") for r in L["links"])


def test_tournament_map_majority():
    links = [{"tour": "atp", "sackmann_tournament": "Brisbane", "espn_tournament": "Brisbane International"}] * 3 + \
            [{"tour": "atp", "sackmann_tournament": "Brisbane", "espn_tournament": "Other"}]
    assert s.tournament_map(links) == [{"tour": "atp", "sackmann_tournament": "Brisbane",
                                        "espn_tournament": "Brisbane International", "linked_matches": 3, "share": 0.75}]


# ---------------------------------------------------------------- download and checksums (no network)

def _fake_manifest(tmp_path):
    files = {}
    for p in sorted(FIX.glob("*/*.csv")):
        rel = p.relative_to(FIX).as_posix()
        files[rel] = {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size, "url": s.url(rel)}
    return s.build_manifest(files, "2026-11-17T00:00:00+00:00")


def test_download_verifies_checksums_without_network(tmp_path, monkeypatch):
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("network used"))
    man = _fake_manifest(tmp_path)
    seen = []

    def get(u):
        seen.append(u)
        rel = u.split(f"/resolve/{s.REVISION}/", 1)[1]
        return (FIX / rel).read_bytes()
    got = s.download(tmp_path / "m", manifest=man, get=get)
    assert set(got) == set(man["files"]) and all(f"/resolve/{s.REVISION}/" in u for u in seen)
    assert s.verify(tmp_path / "m", man)["ok"]
    (tmp_path / "m" / "atp" / "atp_matches_2024.csv").write_text("tampered")
    v = s.verify(tmp_path / "m", man)
    assert not v["ok"] and v["mismatch"] == ["atp/atp_matches_2024.csv"]


def test_download_refuses_changed_file_and_writes_nothing(tmp_path):
    man = _fake_manifest(tmp_path)
    with pytest.raises(ValueError, match="checksum mismatch"):
        s.download(tmp_path / "m", manifest=man, get=lambda u: b"different bytes")
    assert not any((tmp_path / "m").rglob("*.csv"))


def test_committed_manifest_records_provenance():
    man = json.loads((ROOT / "data" / "tennis_sackmann" / "manifest.json").read_text())
    assert man["mirror"] == "https://huggingface.co/datasets/Aneeshers/tennis-sackmann-archive"
    assert re.fullmatch(r"[0-9a-f]{40}", man["revision"]) and man["revision"] == s.REVISION
    assert man["licence"] == "CC BY-NC-SA 4.0"
    assert "Jeff Sackmann" in man["attribution"] and "Tennis Abstract" in man["attribution"]
    assert man["label"] == ("unofficial mirror; original repositories withdrawn by the author (404 since about "
                            "2026-11-02); integrity not verified against the original")
    assert set(s.data_files()) <= set(man["files"])
    assert all(re.fullmatch(r"[0-9a-f]{64}", v["sha256"]) for v in man["files"].values())
    assert man["downloaded_at"].startswith("2026-11-17")


def test_raw_mirror_files_are_not_committed():
    assert "data/local/" in (ROOT / ".gitignore").read_text().split()


def test_data_sources_doc_has_provenance_and_caveat():
    doc = (ROOT / "docs" / "DATA_SOURCES.md").read_text()
    assert "Aneeshers/tennis-sackmann-archive" in doc and s.REVISION in doc
    assert "CC BY-NC-SA 4.0" in doc and "Jeff Sackmann" in doc
    assert "unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); " \
           "integrity not verified against the original" in doc
    man = json.loads((ROOT / "data" / "tennis_sackmann" / "manifest.json").read_text())
    for p in s.data_files():
        assert man["files"][p]["sha256"] in doc


# ---------------------------------------------------------------- walk-forward and decision

def _synthetic_history():
    """Two players; A plays B repeatedly. Mirror pre-2024 says A is far stronger."""
    ms, _ = s.load(FIX)
    tmpl = next(m for m in ms if m.tourney_id == "2024-0339")
    pre = [type(tmpl)(**{**tmpl.__dict__, "tourney_id": f"2015-{i}", "tourney_date": date(2015, 1, 1) + timedelta(days=7 * i),
                         "match_num": i, "winner_id": "1", "winner_name": "Alpha Player", "loser_id": "2",
                         "loser_name": "Beta Player"}) for i in range(40)]
    espn = []
    for i in range(60):
        d = (datetime(2024, 1, 1) + timedelta(days=5 * i)).isoformat()
        espn.append(_espn(100 + i, "Alpha Player", "Beta Player", "Alpha Player" if i % 4 else "Beta Player", d))
    return pre, espn


def test_walk_forward_uses_only_pre_2024_mirror_and_same_rows():
    pre, espn = _synthetic_history()
    pm, _ = s.build_player_map(pre, {"atp": {"Alpha Player", "Beta Player"}})
    wf = th.walk_forward(pre, espn, pm, test_from="2024-06-01")
    r = wf["results"]["all_test_matches"]
    assert wf["warm_start_matches"] == 40 and r["n"] == sum(1 for e in espn if e["date"] >= datetime(2024, 6, 1, tzinfo=timezone.utc))
    # mirror rows from 2024 on must not reach B (ESPN already covers that period): adding one changes nothing
    late = type(pre[0])(**{**pre[0].__dict__, "tourney_date": date(2024, 3, 1), "winner_id": "2", "winner_name": "Beta Player",
                           "loser_id": "1", "loser_name": "Alpha Player"})
    wf2 = th.walk_forward(pre + [late], espn, pm, test_from="2024-06-01")
    assert wf2["results"] == wf["results"] and wf2["warm_start_matches"] == 40


def test_decision_requires_gain_and_market_sample():
    wf = {"results": {"main_A_eligible": {"n": 100, "logloss": {"B_minus_A_ci95": [-0.01, -0.001]}}}}
    small = {"n": 7, "market": {"logloss": 0.5}, "B_with_mirror": {"logloss": 0.4}}
    d = th.decide(wf, small)
    assert d["gain_vs_live_model"] and not d["market_criterion_met"] and not d["adopt_in_live_model"]
    big = {"n": 250, "market": {"logloss": 0.5}, "B_with_mirror": {"logloss": 0.49}}
    assert th.decide(wf, big)["adopt_in_live_model"]
    wf_ns = {"results": {"main_A_eligible": {"n": 100, "logloss": {"B_minus_A_ci95": [-0.01, 0.0]}}}}
    assert not th.decide(wf_ns, big)["adopt_in_live_model"]
    assert th.CRITERIA == {"max_disagreement_rate": 0.01, "logloss_gain_ci_upper_below": 0.0, "min_market_events": 200}


def _db():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY, sport TEXT, league TEXT, kickoff_utc TEXT, home TEXT, away TEXT, "
                "status TEXT, home_score INTEGER, away_score INTEGER)")
    con.execute("CREATE TABLE odds (event_id TEXT, bookmaker TEXT, market TEXT, selection TEXT, price REAL, retrieved_at TEXT)")
    return con


def test_market_check_devigs_median_of_books_before_start():
    con = _db()
    con.execute("INSERT INTO events VALUES ('tennis:ATP:20240107:3','tennis','TENNIS:ATP','2024-01-07T08:00:00+00:00',"
                "'Grigor Dimitrov','Holger Rune','finished',2,0)")
    for b, h, a in (("x", 1.5, 2.5), ("y", 1.6, 2.3), ("z", 1.55, 2.4)):
        con.execute("INSERT INTO odds VALUES ('tennis:ATP:20240107:3',?, 'ML','home',?, '2024-01-07T07:00:00+00:00')", (b, h))
        con.execute("INSERT INTO odds VALUES ('tennis:ATP:20240107:3',?, 'ML','away',?, '2024-01-07T07:00:00+00:00')", (b, a))
    con.execute("INSERT INTO odds VALUES ('tennis:ATP:20240107:3','late','ML','home',9.0,'2024-01-07T09:00:00+00:00')")
    mk = th.market_check(con, {"3": (0.6, 0.7)})
    assert mk["n"] == 1 and mk["median_bookmakers"] == 3
    assert mk["A_espn_only"]["brier"] == pytest.approx(0.16) and mk["B_with_mirror"]["brier"] == pytest.approx(0.09)


def test_run_end_to_end_writes_outputs_and_leaves_db_untouched(tmp_path):
    con = _db()
    con.execute("INSERT INTO events VALUES ('tennis:ATP:20261117:9','tennis','TENNIS:ATP','2026-11-17T08:00:00+00:00',"
                "'Grigor Dimitrov','Someone New','scheduled',NULL,NULL)")
    before = list(con.iterdump())
    man = _fake_manifest(tmp_path)
    out = th.run(con, _espn_brisbane_2024(), mirror_dir=FIX, manifest=man, out_dir=tmp_path / "o",
                 report=tmp_path / "r.md")
    assert list(con.iterdump()) == before
    assert "stopped" not in out and out["coverage"]["links"]["linked"] == 6
    assert out["coverage"]["espn_tour_labels"]["completed_matches_labelled_atp_between_two_wta_players"] == 1
    assert out["coverage"]["players"]["doyen_db_event_players_with_mirror_id"] == {"atp": 1}
    assert out["decision"]["adopt_in_live_model"] is False
    for f in ("coverage.json", "player_map.csv", "tournament_map.csv", "match_links.csv"):
        assert (tmp_path / "o" / f).exists()
    md = (tmp_path / "r.md").read_text()
    assert "unofficial mirror; original repositories withdrawn" in md and "Live model changed: no" in md


def test_run_stops_when_mirror_conflicts_with_known_results(tmp_path):
    espn = _espn_brisbane_2024()
    espn[2] = dict(espn[2], winner="Holger Rune")
    out = th.run(_db(), espn, mirror_dir=FIX, manifest=_fake_manifest(tmp_path), out_dir=tmp_path / "o",
                 report=tmp_path / "r.md")
    assert "stopped" in out and "walk_forward" not in out
    assert "STOPPED" in (tmp_path / "r.md").read_text()


def test_run_refuses_files_that_do_not_match_manifest(tmp_path):
    man = _fake_manifest(tmp_path)
    man["files"]["atp/atp_matches_2024.csv"]["sha256"] = "0" * 64
    with pytest.raises(SystemExit, match="do not match"):
        th.run(_db(), [], mirror_dir=FIX, manifest=man, out_dir=tmp_path / "o", report=tmp_path / "r.md")


def test_live_model_does_not_use_the_mirror():
    for f in ("tennis.py", "pipeline.py", "engine.py", "site.py"):
        assert "sackmann" not in (ROOT / "sbi" / f).read_text().lower()
    wf = (ROOT / ".github" / "workflows")
    if wf.exists():
        assert not any("tennis-history" in p.read_text() for p in wf.glob("*.yml"))
