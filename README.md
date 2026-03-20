# Mentality DB v0.20.6 (March 18, 2026)

## What's Updated

- City search has been fixed and is now more stable.
- The search area in settings is now multi-select (you can select multiple fields at once).
- Changes to settings are applied immediately and don't close the window.
- Unnecessary export settings and backup limits have been removed.

## Search

### Basic Search

- Launched by Enter or the magnifying glass button.
- In Live mode, it is triggered by typing.
- Takes into account the fields selected from the settings.
- For compatibility with old data, it checks the city + address pair.

### Advanced Search

- Works on individual fields, including city, address, and phone number.
- Results are highlighted in the list.

## Settings

Available:
- Theme
- Language
- Search trigger (`manual` / `live`)
- Grid columns
- Date format (`iso` / `ru` / `us`)
- Unsaved action (`ask` / `save` / `discard`)
- Backup before import (`true` / `false`)
- Search scope (multiple field selection)

Removed:
- Default export format
- Default export scope
- Max backups

## Export

Via a single `Export` window:
- format: `mtb` or `csv`
- volume: entire database or selected cards
- export of one or more cards is supported

## Archive

Old versions of the script and documentation are located in `old_data`.
