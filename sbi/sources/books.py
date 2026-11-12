"""Bookmaker name normalisation so the same bookmaker from two feeds counts once.

Bookmaker independence matters for the "3+ bookmakers" rule: ESPN's "Bet 365" and The
Odds API's "Bet365" are one bookmaker; regional skins of the same book are merged; live
in-play feeds are excluded from pre-match odds.
"""
from __future__ import annotations

import re

ALIASES = {
    "bet 365": "Bet365", "bet365": "Bet365", "draftkings": "DraftKings", "draft kings": "DraftKings",
    "fanduel": "FanDuel", "betmgm": "BetMGM", "caesars": "Caesars", "william hill (us)": "Caesars",
    "williamhill_us": "Caesars", "espn bet": "ESPN BET", "betfair": "Betfair Exchange",
    "betfair exchange": "Betfair Exchange", "pinnacle": "Pinnacle", "unibet (se)": "Unibet", "unibet (uk)": "Unibet",
    "unibet (fr)": "Unibet", "unibet (nl)": "Unibet", "unibet (it)": "Unibet", "unibet": "Unibet",
    "winamax (fr)": "Winamax", "winamax (de)": "Winamax", "leovegas (se)": "LeoVegas", "leovegas": "LeoVegas",
    "betclic (fr)": "Betclic", "betclic": "Betclic", "pmu (fr)": "PMU",
}


def normalize_book(name: str) -> str:
    if not name:
        return ""
    k = re.sub(r"\s+", " ", name.strip().lower())
    if "live" in k:
        return ""            # in-play feeds are not pre-match prices
    return ALIASES.get(k, name.strip())
