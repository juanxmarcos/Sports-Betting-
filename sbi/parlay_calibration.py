"""Joint-probability calibration evidence for parlays (issue #33, Phase B of #27).

A parlay's win probability is estimated as the product of its legs' probabilities. That is
only defensible if (a) the legs are close to independent and (b) the leg probabilities are
calibrated. This module measures both on SETTLED historical selections and decides, against
criteria fixed in code before looking at any result, whether the evidence is strong enough.

Method (walk-forward by construction: every selection in `data/backtest/bets_test.csv` was
made on the test seasons with parameters tuned on earlier seasons):
1. Group settled selections by America/New_York calendar day.
2. Inside each day, pair selections greedily in kick-off order into DISJOINT two-leg
   combinations (each selection used at most once) on different events, different
   competitions and with no shared team, i.e. the same screens a live parlay must pass.
3. Compare the observed number of combinations in which both legs won with the number the
   multiplied probabilities predict (Poisson-binomial mean and variance).

The evidence covers ONLY what it measured: the leagues the selections came from and two-leg
combinations. A live parlay whose legs come from other competitions, or with more legs, is
not covered and stays blocked. Nothing here changes a pick, a threshold or the ledger.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

METHOD = "parlay-joint-calibration-v1"
TIMEZONE = "America/New_York"

# Pre-registered pass criteria. Do not loosen these to make parlays appear: a change needs new
# out-of-sample evidence and owner review (docs/PARLAYS.md section 7).
MIN_COMBINATIONS = 200          # disjoint settled combinations, each selection used once
MAX_ABS_Z = 1.96                # observed joint wins within the 95% band of the prediction
MAX_LEG_ABS_Z = 1.96            # the legs themselves must be calibrated too
SUPPORTED_LEGS = 2              # only two-leg combinations are measured


def _bets_path() -> Path:
    return config.DATA_DIR / "backtest" / "bets_test.csv"


def _won(x: str) -> int | None:
    """1 = won, 0 = lost, None = push/void/half results (excluded: they are not a clean binary outcome)."""
    try:
        r = float(x)
    except (TypeError, ValueError):
        return None
    return 1 if r == 1.0 else (0 if r == -1.0 else None)


def load_selections(path: Path | None = None) -> list[dict]:
    p = path or _bets_path()
    if not p.exists():
        return []
    out = []
    with p.open(newline="") as f:
        for row in csv.DictReader(f):
            won = _won(row.get("result"))
            try:
                prob = float(row["final_q"])
                start = datetime.fromisoformat(row["date"])
            except (KeyError, TypeError, ValueError):
                continue
            if won is None or not 0.0 < prob < 1.0 or start.tzinfo is None:
                continue
            out.append({"event": str(row.get("event")), "league": row.get("div") or "", "start": start,
                        "teams": {str(row.get("home", "")).lower(), str(row.get("away", "")).lower()},
                        "prob": prob, "won": won})
    return out


def disjoint_pairs(selections: list[dict]) -> list[tuple[dict, dict]]:
    """Greedy, deterministic, kick-off order: each selection in at most one pair."""
    by_day = defaultdict(list)
    for s in selections:
        by_day[s["start"].astimezone(ZoneInfo(TIMEZONE)).date()].append(s)
    pairs = []
    for day in sorted(by_day):
        pool = sorted(by_day[day], key=lambda s: (s["start"], s["league"], s["event"]))
        used = set()
        for i, a in enumerate(pool):
            if i in used:
                continue
            for j in range(i + 1, len(pool)):
                b = pool[j]
                if j in used or a["event"] == b["event"] or a["league"] == b["league"] or a["teams"] & b["teams"]:
                    continue
                used.update((i, j))
                pairs.append((a, b))
                break
    return pairs


def _z(observed: float, expected: float, variance: float) -> float | None:
    return None if variance <= 0 else (observed - expected) / math.sqrt(variance)


def evaluate(selections: list[dict] | None = None) -> dict:
    """Calibration evidence plus a pass/fail verdict with the exact reasons."""
    sel = load_selections() if selections is None else selections
    pairs = disjoint_pairs(sel)
    joint = [a["prob"] * b["prob"] for a, b in pairs]
    obs = sum(a["won"] * b["won"] for a, b in pairs)
    exp = sum(joint)
    var = sum(p * (1 - p) for p in joint)
    legs = [s for pr in pairs for s in pr]
    leg_obs = sum(s["won"] for s in legs)
    leg_exp = sum(s["prob"] for s in legs)
    leg_var = sum(s["prob"] * (1 - s["prob"]) for s in legs)
    # Outcome correlation between paired legs (phi). Near zero is consistent with independence.
    phi = None
    if len(pairs) >= 3:
        xa = [a["won"] for a, _ in pairs]
        xb = [b["won"] for _, b in pairs]
        ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
        sa = math.sqrt(sum((x - ma) ** 2 for x in xa))
        sb = math.sqrt(sum((x - mb) ** 2 for x in xb))
        if sa > 0 and sb > 0:
            phi = sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / (sa * sb)
    z, leg_z = _z(obs, exp, var), _z(leg_obs, leg_exp, leg_var)

    reasons = []
    if len(pairs) < MIN_COMBINATIONS:
        reasons.append(f"only {len(pairs)} disjoint settled combinations; at least {MIN_COMBINATIONS} are required")
    if z is None or abs(z) > MAX_ABS_Z:
        reasons.append("observed joint wins are outside the 95% band of the multiplied probabilities"
                       if z is not None else "no joint outcomes to compare")
    if leg_z is None or abs(leg_z) > MAX_LEG_ABS_Z:
        reasons.append("leg probabilities are not calibrated on this sample" if leg_z is not None
                       else "no leg outcomes to compare")
    return {
        "method": METHOD, "source": "data/backtest/bets_test.csv (walk-forward test seasons)",
        "selections_settled": len(sel), "combinations": len(pairs), "legs_per_combination": SUPPORTED_LEGS,
        "joint_wins_observed": obs, "joint_wins_expected": round(exp, 2),
        "joint_z": None if z is None else round(z, 2),
        "leg_wins_observed": leg_obs, "leg_wins_expected": round(leg_exp, 2),
        "leg_z": None if leg_z is None else round(leg_z, 2),
        "outcome_correlation_phi": None if phi is None else round(phi, 3),
        "leagues": sorted({s["league"] for s in legs}),
        "criteria": {"min_combinations": MIN_COMBINATIONS, "max_abs_z": MAX_ABS_Z,
                     "max_leg_abs_z": MAX_LEG_ABS_Z, "supported_legs": SUPPORTED_LEGS},
        "passed": not reasons, "reasons": reasons,
    }


def coverage_problem(evidence: dict | None, legs: list[dict]) -> str | None:
    """Why `evidence` does not support a joint probability for these legs. None = supported."""
    if not evidence:
        return "no joint calibration evidence"
    if not evidence.get("passed"):
        return "joint calibration criteria not met"
    if len(legs) > int(evidence.get("legs_per_combination") or 0):
        return f"joint calibration measured only {evidence.get('legs_per_combination')}-leg combinations"
    covered = set(evidence.get("leagues") or [])
    if any(leg.get("league") not in covered for leg in legs):
        return "a leg's competition is outside the calibration evidence"
    return None
