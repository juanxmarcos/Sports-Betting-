# ESPN tennis scoreboard fixtures (issue #49)

Trimmed copies of real responses from ESPN's public tennis scoreboard, recorded 2026-11-17:

- `atp_20250601_roland_garros.json`: `.../sports/tennis/atp/scoreboard?dates=20250601`
- `atp_20250428_madrid.json`: `.../sports/tennis/atp/scoreboard?dates=20250428`

Both come from the **atp** endpoint, yet each holds the women's singles draw too: this is why the
endpoint cannot be used as the tour label. Only one completed main-draw match per draw is kept, and
only the fields `sbi/tennis.py` reads (names, winners, set scores, round, status, draw type).
Nothing was edited apart from removing fields and matches.
