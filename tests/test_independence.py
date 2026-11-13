"""Bookmaker independence: rule v1 (legacy) is unchanged, rule v2 (verified) only ever tightens it."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from sbi import config, db, independence
from sbi import ev as evm
from sbi.engine import UNVERIFIED_REASON, passes, passes_under, price_generic
from sbi.markets import Outcome
from sbi.sources import books
from sbi.sources.books import GROUPS, REGISTRY, group_of, normalize_book, verified_group

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
HA = ["home", "away"]
FLAT = lambda m, s, ln: Outcome(pw=0.5, pl=0.5)  # noqa: E731  (blend weight 0: the model share is unused)


def _price(book, policy, market="ML"):
    return price_generic(FLAT, {(market, None): book}, {}, 0.05, policy=policy)


# ---------- registry ----------
def test_legacy_map_is_frozen():
    """Rule v1 is the baseline everything is measured against: its map must not drift."""
    assert len(GROUPS) == 26
    assert group_of("Nordic Bet") == "Betsson Group" and group_of("Sky Bet") == "Flutter"
    assert group_of("Unibet") == group_of("LeoVegas") == "Kambi"
    assert group_of("DraftKings") == "DraftKings"            # v1: unmapped means "its own operator"
    assert group_of("Some New Book") == "Some New Book"


def test_registry_entries_are_sourced_and_dated():
    for name, b in REGISTRY.items():
        assert normalize_book(name) == name, f"{name}: registry keys must be normalised names"
        assert b.owner and b.pricing and b.checked, name
        if b.verified:
            assert b.source.startswith("https://"), f"{name}: a verified entry needs a source"
            assert b.group, name


def test_registry_never_splits_a_legacy_group():
    """Verification may merge brands or stop counting one; it must never count two brands of one
    legacy group as two operators (that would loosen the rule)."""
    by_legacy = {}
    for name in REGISTRY:
        g = verified_group(name)
        if g and name in GROUPS:
            by_legacy.setdefault(GROUPS[name], set()).add(g)
    assert all(len(v) == 1 for v in by_legacy.values()), by_legacy


def test_canonical_aliases_resolve_to_one_verified_operator():
    for raw in ("Unibet (SE)", "Unibet (UK)", "unibet"):
        assert normalize_book(raw) == "Unibet"
    assert normalize_book("Bet 365") == "Bet365" and verified_group("Bet365")
    assert normalize_book("betfair") == "Betfair Exchange"
    assert normalize_book("DraftKings - Live Odds") == ""    # in-play feeds are not pre-match prices


def test_known_shared_owners_count_once():
    assert verified_group("Paddy Power") == verified_group("Sky Bet")
    assert verified_group("Betsson") == verified_group("Nordic Bet")
    assert verified_group("William Hill") == verified_group("888sport")
    q = {"home": 1.9, "away": 1.95}
    book = {"Paddy Power": q, "Sky Bet": q, "Betsson": q, "Nordic Bet": q}
    assert evm.n_books_verified(book, HA) == 2


def test_unknown_bookmakers_are_not_verified_and_never_counted():
    assert verified_group("Some New Book") is None           # not in the registry at all
    unverified = [n for n, b in REGISTRY.items() if not b.verified]
    assert all(verified_group(n) is None for n in unverified)
    q = {"home": 1.9, "away": 1.95}
    book = {"Pinnacle": q, "Bet365": q, "Mystery A": q, "Mystery B": q, "Mystery C": q}
    assert evm.n_books(book, HA) == 5                        # v1 counts every unknown name
    assert evm.n_books_verified(book, HA) == 2               # v2 counts none of them
    assert evm.unverified_books(book, HA) == ["Mystery A", "Mystery B", "Mystery C"]


def test_aggregates_and_incomplete_quotes_never_count():
    book = {"Pinnacle": {"home": 1.9, "away": 1.95}, "Avg": {"home": 1.9, "away": 1.95},
            "Bet365": {"home": 1.9}}
    assert evm.n_books_verified(book, HA) == 1


# ---------- the gate ----------
def _unknown_heavy_book():
    """Two verified operators and three unknown names that agree with each other."""
    return {"Pinnacle": {"home": 1.95, "away": 1.95}, "Bet365": {"home": 1.91, "away": 1.91},
            "Mystery A": {"home": 2.10, "away": 1.75}, "Mystery B": {"home": 1.80, "away": 2.05},
            "Mystery C": {"home": 1.80, "away": 2.05}}


def test_legacy_policy_is_unchanged_and_verified_blocks_with_a_clear_reason():
    rules = config.SelectionRules()
    c = next(x for x in _price(_unknown_heavy_book(), "legacy") if x.selection == "home")
    assert c.policy == "legacy" and c.n_books == 5 and c.bookmaker == "Mystery A"
    assert passes(c, rules, True) == (True, "ok")                       # v1 publishes this
    assert passes_under(c, "verified", rules, True) == (False, UNVERIFIED_REASON)
    v = next(x for x in _price(_unknown_heavy_book(), "verified") if x.selection == "home")
    assert v.policy == "verified" and v.n_books == 2
    assert passes(v, rules, True) == (False, UNVERIFIED_REASON)
    assert v.unverified_books == ("Mystery A", "Mystery B", "Mystery C")


def test_default_policy_is_legacy_so_nothing_changes_until_the_owner_opts_in(monkeypatch):
    monkeypatch.delenv("SBI_INDEPENDENCE_POLICY", raising=False)
    assert config.SelectionRules().independence_policy == "legacy"
    monkeypatch.setenv("SBI_INDEPENDENCE_POLICY", "verified")
    assert config.SelectionRules().independence_policy == "verified"
    assert config.INDEPENDENCE_RULE_VERSION == {"legacy": "indep-v1", "verified": "indep-v2"}


def test_unverified_price_can_still_be_the_best_price_against_a_verified_reference():
    """Unverified books are not discarded: their price can be the pick, but they are no evidence."""
    rules = config.SelectionRules()
    book = {"Pinnacle": {"home": 1.95, "away": 1.95}, "Bet365": {"home": 1.91, "away": 1.91},
            "Winamax": {"home": 1.90, "away": 1.92}, "Mystery A": {"home": 2.10, "away": 1.75}}
    v = next(x for x in _price(book, "verified") if x.selection == "home")
    assert v.bookmaker == "Mystery A" and v.n_books == 3 and v.consensus_src == "Pinnacle"
    assert passes(v, rules, True) == (True, "ok")
    assert v.ev == pytest.approx(0.5 * 2.10 - 1)


def test_verified_policy_never_creates_a_pick_legacy_would_not_publish():
    """Pure tightening: if the verified-only reference is kinder than the v1 reference, the v1
    verdict still stands."""
    rules = config.SelectionRules()
    # The v1 reference (median over every remaining name) follows four unknown books and shows no
    # value. The verified-only reference would show value. v2 must still say no.
    soft = {"home": 1.85, "away": 1.95}
    book = {"Bet365": {"home": 2.10, "away": 1.75}, "Winamax": soft, "Betsson": soft, "William Hill": soft,
            **{f"Mystery {x}": {"home": 2.05, "away": 1.78} for x in "ABCD"}}
    c = next(x for x in _price(book, "legacy") if x.selection == "home")
    assert c.bookmaker == "Bet365"
    assert c.views["legacy"]["ev"] < rules.min_ev < c.views["verified"]["ev"]
    assert passes_under(c, "legacy", rules, True) == (False, "EV below threshold")
    assert passes_under(c, "verified", rules, True) == (False, "EV below threshold")


def test_candidate_without_views_behaves_as_before():
    from sbi.engine import Candidate
    c = Candidate("1X2", "H", None, 0.5, 0.0, 0.5, 0.5, "Pinnacle", 0.5, 0.5, "Bet365", 2.2, 2.2, 0.10, 0.10, 0.0, 1.0,
                  5, Outcome(pw=0.5, pl=0.5))
    assert c.view("verified") is c and passes(c, config.SelectionRules(), True) == (True, "ok")


# ---------- leave-one-out reference ----------
def test_syndicated_prices_get_one_vote_not_three():
    """Three brands of one operator must not outvote two independent operators in the median."""
    flutter = {"home": 1.50, "away": 2.60}
    book = {"Paddy Power": flutter, "Sky Bet": flutter, "Betfair Sportsbook": flutter,
            "Bet365": {"home": 2.00, "away": 1.85}, "Winamax": {"home": 2.02, "away": 1.83},
            "Betsson": {"home": 2.04, "away": 1.80}, "Mystery A": {"home": 2.20, "away": 1.70}}
    v1, _ = evm.consensus_excluding(book, HA, "Mystery A")          # brands vote separately
    v2, src = evm.consensus_verified_excluding(book, HA, "Mystery A")
    assert src == evm.MEDIAN_VERIFIED
    assert v1["home"] > 0.55                                         # three Flutter votes drag the v1 median
    assert 0.46 < v2["home"] < 0.50                                  # one vote each: the independent view


def test_tested_bookmaker_and_all_its_brands_are_excluded_from_its_own_reference():
    q = {"home": 2.0, "away": 1.9}
    book = {"Betsson": {"home": 2.3, "away": 1.7}, "Nordic Bet": {"home": 2.3, "away": 1.7}, "Bet365": q, "Winamax": q}
    ref, src = evm.consensus_verified_excluding(book, HA, "Betsson")
    assert src == evm.MEDIAN_VERIFIED
    assert ref["home"] == pytest.approx(evm.devig_power([2.0, 1.9])[0])     # Nordic Bet did not vote
    # a sharp reference never prices itself
    book = {"Pinnacle": q, "Bet365": q, "Winamax": q}
    assert evm.consensus_verified_excluding(book, HA, "Pinnacle")[1] == evm.MEDIAN_VERIFIED
    assert evm.consensus_verified_excluding(book, HA, "Bet365")[1] == "Pinnacle"


def test_sharp_reference_is_used_alone_and_unverified_books_cannot_move_it():
    book = {"Pinnacle": {"home": 1.95, "away": 1.95}, "Bet365": {"home": 1.9, "away": 1.9}}
    base, src = evm.consensus_verified_excluding(book, HA, "Bet365")
    noisy = dict(book, **{f"Mystery {i}": {"home": 1.3, "away": 3.6} for i in range(6)})
    ref, src2 = evm.consensus_verified_excluding(noisy, HA, "Bet365")
    assert src == src2 == "Pinnacle" and ref == base


def test_market_average_is_not_a_leave_one_out_reference():
    """"Avg" contains the tested bookmaker's own price, so rule v2 never uses it."""
    book = {"Avg": {"home": 1.9, "away": 1.9}, "Bet365": {"home": 2.2, "away": 1.7}}
    assert evm.consensus_excluding(book, HA, "Bet365")[1] == "Avg"          # v1 behaviour, unchanged
    assert evm.consensus_verified_excluding(book, HA, "Bet365") == (None, None)


