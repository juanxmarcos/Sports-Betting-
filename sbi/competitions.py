"""Human-readable competition names for bets on the site (issue #84).

Display mapping only: nothing in the ledger or the database is rewritten. Every league code in use
maps to a short readable name; an unknown code falls back to the raw competition or league string,
never to a blank label.
"""
from __future__ import annotations

from .sources.international import COMPETITIONS as INT_COMPETITIONS

# League code -> short display name. football-data division codes, US leagues and tennis tours.
LEAGUE_NAMES: dict[str, str] = {
    "E0": "Premier League",
    "E1": "Championship (England)",
    "SP1": "La Liga",
    "D1": "Bundesliga",
    "I1": "Serie A",
    "F1": "Ligue 1",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "B1": "Belgian Pro League",
    "SC0": "Scottish Premiership",
    "NBA": "NBA",
    "NFL": "NFL",
    "TENNIS:ATP": "ATP",
    "TENNIS:WTA": "WTA",
}

# ESPN international codes whose site label differs from the data label in sources/international.py.
INT_DISPLAY: dict[str, str] = {"fifa.friendly": "FIFA Friendly"}


def league_of(event_id: str | None) -> str | None:
    """League code from an event id such as 'football:E0:…', 'football:INT:uefa.nations:…',
    'nba:NBA:…' or 'tennis:ATP:…'. None when the id names no known league."""
    parts = str(event_id or "").split(":")
    if len(parts) < 2 or not parts[1]:
        return None
    if parts[1] == "INT" and len(parts) > 2:
        return f"INT:{parts[2]}"
    code = f"TENNIS:{parts[1]}" if parts[0] == "tennis" else parts[1]
    return code if code in LEAGUE_NAMES else None   # e.g. a test id 'nba:1' names no league


def _tennis(competition: str | None, league: str | None) -> str | None:
    """'ATP · Nitto ATP Finals · Final' -> 'Nitto ATP Finals'; 'ATP · Bybit Stockholm Open · Round 1'
    -> 'ATP · Bybit Stockholm Open' (the tour is kept when the tournament name doesn't say it)."""
    bits = [b.strip() for b in str(competition or "").split("·") if b.strip()]
    tour = (league or "").split(":")[-1].upper() if league else ""
    if bits and bits[0].upper() in ("ATP", "WTA"):
        tour, bits = bits[0].upper(), bits[1:]
    if not bits:
        return None
    name = bits[0]
    return name if not tour or tour in name.upper().split() else f"{tour} · {name}"


def competition_name(league: str | None = None, competition: str | None = None,
                     event_id: str | None = None) -> str:
    """Readable competition for a pick or parlay leg. Falls back to the raw name, never blank
    unless nothing at all is known."""
    league = league or league_of(event_id)
    comp = str(competition or "").strip()
    if (league or "").startswith("TENNIS:") or str(event_id or "").startswith("tennis:"):
        t = _tennis(comp, league)
        if t:
            return t
    if league in ("NBA", "NFL") and comp and comp != league:
        return comp                                   # e.g. "NBA Playoffs"
    if league in LEAGUE_NAMES:
        return LEAGUE_NAMES[league]
    if league and league.startswith("INT:"):
        code = league[4:]
        return INT_DISPLAY.get(code) or INT_COMPETITIONS.get(code) or comp or code
    return comp or league or ""


def label(obj: dict, meta: dict | None = None) -> dict:
    """Set obj['competition_name'] in place (a pick or a leg). `meta` maps event_id -> the stored
    event_meta competition, used when the object itself carries none (old ledger rows)."""
    if not isinstance(obj, dict) or obj.get("competition_name"):
        return obj
    eid = obj.get("event_id")
    comp = obj.get("competition") or (meta or {}).get(eid)
    name = competition_name(obj.get("league"), comp, eid)
    if name:
        obj["competition_name"] = name
    return obj


def label_all(node, meta: dict | None = None) -> None:
    """Label every pick or leg (a dict with an event_id and a title) found anywhere in `node`."""
    if isinstance(node, list):
        for x in node:
            label_all(x, meta)
    elif isinstance(node, dict):
        if node.get("event_id") and node.get("title"):
            label(node, meta)
        for v in node.values():
            if isinstance(v, (list, dict)):
                label_all(v, meta)
