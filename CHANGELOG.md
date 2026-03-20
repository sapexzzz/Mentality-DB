# Mentality DB - Changelog v0.20.4 (March 18, 2026)

## Export

- The export UX has been completely redesigned: the old card selection mode is now replaced by a separate, convenient export window.
- This window allows you to select:
- Export volume: entire database or a single card;
- Export format: mtb or csv.
- When selecting the "single card" mode, a list of cards is displayed for quick selection.
- Added export of a single card to CSV.

## Search

- Improved city search in both normal and advanced modes.
- Added compatibility with legacy data where the city field could appear in the address: city search now checks for city and fallback in address.
- Text comparison in search is now standardized and case-insensitive.

## Editing Hotkeys

Global bindings have been added:
- `Ctrl+A` — Select All
- `Ctrl+Z` — Undo
- `Ctrl+Y` — Redo
- `Ctrl+X` — Cut
- `Ctrl+C` — Copy
- `Ctrl+V` — Paste

These bindings work in card input fields, regular and advanced search fields, and other text controls in the application.

## Localization

- New language keys have been added for the new export window (RU/EN).

## Archiving

- Previous `README`, `CHANGELOG`, and script snapshots have been moved to `old_data`.