def test_only_unverified_books_means_no_reference_and_no_value_claim():
    book = {f"Mystery {i}": {"home": 1.9 + i / 10, "away": 1.9} for i in range(4)}
    assert evm.consensus_verified_excluding(book, HA, "Mystery 3") == (None, None)
    v = next(x for x in _price(book, "verified") if x.selection == "home")
    assert v.market_q is None and v.ev == -1.0 and v.n_books == 0


# ---------- stored data: duplicates across providers, stale quotes ----------
def _db(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('e','nba','NBA',?,'A','B','scheduled','t','t')""", ((NOW + timedelta(days=2)).isoformat(),))
    return con


def _quote(con, bookmaker, source, age_h, home=1.9, away=1.95, market="ML", event="e"):
    for sel, px in (("home", home), ("away", away)):
        con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (event, bookmaker, market, sel, None, px, "pre", source, (NOW - timedelta(hours=age_h)).isoformat()))


def test_same_bookmaker_from_two_providers_counts_once(tmp_path):
    from sbi.pipeline import _latest_books
    con = _db(tmp_path)
    _quote(con, "Bet 365", "espn.com (public scoreboard)", 1)
    _quote(con, "Bet365", "the-odds-api.com", 2)
    _quote(con, "Unibet (SE)", "the-odds-api.com", 1)
    _quote(con, "Unibet", "the-odds-api.com", 1)
    book = _latest_books(con, "e", 24, NOW)[0][("ML", None)]
    assert sorted(book) == ["Bet365", "Unibet"]
    assert evm.n_books(book, HA) == 2 and evm.n_books_verified(book, HA) <= 2


def test_stale_quotes_do_not_count_as_evidence(tmp_path):
    from sbi.pipeline import _latest_books
    con = _db(tmp_path)
    _quote(con, "Pinnacle", "the-odds-api.com", 1)
    _quote(con, "Bet365", "the-odds-api.com", 2)
    _quote(con, "Winamax", "the-odds-api.com", 30)           # older than any freshness limit
    book = _latest_books(con, "e", 24, NOW)[0][("ML", None)]
    assert "Winamax" not in book and evm.n_books_verified(book, HA) == 2


# ---------- audit report ----------
def test_wilson_interval():
    assert independence.wilson(0, 0) is None
    lo, hi = independence.wilson(0, 10)
    assert lo == 0.0 and 0.25 < hi < 0.35                    # zero observed is not zero risk
    lo, hi = independence.wilson(5, 10)
    assert lo < 0.5 < hi


def _audit_db(tmp_path):
    con = _db(tmp_path)
    for name, q in _unknown_heavy_book().items():            # v1: 5 names; v2: 2 verified operators
        _quote(con, name, "the-odds-api.com", 1, q["home"], q["away"])
    con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                   VALUES ('f','nba','NBA',?,'C','D','scheduled','t','t')""", ((NOW + timedelta(days=1)).isoformat(),))
    for name, h, a in (("Pinnacle", 1.95, 1.95), ("Bet365", 1.91, 1.91), ("Winamax", 1.90, 1.92), ("Mystery A", 2.10, 1.75)):
        _quote(con, name, "the-odds-api.com", 1, h, a, event="f")
    prices = {"Pinnacle": {"H": 2.5, "D": 3.3, "A": 3.0}, "Mystery A": {"H": 2.9, "D": 3.2, "A": 2.6},
              "Mystery B": {"H": 2.6, "D": 3.2, "A": 2.8}, "Mystery C": {"H": 2.6, "D": 3.2, "A": 2.8}}
    con.execute("""INSERT INTO recommendations(rec_id,event_id,published_at,sport,league,kickoff_utc,home,away,market,selection,
                   line,bookmaker,odds,model_prob,market_prob,final_prob,fair_odds,ev,ev_lower,stake_units,model_version,evidence_json)
                   VALUES ('r','e',?,'football','INT:x',?,'A','B','1X2','H',NULL,'Mystery A',2.9,0.4,0.38,0.38,2.63,0.102,0.102,
                   1,'t',?)""", (NOW.isoformat(), (NOW + timedelta(days=2)).isoformat(),
                                 json.dumps({"all_prices": prices, "blend_weight": 0.0, "net_odds": 2.9})))
    con.commit()
    con.close()
    return tmp_path / "t.sqlite"


