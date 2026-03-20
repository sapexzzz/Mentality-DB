# Mentality DB v0.20.1 (March 18, 2026)

An application for local storage of contact data with encryption, import, export, and backup.

## Highlights in version 0.20.1

- Basic search works across all main card fields.
- Advanced search displays only found cards and highlights them.
- Custom CTk dialogs have been fixed, including the backup results window.
- Old versions of the script and documentation are automatically stored in the old_data folder.

## Search

### Basic Search
Searches by:
- First Name RU
- Last Name RU
- First Name EN
- Last Name EN
- Country
- City
- Address
- Phone

### Advanced Search
- Search by individual fields
- `Enter` moves to the next field
- `Enter` starts the search in the last field
- After the search, only found cards are shown

## Archive of Old Versions

All old versions are stored in the `old_data` folder:
- Old `README`
- Old `CHANGELOG`
- Old `main.py`

## Run

```bash
python main.py
```

or

```bash
./run.sh
```
