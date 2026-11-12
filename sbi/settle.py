"""Settlement of paper recommendations against official results + closing line value."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import config, db
from . import ev as evm
from .engine import SELECTIONS, books_from_rows
from .markets import pnl, settle_value
from .sources.football_data import EXCHANGES

STATUS = {1.0: "won", 0.5: "half_won", 0.0: "push", -0.5: "half_lost", -1.0: "lost"}


def _closing(con, rec) -> tuple[float | None, float | None]:
    rows = con.execute("""SELECT market,line,bookmaker,selection,price FROM odds
                          WHERE event_id=? AND kind='closing' AND market=? AND IFNULL(line,-999)=IFNULL(?, -999)""",
                       (rec["event_id"], rec["market"], rec["line"])).fetchall()
    if not rows:
        # No published closing line (e.g. internationals): use the last pre-match snapshot per bookmaker
        # taken after publication and before kick-off as the closing proxy.
        rows = con.execute("""SELECT o.market,o.line,o.bookmaker,o.selection,o.price FROM odds o
                              JOIN (SELECT bookmaker, selection, MAX(retrieved_at) mr FROM odds
                                    WHERE event_id=? AND kind='pre' AND market=? AND IFNULL(line,-999)=IFNULL(?,-999)
                                      AND retrieved_at > ? AND retrieved_at < ? GROUP BY bookmaker, selection) x
                                ON o.bookmaker=x.bookmaker AND o.selection=x.selection AND o.retrieved_at=x.mr
                              WHERE o.event_id=? AND o.kind='pre' AND o.market=? AND IFNULL(o.line,-999)=IFNULL(?,-999)""",
                           (rec["event_id"], rec["market"], rec["line"], rec["published_at"], rec["kickoff_utc"],
                            rec["event_id"], rec["market"], rec["line"])).fetchall()
    if not rows:
        return None, None
    book = books_from_rows([tuple(r) for r in rows]).get((rec["market"], rec["line"]), {})
    cons, _ = evm.consensus(book, SELECTIONS[rec["market"]])
    same = book.get(rec["bookmaker"], {}).get(rec["selection"]) or book.get("Avg", {}).get(rec["selection"])
    if not cons:
        return same, None
    net = evm.net_price(rec["bookmaker"], rec["odds"], config.RULES.exchange_commission)
    return same, net * cons[rec["selection"]] - 1  # CLV: EV of our price vs closing fair prob


def settle_all(con, now: datetime) -> dict:
    n = {"settled": 0, "voided": 0, "clv_updated": 0}
    open_recs = con.execute("""SELECT r.*, e.status AS ev_status, e.home_score, e.away_score
                               FROM recommendations r JOIN events e USING(event_id)
                               WHERE r.status='open'""").fetchall()
    for r in open_recs:
        if r["ev_status"] == "finished" and r["home_score"] is not None:
            res = settle_value(r["market"], r["selection"], r["line"], r["home_score"], r["away_score"])
            net = r["odds"]
            if r["bookmaker"] in EXCHANGES:
                net = 1 + (r["odds"] - 1) * (1 - config.RULES.exchange_commission)
            close_px, clv = _closing(con, r)
            con.execute("""UPDATE recommendations SET status=?, pnl_units=?, closing_odds=?, clv=?, settled_at=?
                           WHERE rec_id=?""",
                        (STATUS[res], pnl(res, net, r["stake_units"]), close_px, clv, db.utcnow(), r["rec_id"]))
            n["settled"] += 1
        elif datetime.fromisoformat(r["kickoff_utc"]) < now - timedelta(days=10):
            con.execute("UPDATE recommendations SET status='void', pnl_units=0, settled_at=? WHERE rec_id=?",
                        (db.utcnow(), r["rec_id"]))
            n["voided"] += 1
    # late-arriving closing odds for already-settled recs
    for r in con.execute("SELECT * FROM recommendations WHERE status NOT IN ('open','void') AND clv IS NULL").fetchall():
        close_px, clv = _closing(con, r)
        if clv is not None:
            con.execute("UPDATE recommendations SET closing_odds=?, clv=? WHERE rec_id=?", (close_px, clv, r["rec_id"]))
            n["clv_updated"] += 1
    con.commit()
    return n
