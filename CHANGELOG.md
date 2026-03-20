# Mentality DB - Changelog v0.20.3 (March 18, 2026)

## Search

- Fixed city search in both regular and advanced search.
- Added more robust text normalization (`NFKC` + `casefold` + trimming spaces) so that search correctly finds values ​​like `Rouen` when entering `rouen`.
- Phone search in both modes continues to work by digits, regardless of formatting.

## Regular Search Launch Mode

- Regular search no longer launches every time a character is entered.
- Search is launched only:
- by pressing `Enter` in the search bar;
- by clicking the magnifying glass button next to the search bar.

## Filter Behavior

- Added a separate "applied" search query for regular search so that results only change after explicitly launching a search. - When switching between modes (Database/Trash), the normal search string and filter are reset.

## Archiving

- Previous `README`, `CHANGELOG`, and script snapshot have been moved to `old_data`.
