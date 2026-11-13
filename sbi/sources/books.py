"""Bookmaker name normalisation so the same bookmaker from two feeds counts once.

Bookmaker independence matters for the "3+ bookmakers" rule: ESPN's "Bet 365" and The
Odds API's "Bet365" are one bookmaker; regional skins of the same book are merged; live
in-play feeds are excluded from pre-match odds.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CHECKED = "2026-11-13"   # date the REGISTRY sources below were last checked

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


# ---------- rule v1 ("legacy") map: FROZEN ----------
# Bookmakers that share an owner or a trading/pricing platform tend to quote the SAME prices,
# so they are one piece of evidence for the "3+ independent bookmakers" rule. Best-effort map;
# under rule v1 a bookmaker missing from it is treated as independent. This map is the unchanged
# baseline that rule v2 is measured against: do not edit it. New knowledge goes in REGISTRY below.
GROUPS = {
    "Betsson": "Betsson Group", "Nordic Bet": "Betsson Group", "NordicBet": "Betsson Group", "Betsafe": "Betsson Group",
    "Coral": "Entain", "Ladbrokes": "Entain", "Bwin": "Entain", "Sportingbet": "Entain", "BetMGM": "Entain",
    "Paddy Power": "Flutter", "Betfair Sportsbook": "Flutter", "FanDuel": "Flutter", "Sky Bet": "Flutter",
    "Unibet": "Kambi", "LeoVegas": "Kambi", "BetRivers": "Kambi", "Paf": "Kambi",
    "William Hill": "evoke", "888sport": "evoke",
    "BetOnline.ag": "BetOnline", "Sportsbetting.ag": "BetOnline", "LowVig.ag": "BetOnline",
    "Winamax": "Winamax", "Bet365": "Bet365", "Pinnacle": "Pinnacle", "Betfair Exchange": "Betfair Exchange",
}


def group_of(bookmaker: str) -> str:
    return GROUPS.get(bookmaker, bookmaker)


# ---------- rule v2 ("verified") registry ----------
@dataclass(frozen=True)
class Book:
    group: str        # the operator that counts ONCE: brands sharing an owner OR a price origin are merged
    verified: bool    # True only if owner and price origin are both backed by the source below
    owner: str        # ultimate owner / operating group
    pricing: str      # who originates the sportsbook prices (in-house trading, or a platform vendor)
    source: str       # citation for the price origin (the fact that matters most for independence)
    owner_source: str  # citation for the owner
    evidence: str     # best grade among the citations: official | regulator | trade press | none
    opened: bool      # False: the page blocked automated reading and was seen only as a search summary
    checked: str      # date of the check (ownership and platforms change: re-check, do not assume)
    note: str = ""


def _b(group, verified, owner, pricing, source, owner_source, evidence, opened=False, note=""):
    return Book(group, verified, owner, pricing, source, owner_source, evidence, opened, CHECKED, note)


# How to read this table.
# * verified=True means BOTH the owner and the price origin have a citation below. It does not
#   mean the prices were shown to be independently originated: see reports/independence_audit.md
#   for the measured identical-price shares, and treat "trade press" / opened=False rows as the
#   weakest verified rows, to be re-checked by a person before rule v2 goes live.
# * group merges brands that share a price origin, or share an owner while pricing in-house.
#   When in doubt brands are merged (merging can only lower the count).
# * verified=False rows are listed so the gap is visible. They never count under rule v2.
_KAMBI = "https://www.inderes.fi/releases/kambi-group-plc-and-leovegas-group-sign-turnkey-sportsbook-extension-and-new-odds-feed-agreement"
_FLUTTER_UKGC = "https://www.gamblingcommission.gov.uk/about-us/freedomofinformation/flutter-licences"
_FLUTTER_Q4 = "https://flutter.com/media/hdshhrmb/q4-2025-earnings-release.pdf"
_BETSSON = "https://www.betssonab.com/what-we-do"
_ENTAIN = "https://www.lobbyregister.bundestag.de/media/9d/de/842909/Entain_Annual-Report_2025.pdf"
_EVOKE = "https://www.evokeplc.com/who-we-are/our-history/"
_BANIJAY = "https://igamingbusiness.com/strategy/ma/banijay-group-majority-stake-tipico-betclic/"
_LOUISIANA = "https://lgcb.dps.louisiana.gov/illegal-operators/"
_ENTAIN_NOTE = "Entain technology is cited; one trading team across all Entain brands is not explicitly sourced. Merged anyway."


REGISTRY: dict[str, Book] = {
    # --- sharp references ---
    "Pinnacle": _b("Pinnacle", True, "Ragnarok Corporation N.V. (per a review site; beneficial owners not confirmed)",
                   "in-house; also sells its odds to other operators (Pinnacle Solution)",
                   "https://sbcnews.co.uk/europe/2018/04/30/new-muscle-pinnacle-launches-b2b-platform/",
                   "https://www.gambling.com/ca/sportsbooks/reviews/pinnacle", "trade press",
                   note="Other bookmakers may carry Pinnacle-derived prices, which no ownership map can detect."),
    "Betfair Exchange": _b("Betfair Exchange", True, "Flutter Entertainment (Betfair Ltd)", "exchange: prices set by users",
                           _FLUTTER_UKGC, _FLUTTER_UKGC, "regulator", True,
                           note="Owned by Flutter but not priced by Flutter's traders, so it is kept apart from the "
                                "Flutter sportsbooks (as in rule v1)."),
    # --- single-brand operators ---
    "Bet365": _b("Bet365", True, "bet365 Group (Coates family)", "largely in-house",
                 "https://kansspelautoriteit.nl/publish/library/17/overview_of_the_online_gambling_b2b_market_-_regulus_partners.pdf",
                 "https://sbcnews.co.uk/tag/john-coates/", "trade press"),
    "Winamax": _b("Winamax", True, "Winamax SAS (private)", "in-house",
                  "https://gamingandco.substack.com/p/french-bookmakers-overround-and-margin",
                  "https://rubypayeur.com/societe/winamax-492155932", "trade press"),
    "DraftKings": _b("DraftKings", True, "DraftKings Inc. (Nasdaq: DKNG)", "in-house (ex-SBTech); off Kambi since Q3 2021",
                     "https://www.sec.gov/Archives/edgar/data/1772757/000177275721000031/dkng-110521x8xkexx991.htm",
                     "https://www.sec.gov/Archives/edgar/data/1772757/000177275721000031/dkng-110521x8xkexx991.htm", "official",
                     note="ESPN's displayed odds are DraftKings odds: the two feeds are one bookmaker."),
    "Matchbook": _b("Matchbook", True, "Triplebet Ltd (UKGC account 39504)", "exchange: prices set by users and market makers",
                    "https://www.gamblingcommission.gov.uk/public-register/business/detail/39504",
                    "https://www.gamblingcommission.gov.uk/public-register/business/detail/39504", "regulator", True),
    "BetVictor": _b("BetVictor", True, "BVGroup (private; ultimate shareholder not confirmed)", "in-house; some props bought in",
                    "https://igamingfuture.com/wsf-odds-partners-with-bvgroup-to-power-betvictor-props/",
                    "https://sbcnews.co.uk/sportsbook/2023/06/14/betvictor-rebrands-bvgroup/", "trade press"),
    "Betfred": _b("Betfred", True, "Betfred Group; online entity Petfre (Gibraltar) Ltd (UKGC account 39544)",
                  "in-house platform (ex-Sharp Gaming)",
                  "https://sbcnews.co.uk/sportsbook/2024/05/15/betfred-sharpgaming-rebrand/",
                  "https://www.gamblingcommission.gov.uk/public-register/business/detail/39544", "regulator"),
    "Coolbet": _b("Coolbet", True, "GAN Ltd (reported as owned by Sega Sammy since 2025; close not officially confirmed)",
                  "in-house proprietary sportsbook",
                  "https://europeangaming.eu/portal/latest-news/2020/11/18/81724/gan-signs-agreement-to-acquire-coolbet",
                  "https://europeangaming.eu/portal/latest-news/2020/11/18/81724/gan-signs-agreement-to-acquire-coolbet",
                  "trade press", note="The price-origin source dates from 2020."),
    "Caesars": _b("Caesars", True, "Caesars Entertainment", "in-house (Liberty platform)",
                  "https://www.boardroomalpha.com/sec/czr-10-k-2026-02-17-0001590895-26-000011",
                  "https://www.boardroomalpha.com/sec/czr-10-k-2026-02-17-0001590895-26-000011", "official",
                  note="10-K read through an aggregator. Includes William Hill US."),
    "ESPN BET": _b("PENN", True, "PENN Entertainment", "in-house (theScore Bet risk and trading platform)",
                   "https://sbcamericas.com/2022/07/26/thescore-bet-launches-in-house-sportsbook-risk-and-trading-platform/",
                   "https://espnpressroom.com/press-release/espn-and-draftkings-enter-multi-year-agreement/", "trade press",
                   note="Rebranded theScore Bet on 2025-12-01; treat both names as one bookmaker."),
    # --- Banijay Gaming: one owner since April 2026, platforms reported as separate. Merged (conservative). ---
    "Betclic": _b("Banijay Gaming", True, "Banijay Gaming (Banijay Group)", "in-house proprietary platform",
                  _BANIJAY, "https://group.banijay.com/who-we-are/", "trade press"),
    "Tipico": _b("Banijay Gaming", True, "Banijay Gaming (65% since 2026-04-23)", "in-house platform and trading",
                 _BANIJAY, "https://live.euronext.com/en/products/equities/company-news/2026-04-23-banijay-group-completes-acquisition-tipico-group",
                 "trade press", note="No evidence that Tipico and Betclic trading have merged; counted once anyway."),
    # --- Betsson AB: shared in-house sportsbook ---
    **{n: _b("Betsson Group", True, "Betsson AB", "shared in-house sportsbook", _BETSSON, _BETSSON, "official", True)
       for n in ("Betsson", "Nordic Bet", "NordicBet", "Betsafe")},
    # --- Entain ---
    **{n: _b("Entain", True, "Entain plc", "Entain proprietary technology", _ENTAIN, _ENTAIN, "official", note=_ENTAIN_NOTE)
       for n in ("Coral", "Ladbrokes", "Bwin", "Sportingbet")},
    "BetMGM": _b("Entain", True, "Entain / MGM Resorts 50-50 joint venture (US)", "Entain technology (plus Angstrom for parlays)",
                 "https://www.legalsportsreport.com/124767/entain-to-help-betmgm-angstrom-sports-purchase/", _ENTAIN, "official",
                 note="BetMGM UK is a different book: it is run by LeoVegas on its own platform."),
    # --- Flutter sportsbooks ---
    **{n: _b("Flutter", True, "Flutter Entertainment", "Flutter in-house (shared UK and Ireland platform)",
             _FLUTTER_Q4, _FLUTTER_UKGC, "regulator", True) for n in ("Paddy Power", "Betfair Sportsbook", "Sky Bet")},
    "FanDuel": _b("Flutter", True, "Flutter Entertainment", "Flutter / FanDuel proprietary pricing",
                  "https://flutter.com/media/2yacvpj1/q1-2025-shareholder-letter-website.pdf", _FLUTTER_UKGC, "official",
                  note="Whether FanDuel prices are separate from the UK and Ireland brands is not sourced; counted once."),
    # --- Kambi-priced books (turnkey or odds feed) ---
    "Unibet": _b("Kambi", True, "FDJ United (ex-Kindred)", "Kambi turnkey or Kambi odds feed, depending on the market",
                 "https://igamingbusiness.com/tech-innovation/fdj-united-accelerates-internalised-tech-stack-rollout/",
                 "https://www.fdjunited.com/presse/fdjs-tender-offer-for-kindred-succeeds-creating-a-european-gaming-champion/",
                 "trade press", True,
                 note="Moving to an in-house platform market by market (target end 2027), but even migrated markets take "
                      "Kambi's odds feed, so it is not independent of Kambi anywhere as of February 2026."),
    "LeoVegas": _b("Kambi", True, "MGM Resorts", "Kambi turnkey in most markets; in-house 'Tiger' in DK, BR, SE and UK",
                   _KAMBI, _KAMBI, "official", True,
                   note="Where Tiger is live LeoVegas may price itself; the stored feed does not say which market a quote "
                        "is from, so it stays in the Kambi group (conservative, and unchanged from rule v1)."),
    "BetRivers": _b("Kambi", True, "Rush Street Interactive", "Kambi (trading and risk)",
                    "https://mfn.se/a/kambi-group/kambi-group-plc-and-rush-street-interactive-agree-to-a-multi-year-sportsbook-partnership-extension",
                    "https://mfn.se/a/kambi-group/kambi-group-plc-and-rush-street-interactive-agree-to-a-multi-year-sportsbook-partnership-extension",
                    "official", True),
    "Paf": _b("Kambi", True, "Government of Åland (owner source is weak)", "Kambi turnkey",
              "https://www.inderes.fi/releases/kambi-group-plc-and-paf-sign-long-term-sportsbook-partnership-extension",
              "https://www.inderes.fi/releases/kambi-group-plc-and-paf-sign-long-term-sportsbook-partnership-extension", "official", True),
    "PMU": _b("Kambi", True, "PMU (French racing GIE)", "Kambi turnkey (pricing, trading, risk), signed 2026-03-31",
              "https://www.inderes.fi/en/releases/kambi-group-plc-signs-long-term-turnkey-sportsbook-partnership-with-french-leading-betting-operator-pmur",
              "https://entreprise.pmu.fr/le-e-commerce", "official", True,
              note="Rule v1 counted PMU as its own operator. The release gives no go-live date; counted with Kambi."),
    # --- evoke ---
    **{n: _b("evoke", True, "evoke plc", "in-house", _EVOKE, _EVOKE, "official", True,
             note="One owner; a shared trading team is not sourced. Counted once. Sale to Bally's Intralot agreed "
                  "June 2026, not completed.") for n in ("William Hill", "888sport")},
    # --- NOT verified: listed so the gap is visible; never counted under rule v2 ---
    "1xBet": _b("", False, "disputed (Caecus N.V. holds the Curaçao licence)", "not found", "", "", "none"),
    "BetAnything": _b("", False, "not found (formerly BetAnySports)", "not found", "", _LOUISIANA, "none"),
    "GTbets": _b("", False, "not found", "not found", "", _LOUISIANA, "none"),
    "Everygame": _b("", False, "CitoPedia N.V. (per the Louisiana regulator's list)", "not found", "", _LOUISIANA, "regulator", True),
    "MyBookie.ag": _b("", False, "Duranbah Limited N.V. (per the Michigan regulator, via press)", "not found", "",
                      "https://www.fox2detroit.com/news/state-orders-gambling-website-cease-operations-michigan", "trade press"),
    "Marathon Bet": _b("", False, "Panbet Curacao N.V.", "in-house according to a 2016 profile only (too old to rely on)",
                       "https://sbcnews.co.uk/europe/2016/09/06/bos-speaker-profile-viktor-hoffman-marathonbet-test-legacy-tackling-future-industry-change/",
                       "https://sbcnews.co.uk/tag/panbet/", "trade press"),
    "Codere (IT)": _b("", False, "Codere Online Luxembourg S.A. (Nasdaq-listed)",
                      "group trading team per older filings; not confirmed for the Italian site (launched October 2025)",
                      "https://www.sec.gov/Archives/edgar/data/0001866782/000182912626004041/codereonline_20f.htm",
                      "https://www.sec.gov/Archives/edgar/data/0001866782/000182912626004041/codereonline_20f.htm", "official"),
    **{n: _b("", False, "one operator according to affiliate sites only; legal entity names conflict", "not found", "", "", "none")
       for n in ("BetOnline.ag", "Sportsbetting.ag", "LowVig.ag")},
    "Bovada": _b("", False, "Harp Media B.V. (per the Louisiana regulator's list)", "not found", "", _LOUISIANA, "regulator", True),
    "BetUS": _b("", False, "named 'Milvus' in a Florida regulator letter (via press)", "not found", "",
                "https://cdcgaming.com/florida-gaming-commission-sends-cease-and-desist-letter-to-three-overseas-operators/", "trade press"),
}


def verified_group(bookmaker: str) -> str | None:
    """The verified operator behind a (normalised) bookmaker name, or None.

    None means "not verified", which is NOT the same as "independent": such a bookmaker is never
    counted toward the 3-bookmaker gate under rule v2 and never feeds its market reference."""
    b = REGISTRY.get(bookmaker)
    return b.group if b and b.verified else None
