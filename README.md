# LocalSunoDb v1.05

Clean LocalSunoDb repository baseline.

## Start

The database file is intentionally not included in this ZIP.
Place `suno_finder_v4.db` in the repository root, next to `LocalSunoDb.py`, then run:

`python LocalSunoDb.py`

Runtime errors are appended to root-level `error.log`.

## Naming

Application modules use the `ls_` / `LS_` prefixes throughout. The database filename and Python entrypoint are intentionally kept for compatibility with the existing database and launch workflow.

## Playback

- Tracks with confirmed PC audio keep the LocalSunoDb local player.
- Suno-only Library Play opens the same `suno.com/song/<track-id>` page as clicking the track title.
- Imports preview uses a single round Suno.com Play button; no embedded `<audio>` player is created.

## Repository hygiene

The package contains no `suno_finder_v4.db`, WAV/MP3/M4A files, browser audio cache, logs, `__pycache__`, or saved UI/runtime state.
