# 🧠 Mentality DB v0.20.0 (March 18, 2026)

An app for securely storing contact data with encryption and backup.

## 📦 Installation

```bash
pip install customtkinter pillow cryptography
```

## 🚀 Run

```bash
python main.py
# or
./run.sh
```

## ✨ Features

- 🔐 AES-256 encryption of all personal data
- 📂 Create, edit, and delete contacts
- 📷 Add photos to contacts
- 🗑 Recycle Bin with restore
- 📤 Export to .mtb and CSV
- 📥 Import from .mtb
- 💾 Database backup
- 📋 Duplicate contacts
- 📅 Contact change history
- 🔍 Quick and advanced search with highlighting
- ⌨️ Enter navigation (next field / save)
- 🌐 Multilingual support (RU/EN) from JSON files
- 🎨 Dark and light themes
- 🪟 Consistent style for all dialog boxes

## 📁 Structure

```
mentality_db/
├── main.py # Main code
├── config.json # Configuration
├── run.sh # Launch script
├── languages/ # Language files (ru.json, en.json)
└── exports/ # Export, CSV, backups
```

## 🌐 Languages

Languages ​​are loaded from the `languages/` folder (JSON files). To add a new language, create an `xx.json` file based on the existing ones.

## 📄 Versioning

CHANGELOG and README files are created with the date and version in their names.
