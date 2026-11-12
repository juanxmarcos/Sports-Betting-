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
        elif r["ev_status"] == "void":   # e.g. tennis walkover / cancelled event -> stake returned
            con.execute("UPDATE recommendations SET status='void', pnl_units=0, settled_at=? WHERE rec_id=?",
                        (db.utcnow(), r["rec_id"]))
            n["voided"] += 1
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


def reassess_open(con, now: datetime) -> dict:
    """Re-price every open, not-yet-started recommendation against the latest odds.

    Appends a row to rec_updates only when the status or the price changes:
      active    - still qualifies (EV >= threshold) at an available price
      updated   - still positive but the edge or price moved materially
      withdrawn - the price no longer offers value (EV <= 0) or vanished
      expired   - kick-off passed (awaiting settlement)
    """
    from .pipeline import _latest_books
    rules = config.RULES
    out = {"checked": 0, "appended": 0}
    for r in con.execute("SELECT * FROM recommendations WHERE status='open'").fetchall():
        if _integrity_withdrawn(con, r["rec_id"]):
            continue   # terminal: a pick that failed the integrity audit is never re-activated by price moves
        last = con.execute("SELECT * FROM rec_updates WHERE rec_id=? ORDER BY id DESC LIMIT 1", (r["rec_id"],)).fetchone()
        ko = datetime.fromisoformat(r["kickoff_utc"])
        if ko <= now:
            if not last or last["status"] != "expired":
                con.execute("""INSERT INTO rec_updates(rec_id,checked_at,status,note) VALUES (?,?,?,?)""",
                            (r["rec_id"], now.isoformat(), "expired", "Event started; awaiting result."))
                out["appended"] += 1
            continue
        out["checked"] += 1
        books, ts, _ = _latest_books(con, r["event_id"], rules.max_odds_age_hours, now)
        book = books.get((r["market"], r["line"]), {})
        sels = SELECTIONS.get(r["market"], ["H", "A"])
        cons, _ = evm.consensus(book, sels)
        same = (book.get(r["bookmaker"]) or {}).get(r["selection"])
        bk, quoted, net = evm.best_price(evm.clean(book, sels), r["selection"], rules.exchange_commission)
        if not cons or not bk:
            status, ev_now, note = ("withdrawn", None, "No current price available.") if not book else \
                                   (last["status"] if last else "active", None, "Consensus unavailable; unchanged.")
        else:
            q = cons[r["selection"]]
            ev_now = net * q - 1
            if ev_now >= rules.min_ev:
                status = "active"
                note = (f"Still qualifies: best {quoted:.2f} at {bk} vs fair {1 / q:.2f}.")
            elif ev_now > 0:
                status = "updated"
                note = (f"Edge has narrowed to {ev_now * 100:+.1f}%: best {quoted:.2f} at {bk}, fair {1 / q:.2f}.")
            else:
                status = "withdrawn"
                note = (f"No longer value: best {quoted:.2f} vs fair {1 / q:.2f} (market moved).")
        changed = (not last or last["status"] != status or
                   (quoted and last["best_odds"] and abs(quoted - last["best_odds"]) > 1e-9))
        if changed and not (not last and status == "active" and quoted and abs(quoted - r["odds"]) < 1e-9):
            con.execute("""INSERT INTO rec_updates(rec_id,checked_at,status,best_odds,best_bookmaker,original_book_odds,
                           consensus_prob,ev_now,note) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (r["rec_id"], now.isoformat(), status, quoted if bk else None, bk, same,
                         cons[r["selection"]] if cons else None, ev_now, note))
            out["appended"] += 1
    con.commit()
    out.update(_news_triggers(con, now))
    return out


def _news_triggers(con, now: datetime) -> dict:
    """Append 'updated' notes when injury status changes or lineups are confirmed after publication.
    Notes only: the price-based status logic above still decides active/withdrawn."""
    from .sources.espn_extra import _ensure
    _ensure(con)
    n = 0
    for r in con.execute("SELECT * FROM recommendations WHERE status='open' AND kickoff_utc > ?", (now.isoformat(),)).fetchall():
        if _integrity_withdrawn(con, r["rec_id"]):
            continue
        sport = "nba" if r["league"] == "NBA" else ("nfl" if r["league"] == "NFL" else None)
        logged = {u["note"] for u in con.execute("SELECT note FROM rec_updates WHERE rec_id=?", (r["rec_id"],))}
        last = con.execute("SELECT status FROM rec_updates WHERE rec_id=? ORDER BY id DESC LIMIT 1", (r["rec_id"],)).fetchone()
        st = last["status"] if last else "active"
        notes = []
        if sport:
            for c in con.execute("""SELECT team, player, old_status, new_status FROM injury_changes WHERE sport=?
                                    AND team IN (?,?) AND first_seen > ? ORDER BY id""", (sport, r["home"], r["away"], r["published_at"])):
                notes.append(f"Injury update: {c['player']} ({c['team']}) {c['old_status'] or 'not listed'} → {c['new_status']}.")
        # material price movement of the sharp reference since publication (>= 3 probability points)
        if r["market_prob"]:
            from .pipeline import _latest_books
            books, _, _ = _latest_books(con, r["event_id"], config.RULES.max_odds_age_hours, now)
            book = books.get((r["market"], r["line"]), {})
            cons, src = evm.consensus_excluding(book, SELECTIONS.get(r["market"], ["H", "A"]), r["bookmaker"])
            recent_mv = con.execute("""SELECT 1 FROM rec_updates WHERE rec_id=? AND note LIKE 'Market moved%'
                                       AND checked_at > ?""", (r["rec_id"], (now - timedelta(hours=6)).isoformat())).fetchone()
            if cons and r["selection"] in cons and abs(cons[r["selection"]] - r["market_prob"]) >= 0.03 and not recent_mv:
                notes.append(f"Market moved: fair probability {r['market_prob'] * 100:.0f}% → {cons[r['selection']] * 100:.0f}% ({src}).")
        w = con.execute("SELECT * FROM event_weather WHERE event_id=?", (r["event_id"],)).fetchone()
        if w and ((w["gust_mph"] or 0) >= 20 or (w["precip_pct"] or 0) >= 60):
            notes.append(f"Weather: gusts {w['gust_mph']:.0f} mph, precipitation {w['precip_pct']:.0f}%.")
        lu = con.execute("SELECT COUNT(*) n, SUM(confirmed) c FROM lineups WHERE event_id=?", (r["event_id"],)).fetchone()
        if lu["n"] == 2 and lu["c"] == 2:
            notes.append("Starting lineups confirmed (ESPN).")
        for note in notes:
            if note not in logged:
                con.execute("INSERT INTO rec_updates(rec_id,checked_at,status,note) VALUES (?,?,?,?)",
                            (r["rec_id"], now.isoformat(), "updated" if st in ("active", "updated") else st, note))
                n += 1
    con.commit()
    return {"news_notes": n}


def _integrity_withdrawn(con, rec_id) -> bool:
    return bool(con.execute("SELECT 1 FROM rec_updates WHERE rec_id=? AND status='withdrawn' AND note LIKE 'Integrity audit%'",
                            (rec_id,)).fetchone())
