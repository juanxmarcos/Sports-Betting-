"""Jeff Sackmann's ATP/WTA match archives, read from an UNOFFICIAL mirror (issue #45, owner decision on #39).

The original repositories (github.com/JeffSackmann/tennis_atp and tennis_wta) have returned 404
since about 2026-11-02. The owner chose to use a third-party copy:

    Hugging Face dataset ``Aneeshers/tennis-sackmann-archive`` (labelled cc-by-nc-sa-4.0),
    pinned to one revision so every download is the same bytes.

Integrity has NOT been verified against the original repositories (they are gone). What is
verified is that the files we use are the files recorded in ``data/tennis_sackmann/manifest.json``
(SHA-256 per file).

Licence: CC BY-NC-SA 4.0. Data compiled by Jeff Sackmann / Tennis Abstract. Doyen is a
non-commercial project (owner decision on #15). Raw CSVs are NOT committed: they are downloaded
on request into ``data/local/tennis_sackmann/`` (gitignored).

Scope: tour-level singles main draws only (``atp_matches_YYYY.csv``, ``wta_matches_YYYY.csv``).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .. import config

MIRROR_REPO = "Aneeshers/tennis-sackmann-archive"
MIRROR_PAGE = f"https://huggingface.co/datasets/{MIRROR_REPO}"
# Dataset revision (git commit on Hugging Face) read on 2026-11-17; its lastModified is 2026-06-25.
REVISION = "8ac86f7c62889b5d5c4cfec4c6403edcb8c5d993"
RESOLVE = "https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}"
TOURS = ("atp", "wta")
SEASONS = tuple(range(2010, 2027))
DOC_FILES = ("README.md", "LICENSE", "atp/UPSTREAM_README.md", "wta/UPSTREAM_README.md",
             "atp/matches_data_dictionary.txt")
ATTRIBUTION = ("Tennis match data compiled by Jeff Sackmann / Tennis Abstract "
               "(originally github.com/JeffSackmann/tennis_atp and tennis_wta), licensed CC BY-NC-SA 4.0 "
               "(https://creativecommons.org/licenses/by-nc-sa/4.0/). Read from an unofficial mirror; "
               "original repositories withdrawn by the author (404 since about 2026-11-02); "
               "integrity not verified against the original.")
CAVEAT = ("unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); "
          "integrity not verified against the original")

MANIFEST = config.DATA_DIR / "tennis_sackmann" / "manifest.json"
LOCAL_DIR = config.DATA_DIR / "local" / "tennis_sackmann"


def data_files(seasons=SEASONS) -> list[str]:
    return [f"{t}/{t}_matches_{y}.csv" for t in TOURS for y in seasons]


def url(path: str, rev: str = REVISION) -> str:
    return RESOLVE.format(repo=MIRROR_REPO, rev=rev, path=path)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text())


def verify(directory: Path = LOCAL_DIR, manifest: dict | None = None) -> dict:
    """Compare local files with the manifest checksums. Returns {"ok", "missing", "mismatch"}."""
    manifest = manifest if manifest is not None else load_manifest()
    missing, mismatch = [], []
    for path, meta in sorted(manifest["files"].items()):
        p = Path(directory) / path
        if not p.exists():
            missing.append(path)
        elif sha256_file(p) != meta["sha256"]:
            mismatch.append(path)
    return {"ok": not missing and not mismatch, "missing": missing, "mismatch": mismatch,
            "checked": len(manifest["files"])}


def download(directory: Path = LOCAL_DIR, manifest: dict | None = None, get=None,
             paths: list[str] | None = None) -> dict:
    """Download the pinned files. If a manifest is given, every file must match its checksum.

    ``get(url) -> bytes`` is injectable so tests never touch the network.
    Returns {path: {"sha256", "bytes", "url"}}.
    """
    if get is None:
        import requests

        def get(u):  # noqa: E306
            r = requests.get(u, headers={"User-Agent": config.USER_AGENT}, timeout=120)
            r.raise_for_status()
            return r.content
    paths = paths or (list(manifest["files"]) if manifest else list(DOC_FILES) + data_files())
    rev = (manifest or {}).get("revision", REVISION)
    out, bad = {}, []
    for path in paths:
        body = get(url(path, rev))
        digest = sha256_bytes(body)
        if manifest is not None and manifest["files"].get(path, {}).get("sha256") != digest:
            bad.append(path)
            continue
        p = Path(directory) / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        out[path] = {"sha256": digest, "bytes": len(body), "url": url(path, rev)}
    if bad:
        raise ValueError(f"checksum mismatch, files not written: {', '.join(bad)}")
    return out


def build_manifest(files: dict, downloaded_at: str | None = None) -> dict:
    return {"source": "Jeff Sackmann tennis_atp / tennis_wta (tour-level singles)",
            "mirror": MIRROR_PAGE, "mirror_repo": MIRROR_REPO, "revision": REVISION,
            "downloaded_at": downloaded_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "licence": "CC BY-NC-SA 4.0", "attribution": ATTRIBUTION, "label": CAVEAT,
            "files": {k: files[k] for k in sorted(files)}}


# ---------------------------------------------------------------- parsing

SURFACES = {"hard": "hard", "clay": "clay", "grass": "grass", "carpet": "hard"}


@dataclass
class Match:
    tour: str
    tourney_id: str
    tourney_name: str
    surface: str
    level: str
    tourney_date: date
    match_num: int
    round: str
    best_of: int
    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    score: str
    walkover: bool = False
    retired: bool = False
    source_file: str = ""

    @property
    def source_id(self) -> str:
        return f"{self.tour}:{self.tourney_id}:{self.match_num}"


def parse_csv(text: str, tour: str, source_file: str = "") -> tuple[list[Match], int]:
    """Parse one matches file. Returns (matches, rows_dropped)."""
    out, dropped = [], 0
    for r in csv.DictReader(io.StringIO(text)):
        try:
            wn, ln = (r.get("winner_name") or "").strip(), (r.get("loser_name") or "").strip()
            d = datetime.strptime(r["tourney_date"].strip(), "%Y%m%d").date()
            if not wn or not ln or not r.get("winner_id") or not r.get("loser_id"):
                raise ValueError("missing player")
            score = (r.get("score") or "").strip()
            up = score.upper()
            out.append(Match(tour=tour, tourney_id=r["tourney_id"].strip(), tourney_name=r["tourney_name"].strip(),
                             surface=SURFACES.get((r.get("surface") or "").strip().lower(), "hard"),
                             level=(r.get("tourney_level") or "").strip(), tourney_date=d,
                             match_num=int(r.get("match_num") or 0), round=(r.get("round") or "").strip(),
                             best_of=int(r.get("best_of") or 3), winner_id=r["winner_id"].strip(), winner_name=wn,
                             loser_id=r["loser_id"].strip(), loser_name=ln, score=score,
                             walkover=("W/O" in up or "WALKOVER" in up or up == ""),
                             retired=("RET" in up or "DEF" in up or "ABD" in up), source_file=source_file))
        except (KeyError, ValueError):
            dropped += 1
    return out, dropped


def load(directory: Path = LOCAL_DIR, seasons=SEASONS) -> tuple[list[Match], dict]:
    rows, stats = [], {"files": 0, "dropped": 0}
    for path in data_files(seasons):
        p = Path(directory) / path
        if not p.exists():
            continue
        tour = path.split("/")[0]
        ms, dropped = parse_csv(p.read_text(encoding="utf-8"), tour, path)
        rows += ms
        stats["files"] += 1
        stats["dropped"] += dropped
    rows.sort(key=lambda m: (m.tourney_date, m.tourney_id, m.match_num))
    return rows, stats


# ---------------------------------------------------------------- names

def norm_name(s: str) -> str:
    """Accent-, case- and punctuation-insensitive key: 'Stan Wawrinka' == 'stan  wawrinka'."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z ]+", " ", s.lower().replace("-", " ").replace("'", ""))
    return " ".join(s.split())


