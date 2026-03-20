# Mentality DB v0.20.2 (March 18, 2026)

Local contact database with encryption, import/export, backup, and advanced search.

## What's fixed in this version

- Search by address and phone number works in both standard and advanced modes.
- Standard search now includes all card text fields.
- Advanced search correctly filters and highlights found cards.
- New cards are not created in the database until explicitly saved.
- Exiting a new card without saving no longer leaves empty entries.
- Application dialogs work without display errors and use the interface theme.

## Search

### Standard
Searches by:
- First name RU/EN
- Last name RU/EN
- Country
- City
- Address
- Phone

### Advanced
- Search by individual fields
- Enter switches focus to the next field
- Enter in the last field starts the search
- Results are highlighted and displayed as a list filter

## Old Version Storage Policy

Old versions are always stored in the `old_data` folder:
- Previous `main.py`
- Previous `README`
- Previous `CHANGELOG`

## Run

```bash
python main.py
```

or

```bash
./run.sh
```
