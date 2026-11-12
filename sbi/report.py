"""Daily Betting Intelligence Report (Markdown). Publishes 'No qualifying
opportunities today' when nothing passes the rules - never fills a quota."""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment

from . import config
from .performance import rec_metrics

SEL_NAMES = {"H": "Home win", "D": "Draw", "A": "Away win", "over": "Over", "under": "Under"}


def local(ts: str | None) -> str:
    if not ts:
        return "n/a"
    return datetime.fromisoformat(ts).astimezone(ZoneInfo(config.TIMEZONE)).strftime("%a %d %b %H:%M %Z")


def describe(r) -> str:
    m, s, ln = r["market"], r["selection"], r["line"]
    if m == "1X2":
        return {"H": f"{r['home']} to win", "D": "Draw", "A": f"{r['away']} to win"}[s]
    if m == "OU":
        return f"{SEL_NAMES[s]} {ln:g} goals"
    if m == "AH":
        team, h = (r["home"], ln) if s == "home" else (r["away"], -ln)
        return f"{team} {h:+g} (Asian handicap)"
    return f"{m} {s} {ln}"


TEMPLATE = r"""# Daily Betting Intelligence Report — {{ date }}

*Research and paper-trading only. Not financial advice. No bets are placed automatically.
All times {{ tz }}. Generated {{ generated }}. Model `{{ model_version }}`.*

## Daily overview

| Item | Value |
|---|---|
| Events in 48h window | {{ s.events_in_window }} |
| Events analysed (model + odds) | {{ s.analysed_events }} |
| Leagues covered | {{ leagues or "none" }} |
| Qualifying opportunities | **{{ recs|length }}** |
| Highest estimated EV | {{ best_ev }} |
| Blend weight on model (1X2/OU/AH) | {{ blend }} |

{% if warnings %}**Data warnings**
{% for w in warnings %}- {{ w }}
{% endfor %}{% endif %}

{% if not recs %}
## No qualifying opportunities today

Nothing passed the selection rules (minimum EV {{ "%.0f"|format(rules.min_ev*100) }}%, positive EV at
the pessimistic 10th-percentile probability, at least {{ rules.min_bookmakers }} bookmakers, odds
{{ rules.min_odds }}–{{ rules.max_odds }}, at least {{ rules.min_team_matches }} matches per team, fresh odds).
No pick is better than a weak pick.
{% else %}
## Ranked selections

Ranking: by **pessimistic EV** (EV computed with the 10th-percentile model probability from
parameter uncertainty), so that thinly estimated edges rank below robust ones.

{% for r in recs %}
### {{ loop.index }}. {{ r.desc }} — {{ r.home }} v {{ r.away }}

| Field | Value |
|---|---|
| Sport / competition | Football — {{ r.league_name }} |
| Kick-off | {{ r.ko }} |
| Market / selection | {{ r.market }} — **{{ r.desc }}** |
| Best price | **{{ "%.2f"|format(r.odds) }}** @ {{ r.bookmaker }}{% if r.net_odds != r.odds %} (net {{ "%.3f"|format(r.net_odds) }} after commission){% endif %} |
| Model probability (raw) | {{ "%.1f"|format(r.model_prob*100) }}% (±{{ "%.1f"|format((r.prob_sd or 0)*100) }} pp param. sd; p10 {{ "%.1f"|format(r.ev_d.model_q_p10*100) }}%) |
| Market no-vig probability | {{ "%.1f"|format(r.market_prob*100) if r.market_prob is not none else "n/a" }}% ({{ r.ev_d.consensus_source }}) |
| Final probability (blend) | {{ "%.1f"|format(r.final_prob*100) }}% |
| Fair odds | {{ "%.2f"|format(r.fair_odds) }} |
| Expected value | **{{ "%+.1f"|format(r.ev*100) }}%** (pessimistic {{ "%+.1f"|format(r.ev_lower*100) }}%) |
| Stake (paper) | {{ r.stake_units }} unit |
| Bookmakers quoting | {{ r.ev_d.n_bookmakers }} |
| Odds snapshot | {{ r.odds_ts }} |

**Statistical evidence.** Expected goals {{ r.ev_d.expected_goals.home }}–{{ r.ev_d.expected_goals.away }};
model strength rank {{ r.ev_d.strength_rank.home }} vs {{ r.ev_d.strength_rank.away }} (of {{ r.ev_d.strength_rank.of }}).
Recent form — {{ r.home }}: {{ r.form_h.last }} (GF {{ r.form_h.gf }}, GA {{ r.form_h.ga }}{% if r.form_h.xg_for_avg is defined %}, xG {{ r.form_h.xg_for_avg }}/{{ r.form_h.xg_against_avg }}{% endif %});
{{ r.away }}: {{ r.form_a.last }} (GF {{ r.form_a.gf }}, GA {{ r.form_a.ga }}{% if r.form_a.xg_for_avg is defined %}, xG {{ r.form_a.xg_for_avg }}/{{ r.form_a.xg_against_avg }}{% endif %}).
Model 1X2: {{ "%.0f"|format(r.ev_d.model_markets["1X2:H"]*100) }}/{{ "%.0f"|format(r.ev_d.model_markets["1X2:D"]*100) }}/{{ "%.0f"|format(r.ev_d.model_markets["1X2:A"]*100) }}%,
O2.5 {{ "%.0f"|format(r.ev_d.model_markets["OU:over:2.5"]*100) }}%, BTTS {{ "%.0f"|format(r.ev_d.model_markets["BTTS:yes"]*100) }}%.

**Why it may be value.** The best available price ({{ "%.2f"|format(r.odds) }}) exceeds the estimated fair
price ({{ "%.2f"|format(r.fair_odds) }}). {% if r.market_prob is not none and r.model_prob > r.market_prob %}The
model rates this outcome {{ "%.1f"|format((r.model_prob-r.market_prob)*100) }} pp above the de-vigged consensus.{% else %}The edge
comes mainly from the price being out of line with the consensus of other bookmakers.{% endif %}

**Context / research flags.** {% if r.notes %}{% for n in r.notes %}
- [{{ n.evidence_type }} · {{ n.category }} · {{ n.direction }}] {{ n.claim }}{% if n.source_url %} ([source]({{ n.source_url }}), {{ n.retrieved_at }}){% endif %}{% endfor %}
{% else %}No contextual research recorded yet (team news is not modelled — check before acting).{% endif %}

**Reasons this could be wrong.**
{% for x in r.ev_d.risks %}- {{ x }}
{% endfor %}
Sources: {% for u in r.urls %}<{{ u }}> {% endfor %}

{% endfor %}
{% endif %}

## Closest candidates (transparency)

| Match | Market | Odds | Final p | EV | Pess. EV | Status |
|---|---|---|---|---|---|---|
{% for c in s.top_candidates[:10] %}| {{ c.match }} ({{ c.league }}) | {{ c.market }} {{ c.selection }}{% if c.line is not none %} {{ c.line }}{% endif %} | {{ "%.2f"|format(c.odds) }} {{ c.bookmaker }} | {{ "%.1f"|format(c.final_q*100) }}% | {{ "%+.1f"|format(c.ev*100) }}% | {{ "%+.1f"|format(c.ev_lower*100) }}% | {{ c.reason }} |
{% endfor %}

## Track record (paper, fixed 1-unit stakes)

{% if perf.settled %}Settled {{ perf.settled }} · W {{ perf.won }} / L {{ perf.lost }} / P {{ perf.push }} ·
profit {{ "%+.2f"|format(perf.profit_units) }}u · yield {{ "%+.1f"|format(perf.yield*100) }}%
(95% CI {{ "%+.1f"|format(perf.yield_ci95[0]*100) }}% to {{ "%+.1f"|format(perf.yield_ci95[1]*100) }}%) ·
avg CLV {{ "%+.1f"|format((perf.avg_clv or 0)*100) }}% · max drawdown {{ perf.max_drawdown_units }}u.
{% endif %}*{{ perf.sample_warning }}*
"""


