# Changelog

All notable changes to this project will be documented in this file.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.20.6] — 2026-03-20

### Fixed
- **Double paste bug**: removed global `bind_all` for `Ctrl+C/V/X` — CTkEntry handles these natively; the extra `event_generate("<<Paste>>")` caused every paste to insert content twice.
- **Language change** now immediately closes the settings window and rebuilds the full UI with the new locale (previously required restart).
- **`entry_map` AttributeError risk**: `self.entry_map = {}` is now initialized in `__init__` before UI build.
- **Unsafe export filenames**: card names used directly in filenames are now sanitized (non-alphanumeric characters replaced with `_`, max 40 chars).

### Changed
- `settings_note` text updated in both `ru.json` and `en.json` to mention that language change reloads the interface.
- Search fields config migration: old single-choice `search_scope` value is automatically converted to the new `search_fields` list on startup.

---

## [0.20.5] — 2026-03-18

### Added
- Settings window no longer closes or navigates away when changing a value.
- Search scope is now a multi-select checkbox list (individual fields).
- Grid columns change now applies immediately without reopening the window.
- Search trigger `manual/live` toggle applies to the search entry without restart.

### Removed
- "Default export format" and "Default export scope" settings (handled in export dialog directly).
- "Max backups" setting.

### Fixed
- Legacy `search_scope` config values migrated to new `search_fields` list format.
- City search stability improvements.

---

## [0.20.4] — 2026-03-18

### Added
- Multi-card export: select one or more cards and export them together as MTB or CSV.
- Unified export dialog (format + scope in one window).
- Removed separate CSV button from sidebar; all export flows go through the unified dialog.
- Unsaved-changes tracking: prompts to save, discard, or cancel when leaving a modified card.
- `backup_before_import` config flag controls whether a backup is made before every import.
- Configurable datetime format for card history (`iso` / `ru` / `us`).

### Changed
- Export filename for a single card uses sanitized first+last name.
- Export filename for multiple cards uses `selected_N_YYYYMMDD` pattern.

---

## [0.20.3] — 2026-03-18

### Added
- Manual search trigger: search only fires on Enter or loupe button click (configurable in settings).
- Live search mode: optional, fires on every keystroke.
- 🔎 loupe button next to search field.

### Fixed
- City search: text normalization via `unicodedata.NFKC` + `casefold` for reliable Unicode matching.
- Fallback: city/address fields searched together for legacy data where the fields may be swapped.

---

## [0.20.2] — 2026-03-18

### Added
- Advanced search: per-field filtering with result highlighting in card grid.
- Highlighted cards shown with green border.
- Enter key navigates between advanced search fields; last field triggers search.

### Fixed
- Advanced search correctly handles phone normalization (digits only comparison).
- `grab_set` timing issue in backup dialog resolved.

---

## [0.20.1] — 2026-03-18

### Added
- Enter key navigation between fields in card edit view.
- Enter on last field saves the card.
- Custom CTk-native dialogs (theme-aware, replaces `messagebox`/`simpledialog`).

### Fixed
- CSV export: `initialfile` and `defaultextension` used correctly.
- CSV column order no longer shifts when country field is empty.
- Phone validation removed from save path (not required).

---

## [0.20.0] — 2026-03-18

### Added
- Full RU/EN localization loaded exclusively from `languages/` JSON files.
- Language auto-generation removed; app fails explicitly if no language files found.
- `old_data/` archive folder for previous versions of scripts and docs.
- Versioned `README_vX.Y.Z_YYYYMMDD.md` and `CHANGELOG_vX.Y.Z_YYYYMMDD.md` policy.

### Fixed
- Image window memory leak: `CTkImage` reference stored on the window object.

---

## [0.19.3] — 2026-03-18

### Added
- CSV export (`export_csv()`).
- Auto backup (`auto_backup()`).
- Card duplication (`duplicate_card()`).
- Card history view (`show_card_history()`): creation and update timestamps.
- Advanced search (`advanced_search()`).
- `Ctrl+A`, `Ctrl+Z`, `Ctrl+Y` global shortcuts.

### Fixed
- `created_at` / `updated_at` fields now set correctly on import.
- Photo load errors show truncated message instead of crashing.
- `open_full_image()` wrapped in try/except.
