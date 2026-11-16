"""nflverse injury adapter: parsing, states, updates/retractions, idempotency and HTTP failure modes.

Fixture-based: no test touches the network (tests/fixtures/nflverse)."""
from pathlib import Path

import pytest

from sbi import config, db
from sbi.sources import nflverse_injuries as nv
from sbi.sources.http import SourceBlocked

FX = Path(__file__).parent / "fixtures" / "nflverse"
WED, FRI, LEGACY = (FX / n for n in ("week10_wed.csv", "week10_fri.csv", "legacy_2024.csv"))


@pytest.fixture
def con(tmp_path):
    return db.connect(tmp_path / "t.sqlite")


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


class Resp:
    def __init__(self, status, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}


class Session:
    """Scripted HTTP: each item is a Resp or an exception to raise."""
    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def get(self, url, headers=None, timeout=None):
        self.calls.append(dict(headers or {}))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fetcher(path, outcome="fetched", published="2026-11-11T07:00:00+00:00"):
    return lambda url: {"outcome": outcome, "http_status": 200, "content": Path(path).read_bytes(),
                        "etag": '"e"', "last_modified": published}


def by_id(records):
    return {r["gsis_id"]: r for r in records}


# ---------------------------------------------------------------- parsing and states

def test_practice_and_designation_are_separate_facts():
    recs, skipped = nv.parse(WED.read_bytes())
    qb = by_id(recs)["00-0000001"]
    assert (qb["practice_status"], qb["report_status"]) == ("DNP", None)     # DNP is not turned into a designation
    assert qb["practice_injury"] == "Elbow / Knee" and qb["team_name"] == "Kansas City Chiefs"
    assert {r["practice_status"] for r in recs} == {"DNP", "Limited", "Full"}
    assert skipped == {}
    fri = by_id(nv.parse(FRI.read_bytes())[0])
    assert {fri[i]["report_status"] for i in ("00-0000001", "00-0000004", "00-0000006")} == {"Questionable", "Out", "Doubtful"}
    assert fri["00-0000003"]["report_status"] is None and fri["00-0000003"]["practice_status"] == "Full"


def test_bad_rows_are_skipped_and_counted_not_repaired():
    recs, skipped = nv.parse(FRI.read_bytes())
    assert skipped == {"unknown_team": 1, "no_player_id": 1, "bad_season_or_week": 1, "duplicate": 1}
    assert "00-0000007" not in by_id(recs) and len(recs) == 5


def test_legacy_schema_duplicates_and_unrecognised_text():
    recs, skipped = nv.parse(LEGACY.read_bytes())
    r = by_id(recs)
    assert r["00-0000011"]["report_status"] == "Out"                  # later date_modified wins
    assert r["00-0000011"]["row_modified_at"] == "2024-12-15T14:17:06Z"
    assert r["00-0000011"]["practice_status"] is None and r["00-0000011"]["practice_raw"] is None   # whitespace only
    assert (r["00-0000012"]["report_status"], r["00-0000012"]["report_raw"]) == (None, "Note")
    assert "00-0000013" not in r                                       # conflicting, no time to choose by: dropped
    assert (r["00-0000014"]["report_status"], r["00-0000014"]["practice_status"]) == ("Probable", None)
    assert r["00-0000014"]["practice_raw"] == "Out (Definitely Will Not Play)"
    assert skipped == {"duplicate": 1, "conflicting_duplicate": 2}


@pytest.mark.parametrize("body", [b"", b"<html><body>Not Found</body></html>", b"season,team,week\n2026,KC,10\n",
                                  WED.read_bytes().split(b"\n")[0] + b"\n", b"\xff\xfe\x00bad",
                                  WED.read_bytes().split(b"\n")[0] + b"\n2026,REG,REG,XXX,10,00-0000001,QB,a,a,a,,,,,,\n"])
def test_malformed_responses_are_rejected(body):
    with pytest.raises(nv.SourceMalformed):
        nv.parse(body)


def test_season_for():
    from datetime import datetime
    assert nv.season_for(datetime(2026, 11, 13)) == 2026 and nv.season_for(datetime(2027, 2, 7)) == 2026
    assert nv.season_for(datetime(2027, 3, 1)) == 2027


# ---------------------------------------------------------------- storage: updates, retractions, idempotency