@pytest.fixture
def audit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)        # no stored history replay in a test run
    path = _audit_db(tmp_path)
    before = path.read_bytes()
    con = independence.connect_ro(path)
    rep = independence.build(con, NOW)
    con.close()
    assert path.read_bytes() == before                       # the audit never writes to the database
    return rep


def test_audit_measures_blocked_candidates_with_limits(audit):
    nba = audit["upcoming"]["by_sport"]["nba"]
    assert nba["markets_v1_3plus"] == 2 and nba["markets_v2_3plus"] == 1
    assert nba["cand_v1"] == 2 and nba["cand_v2"] == 1       # event f survives, event e is blocked
    share = audit["upcoming"]["blocked_share"]["price_rule_candidates"]
    assert share["blocked"] == 1 and share["of"] == 2 and share["ci95"][0] < 0.5 < share["ci95"][1]
    blocked = audit["upcoming"]["blocked_candidates"]
    assert [b["blocked_because"] for b in blocked] == [UNVERIFIED_REASON]
    assert blocked[0]["event_id"] == "e" and blocked[0]["price_book_verified"] is False
    assert audit["upcoming"]["total"]["cand_v2"] <= audit["upcoming"]["total"]["cand_v1"]


def test_audit_reviews_published_picks_without_touching_them(audit):
    (p,) = audit["published"]
    assert p["books_v1"] == 4 and p["operators_v2"] == 1 and p["v2_verdict"] == UNVERIFIED_REASON
    assert p["odds"] == 2.9 and p["ev_published"] == 0.102   # reported as published, not recomputed over


