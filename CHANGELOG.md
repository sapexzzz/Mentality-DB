# Mentality DB - Changelog v0.20.5 (March 18, 2026)

## Export

- Completely updated export window.
- Added volume selection:
- `Entire database`
- `One or several`
- Added export of multiple selected cards (not just one or all).
- Removed separate CSV button from the main menu: CSV export logic has been moved to a single export window.
- Added default export settings (format and volume).

## Search

- Improved city search in both regular and advanced search.
- Fallback for old data where the city may have appeared in the address has been preserved.
- Search is case-insensitive with text normalization.
- Added settings for search scope (`all` / `names`) and run mode (`manual` / `live`).

## Hotkeys

- Support for `Ctrl+A`, `Ctrl+Z`, `Ctrl+Y`, `Ctrl+X`, `Ctrl+C`, `Ctrl+V` for application input fields.

## Settings

Important settings have been added:
- Search launch (`manual`/`live`)
- Search scope (`all`/`names`)
- Number of card list columns
- Date format
- Behavior with unsaved changes (`ask`/`save`/`discard`)
- Default export format
- Default export size
- Backup before import (`true`/`false`)
- Backup storage limit

## Data Security

- Added checking for unsaved changes when closing a card.
- Added backup rotation (storing the last N copies).

## Archiving

- Previous README/CHANGELOG and script snapshot have been moved to `old_data`.
