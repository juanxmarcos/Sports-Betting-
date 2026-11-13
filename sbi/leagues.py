"""Soccer club league allowlist: which football-data.co.uk divisions Doyen stores, and what it may do with each.

Two tiers, both explicit. A division that is not listed here is never ingested, even when it
appears in a file Doyen already downloads.

  active      Analysed and eligible for picks. Exactly `config.FOOTBALL_LEAGUES` (unchanged).
  monitoring  Fixtures, pre-match odds and results are STORED and measured by `python -m sbi coverage`,
              but the division is never priced, never shown on the public site and can never produce
              a pick. `pipeline.analyse` reads only the active tier.

Moving a division from monitoring to active is a deliberate code change that needs its own
walk-forward evidence (`python -m sbi league-eval`, docs/DATA_SOURCES.md) and the owner's approval.
Nothing in this module or in the evaluation promotes a division automatically.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import config

ACTIVE, MONITORING = "active", "monitoring"


@dataclass(frozen=True)
class League:
    code: str            # football-data.co.uk division code, also `events.league`
    name: str
    country: str
    level: int           # 1 = top flight
    status: str          # ACTIVE | MONITORING
    note: str = ""


# Monitoring tier: divisions observed in the already-downloaded fixtures.csv on 2026-11-13, each with
# ten seasons of results in mmz4281/{season}/{code}.csv. Verified per division in reports/league_validation.md.
_MONITORING = (
    League("E2", "England League One", "England", 3, MONITORING),
    League("E3", "England League Two", "England", 4, MONITORING),
    League("EC", "England National League", "England", 5, MONITORING, "no xG columns in the file"),
    League("SC1", "Scotland Championship", "Scotland", 2, MONITORING, "10 teams; no xG columns"),
    League("SC2", "Scotland League One", "Scotland", 3, MONITORING, "10 teams; no xG columns"),
    League("SC3", "Scotland League Two", "Scotland", 4, MONITORING, "10 teams; no xG columns"),
    League("SP2", "Spain Segunda Division", "Spain", 2, MONITORING),
)
_LEVEL = {"E0": 1, "E1": 2, "SP1": 1, "D1": 1, "I1": 1, "F1": 1, "N1": 1, "P1": 1, "B1": 1, "SC0": 1}

LEAGUES: dict[str, League] = {
    **{c: League(c, n, n.split(" ")[0], _LEVEL.get(c, 1), ACTIVE) for c, n in config.FOOTBALL_LEAGUES.items()},
    **{lg.code: lg for lg in _MONITORING if lg.code not in config.FOOTBALL_LEAGUES},
}


def active() -> list[str]:
    """Divisions that may be analysed. Always the keys of config.FOOTBALL_LEAGUES."""
    return list(config.FOOTBALL_LEAGUES)


def monitoring() -> list[str]:
    return [c for c, lg in LEAGUES.items() if lg.status == MONITORING and c not in config.FOOTBALL_LEAGUES]


def stored() -> list[str]:
    """Every division Doyen ingests: active first, then monitoring."""
    return active() + monitoring()


def status(code: str) -> str:
    """'active', 'monitoring', 'international' (separate connector), or 'unlisted' for anything else."""
    if code in config.FOOTBALL_LEAGUES:
        return ACTIVE
    if code in LEAGUES:
        return MONITORING
    return "international" if str(code).startswith("INT:") else "unlisted"   # INT: has its own connector and model


def name(code: str) -> str:
    return LEAGUES[code].name if code in LEAGUES else code


def is_analysable(code: str) -> bool:
    return code in config.FOOTBALL_LEAGUES


# ---------------------------------------------------------------- team names
# football-data.co.uk spells each club one way across the ten seasons checked (no near-duplicate
# spellings inside any division), so its own files need no aliases. This table maps common spellings
# from OTHER feeds onto the football-data spelling, per division. It is deliberately short and exact:
# a name that is not listed is returned unchanged and is never fuzzy-matched, because joining two
# different clubs is worse than failing to join one.
TEAM_ALIASES: dict[str, dict[str, str]] = {
    "E2": {"mk dons": "Milton Keynes Dons", "sheffield wednesday": "Sheffield Weds",
           "wimbledon": "AFC Wimbledon", "burton albion": "Burton"},
    "E3": {"bristol rovers": "Bristol Rvs"},
}


def _key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def canonical_team(code: str, team: str) -> str:
    """The football-data spelling of `team` in division `code`, or the trimmed name if no exact alias exists.

    Aliases are scoped to one division: the same words can be a different club elsewhere."""
    t = re.sub(r"\s+", " ", str(team).strip())
    return TEAM_ALIASES.get(code, {}).get(_key(t), t)