def test_updates_retraction_restore_and_idempotency(con):
    a = nv.ingest(con, 2026, fetcher(WED))
    assert (a["outcome"], a["rows"], a["new"], a["changed"]) == ("fetched", 5, 5, 0)
    again = nv.ingest(con, 2026, fetcher(WED))
    assert (again["new"], again["changed"], again["retracted"], again["restored"]) == (0, 0, 0, 0)
    assert con.execute("SELECT COUNT(*) FROM nfl_report_updates").fetchone()[0] == 5

    b = nv.ingest(con, 2026, fetcher(FRI, published="2026-11-13T07:00:00+00:00"))
    assert (b["new"], b["changed"], b["retracted"]) == (1, 3, 1)      # QB One, Tackle Four, QB Five changed; Receiver Two gone
    qb = con.execute("SELECT * FROM nfl_report_current WHERE gsis_id='00-0000001'").fetchone()
    assert (qb["report_status"], qb["practice_status"], qb["source_published_at"]) == ("Questionable", "Limited", "2026-11-13T07:00:00+00:00")
    gone = con.execute("SELECT * FROM nfl_report_current WHERE gsis_id='00-0000002'").fetchone()
    assert gone["retracted_at"] is not None and gone["practice_status"] == "Limited"       # kept, not deleted
    log = [tuple(r) for r in con.execute("""SELECT change, old_practice_status, new_practice_status, old_report_status,
                                            new_report_status FROM nfl_report_updates WHERE gsis_id='00-0000001' ORDER BY id""")]
    assert log == [("new", None, "DNP", None, None), ("changed", "DNP", "Limited", None, "Questionable")]

    c = nv.ingest(con, 2026, fetcher(WED, published="2026-11-14T07:00:00+00:00"))          # the provider reverts
    assert (c["restored"], c["retracted"]) == (1, 1)                                        # Receiver Two back, Corner Six gone
    assert [r[0] for r in con.execute("SELECT change FROM nfl_report_updates WHERE gsis_id='00-0000002' ORDER BY id")] == \
        ["new", "retracted", "restored"]
    assert [r["outcome"] for r in con.execute("SELECT outcome FROM nfl_report_fetches ORDER BY id")] == ["fetched"] * 4


def test_update_log_is_append_only(con):
    nv.ingest(con, 2026, fetcher(WED))
    for sql in ("UPDATE nfl_report_updates SET change='changed'", "DELETE FROM nfl_report_updates"):
        with pytest.raises(Exception, match="append-only"):
            con.execute(sql)


def test_not_modified_writes_nothing_but_is_logged(con):
    nv.ingest(con, 2026, fetcher(WED))
    n = nv.ingest(con, 2026, fetcher(FRI, outcome="not_modified"))      # content ignored: provider says unchanged
    assert n["outcome"] == "not_modified" and "rows" not in n
    assert con.execute("SELECT COUNT(*) FROM nfl_report_updates").fetchone()[0] == 5
    assert con.execute("SELECT outcome FROM nfl_report_fetches ORDER BY id DESC").fetchone()[0] == "not_modified"


def test_not_modified_with_empty_database_loads_the_cached_copy(con):
    assert nv.ingest(con, 2026, fetcher(WED, outcome="not_modified"))["new"] == 5


def test_truncated_file_does_not_retract_the_season(con, tmp_path):
    lines = WED.read_bytes().split(b"\n")
    big = tmp_path / "big.csv"
    big.write_bytes(b"\n".join([lines[0]] + [lines[1].replace(b"00-0000001", b"00-%07d" % i) for i in range(100, 160)]) + b"\n")
    assert nv.ingest(con, 2026, fetcher(big))["new"] == 60
    small = tmp_path / "small.csv"
    small.write_bytes(b"\n".join([lines[0], lines[1].replace(b"00-0000001", b"00-0000100")]) + b"\n")
    r = nv.ingest(con, 2026, fetcher(small))
    assert r["outcome"] == "malformed" and "refusing to retract" in r["error"]
    assert con.execute("SELECT COUNT(*) FROM nfl_report_current WHERE retracted_at IS NULL").fetchone()[0] == 60
    assert "refusing" in con.execute("SELECT last_error FROM provider_status WHERE provider=?", (nv.PROVIDER,)).fetchone()[0]


def test_wrong_season_file_is_rejected(con):
    r = nv.ingest(con, 2026, fetcher(LEGACY))
    assert r["outcome"] == "malformed" and con.execute("SELECT COUNT(*) FROM nfl_report_current").fetchone()[0] == 0


@pytest.mark.parametrize("exc,outcome", [(SourceBlocked("HTTP 429"), "blocked"), (SourceBlocked("HTTP 403"), "blocked"),
                                         (nv.SourceUnavailable("timeout"), "error"), (nv.SourceMalformed("html"), "malformed")])