def write_daily(con, now: datetime, s: dict):
    day = now.astimezone(ZoneInfo(config.TIMEZONE)).strftime("%Y-%m-%d")
    rows = con.execute("SELECT * FROM recommendations WHERE substr(published_at,1,10)=? ORDER BY rank",
                       (now.strftime("%Y-%m-%d"),)).fetchall()
    recs = []
    for r in rows:
        d = dict(r)
        e = json.loads(r["evidence_json"] or "{}")
        d.update(desc=describe(r), ko=local(r["kickoff_utc"]), ev_d=e,
                 league_name=config.FOOTBALL_LEAGUES.get(r["league"], r["league"]),
                 net_odds=e.get("net_odds", r["odds"]), odds_ts=local(r["odds_retrieved_at"]),
                 form_h=e["form"][r["home"]], form_a=e["form"][r["away"]],
                 urls=json.loads(r["source_urls"] or "[]"),
                 notes=[dict(n) for n in con.execute("SELECT * FROM research_notes WHERE event_id=? ORDER BY id",
                                                     (r["event_id"],))])
        recs.append(d)
    md = Environment(trim_blocks=False).from_string(TEMPLATE).render(
        date=day, tz=config.TIMEZONE, generated=local(now.isoformat()), model_version=config.MODEL.model_version,
        s={"top_candidates": [], "analysed_events": 0, "events_in_window": 0, **s},
        leagues=", ".join(config.FOOTBALL_LEAGUES.get(k, k) for k in s.get("leagues", {})),
        recs=recs, best_ev=(f"{max(r['ev'] for r in recs) * 100:+.1f}%" if recs else "—"),
        blend="/".join(f"{config.MODEL.blend_weight.get(k, 0):.2f}" for k in ("1X2", "OU", "AH")),
        warnings=s.get("warnings", [])[:25], rules=config.RULES, perf=rec_metrics(con))
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    p = config.REPORTS_DIR / f"{day}.md"
    p.write_text(md)
    (config.REPORTS_DIR / "latest.md").write_text(md)
    return p
