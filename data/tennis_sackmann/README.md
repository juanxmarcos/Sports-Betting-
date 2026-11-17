# Tennis history: Sackmann archive (unofficial mirror)

**Unofficial mirror; original repositories withdrawn by the author (404 since about 2026-11-02); integrity not verified against the original.**

Files here are derived by `python -m sbi tennis-history` (issue #45) from Jeff Sackmann's tour-level
ATP/WTA match results, read from the Hugging Face dataset `Aneeshers/tennis-sackmann-archive` at the
revision pinned in `manifest.json`. Raw CSVs are not committed (they go to `data/local/tennis_sackmann/`).

- `manifest.json`: mirror URL, revision, download date, licence, label and SHA-256 per file.
- `player_map.csv`: Sackmann player ID ↔ the ESPN display name Doyen uses (exact or initial+surname; ambiguous names left out).
- `tournament_map.csv`: Sackmann tournament name ↔ ESPN tournament name, by majority of linked matches.
- `match_links.csv`: Sackmann match ID (`tour:tourney_id:match_num`) ↔ ESPN match ID.
- `coverage.json`: coverage, sanity check, walk-forward and decision (see `reports/tennis_history.md`).

Data compiled by **Jeff Sackmann / Tennis Abstract** (originally github.com/JeffSackmann/tennis_atp and
tennis_wta). Licence: **CC BY-NC-SA 4.0** (https://creativecommons.org/licenses/by-nc-sa/4.0/). These
derived files are shared under the same licence. Research only; the live tennis model does not use them.
