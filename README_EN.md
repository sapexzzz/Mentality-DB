# 🗂 Mentality DB

> Local encrypted contact database with a graphical user interface  
> Version: **0.20.6** · Python 3.10+ · CustomTkinter · SQLite

---

## 📋 About

**Mentality DB** is a desktop application for managing a personal address book.  
All data is stored locally in an encrypted SQLite database (Fernet AES-128-CBC).  
Supports photos, search, export/import, backups, and switchable themes.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔒 Encryption | All card fields and photos are encrypted with a Fernet key |
| 👤 Cards | First/last name (RU/EN), country, city, address, phone, photos |
| 🔍 Search | Basic (string) and advanced (per-field); multilingual, case-insensitive |
| 📤 Export | MTB (JSON hex-blob) and CSV; full database or selected cards |
| 📥 Import | Merge with existing data with optional replacement |
| 💾 Backup | Manual database backup creation |
| 🌍 Localization | Russian and English; files in `languages/` |
| 🎨 Themes | Dark / Light |
| 🗑 Trash | Deleted contacts go to trash before permanent deletion |
| 📋 Duplicate | Quick card cloning |
| 📅 History | Creation and last-updated timestamps |

---

## ⚙️ Requirements

```
Python >= 3.10
customtkinter >= 5.2
cryptography >= 41.0
Pillow >= 10.0
```

---

## 🚀 Installation & Run

```bash
# Clone the repository
git clone https://github.com/your-username/mentality-db.git
cd mentality-db

# Install dependencies
pip install customtkinter cryptography Pillow

# Run
python main.py
```

Or via `run.sh`:

```bash
bash run.sh
```

---

## 📂 Project Structure

```
mentality_db/
├── main.py              # Main application file
├── config.json          # Settings (auto-created)
├── database.db          # Database (auto-created)
├── .mentality_key       # Encryption key (DO NOT share!)
├── run.sh               # Quick launch script
├── languages/
│   ├── ru.json          # Russian localization
│   └── en.json          # English localization
├── exports/             # Export folder (MTB, CSV, backups)
└── old_data/            # Archive of previous versions
```

> ⚠️ **IMPORTANT**: `.mentality_key` is the only key to your data.  
> Without it, decryption is impossible. Back it up separately.

---

## 🖥 Usage

### Creating a Card

1. Click **➕ Create Card** in the main window.
2. Fill in the fields (Tab/Enter moves between fields).
3. Click **💾 Save Changes**.

### Search

- **Basic**: type a query in the search bar, press Enter or 🔎.
- **Advanced**: click **🔍 Advanced**, set per-field conditions.

In settings you can choose the search trigger (`manual` / `live`) and which fields to search.

### Export

Click **📤 Export**, choose:
- **Format**: `MTB` (full with photos) or `CSV` (text, no photos)
- **Scope**: full database or selected cards

### Import

Click **📥 Import**, select a `.mtb` file.  
If a card with the same name already exists, you will be asked to replace or copy.

---

## 🔧 Settings

| Parameter | Values | Default |
|---|---|---|
| Theme | Dark / Light | Dark |
| Language | ru / en | ru |
| Search trigger | manual / live | manual |
| Grid columns | 3–6 | 5 |
| Date format | iso / ru / us | iso |
| Unsaved changes | ask / save / discard | ask |
| Backup before import | true / false | true |
| Search scope | multi-select field list | all fields |

> Language change reloads the interface immediately.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+A` | Select all in field |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Enter` (in card) | Move to next field |
| `Enter` (last field) | Save card |
| `Esc` | Back / exit export mode |

---

## 📝 License

This project is distributed under the [MIT](LICENSE) license.

---

## 📌 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full history of changes.