def short_key(s: str) -> str:
    """First initial + last token: 'Felix Auger Aliassime' -> 'f aliassime'."""
    t = norm_name(s).split()
    return f"{t[0][0]} {t[-1]}" if len(t) >= 2 else (t[0] if t else "")


@dataclass
class PlayerMap:
    """Maps Sackmann (tour, player_id) to the display name Doyen's ESPN events use."""
    by_id: dict = field(default_factory=dict)      # (tour, id) -> (espn_name, method)
    unmatched: dict = field(default_factory=dict)  # (tour, id) -> sackmann_name

    def espn(self, tour: str, pid: str) -> str | None:
        hit = self.by_id.get((tour, pid))
        return hit[0] if hit else None

    def key(self, tour: str, pid: str) -> str:
        """Elo key: the ESPN name when matched, otherwise a namespaced Sackmann id."""
        return self.espn(tour, pid) or f"sackmann:{tour}:{pid}"

    def rows(self, names: dict) -> list[dict]:
        out = [{"tour": t, "sackmann_id": pid, "sackmann_name": names.get((t, pid), ""), "espn_name": e, "method": how}
               for (t, pid), (e, how) in self.by_id.items()]
        return sorted(out, key=lambda r: (r["tour"], r["sackmann_name"]))


def build_player_map(sack: list[Match], espn_names: dict[str, set[str]]) -> tuple[PlayerMap, dict]:
    """espn_names: {tour: {display names seen in Doyen's ESPN tennis data}}.

    1. exact normalised name, unique on both sides within the tour;
    2. otherwise first initial + surname, only if unique on both sides.
    Anything ambiguous stays unmatched (never guessed).
    """
    names = {}
    for m in sack:
        names[(m.tour, m.winner_id)] = m.winner_name
        names[(m.tour, m.loser_id)] = m.loser_name
    pm = PlayerMap()
    # Doyen's ESPN feed labels women's matches at combined events (Slams, Indian Wells, Miami...) as "atp",
    # so ESPN names are pooled across both labels; uniqueness checks below still apply.
    espn = set().union(*espn_names.values()) if espn_names else set()
    for tour in TOURS:
        e_full, e_short = {}, {}
        for n in espn:
            e_full.setdefault(norm_name(n), set()).add(n)
            e_short.setdefault(short_key(n), set()).add(n)
        s_full, s_short = {}, {}
        for (t, pid), n in names.items():
            if t == tour:
                s_full.setdefault(norm_name(n), set()).add(pid)
                s_short.setdefault(short_key(n), set()).add(pid)
        used = set()
        for (t, pid), n in names.items():
            if t != tour:
                continue
            k = norm_name(n)
            if len(e_full.get(k, ())) == 1 and len(s_full.get(k, ())) == 1:
                e = next(iter(e_full[k]))
                pm.by_id[(t, pid)] = (e, "exact")
                used.add(e)
        for (t, pid), n in names.items():
            if t != tour or (t, pid) in pm.by_id:
                continue
            k = short_key(n)
            cand = e_short.get(k, set()) - used
            if len(cand) == 1 and len(s_short.get(k, ())) == 1 and len(e_short.get(k, ())) == 1:
                e = next(iter(cand))
                pm.by_id[(t, pid)] = (e, "initial+surname")
                used.add(e)
            elif (t, pid) not in pm.by_id:
                pm.unmatched[(t, pid)] = n
    tours_of = {}
    for (t, _pid), (e, _how) in pm.by_id.items():
        tours_of.setdefault(e, set()).add(t)
    for k in [k for k, (e, _how) in pm.by_id.items() if len(tours_of[e]) > 1]:   # same name on both tours: ambiguous
        pm.unmatched[k] = names[k]
        del pm.by_id[k]
    return pm, names


