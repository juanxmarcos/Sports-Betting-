"""Plain-language explanations for picks, built ONLY from stored evidence.

Rules: every sentence is derived from a number in the evidence (prices, consensus,
model output, recent results). Nothing is invented; when evidence is missing the
sentence is omitted rather than filled with generic praise.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone

SEL_SOCCER = {"H": "{home} to win", "D": "Draw", "A": "{away} to win"}


def selection_label(r: dict) -> str:
    m, s, ln, home, away = r["market"], r["selection"], r.get("line"), r["home"], r["away"]
    if m == "1X2":
        return SEL_SOCCER[s].format(home=home, away=away)
    if m in ("OU", "TOTAL"):
        unit = "goals" if m == "OU" else "points"
        return f"{'Over' if s == 'over' else 'Under'} {ln:g} {unit}"
    if m in ("AH", "SPREAD"):
        team, h = (home, ln) if s == "home" else (away, -ln)
        return f"{team} {h:+g}"
    if m == "ML":
        return f"{home if s in ('H', 'home') else away} to win"
    return f"{s}"


def market_label(m: str) -> str:
    from .watch import MARKET_LABEL
    return MARKET_LABEL.get(m, m)


def _pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"


def ev_plain(ev: float) -> str:
    return (f"If Doyen's probability is right, this price returns about ${ev * 100:.2f} profit per $100 staked "
            f"on average over many similar bets — an estimate, not a promise.")


def _form_sentence(team: str, f: dict | None) -> str | None:
    if not f or not f.get("n"):
        return None
    w = f["last"].count("W")
    d = f["last"].count("D")
    s = f"{team} have {w} win{'s' if w != 1 else ''}"
    if d:
        s += f" and {d} draw{'s' if d != 1 else ''}"
    s += f" in their last {f['n']} ({f['gf']} scored, {f['ga']} conceded"
    if f.get("xg_for_avg") is not None:
        s += f"; xG {f['xg_for_avg']} for, {f['xg_against_avg']} against per game"
    return s + ")"


def explain(r: dict, e: dict) -> dict:
    """r: recommendation row (dict), e: evidence dict. Returns {'why': str, 'risk': str, 'risks': [...]}."""
    sel = selection_label(r)
    prices = e.get("all_prices") or {}
    quotes = [q.get(r["selection"]) for q in prices.values() if isinstance(q, dict) and q.get(r["selection"])]
    median = statistics.median(quotes) if quotes else None
    src = e.get("consensus_source") or "the market"
    fair = 1 / r["market_prob"] if r.get("market_prob") else None
    parts = []
    if fair:
        parts.append(f"{r['bookmaker']} is offering {r['odds']:.2f} on {sel}, longer than the sharpest price in this market: "
                     f"{src} implies a {_pct(r['market_prob'], 1)} chance, which is fair odds of {fair:.2f}.")
    if median and len(quotes) >= 3:
        parts.append(f"Across {len(quotes)} bookmakers the typical price is {median:.2f}, so this quote stands "
                     f"{(r['odds'] / median - 1) * 100:.0f}% above the pack.")
    mp, mk = r.get("model_prob"), r.get("market_prob")
    w = e.get("blend_weight", 0) or 0
    if mp is not None and mk is not None:
        gap = mp - mk
        if abs(gap) < 0.02:
            parts.append(f"Doyen's own model agrees ({_pct(mp, 1)}).")
        elif gap > 0:
            parts.append(f"Doyen's own model is more positive still ({_pct(mp, 1)}).")
        else:
            parts.append(f"Doyen's own model is less optimistic ({_pct(mp, 1)}), so the case rests on the price, "
                         "not on the model." if w < 0.05 else f"Doyen's model is at {_pct(mp, 1)}.")
    xg = e.get("expected_goals")
    if xg and r["market"] in ("1X2", "OU", "AH"):
        parts.append(f"The goal model projects {xg['home']}–{xg['away']} expected goals.")
    for team in (r["home"], r["away"]):
        fs = _form_sentence(team, (e.get("form") or {}).get(team))
        if fs:
            parts.append(fs + ".")
    for k in ("context",):
        if e.get(k):
            parts.append(e[k])

    risks = list(e.get("risks") or [])
    main = None
    if mp is not None and mk is not None and mp < mk - 0.05:
        main = (f"Doyen's model disagrees with the market ({_pct(mp, 0)} vs {_pct(mk, 0)}). The market may know "
                "something the model doesn't, such as team news.")
    ts = r.get("odds_retrieved_at")
    if not main and ts:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds() / 3600
        if age > 24:
            main = f"The price is {age:.0f} hours old and may no longer be available."
    if not main and r["market"] in ("AH", "SPREAD") and e.get("stake_share_active", 1) < 0.95:
        main = "A whole or quarter line: part of the stake can be refunded on certain results."
    if not main:
        main = {"soccer": "Lineups aren't confirmed yet; a late absence can move this price quickly.",
                "nfl": "Quarterback and injury news isn't modelled; check the final injury report.",
                "nba": "Late scratches and rest decisions aren't modelled; check availability before tip-off.",
                "tennis": "Fitness and withdrawals aren't modelled; check for late injury news.",
                "golf": "Golf outcomes are highly variable; even a correct probability loses most of the time."
                }.get(r.get("sport", "soccer"), "Unmodelled news can move this price.")
    return {"why": " ".join(parts) or "The available price is above Doyen's estimate of fair value.",
            "risk": main, "risks": risks}
