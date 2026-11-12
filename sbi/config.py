"""Central configuration. Everything tunable lives here or in env vars.

No secrets are stored in this file. Optional credentials (e.g. ODDS_API_KEY for
The Odds API free tier) are read from the environment only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SBI_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("SBI_DB", DATA_DIR / "sbi.sqlite"))
REPORTS_DIR = Path(os.environ.get("SBI_REPORTS_DIR", ROOT / "reports"))
SITE_DIR = Path(os.environ.get("SBI_SITE_DIR", ROOT / "docs" / "dashboard"))
CACHE_DIR = DATA_DIR / "cache"

# Display timezone for reports/dashboard (IANA name). Storage is always UTC.
TIMEZONE = os.environ.get("SBI_TIMEZONE", "America/New_York")  # US Eastern (EST/EDT)

USER_AGENT = "sbi-research/0.1 (personal non-commercial research)"

# football-data.co.uk division codes -> human names. These leagues all appear
# in football-data's free fixtures.csv with multi-bookmaker odds.
FOOTBALL_LEAGUES: dict[str, str] = {
    "E0": "England Premier League",
    "E1": "England Championship",
    "SP1": "Spain La Liga",
    "D1": "Germany Bundesliga",
    "I1": "Italy Serie A",
    "F1": "France Ligue 1",
    "N1": "Netherlands Eredivisie",
    "P1": "Portugal Primeira Liga",
    "B1": "Belgium Pro League",
    "SC0": "Scotland Premiership",
}


@dataclass
class SelectionRules:
    """Conservative filters applied before anything is published.

    Rationale for each default is documented in docs/METHODOLOGY.md.
    """
    min_ev: float = 0.03            # point-estimate EV must be >= 3%
    min_ev_lower: float = 0.0       # EV at the pessimistic (10th pct) prob must be > 0
    min_odds: float = 1.30
    max_odds: float = 6.00          # longshots: model error dominates
    min_team_matches: int = 12      # per team, in the training window
    max_prob_sd: float = 0.06       # parameter-uncertainty sd of the model prob
    min_bookmakers: int = 3         # consensus needs >= 3 prices
    max_odds_age_hours: float = 96  # older odds snapshots flagged as stale -> excluded
    exchange_commission: float = 0.05  # applied to Betfair Exchange prices
    max_per_event: int = 1          # one selection per event (markets are correlated)
    stake_units: float = 1.0        # fixed-unit staking only
    max_daily_units: float = 10.0
    markets: tuple = ("1X2", "OU", "AH")


@dataclass
class ModelConfig:
    model_version: str = "dc-0.1"
    xi: float = 0.0019              # time-decay per day (overwritten by tuned value if present)
    ridge: float = 2.0              # L2 shrinkage on attack/defence
    lookback_days: int = 3 * 365
    max_goals: int = 10
    n_param_draws: int = 300
    # Linear pool weight on the model vs de-vigged market consensus, per market.
    # Overwritten by data/tuned.json produced by `sbi backtest`.
    blend_weight: dict = field(default_factory=lambda: {"1X2": 0.0, "OU": 0.0, "AH": 0.0})


@dataclass
class Simulator:
    bankroll_units: float = 100.0


RULES = SelectionRules()
MODEL = ModelConfig()
SIM = Simulator()


def load_tuned() -> None:
    """Apply hyperparameters selected by the out-of-sample backtest, if any."""
    import json
    p = DATA_DIR / "tuned.json"
    if p.exists():
        t = json.loads(p.read_text())
        MODEL.xi = t.get("xi", MODEL.xi)
        MODEL.ridge = t.get("ridge", MODEL.ridge)
        MODEL.blend_weight.update(t.get("blend_weight", {}))