def test_audit_report_states_what_is_deployed(audit):
    md = independence.render(audit)
    assert "Deployed rule: indep-v1 (`legacy`)" in md and "**staged**" in md
    assert "1 of 2" in md and "95% limits" in md
    assert "Picks already published (not changed)" in md
    assert "Not run for this report" in md                   # no history file in a test run


def test_price_identity_flags_identical_three_way_quotes(tmp_path):
    con = db.connect(tmp_path / "t.sqlite")
    for i in range(25):
        con.execute("""INSERT INTO events(event_id,sport,league,kickoff_utc,home,away,status,source,updated_at)
                       VALUES (?,'football','x',?,'A','B','scheduled','t','t')""", (f"e{i}", NOW.isoformat()))
        for name, shift in (("Betsson", 0.0), ("Nordic Bet", 0.0), ("Bet365", 0.01 * (i + 1))):
            for sel, px in (("H", 2.0 + i / 100), ("D", 3.3), ("A", 3.6)):
                con.execute("""INSERT INTO odds(event_id,bookmaker,market,selection,line,price,kind,source,retrieved_at)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (f"e{i}", name, "1X2", sel, None, px + shift, "pre", "t", NOW.isoformat()))
    pairs = {(p["a"], p["b"]): p for p in independence.price_identity(con)}
    assert pairs[("Betsson", "Nordic Bet")]["identical_share"] == 1.0
    assert pairs[("Betsson", "Nordic Bet")]["same_verified_operator"] is True
    assert pairs[("Bet365", "Betsson")]["identical_share"] == 0.0


def test_new_pick_evidence_records_the_rule_that_decided_it(tmp_path):
    from sbi.pipeline import publish_pick
    con = _db(tmp_path)
    c = next(x for x in _price(_unknown_heavy_book(), "legacy") if x.selection == "home")
    from types import SimpleNamespace
    event = SimpleNamespace(league="NBA", kickoff_utc=(NOW + timedelta(days=2)).isoformat(), home="A", away="B", source_url="u")
    n = publish_pick(con, NOW, "e", c, event, {}, {("ML", None): _unknown_heavy_book()}, [], NOW.isoformat(), 1, "t", [])
    assert n == 1
    ind = json.loads(con.execute("SELECT evidence_json FROM recommendations").fetchone()[0])["independence"]
    assert ind["policy"] == "legacy" and ind["rule_version"] == "indep-v1"
    assert ind["bookmakers_v1"] == 5 and ind["verified_operators_v2"] == 2
    assert ind["unverified_bookmakers"] == ["Mystery A", "Mystery B", "Mystery C"]


def test_registry_is_what_the_coverage_audit_calls_known():
    from sbi import coverage
    assert coverage.operator_bounds({"Paddy Power", "Sky Bet", "Pinnacle"}) == (2, 2)
    assert coverage.operator_bounds({"Pinnacle", "Mystery A", "Mystery B"}) == (1, 3)
    assert books.CHECKED >= "2026-11-13"
