# Mentality DB v0.20.5 (March 18, 2026)

## What's New

- New combined export: select format (mtb/csv) and size (entire database or one or several cards).
- Multi-export of selected cards.
- Enhanced city search in normal and advanced modes.
- Added global editing hotkeys.
- The settings menu has been expanded with key application behavior parameters.

## Export

The 'Export' button opens a window where you can:
- select format (mtb, csv)
- select size:
- entire database
- one or several cards

In 'one or several' mode, you can mark multiple cards at once.

## Search

### Basic Search
- Supports case-insensitive search
- Takes text normalization into account
- Covers all fields when scope=`all`

### Advanced Search
- Searches by selected fields
- Correct search by city and phone number
- Enter switches fields, starts the search on the last field

## Hotkeys

- `Ctrl+A` — Select all
- `Ctrl+Z` — Undo
- `Ctrl+Y` — Redo
- `Ctrl+X` — Cut
- `Ctrl+C` — Copy
- `Ctrl+V` — Paste

## New Settings

- Theme, Language
- Search trigger (`manual` / `live`)
- Search scope (`all` / `names`)
- Grid columns
- Date format (`iso` / `ru` / `us`)
- Unsaved action (`ask` / `save` / `discard`)
- Default export format (`mtb` / `csv`)
- Default export scope (`full` / `selected`)
- Backup before import (`true` / `false`)
- Max backups

## Archive of old versions

Old versions of the script and documents are stored in `old_data`.# Mentality DB v0.20.4 (March 18, 2026)

## Version Highlights

- New, beautiful and convenient export via a separate export settings window.
- Reliable city search in both standard and advanced search.
- Global editing hotkeys (Ctrl+A/Z/Y/X/C/V).

## New Export

The export button opens a window where you can select:
- **Size**: entire database or a single card
- **Format**: mtb or csv

A list of cards is available for the "single card" mode.

## Search

### Basic Search
- Searches all card fields
- Case-insensitive
- Considers old data variations for the city

### Advanced Search
- Searches selected fields
- Case-insensitive
- Uses digit comparison for phone numbers

## Hotkeys

- `Ctrl+A` — Select all
- `Ctrl+Z` — Undo
- `Ctrl+Y` — Redo
- `Ctrl+X` — Cut
- `Ctrl+C` — Copy
- `Ctrl+V` — Paste

## Storing Old Versions

Old versions of code and documents are saved in the `old_data` folder.
