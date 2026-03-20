# Mentality DB - Changelog v0.20.1 (March 18, 2026)

## Fixed

- Standard search now searches all card text fields: first name RU, last name RU, first name EN, last name EN, country, city, address, phone.
- Advanced search now not only finds records but also displays the results: found cards are highlighted and simultaneously filtered in the list.
- Advanced search logic has been fixed: after searching, the application switches to database mode, clears the standard search bar, and displays only the found cards.
- Fixed a crash in backup and other custom dialogs on Linux: `CTkToplevel` is now visible first, and only then `grab_set()` is attempted.
- Fixed clearing search state: during a standard search, filters and highlighting from advanced search are reset.

## Improved

- Export and import are now located next to each other in the sidebar.
- The colors of the main menu buttons have been updated to make them visually distinct.
- Old versions of documentation and code are now saved to the `old_data` folder.

## Archiving

The following are saved in `old_data`:
- Previous `README`
- Previous `CHANGELOG`
- A snapshot of the previous script: `main_v0.20.0_20260318.py`