# ---------------------------------------------------------------- links to ESPN results

def link_matches(sack: list[Match], espn: list[dict], pm: PlayerMap, window_days: int = 21) -> dict:
    """Pair mirror matches with Doyen's completed ESPN matches, in two passes.

    Pass 1 (candidates): same unordered player pair (players mapped within the mirror's tour), ESPN date within
    [tourney_date - 3, tourney_date + window_days].
    Pass 2 (confirmation): the ESPN tournament must be the one most of that mirror tournament's
    candidates point to. This drops pairs that met in two nearby events (e.g. Indian Wells and Miami).
    Returns confirmed links, winner disagreements among them, and the number of candidates rejected.
    """
    cand = _candidate_links(sack, espn, pm, window_days)
    votes = {}
    for r in cand:
        v = votes.setdefault((r["tour"], r["sackmann_id"].rsplit(":", 1)[0]), {})
        v[r["espn_event"]] = v.get(r["espn_event"], 0) + 1
    best = {k: max(v.items(), key=lambda kv: (kv[1], kv[0]))[0] for k, v in votes.items()}
    links = [r for r in cand if best[(r["tour"], r["sackmann_id"].rsplit(":", 1)[0])] == r["espn_event"]]
    return {"links": links, "disagreements": [r for r in links if r["winner_espn"] != r["winner_sackmann"]],
            "rejected_other_tournament": len(cand) - len(links), "candidates": len(cand)}


def _candidate_links(sack, espn, pm, window_days) -> list[dict]:
    idx = {}
    for e in espn:
        if not (e.get("completed") and e.get("winner")) or e.get("walkover"):
            continue
        idx.setdefault(frozenset((e["p1"], e["p2"])), []).append(e)   # ESPN tour label not trusted (see build_player_map)
    links, used = [], set()
    for m in sack:
        if m.walkover:
            continue
        w, l = pm.espn(m.tour, m.winner_id), pm.espn(m.tour, m.loser_id)
        if not w or not l:
            continue
        best = None
        for e in idx.get(frozenset((w, l)), []):
            d = (e["date"].date() - m.tourney_date).days
            if -3 <= d <= window_days and e["id"] not in used:
                if best is None or d < (best["date"].date() - m.tourney_date).days:
                    best = e
        if best is None:
            continue
        used.add(best["id"])
        rec = {"tour": m.tour, "sackmann_id": m.source_id, "espn_id": best["id"], "date": best["date"].date().isoformat(),
               "sackmann_tournament": m.tourney_name, "espn_tournament": best["tournament"],
               "espn_event": str(best.get("event_id_espn") or best["tournament"]),
               "winner_sackmann": w, "winner_espn": best["winner"], "retired": m.retired}
        links.append(rec)
    return links


def tournament_map(links: list[dict]) -> list[dict]:
    """Majority ESPN tournament name per (tour, Sackmann tournament name)."""
    votes = {}
    for r in links:
        votes.setdefault((r["tour"], r["sackmann_tournament"]), {}).setdefault(r["espn_tournament"], 0)
        votes[(r["tour"], r["sackmann_tournament"])][r["espn_tournament"]] += 1
    out = []
    for (t, s), v in sorted(votes.items()):
        e, n = max(v.items(), key=lambda kv: (kv[1], kv[0]))
        out.append({"tour": t, "sackmann_tournament": s, "espn_tournament": e, "linked_matches": n,
                    "share": round(n / sum(v.values()), 3)})
    return out