def test_failures_keep_stored_data_and_are_logged(con, exc, outcome):
    nv.ingest(con, 2026, fetcher(WED))

    def boom(url):
        raise exc
    r = nv.ingest(con, 2026, boom)                                    # never raises
    assert r["outcome"] == outcome and r["error"]
    assert con.execute("SELECT COUNT(*) FROM nfl_report_current WHERE retracted_at IS NULL").fetchone()[0] == 5
    row = con.execute("SELECT outcome, error FROM nfl_report_fetches ORDER BY id DESC").fetchone()
    assert row["outcome"] == outcome and row["error"]
    assert con.execute("SELECT last_success FROM provider_status WHERE provider=?", (nv.PROVIDER,)).fetchone()[0]


def test_not_published_is_not_an_error(con):
    r = nv.ingest(con, 2027, lambda url: {"outcome": "not_published", "http_status": 404, "content": None,
                                         "etag": None, "last_modified": None})
    assert r["outcome"] == "not_published" and "error" not in r
    assert con.execute("SELECT 1 FROM provider_status WHERE provider=?", (nv.PROVIDER,)).fetchone() is None


# ---------------------------------------------------------------- HTTP: conditional requests, blocks, backoff

URL = nv.URL.format(season=2026)


def test_conditional_fetch_sends_validators_and_reuses_one_cache_file(cache):
    body = WED.read_bytes()
    s = Session(Resp(200, body, {"ETag": '"abc"', "Last-Modified": "Wed, 11 Nov 2026 07:00:10 GMT"}), Resp(304))
    first = nv.conditional_fetch(URL, session=s)
    assert (first["outcome"], first["last_modified"]) == ("fetched", "2026-11-11T07:00:10+00:00")
    assert "If-None-Match" not in s.calls[0] and s.calls[0]["User-Agent"] == config.USER_AGENT
    second = nv.conditional_fetch(URL, session=s)
    assert second["outcome"] == "not_modified" and second["content"] == body
    assert s.calls[1]["If-None-Match"] == '"abc"' and s.calls[1]["If-Modified-Since"] == "Wed, 11 Nov 2026 07:00:10 GMT"
    assert len(list(cache.iterdir())) == 2                              # body + metadata, overwritten each time


@pytest.mark.parametrize("code", [401, 403, 429])
def test_blocked_is_not_retried(cache, code):
    s = Session(Resp(code), Resp(200, b"x"))
    with pytest.raises(SourceBlocked):
        nv.conditional_fetch(URL, session=s, sleep=lambda x: None)
    assert len(s.calls) == 1


def test_timeouts_back_off_then_succeed_or_give_up(cache):
    import requests
    waits = []
    s = Session(requests.Timeout("slow"), Resp(503), Resp(200, WED.read_bytes(), {}))
    assert nv.conditional_fetch(URL, session=s, sleep=waits.append)["outcome"] == "fetched"
    assert waits == [1, 2]
    waits.clear()
    s = Session(requests.Timeout("slow"), requests.ConnectionError("down"), requests.Timeout("slow"))
    with pytest.raises(nv.SourceUnavailable):
        nv.conditional_fetch(URL, session=s, sleep=waits.append)
    assert len(s.calls) == 3 and waits == [1, 2]                        # bounded: three attempts, no more


def test_404_and_oversized(cache, monkeypatch):
    assert nv.conditional_fetch(URL, session=Session(Resp(404)))["outcome"] == "not_published"
    monkeypatch.setattr(nv, "MAX_BYTES", 10)
    with pytest.raises(nv.SourceMalformed):
        nv.conditional_fetch(URL, session=Session(Resp(200, b"x" * 11)))
    assert not any(cache.iterdir())                                      # nothing oversized is cached


def test_end_to_end_through_http_layer(con, cache, monkeypatch):
    s = Session(Resp(200, WED.read_bytes(), {"ETag": '"1"', "Last-Modified": "Wed, 11 Nov 2026 07:00:10 GMT"}), Resp(304),
                Resp(429))
    f = lambda url: nv.conditional_fetch(url, session=s, sleep=lambda x: None)   # noqa: E731
    assert [nv.ingest(con, 2026, f)["outcome"] for _ in range(3)] == ["fetched", "not_modified", "blocked"]
    assert con.execute("SELECT COUNT(*) FROM nfl_report_current").fetchone()[0] == 5
