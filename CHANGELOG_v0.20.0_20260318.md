# Mentality DB - Changelog v0.20.0 (March 18, 2026)

## 🐛 BUGS FIXED

### 1. CSV export - column shift
- **Problem**: The "Created" and "Updated" columns contained incorrect data. Indexes `r[9]` (deleted) and `r[10]` (created_at) were misaligned — `r[10]` (created_at) and `r[11]` (updated_at) are needed.
- **Solution**: Fixed column indexes in CSV export.

### 2. CSV export — "bad option -filename" error.
- **Problem**: `filedialog.asksaveasfilename(filename=...)` — `filename` parameter does not exist.
- **Solution**: Replaced with `initialfile=` + `defaultextension=".csv"` (fixed in v0.19.3).

## ✨ NEW FEATURES

### 1. **Navigation with Enter**
- Enter moves the cursor to the next input field.
- In the last field, Enter saves the card and returns to the menu.

### 2. **Search Results Highlighting**
- Advanced Search closes the window after clicking "Search"
- Found cards are highlighted with a green border
- Highlighting is reset when switching modes

### 3. **Unified Dialog Style (CTkToplevel)**
- All dialogs (exit, export, import, delete, etc.) now use CTkToplevel
- Support for theme switching (Dark/Light) for all windows
- Unified appearance with settings and advanced search

## 🔧 CHANGES

- Removed phone format check (validate_phone no longer blocks saving)
- Version updated: 0.19.3 → 0.20.0
- Removed dependency on `tkinter.messagebox` for custom dialogs
