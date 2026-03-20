import sqlite3
import os
import json
import customtkinter as ctk # type: ignore
from PIL import Image # type: ignore
import io
from datetime import datetime
from tkinter import filedialog
import re
import csv
import shutil
import unicodedata

# --- ШИФРОВАНИЕ ---
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# --- ПАТЧ ДЛЯ Python 3.13+ ---
try:
    from customtkinter.windows.widgets import ctk_scrollable_frame # type: ignore
    original_check = ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas
    def patched_check(self, widget):
        if isinstance(widget, str): return False
        return original_check(self, widget)
    ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas = patched_check
except: pass

# --- CONFIG & PATHS ---
VERSION = "0.20.4"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_NAME = os.path.join(SCRIPT_DIR, "database.db")
KEY_PATH = os.path.join(SCRIPT_DIR, ".mentality_key")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
EXPORT_DIR = os.path.join(SCRIPT_DIR, "exports")
LANG_DIR = os.path.join(SCRIPT_DIR, "languages")
OLD_DATA_DIR = os.path.join(SCRIPT_DIR, "old_data")

for d in [EXPORT_DIR, LANG_DIR, OLD_DATA_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class MentalityCore:
    def __init__(self):
        if not HAS_CRYPTO: raise ImportError("pip install cryptography")
        self.key = self.load_or_create_key()
        self.cipher = Fernet(self.key)
        self.init_db()
        self.cfg = self.load_config()
        self.languages = {}
        self.init_languages()

    def load_or_create_key(self):
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as kf: return kf.read()
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as kf: kf.write(key)
        return key

    def encrypt(self, data):
        if not data: return None
        if isinstance(data, str): data = data.encode('utf-8')
        return self.cipher.encrypt(data)

    def decrypt(self, data, err_msg="[Error]"):
        if not data: return ""
        try:
            dec = self.cipher.decrypt(data)
            try: return dec.decode('utf-8')
            except: return dec
        except: return err_msg

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name BLOB, last_name BLOB, first_name_en BLOB, last_name_en BLOB,
                country BLOB, city BLOB, address BLOB, phones BLOB,
                deleted INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER,
                photo BLOB, created_at TEXT)""")

    def load_config(self):
        default = {
            "language": "ru",
            "theme": "Dark",
            "search_trigger": "manual",
            "search_scope": "all",
            "grid_columns": 5,
            "date_format": "iso",
            "unsaved_action": "ask",
            "export_default_format": "mtb",
            "export_default_scope": "full",
            "backup_before_import": True,
            "max_backups": 10,
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if not isinstance(loaded, dict):
                    return default
                merged = default.copy()
                merged.update(loaded)
                return merged
            except: pass
        return default

    def save_config(self, cfg):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def init_languages(self):
        for file in os.listdir(LANG_DIR):
            if file.endswith(".json"):
                lang_name = file.replace(".json", "")
                with open(os.path.join(LANG_DIR, file), "r", encoding="utf-8") as f:
                    self.languages[lang_name] = json.load(f)
        if not self.languages:
            raise FileNotFoundError(f"No language files found in {LANG_DIR}")

    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        """Validate phone format (basic)"""
        if not phone:
            return True
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        return len(phone) >= 6 and any(c.isdigit() for c in phone)

    def create_backup(self):
        """Create automatic backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(EXPORT_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_NAME, backup_path)
            try:
                keep = int(self.cfg.get("max_backups", 10))
                if keep > 0:
                    backups = sorted(
                        [f for f in os.listdir(EXPORT_DIR) if f.startswith("backup_") and f.endswith(".db")]
                    )
                    if len(backups) > keep:
                        for old in backups[:-keep]:
                            os.remove(os.path.join(EXPORT_DIR, old))
            except Exception:
                pass
            return backup_path
        except Exception as e:
            return None

class MentalityGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.core = None
        try: self.core = MentalityCore()
        except Exception as e:
            self.show_error("Error", str(e)); self.destroy(); return

        ctk.set_appearance_mode(self.core.cfg.get("theme", "Dark"))
        self.title(f"Mentality DB v{VERSION}")
        self.geometry("1250x850")
        self.current_mode = 0
        self.temp_images = []
        self.export_selection_mode = False
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.current_edit_card_id = None
        self.basic_search_query = ""
        self.entry_initial_values = {}

        self.bind("<Escape>", lambda e: self.handle_esc())
        self.setup_global_shortcuts()
        self.rebuild_ui()

    # --- Custom dialogs (CTkToplevel, theme-aware) ---
    def _dialog(self, title, message, buttons, icon_color="#3498db"):
        result = [None]
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("420x180")
        dlg.attributes('-topmost', True)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.update_idletasks()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except Exception:
            pass

        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=15)
        ctk.CTkLabel(body, text=message, wraplength=370, justify="left", font=("Arial", 13)).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")
        for text, value, color in buttons:
            def cmd(v=value): result[0] = v; dlg.destroy()
            ctk.CTkButton(btn_frame, text=text, width=100, fg_color=color, command=cmd).pack(side="left", padx=5, expand=True)

        dlg.wait_window()
        return result[0]

    def show_info(self, title, message):
        self._dialog(title, message, [("OK", True, "#2b8a3e")])

    def show_error(self, title, message):
        self._dialog(title, message, [("OK", True, "#c0392b")], "#c0392b")

    def ask_yes_no(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        return self._dialog(title, message, [(yes, True, "#2b8a3e"), (no, False, "#c0392b")])

    def ask_yes_no_cancel(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        cancel = "Отмена" if lang == "ru" else "Cancel"
        return self._dialog(title, message, [(yes, "yes", "#2b8a3e"), (no, "no", "#3498db"), (cancel, "cancel", "#7f8c8d")])

    def loc(self, key):
        lang = self.core.cfg.get("language", "ru")
        lang_data = self.core.languages.get(lang, self.core.languages.get("ru", {}))
        return lang_data.get(key, key)

    @staticmethod
    def _to_text(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(value)

    @staticmethod
    def _normalize_phone(value):
        return "".join(ch for ch in str(value) if ch.isdigit())

    @staticmethod
    def _normalize_text(value):
        text = MentalityGUI._to_text(value)
        text = unicodedata.normalize("NFKC", text)
        return " ".join(text.strip().casefold().split())

    def _format_datetime(self, value):
        text = self._to_text(value)
        if not text:
            return ""
        fmt = self.core.cfg.get("date_format", "iso")
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            return text
        if fmt == "ru":
            return dt.strftime("%d.%m.%Y %H:%M")
        if fmt == "us":
            return dt.strftime("%m/%d/%Y %I:%M %p")
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def setup_global_shortcuts(self):
        # Cross-window edit shortcuts for all Entry/Text-like widgets.
        self.bind_all("<Control-a>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-A>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-z>", self._shortcut_undo, add="+")
        self.bind_all("<Control-Z>", self._shortcut_undo, add="+")
        self.bind_all("<Control-y>", self._shortcut_redo, add="+")
        self.bind_all("<Control-Y>", self._shortcut_redo, add="+")
        self.bind_all("<Control-x>", self._shortcut_cut, add="+")
        self.bind_all("<Control-X>", self._shortcut_cut, add="+")
        self.bind_all("<Control-c>", self._shortcut_copy, add="+")
        self.bind_all("<Control-C>", self._shortcut_copy, add="+")
        self.bind_all("<Control-v>", self._shortcut_paste, add="+")
        self.bind_all("<Control-V>", self._shortcut_paste, add="+")

    def _focused_widget(self):
        try:
            return self.focus_get()
        except Exception:
            return None

    def _shortcut_select_all(self, event=None):
        w = self._focused_widget()
        if not w:
            return "break"
        try:
            w.event_generate("<<SelectAll>>")
        except Exception:
            try:
                w.select_range(0, "end")
            except Exception:
                pass
        try:
            w.icursor("end")
        except Exception:
            pass
        return "break"

    def _shortcut_undo(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Undo>>")
            except Exception: pass
        return "break"

    def _shortcut_redo(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Redo>>")
            except Exception: pass
        return "break"

    def _shortcut_cut(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Cut>>")
            except Exception: pass
        return "break"

    def _shortcut_copy(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Copy>>")
            except Exception: pass
        return "break"

    def _shortcut_paste(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Paste>>")
            except Exception: pass
        return "break"

    def handle_esc(self):
        if self.export_selection_mode:
            self.export_selection_mode = False; self.refresh_ui(); return
        if hasattr(self, 'details_view') and self.details_view.winfo_viewable(): self.close_card()

    def rebuild_ui(self):
        for widget in self.winfo_children(): widget.destroy()
        self.gallery_view = ctk.CTkFrame(self, fg_color="transparent")
        self.gallery_view.pack(fill="both", expand=True)
        self.details_view = ctk.CTkFrame(self, fg_color="transparent")

        # SIDEBAR
        side = ctk.CTkFrame(self.gallery_view, width=180)
        side.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(side, text=self.loc("menu"), font=("Arial", 18, "bold")).pack(pady=15)

        ctk.CTkButton(side, text=self.loc("base"), fg_color="#1a6b9a", hover_color="#2980b9", command=lambda: self.set_mode(0)).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("trash"), fg_color="#5d6d7e", hover_color="#7f8c8d", command=lambda: self.set_mode(1)).pack(pady=5, padx=10, fill="x")

        exp_row = ctk.CTkFrame(side, fg_color="transparent")
        exp_row.pack(pady=5, padx=10, fill="x")
        exp_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(exp_row, text=self.loc("exp"), fg_color="#2980b9", hover_color="#3498db", command=self.ask_export_type).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(exp_row, text=self.loc("imp"), fg_color="#d35400", hover_color="#e67e22", command=self.import_data).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkButton(side, text=self.loc("backup_btn"), fg_color="#7d3c98", hover_color="#9b59b6", command=self.auto_backup).pack(pady=5, padx=10, fill="x")

        ctk.CTkButton(side, text=self.loc("exit"), fg_color="#c0392b", hover_color="#e74c3c", command=self.quit_app).pack(side="bottom", pady=(5, 20), padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("settings"), command=self.open_settings).pack(side="bottom", pady=5, padx=10, fill="x")

        # CONTENT
        cont = ctk.CTkFrame(self.gallery_view, fg_color="transparent")
        cont.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(cont, height=50)
        top.pack(fill="x", pady=(0, 10))
        self.search_entry = ctk.CTkEntry(top, width=400, placeholder_text=self.loc("search_base"))
        self.search_entry.pack(side="left", padx=20, pady=10)
        self.search_entry.bind("<Return>", lambda e: self.apply_basic_search())
        if self.core.cfg.get("search_trigger", "manual") == "live":
            self.search_entry.bind("<KeyRelease>", lambda e: self.apply_basic_search())
        ctk.CTkButton(top, text="🔎", width=36, command=self.apply_basic_search).pack(side="left", padx=(0, 8), pady=10)
        ctk.CTkButton(top, text=self.loc("search_advanced"), width=100, command=self.advanced_search).pack(side="left", padx=5, pady=10)

        self.scroll = ctk.CTkScrollableFrame(cont, label_text=self.loc("list_title"), label_font=("Arial", 20, "bold"))
        self.scroll.pack(fill="both", expand=True)
        self.refresh_ui()

    def apply_basic_search(self):
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.basic_search_query = self._normalize_text(self.search_entry.get())
        self.refresh_ui()

    def set_mode(self, mode):
        self.export_selection_mode = False; self.highlighted_ids = set(); self.filtered_ids = None; self.basic_search_query = ""; self.current_mode = mode
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, "end")
        self.refresh_ui()

    def refresh_ui(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.temp_images.clear()

        ctrl = ctk.CTkFrame(self.scroll, fg_color="transparent"); ctrl.pack(fill="x", padx=5, pady=(5, 15))
        if self.export_selection_mode:
            ctk.CTkLabel(ctrl, text=self.loc("export_ask"), text_color="#e67e22", font=("Arial", 14, "bold")).pack(side="left", padx=10)
        elif self.current_mode == 0:
            ctk.CTkButton(ctrl, text=self.loc("create"), fg_color="#2b8a3e", command=self.create_card).pack(side="left", padx=5)
        else:
            ctk.CTkButton(ctrl, text=self.loc("empty_trash"), fg_color="#7f8c8d", command=self.empty_trash).pack(side="right", padx=5)

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT * FROM cards WHERE deleted=?", (self.current_mode,)).fetchall()

        grid = ctk.CTkFrame(self.scroll, fg_color="transparent"); grid.pack(fill="both", expand=True)
        cols = int(self.core.cfg.get("grid_columns", 5))
        cols = max(2, min(cols, 8))
        grid.grid_columnconfigure(tuple(range(cols)), weight=1)

        disp = 0
        search = self.basic_search_query
        phone_search = self._normalize_phone(search)
        err = self.loc("decryption_error")

        for r in rows:
            fn = self._to_text(self.core.decrypt(r[1], err))
            ln = self._to_text(self.core.decrypt(r[2], err))
            fn_en = self._to_text(self.core.decrypt(r[3], err))
            ln_en = self._to_text(self.core.decrypt(r[4], err))
            country = self._to_text(self.core.decrypt(r[5], err))
            city = self._to_text(self.core.decrypt(r[6], err))
            address = self._to_text(self.core.decrypt(r[7], err))
            phones = self._to_text(self.core.decrypt(r[8], err))
            if self.filtered_ids is not None and r[0] not in self.filtered_ids:
                continue
            if self.core.cfg.get("search_scope", "all") == "names":
                haystack = self._normalize_text(f"{fn} {ln} {fn_en} {ln_en}")
            else:
                haystack = self._normalize_text(f"{fn} {ln} {fn_en} {ln_en} {country} {city} {address} {phones}")
            phone_haystack = self._normalize_phone(phones)
            # Fallback for legacy data where city/address could be swapped.
            city_address_haystack = self._normalize_text(f"{city} {address}")
            if search and search not in haystack and (not phone_search or phone_search not in phone_haystack):
                if search not in city_address_haystack:
                    continue

            color = "#e67e22" if self.export_selection_mode else ("#27ae60" if r[0] in self.highlighted_ids else "#3d3d3d")
            frame = ctk.CTkFrame(grid, fg_color="#2b2b2b", height=50, corner_radius=25, border_width=2, border_color=color)
            frame.grid(row=disp//cols, column=disp%cols, padx=8, pady=8, sticky="ew")
            frame.grid_propagate(False)

            name = f"{fn} {ln}".strip() or self.loc("no_name")
            cmd = (lambda c=r[0]: self.perform_export(c)) if self.export_selection_mode else (lambda c=r[0]: self.open_card(c))
            ctk.CTkButton(frame, text=name, fg_color="transparent", command=cmd).place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.8)
            disp += 1

    def open_card(self, cid):
        self.gallery_view.pack_forget(); self.details_view.pack(fill="both", expand=True)
        for w in self.details_view.winfo_children(): w.destroy()
        is_new = cid is None
        self.current_edit_card_id = cid

        top = ctk.CTkFrame(self.details_view, fg_color="transparent"); top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text=self.loc("back"), width=100, command=self.close_card).pack(side="left")
        if not is_new:
            ctk.CTkButton(top, text=self.loc("history_btn"), width=100, command=lambda: self.show_card_history(cid)).pack(side="left", padx=5)

        if self.current_mode == 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("to_trash"), fg_color="#c0392b", command=lambda: self.trash_card(cid)).pack(side="right")
            ctk.CTkButton(top, text=self.loc("duplicate_btn"), fg_color="#3498db", command=lambda: self.duplicate_card(cid)).pack(side="right", padx=5)
        elif self.current_mode != 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("perm_del"), fg_color="#922b21", command=lambda: self.perm_del_card(cid)).pack(side="right", padx=5)
            ctk.CTkButton(top, text=self.loc("restore"), fg_color="#2b8a3e", command=lambda: self.restore_card(cid)).pack(side="right", padx=5)

        tabs = ctk.CTkTabview(self.details_view); tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        t_info, t_photo = tabs.add(self.loc("tab_info")), tabs.add(self.loc("tab_photo"))

        row_data = {}
        if not is_new:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                row_data = dict(row) if row else {}

        self.entry_map = {}
        self.entry_initial_values = {}
        err = self.loc("decryption_error")
        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]

        f_info = ctk.CTkScrollableFrame(t_info, fg_color="transparent"); f_info.pack(fill="both", expand=True)
        entries_list = []
        for i, text in enumerate(self.loc("labels")):
            col = db_cols[i]
            f = ctk.CTkFrame(f_info, fg_color="transparent"); f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=text, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=400)
            existing = self.core.decrypt(row_data.get(col), err) if not is_new else ""
            existing_text = self._to_text(existing)
            e.insert(0, existing_text)
            if self.current_mode == 1: e.configure(state="disabled")
            else:
                self.entry_map[col] = e
                self.entry_initial_values[col] = existing_text
                entries_list.append(e)
            e.pack(side="left")

        # Enter: next field or save+exit on last
        if self.current_mode == 0:
            for idx, entry in enumerate(entries_list):
                if idx < len(entries_list) - 1:
                    next_e = entries_list[idx + 1]
                    entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
                else:
                    entry.bind("<Return>", lambda ev, c=cid: self.save_info(c))

        if self.current_mode == 0:
            # Кнопка Сохранить прижата влево
            ctk.CTkButton(f_info, text=self.loc("save_btn"), fg_color="#2b8a3e", command=lambda: self.save_info(self.current_edit_card_id)).pack(pady=20, padx=150, anchor="w")

        self.photo_grid = ctk.CTkScrollableFrame(t_photo, fg_color="transparent"); self.photo_grid.pack(fill="both", expand=True)
        if self.current_mode == 0 and not is_new: ctk.CTkButton(t_photo, text=self.loc("add_photo"), command=lambda: self.add_photo(cid)).pack(pady=10)
        if not is_new:
            self.load_photos(cid)

    def load_photos(self, cid):
        for w in self.photo_grid.winfo_children(): w.destroy()
        with sqlite3.connect(DB_NAME) as conn:
            photos = conn.execute("SELECT id, photo FROM photos WHERE card_id=?", (cid,)).fetchall()
        self.photo_grid.grid_columnconfigure((0,1,2,3,4), weight=1)
        for i, (pid, enc) in enumerate(photos):
            frame = ctk.CTkFrame(self.photo_grid, fg_color="#222222", corner_radius=10); frame.grid(row=i//5, column=i%5, padx=8, pady=8)
            try:
                raw = self.core.decrypt(enc, None)
                if raw is None:
                    raise ValueError("Decryption returned None")
                img = Image.open(io.BytesIO(raw)); img.thumbnail((160, 160))
                ctk_img = ctk.CTkImage(img, size=(160, 160)); self.temp_images.append(ctk_img)
                lbl = ctk.CTkLabel(frame, image=ctk_img, text="", cursor="hand2")
                lbl.pack(pady=10, padx=10)
                lbl.bind("<Button-1>", lambda e, d=raw: self.open_full_image(d))
            except Exception as err:
                error_msg = f"Error: {str(err)[:30]}"
                ctk.CTkLabel(frame, text=error_msg, text_color="#e74c3c").pack(pady=40, padx=20)
            if self.current_mode == 0:
                ctk.CTkButton(frame, text=self.loc("delete"), fg_color="#c0392b", height=20, command=lambda p=pid: self.del_photo(p, cid)).pack(pady=10)

    def open_full_image(self, data):
        top = ctk.CTkToplevel(self); top.title(self.loc("view_title")); top.attributes('-topmost', True)
        try:
            img = Image.open(io.BytesIO(data)); w, h = img.size
            ratio = min(800/w, 800/h) if w>800 or h>800 else 1
            ctk_img = ctk.CTkImage(img, size=(int(w*ratio), int(h*ratio)))
            lbl = ctk.CTkLabel(top, image=ctk_img, text=""); top.image = ctk_img; lbl.pack(padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(top, text=f"Error: {str(e)[:50]}").pack(padx=20, pady=20)

    def save_info(self, cid):
        now = datetime.now().isoformat()
        upd = {k: self.core.encrypt(v.get()) for k, v in self.entry_map.items()}
        if cid is None:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        upd.get("first_name"), upd.get("last_name"), upd.get("first_name_en"), upd.get("last_name_en"),
                        upd.get("country"), upd.get("city"), upd.get("address"), upd.get("phones"),
                        0, now, now
                    )
                )
        else:
            upd["updated_at"] = now
            sql = "UPDATE cards SET " + ", ".join([f"{k}=?" for k in upd.keys()]) + " WHERE id=?"
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(sql, list(upd.values()) + [cid])
        self.close_card(force=True)

    def ask_export_type(self):
        if self.current_mode == 1:
            self.set_mode(0)
        self.open_export_dialog()

    def open_export_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title(self.loc("exp"))
        dlg.geometry("700x560")
        dlg.attributes('-topmost', True)
        dlg.transient(self)

        state = {
            "scope": ctk.StringVar(value=self.core.cfg.get("export_default_scope", "full")),
            "format": ctk.StringVar(value=self.core.cfg.get("export_default_format", "mtb")),
        }

        root = ctk.CTkFrame(dlg, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(root, text=self.loc("exp"), font=("Arial", 22, "bold")).pack(anchor="w", pady=(0, 10))

        opt = ctk.CTkFrame(root)
        opt.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(opt, text=self.loc("export_scope"), width=120, anchor="w").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkSegmentedButton(opt, values=["full", "selected"],
                               variable=state["scope"],
                       dynamic_resizing=False,
                               command=lambda _: update_single_visibility()).grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(opt, text=self.loc("export_format"), width=120, anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkSegmentedButton(opt, values=["mtb", "csv"], variable=state["format"]).grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        opt.grid_columnconfigure(1, weight=1)

        cap = ctk.CTkFrame(opt, fg_color="transparent")
        cap.grid(row=0, column=1, padx=10, pady=(42, 0), sticky="ew")
        cap.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(cap, text=self.loc("export_scope_full"), anchor="center").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(cap, text=self.loc("export_scope_single"), anchor="center").grid(row=0, column=1, sticky="ew")

        single_frame = ctk.CTkFrame(root)
        single_frame.pack(fill="both", expand=True, pady=(0, 12))
        ctk.CTkLabel(single_frame, text=self.loc("export_pick_card"), anchor="w").pack(anchor="w", padx=10, pady=(10, 6))

        list_scroll = ctk.CTkScrollableFrame(single_frame, height=260)
        list_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT id, first_name, last_name, first_name_en, last_name_en FROM cards WHERE deleted=0 ORDER BY id DESC").fetchall()
        err = self.loc("decryption_error")
        card_items = []
        selected_map = {}
        for cid, fn_b, ln_b, fn_en_b, ln_en_b in rows:
            fn = self._to_text(self.core.decrypt(fn_b, err)).strip()
            ln = self._to_text(self.core.decrypt(ln_b, err)).strip()
            fn_en = self._to_text(self.core.decrypt(fn_en_b, err)).strip()
            ln_en = self._to_text(self.core.decrypt(ln_en_b, err)).strip()
            title = f"{fn} {ln}".strip() or f"{fn_en} {ln_en}".strip() or f"#{cid}"
            card_items.append((cid, title))

        if card_items:
            for cid, title in card_items:
                selected_map[cid] = ctk.BooleanVar(value=False)
                ctk.CTkCheckBox(list_scroll, text=title, variable=selected_map[cid]).pack(anchor="w", pady=3, padx=4)
        else:
            ctk.CTkLabel(list_scroll, text=self.loc("export_no_cards")).pack(anchor="w", padx=4, pady=6)

        def toggle_all(selection):
            if not selection:
                return
            all_selected = all(v.get() for v in selection.values())
            for var in selection.values():
                var.set(not all_selected)

        ctk.CTkButton(single_frame, text=self.loc("export_toggle_all"), width=160,
                      command=lambda: toggle_all(selected_map)).pack(anchor="e", padx=10, pady=(0, 10))

        btn = ctk.CTkFrame(root, fg_color="transparent")
        btn.pack(fill="x")

        def run_export():
            card_ids = None
            scope_val = state["scope"].get()
            if scope_val == "selected":
                selected = [cid for cid, var in selected_map.items() if var.get()]
                if not selected:
                    self.show_error(self.loc("error"), self.loc("export_select_card"))
                    return
                card_ids = selected

            fmt = state["format"].get().lower()
            dlg.destroy()
            if fmt == "csv":
                self.export_csv(card_ids)
            else:
                self.perform_export(card_ids)

        ctk.CTkButton(btn, text=self.loc("back"), width=120, fg_color="#7f8c8d", command=dlg.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn, text=self.loc("exp"), width=160, fg_color="#2980b9", hover_color="#3498db", command=run_export).pack(side="right")

        def update_single_visibility():
            scope_val = state["scope"].get()
            if scope_val == "full":
                single_frame.pack_forget()
            else:
                single_frame.pack(fill="both", expand=True, pady=(0, 12))

        update_single_visibility()

    def perform_export(self, selection=None):
        self.export_selection_mode = False; filename = "full_db"
        if isinstance(selection, int):
            selection = [selection]
        if selection and len(selection) == 1:
            with sqlite3.connect(DB_NAME) as conn:
                r = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (selection[0],)).fetchone()
                fn, ln = self.core.decrypt(r[0], "Card"), self.core.decrypt(r[1], "Data")
                filename = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}"
        elif selection and len(selection) > 1:
            filename = f"selected_{len(selection)}_{datetime.now().strftime('%Y%m%d')}"
        path = os.path.join(EXPORT_DIR, f"{filename}.mtb")
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                if selection:
                    placeholders = ",".join(["?"] * len(selection))
                    c = [dict(r) for r in conn.execute(f"SELECT * FROM cards WHERE id IN ({placeholders})", selection).fetchall()]
                    p = [dict(r) for r in conn.execute(f"SELECT * FROM photos WHERE card_id IN ({placeholders})", selection).fetchall()]
                else:
                    c = [dict(r) for r in conn.execute("SELECT * FROM cards").fetchall()]
                    p = [dict(r) for r in conn.execute("SELECT * FROM photos").fetchall()]
            for r in c:
                for k in r:
                    if isinstance(r[k], bytes): r[k] = r[k].hex()
            for r in p: r['photo'] = r['photo'].hex()
            with open(path, "w") as f: json.dump({"cards": c, "photos": p}, f)
            self.show_info(self.loc("exp"), self.loc("export_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))
        self.refresh_ui()

    def create_card(self):
        self.open_card(None)

    def add_photo(self, cid):
        ps = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if not ps: return
        with sqlite3.connect(DB_NAME) as conn:
            for p in ps:
                with open(p, "rb") as f: blob = f.read()
                conn.execute("INSERT INTO photos(card_id, photo, created_at) VALUES (?,?,?)", (cid, self.core.encrypt(blob), datetime.now().isoformat()))
        self.load_photos(cid)

    def del_photo(self, pid, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM photos WHERE id=?", (pid,))
        self.load_photos(cid)

    def trash_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=1 WHERE id=?", (cid,))
        self.close_card()

    def restore_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=0 WHERE id=?", (cid,))
        self.close_card()

    def perm_del_card(self, cid):
        if self.ask_yes_no(self.loc("perm_del"), self.loc("perm_del_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id=?", (cid,)); conn.execute("DELETE FROM cards WHERE id=?", (cid,))
            self.close_card()

    def _has_unsaved_changes(self):
        if self.current_mode != 0 or not self.entry_map:
            return False
        for col, entry in self.entry_map.items():
            if self._to_text(entry.get()) != self._to_text(self.entry_initial_values.get(col, "")):
                return True
        return False

    def close_card(self, force=False):
        if not force and self._has_unsaved_changes():
            action = self.core.cfg.get("unsaved_action", "ask")
            if action == "save":
                self.save_info(self.current_edit_card_id)
                return
            if action == "ask":
                res = self.ask_yes_no_cancel(self.loc("unsaved_title"), self.loc("unsaved_message"))
                if res == "yes":
                    self.save_info(self.current_edit_card_id)
                    return
                if res == "cancel":
                    return
        self.current_edit_card_id = None
        self.entry_map = {}
        self.entry_initial_values = {}
        self.details_view.pack_forget(); self.gallery_view.pack(fill="both", expand=True); self.refresh_ui()

    def empty_trash(self):
        with sqlite3.connect(DB_NAME) as conn:
            if conn.execute("SELECT COUNT(*) FROM cards WHERE deleted=1").fetchone()[0] == 0:
                self.show_info(self.loc("trash"), self.loc("trash_is_empty")); return
        if self.ask_yes_no(self.loc("trash"), self.loc("empty_trash_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id IN (SELECT id FROM cards WHERE deleted=1)")
                conn.execute("DELETE FROM cards WHERE deleted=1")
            self.refresh_ui()

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("Mentality Backup", "*.mtb")])
        if not path: return
        try:
            if self.core.cfg.get("backup_before_import", True):
                self.core.create_backup()
            with open(path, "r") as f: data = json.load(f)
            with sqlite3.connect(DB_NAME) as conn:
                for c in data['cards']:
                    for k in ['first_name', 'last_name', 'first_name_en', 'last_name_en', 'country', 'city', 'address', 'phones']:
                        if c[k]: c[k] = bytes.fromhex(c[k])
                    fn, ln = self.core.decrypt(c['first_name'], "User"), self.core.decrypt(c['last_name'], "Import")
                    ex = conn.execute("SELECT id FROM cards WHERE first_name=? AND last_name=?", (c['first_name'], c['last_name'])).fetchone()
                    mode = "new"
                    if ex:
                        res = self.ask_yes_no_cancel(self.loc("duplicate_title"), self.loc("duplicate_msg").format(fn, ln))
                        if res == "yes": mode = "replace"
                        elif res == "no": mode = "new"
                        else: continue
                    if mode == "replace":
                        cid = ex[0]
                        conn.execute("UPDATE cards SET first_name_en=?, last_name_en=?, country=?, city=?, address=?, phones=? WHERE id=?", (c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], cid))
                        conn.execute("DELETE FROM photos WHERE card_id=?", (cid,))
                    else:
                        cid = conn.execute("INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c['first_name'], c['last_name'], c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], 0, datetime.now().isoformat(), datetime.now().isoformat())).lastrowid
                    for p in [ph for ph in data['photos'] if ph['card_id'] == c['id']]:
                        conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)", (cid, bytes.fromhex(p['photo']), p['created_at']))
            self.refresh_ui(); self.show_info(self.loc("success"), self.loc("import_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))

    def open_settings(self):
        sw = ctk.CTkToplevel(self); sw.title(self.loc("settings")); sw.geometry("520x560"); sw.attributes('-topmost', True)

        def set_cfg(key, value, rebuild=False, apply_theme=False):
            self.core.cfg[key] = value
            self.core.save_config(self.core.cfg)
            if apply_theme:
                ctk.set_appearance_mode(value)
            if rebuild:
                self.rebuild_ui()

        options = [
            (self.loc("settings_theme"), "theme", ["Dark", "Light"], lambda v: set_cfg("theme", v, rebuild=True, apply_theme=True)),
            (self.loc("settings_language"), "language", list(self.core.languages.keys()), lambda v: set_cfg("language", v, rebuild=True)),
            (self.loc("settings_search_trigger"), "search_trigger", ["manual", "live"], lambda v: set_cfg("search_trigger", v, rebuild=True)),
            (self.loc("settings_search_scope"), "search_scope", ["all", "names"], lambda v: set_cfg("search_scope", v)),
            (self.loc("settings_grid_columns"), "grid_columns", ["3", "4", "5", "6"], lambda v: set_cfg("grid_columns", int(v), rebuild=True)),
            (self.loc("settings_date_format"), "date_format", ["iso", "ru", "us"], lambda v: set_cfg("date_format", v)),
            (self.loc("settings_unsaved_action"), "unsaved_action", ["ask", "save", "discard"], lambda v: set_cfg("unsaved_action", v)),
            (self.loc("settings_export_default_format"), "export_default_format", ["mtb", "csv"], lambda v: set_cfg("export_default_format", v)),
            (self.loc("settings_export_default_scope"), "export_default_scope", ["full", "selected"], lambda v: set_cfg("export_default_scope", v)),
            (self.loc("settings_backup_before_import"), "backup_before_import", ["true", "false"], lambda v: set_cfg("backup_before_import", v == "true")),
            (self.loc("settings_max_backups"), "max_backups", ["3", "5", "10", "20", "50"], lambda v: set_cfg("max_backups", int(v))),
        ]

        for label, key, vals, cmd in options:
            f = ctk.CTkFrame(sw, fg_color="transparent"); f.pack(fill="x", padx=30, pady=10)
            ctk.CTkLabel(f, text=label).pack(side="left")
            cur = self.core.cfg.get(key)
            if isinstance(cur, bool):
                cur = "true" if cur else "false"
            else:
                cur = str(cur)
            ctk.CTkOptionMenu(f, values=vals, command=cmd, variable=ctk.StringVar(value=cur)).pack(side="right")

    def quit_app(self):
        if self.ask_yes_no(self.loc("exit"), self.loc("exit_confirm")): self.quit()

    def export_csv(self, selection=None):
        """Export database to CSV format"""
        try:
            if isinstance(selection, int):
                selection = [selection]
            initial_name = "contacts.csv"
            if selection and len(selection) == 1:
                with sqlite3.connect(DB_NAME) as conn:
                    row = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (selection[0],)).fetchone()
                if row:
                    fn = self._to_text(self.core.decrypt(row[0], "Card")).strip() or "Card"
                    ln = self._to_text(self.core.decrypt(row[1], "Data")).strip() or "Data"
                    initial_name = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}.csv"
            elif selection and len(selection) > 1:
                initial_name = f"selected_{len(selection)}_{datetime.now().strftime('%Y%m%d')}.csv"
            path = filedialog.asksaveasfilename(initialfile=initial_name, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path: return
            with sqlite3.connect(DB_NAME) as conn:
                if selection:
                    placeholders = ",".join(["?"] * len(selection))
                    rows = conn.execute(f"SELECT * FROM cards WHERE id IN ({placeholders}) AND deleted=0 ORDER BY first_name", selection).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM cards WHERE deleted=0 ORDER BY first_name").fetchall()
            
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.loc("csv_headers"))
                err = self.loc("decryption_error")
                for r in rows:
                    fn = self.core.decrypt(r[1], "[Enc]")
                    ln = self.core.decrypt(r[2], "[Enc]")
                    fn_en = self.core.decrypt(r[3], "[Enc]")
                    ln_en = self.core.decrypt(r[4], "[Enc]")
                    country = self.core.decrypt(r[5], "[Enc]")
                    city = self.core.decrypt(r[6], "[Enc]")
                    address = self.core.decrypt(r[7], "[Enc]")
                    phones = self.core.decrypt(r[8], "[Enc]")
                    writer.writerow([fn, ln, fn_en, ln_en, country, city, address, phones, r[10], r[11]])
            self.show_info(self.loc("export_csv_title"), self.loc("export_csv_done").format(path))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def auto_backup(self):
        """Create automatic backup"""
        try:
            backup_path = self.core.create_backup()
            if backup_path:
                self.show_info(self.loc("success"), self.loc("backup_done").format(backup_path))
            else:
                self.show_error(self.loc("error"), self.loc("backup_fail"))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def duplicate_card(self, cid):
        """Create duplicate of contact"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                
                # Insert new card
                new_id = conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row['first_name'], row['last_name'], row['first_name_en'], row['last_name_en'], 
                     row['country'], row['city'], row['address'], row['phones'], 
                     datetime.now().isoformat(), datetime.now().isoformat())
                ).lastrowid
                
                # Copy photos
                photos = conn.execute("SELECT photo FROM photos WHERE card_id=?", (cid,)).fetchall()
                for photo in photos:
                    conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)",
                               (new_id, photo[0], datetime.now().isoformat()))
            
            self.show_info(self.loc("success"), self.loc("duplicate_success"))
            self.refresh_ui()
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def show_card_history(self, cid):
        """Show card creation and update dates"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT created_at, updated_at FROM cards WHERE id=?", (cid,)).fetchone()
            
            if row:
                created = row[0] or self.loc("history_unknown")
                updated = row[1] or self.loc("history_not_updated")
                msg = self.loc("history_created").format(self._format_datetime(created)) + "\n" + self.loc("history_updated").format(self._format_datetime(updated))
                self.show_info(self.loc("history_title"), msg)
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def advanced_search(self):
        """Open advanced search window"""
        sw = ctk.CTkToplevel(self)
        sw.title(self.loc("search_advanced_title"))
        sw.geometry("500x430")
        sw.attributes('-topmost', True)

        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]
        labels = self.loc("labels")
        search_vars = {}
        entries_list = []

        f_search = ctk.CTkScrollableFrame(sw, fg_color="transparent")
        f_search.pack(fill="both", expand=True, padx=20, pady=20)

        for i, label in enumerate(labels):
            f = ctk.CTkFrame(f_search, fg_color="transparent")
            f.pack(fill="x", pady=5)
            ctk.CTkLabel(f, text=label, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=300)
            e.pack(side="left")
            search_vars[db_cols[i]] = e
            entries_list.append(e)

        def perform_search():
            query_terms = {k: v.get().strip() for k, v in search_vars.items() if v.get().strip()}
            if not query_terms:
                return
            err = self.loc("decryption_error")
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0").fetchall()
            found_ids = set()
            for row in rows:
                match = True
                for col, term in query_terms.items():
                    col_idx = db_cols.index(col)
                    decrypted = self._normalize_text(self.core.decrypt(row[col_idx + 1], err))
                    term_norm = self._normalize_text(term)
                    if col == "phones":
                        if self._normalize_phone(term_norm) not in self._normalize_phone(decrypted):
                            match = False
                            break
                    elif col == "city":
                        city_val = self._normalize_text(self.core.decrypt(row[6], err))
                        address_val = self._normalize_text(self.core.decrypt(row[7], err))
                        if term_norm not in city_val and term_norm not in address_val:
                            match = False
                            break
                    elif term_norm not in decrypted:
                        match = False
                        break
                if match:
                    found_ids.add(row[0])
            sw.destroy()
            self.current_mode = 0
            self.export_selection_mode = False
            self.search_entry.delete(0, "end")
            self.basic_search_query = ""
            self.highlighted_ids = found_ids
            self.filtered_ids = found_ids
            self.refresh_ui()

        # Enter key: navigate between fields, last field triggers search
        for idx, entry in enumerate(entries_list):
            if idx < len(entries_list) - 1:
                next_e = entries_list[idx + 1]
                entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
            else:
                entry.bind("<Return>", lambda ev: perform_search())

        ctk.CTkButton(f_search, text=self.loc("search_btn"), fg_color="#2b8a3e", command=perform_search).pack(pady=20)

if __name__ == "__main__":
    app = MentalityGUI(); app.mainloop()
import sqlite3
import os
import json
import customtkinter as ctk # type: ignore
from PIL import Image # type: ignore
import io
from datetime import datetime
from tkinter import filedialog
import re
import csv
import shutil
import unicodedata

# --- ШИФРОВАНИЕ ---
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# --- ПАТЧ ДЛЯ Python 3.13+ ---
try:
    from customtkinter.windows.widgets import ctk_scrollable_frame # type: ignore
    original_check = ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas
    def patched_check(self, widget):
        if isinstance(widget, str): return False
        return original_check(self, widget)
    ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas = patched_check
except: pass

# --- CONFIG & PATHS ---
VERSION = "0.20.3"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_NAME = os.path.join(SCRIPT_DIR, "database.db")
KEY_PATH = os.path.join(SCRIPT_DIR, ".mentality_key")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
EXPORT_DIR = os.path.join(SCRIPT_DIR, "exports")
LANG_DIR = os.path.join(SCRIPT_DIR, "languages")
OLD_DATA_DIR = os.path.join(SCRIPT_DIR, "old_data")

for d in [EXPORT_DIR, LANG_DIR, OLD_DATA_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class MentalityCore:
    def __init__(self):
        if not HAS_CRYPTO: raise ImportError("pip install cryptography")
        self.key = self.load_or_create_key()
        self.cipher = Fernet(self.key)
        self.init_db()
        self.cfg = self.load_config()
        self.languages = {}
        self.init_languages()

    def load_or_create_key(self):
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as kf: return kf.read()
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as kf: kf.write(key)
        return key

    def encrypt(self, data):
        if not data: return None
        if isinstance(data, str): data = data.encode('utf-8')
        return self.cipher.encrypt(data)

    def decrypt(self, data, err_msg="[Error]"):
        if not data: return ""
        try:
            dec = self.cipher.decrypt(data)
            try: return dec.decode('utf-8')
            except: return dec
        except: return err_msg

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name BLOB, last_name BLOB, first_name_en BLOB, last_name_en BLOB,
                country BLOB, city BLOB, address BLOB, phones BLOB,
                deleted INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER,
                photo BLOB, created_at TEXT)""")

    def load_config(self):
        default = {"language": "ru", "theme": "Dark"}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return default

    def save_config(self, cfg):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def init_languages(self):
        for file in os.listdir(LANG_DIR):
            if file.endswith(".json"):
                lang_name = file.replace(".json", "")
                with open(os.path.join(LANG_DIR, file), "r", encoding="utf-8") as f:
                    self.languages[lang_name] = json.load(f)
        if not self.languages:
            raise FileNotFoundError(f"No language files found in {LANG_DIR}")

    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        """Validate phone format (basic)"""
        if not phone:
            return True
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        return len(phone) >= 6 and any(c.isdigit() for c in phone)

    def create_backup(self):
        """Create automatic backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(EXPORT_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_NAME, backup_path)
            return backup_path
        except Exception as e:
            return None

class MentalityGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.core = None
        try: self.core = MentalityCore()
        except Exception as e:
            self.show_error("Error", str(e)); self.destroy(); return

        ctk.set_appearance_mode(self.core.cfg.get("theme", "Dark"))
        self.title(f"Mentality DB v{VERSION}")
        self.geometry("1250x850")
        self.current_mode = 0
        self.temp_images = []
        self.export_selection_mode = False
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.current_edit_card_id = None
        self.basic_search_query = ""

        self.bind("<Escape>", lambda e: self.handle_esc())
        self.setup_global_shortcuts()
        self.rebuild_ui()

    # --- Custom dialogs (CTkToplevel, theme-aware) ---
    def _dialog(self, title, message, buttons, icon_color="#3498db"):
        result = [None]
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("420x180")
        dlg.attributes('-topmost', True)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.update_idletasks()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except Exception:
            pass

        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=15)
        ctk.CTkLabel(body, text=message, wraplength=370, justify="left", font=("Arial", 13)).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")
        for text, value, color in buttons:
            def cmd(v=value): result[0] = v; dlg.destroy()
            ctk.CTkButton(btn_frame, text=text, width=100, fg_color=color, command=cmd).pack(side="left", padx=5, expand=True)

        dlg.wait_window()
        return result[0]

    def show_info(self, title, message):
        self._dialog(title, message, [("OK", True, "#2b8a3e")])

    def show_error(self, title, message):
        self._dialog(title, message, [("OK", True, "#c0392b")], "#c0392b")

    def ask_yes_no(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        return self._dialog(title, message, [(yes, True, "#2b8a3e"), (no, False, "#c0392b")])

    def ask_yes_no_cancel(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        cancel = "Отмена" if lang == "ru" else "Cancel"
        return self._dialog(title, message, [(yes, "yes", "#2b8a3e"), (no, "no", "#3498db"), (cancel, "cancel", "#7f8c8d")])

    def loc(self, key):
        lang = self.core.cfg.get("language", "ru")
        lang_data = self.core.languages.get(lang, self.core.languages.get("ru", {}))
        return lang_data.get(key, key)

    @staticmethod
    def _to_text(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(value)

    @staticmethod
    def _normalize_phone(value):
        return "".join(ch for ch in str(value) if ch.isdigit())

    @staticmethod
    def _normalize_text(value):
        text = MentalityGUI._to_text(value)
        text = unicodedata.normalize("NFKC", text)
        return " ".join(text.strip().casefold().split())

    def setup_global_shortcuts(self):
        # Cross-window edit shortcuts for all Entry/Text-like widgets.
        self.bind_all("<Control-a>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-A>", self._shortcut_select_all, add="+")
        self.bind_all("<Control-z>", self._shortcut_undo, add="+")
        self.bind_all("<Control-Z>", self._shortcut_undo, add="+")
        self.bind_all("<Control-y>", self._shortcut_redo, add="+")
        self.bind_all("<Control-Y>", self._shortcut_redo, add="+")
        self.bind_all("<Control-x>", self._shortcut_cut, add="+")
        self.bind_all("<Control-X>", self._shortcut_cut, add="+")
        self.bind_all("<Control-c>", self._shortcut_copy, add="+")
        self.bind_all("<Control-C>", self._shortcut_copy, add="+")
        self.bind_all("<Control-v>", self._shortcut_paste, add="+")
        self.bind_all("<Control-V>", self._shortcut_paste, add="+")

    def _focused_widget(self):
        try:
            return self.focus_get()
        except Exception:
            return None

    def _shortcut_select_all(self, event=None):
        w = self._focused_widget()
        if not w:
            return "break"
        try:
            w.event_generate("<<SelectAll>>")
        except Exception:
            try:
                w.select_range(0, "end")
            except Exception:
                pass
        try:
            w.icursor("end")
        except Exception:
            pass
        return "break"

    def _shortcut_undo(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Undo>>")
            except Exception: pass
        return "break"

    def _shortcut_redo(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Redo>>")
            except Exception: pass
        return "break"

    def _shortcut_cut(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Cut>>")
            except Exception: pass
        return "break"

    def _shortcut_copy(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Copy>>")
            except Exception: pass
        return "break"

    def _shortcut_paste(self, event=None):
        w = self._focused_widget()
        if w:
            try: w.event_generate("<<Paste>>")
            except Exception: pass
        return "break"

    def handle_esc(self):
        if self.export_selection_mode:
            self.export_selection_mode = False; self.refresh_ui(); return
        if hasattr(self, 'details_view') and self.details_view.winfo_viewable(): self.close_card()

    def rebuild_ui(self):
        for widget in self.winfo_children(): widget.destroy()
        self.gallery_view = ctk.CTkFrame(self, fg_color="transparent")
        self.gallery_view.pack(fill="both", expand=True)
        self.details_view = ctk.CTkFrame(self, fg_color="transparent")

        # SIDEBAR
        side = ctk.CTkFrame(self.gallery_view, width=180)
        side.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(side, text=self.loc("menu"), font=("Arial", 18, "bold")).pack(pady=15)

        ctk.CTkButton(side, text=self.loc("base"), fg_color="#1a6b9a", hover_color="#2980b9", command=lambda: self.set_mode(0)).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("trash"), fg_color="#5d6d7e", hover_color="#7f8c8d", command=lambda: self.set_mode(1)).pack(pady=5, padx=10, fill="x")

        exp_row = ctk.CTkFrame(side, fg_color="transparent")
        exp_row.pack(pady=5, padx=10, fill="x")
        exp_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(exp_row, text=self.loc("exp"), fg_color="#2980b9", hover_color="#3498db", command=self.ask_export_type).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(exp_row, text=self.loc("imp"), fg_color="#d35400", hover_color="#e67e22", command=self.import_data).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkButton(side, text=self.loc("exp_csv"), fg_color="#16a085", hover_color="#1abc9c", command=self.export_csv).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("backup_btn"), fg_color="#7d3c98", hover_color="#9b59b6", command=self.auto_backup).pack(pady=5, padx=10, fill="x")

        ctk.CTkButton(side, text=self.loc("exit"), fg_color="#c0392b", hover_color="#e74c3c", command=self.quit_app).pack(side="bottom", pady=(5, 20), padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("settings"), command=self.open_settings).pack(side="bottom", pady=5, padx=10, fill="x")

        # CONTENT
        cont = ctk.CTkFrame(self.gallery_view, fg_color="transparent")
        cont.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(cont, height=50)
        top.pack(fill="x", pady=(0, 10))
        self.search_entry = ctk.CTkEntry(top, width=400, placeholder_text=self.loc("search_base"))
        self.search_entry.pack(side="left", padx=20, pady=10)
        self.search_entry.bind("<Return>", lambda e: self.apply_basic_search())
        ctk.CTkButton(top, text="🔎", width=36, command=self.apply_basic_search).pack(side="left", padx=(0, 8), pady=10)
        ctk.CTkButton(top, text=self.loc("search_advanced"), width=100, command=self.advanced_search).pack(side="left", padx=5, pady=10)

        self.scroll = ctk.CTkScrollableFrame(cont, label_text=self.loc("list_title"), label_font=("Arial", 20, "bold"))
        self.scroll.pack(fill="both", expand=True)
        self.refresh_ui()

    def apply_basic_search(self):
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.basic_search_query = self._normalize_text(self.search_entry.get())
        self.refresh_ui()

    def set_mode(self, mode):
        self.export_selection_mode = False; self.highlighted_ids = set(); self.filtered_ids = None; self.basic_search_query = ""; self.current_mode = mode
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, "end")
        self.refresh_ui()

    def refresh_ui(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.temp_images.clear()

        ctrl = ctk.CTkFrame(self.scroll, fg_color="transparent"); ctrl.pack(fill="x", padx=5, pady=(5, 15))
        if self.export_selection_mode:
            ctk.CTkLabel(ctrl, text=self.loc("export_ask"), text_color="#e67e22", font=("Arial", 14, "bold")).pack(side="left", padx=10)
        elif self.current_mode == 0:
            ctk.CTkButton(ctrl, text=self.loc("create"), fg_color="#2b8a3e", command=self.create_card).pack(side="left", padx=5)
        else:
            ctk.CTkButton(ctrl, text=self.loc("empty_trash"), fg_color="#7f8c8d", command=self.empty_trash).pack(side="right", padx=5)

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT * FROM cards WHERE deleted=?", (self.current_mode,)).fetchall()

        grid = ctk.CTkFrame(self.scroll, fg_color="transparent"); grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0,1,2,3,4), weight=1)

        disp = 0
        search = self.basic_search_query
        phone_search = self._normalize_phone(search)
        err = self.loc("decryption_error")

        for r in rows:
            fn = self._to_text(self.core.decrypt(r[1], err))
            ln = self._to_text(self.core.decrypt(r[2], err))
            fn_en = self._to_text(self.core.decrypt(r[3], err))
            ln_en = self._to_text(self.core.decrypt(r[4], err))
            country = self._to_text(self.core.decrypt(r[5], err))
            city = self._to_text(self.core.decrypt(r[6], err))
            address = self._to_text(self.core.decrypt(r[7], err))
            phones = self._to_text(self.core.decrypt(r[8], err))
            if self.filtered_ids is not None and r[0] not in self.filtered_ids:
                continue
            haystack = self._normalize_text(f"{fn} {ln} {fn_en} {ln_en} {country} {city} {address} {phones}")
            phone_haystack = self._normalize_phone(phones)
            # Fallback for legacy data where city/address could be swapped.
            city_address_haystack = self._normalize_text(f"{city} {address}")
            if search and search not in haystack and (not phone_search or phone_search not in phone_haystack):
                if search not in city_address_haystack:
                    continue

            color = "#e67e22" if self.export_selection_mode else ("#27ae60" if r[0] in self.highlighted_ids else "#3d3d3d")
            frame = ctk.CTkFrame(grid, fg_color="#2b2b2b", height=50, corner_radius=25, border_width=2, border_color=color)
            frame.grid(row=disp//5, column=disp%5, padx=8, pady=8, sticky="ew")
            frame.grid_propagate(False)

            name = f"{fn} {ln}".strip() or self.loc("no_name")
            cmd = (lambda c=r[0]: self.perform_export(c)) if self.export_selection_mode else (lambda c=r[0]: self.open_card(c))
            ctk.CTkButton(frame, text=name, fg_color="transparent", command=cmd).place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.8)
            disp += 1

    def open_card(self, cid):
        self.gallery_view.pack_forget(); self.details_view.pack(fill="both", expand=True)
        for w in self.details_view.winfo_children(): w.destroy()
        is_new = cid is None
        self.current_edit_card_id = cid

        top = ctk.CTkFrame(self.details_view, fg_color="transparent"); top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text=self.loc("back"), width=100, command=self.close_card).pack(side="left")
        if not is_new:
            ctk.CTkButton(top, text=self.loc("history_btn"), width=100, command=lambda: self.show_card_history(cid)).pack(side="left", padx=5)

        if self.current_mode == 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("to_trash"), fg_color="#c0392b", command=lambda: self.trash_card(cid)).pack(side="right")
            ctk.CTkButton(top, text=self.loc("duplicate_btn"), fg_color="#3498db", command=lambda: self.duplicate_card(cid)).pack(side="right", padx=5)
        elif self.current_mode != 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("perm_del"), fg_color="#922b21", command=lambda: self.perm_del_card(cid)).pack(side="right", padx=5)
            ctk.CTkButton(top, text=self.loc("restore"), fg_color="#2b8a3e", command=lambda: self.restore_card(cid)).pack(side="right", padx=5)

        tabs = ctk.CTkTabview(self.details_view); tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        t_info, t_photo = tabs.add(self.loc("tab_info")), tabs.add(self.loc("tab_photo"))

        row_data = {}
        if not is_new:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                row_data = dict(row) if row else {}

        self.entry_map = {}
        err = self.loc("decryption_error")
        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]

        f_info = ctk.CTkScrollableFrame(t_info, fg_color="transparent"); f_info.pack(fill="both", expand=True)
        entries_list = []
        for i, text in enumerate(self.loc("labels")):
            col = db_cols[i]
            f = ctk.CTkFrame(f_info, fg_color="transparent"); f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=text, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=400)
            existing = self.core.decrypt(row_data.get(col), err) if not is_new else ""
            e.insert(0, self._to_text(existing))
            if self.current_mode == 1: e.configure(state="disabled")
            else: self.entry_map[col] = e; entries_list.append(e)
            e.pack(side="left")

        # Enter: next field or save+exit on last
        if self.current_mode == 0:
            for idx, entry in enumerate(entries_list):
                if idx < len(entries_list) - 1:
                    next_e = entries_list[idx + 1]
                    entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
                else:
                    entry.bind("<Return>", lambda ev, c=cid: self.save_info(c))

        if self.current_mode == 0:
            # Кнопка Сохранить прижата влево
            ctk.CTkButton(f_info, text=self.loc("save_btn"), fg_color="#2b8a3e", command=lambda: self.save_info(self.current_edit_card_id)).pack(pady=20, padx=150, anchor="w")

        self.photo_grid = ctk.CTkScrollableFrame(t_photo, fg_color="transparent"); self.photo_grid.pack(fill="both", expand=True)
        if self.current_mode == 0 and not is_new: ctk.CTkButton(t_photo, text=self.loc("add_photo"), command=lambda: self.add_photo(cid)).pack(pady=10)
        if not is_new:
            self.load_photos(cid)

    def load_photos(self, cid):
        for w in self.photo_grid.winfo_children(): w.destroy()
        with sqlite3.connect(DB_NAME) as conn:
            photos = conn.execute("SELECT id, photo FROM photos WHERE card_id=?", (cid,)).fetchall()
        self.photo_grid.grid_columnconfigure((0,1,2,3,4), weight=1)
        for i, (pid, enc) in enumerate(photos):
            frame = ctk.CTkFrame(self.photo_grid, fg_color="#222222", corner_radius=10); frame.grid(row=i//5, column=i%5, padx=8, pady=8)
            try:
                raw = self.core.decrypt(enc, None)
                if raw is None:
                    raise ValueError("Decryption returned None")
                img = Image.open(io.BytesIO(raw)); img.thumbnail((160, 160))
                ctk_img = ctk.CTkImage(img, size=(160, 160)); self.temp_images.append(ctk_img)
                lbl = ctk.CTkLabel(frame, image=ctk_img, text="", cursor="hand2")
                lbl.pack(pady=10, padx=10)
                lbl.bind("<Button-1>", lambda e, d=raw: self.open_full_image(d))
            except Exception as err:
                error_msg = f"Error: {str(err)[:30]}"
                ctk.CTkLabel(frame, text=error_msg, text_color="#e74c3c").pack(pady=40, padx=20)
            if self.current_mode == 0:
                ctk.CTkButton(frame, text=self.loc("delete"), fg_color="#c0392b", height=20, command=lambda p=pid: self.del_photo(p, cid)).pack(pady=10)

    def open_full_image(self, data):
        top = ctk.CTkToplevel(self); top.title(self.loc("view_title")); top.attributes('-topmost', True)
        try:
            img = Image.open(io.BytesIO(data)); w, h = img.size
            ratio = min(800/w, 800/h) if w>800 or h>800 else 1
            ctk_img = ctk.CTkImage(img, size=(int(w*ratio), int(h*ratio)))
            lbl = ctk.CTkLabel(top, image=ctk_img, text=""); top.image = ctk_img; lbl.pack(padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(top, text=f"Error: {str(e)[:50]}").pack(padx=20, pady=20)

    def save_info(self, cid):
        now = datetime.now().isoformat()
        upd = {k: self.core.encrypt(v.get()) for k, v in self.entry_map.items()}
        if cid is None:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        upd.get("first_name"), upd.get("last_name"), upd.get("first_name_en"), upd.get("last_name_en"),
                        upd.get("country"), upd.get("city"), upd.get("address"), upd.get("phones"),
                        0, now, now
                    )
                )
        else:
            upd["updated_at"] = now
            sql = "UPDATE cards SET " + ", ".join([f"{k}=?" for k in upd.keys()]) + " WHERE id=?"
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(sql, list(upd.values()) + [cid])
        self.close_card()

    def ask_export_type(self):
        if self.current_mode == 1:
            self.set_mode(0)
        self.open_export_dialog()

    def open_export_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title(self.loc("exp"))
        dlg.geometry("700x560")
        dlg.attributes('-topmost', True)
        dlg.transient(self)

        state = {
            "scope": ctk.StringVar(value=self.loc("export_scope_full")),
            "format": ctk.StringVar(value="mtb"),
            "selected_id": ctk.StringVar(value=""),
        }

        root = ctk.CTkFrame(dlg, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(root, text=self.loc("exp"), font=("Arial", 22, "bold")).pack(anchor="w", pady=(0, 10))

        opt = ctk.CTkFrame(root)
        opt.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(opt, text=self.loc("export_scope"), width=120, anchor="w").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkSegmentedButton(opt, values=[self.loc("export_scope_full"), self.loc("export_scope_single")],
                               variable=state["scope"],
                               command=lambda _: update_single_visibility()).grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(opt, text=self.loc("export_format"), width=120, anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ctk.CTkSegmentedButton(opt, values=["mtb", "csv"], variable=state["format"]).grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        opt.grid_columnconfigure(1, weight=1)

        single_frame = ctk.CTkFrame(root)
        single_frame.pack(fill="both", expand=True, pady=(0, 12))
        ctk.CTkLabel(single_frame, text=self.loc("export_pick_card"), anchor="w").pack(anchor="w", padx=10, pady=(10, 6))

        list_scroll = ctk.CTkScrollableFrame(single_frame, height=260)
        list_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT id, first_name, last_name, first_name_en, last_name_en FROM cards WHERE deleted=0 ORDER BY id DESC").fetchall()
        err = self.loc("decryption_error")
        card_items = []
        for cid, fn_b, ln_b, fn_en_b, ln_en_b in rows:
            fn = self._to_text(self.core.decrypt(fn_b, err)).strip()
            ln = self._to_text(self.core.decrypt(ln_b, err)).strip()
            fn_en = self._to_text(self.core.decrypt(fn_en_b, err)).strip()
            ln_en = self._to_text(self.core.decrypt(ln_en_b, err)).strip()
            title = f"{fn} {ln}".strip() or f"{fn_en} {ln_en}".strip() or f"#{cid}"
            card_items.append((cid, title))

        if card_items:
            for cid, title in card_items:
                ctk.CTkRadioButton(list_scroll, text=title, value=str(cid), variable=state["selected_id"]).pack(anchor="w", pady=3, padx=4)
        else:
            ctk.CTkLabel(list_scroll, text=self.loc("export_no_cards")).pack(anchor="w", padx=4, pady=6)

        btn = ctk.CTkFrame(root, fg_color="transparent")
        btn.pack(fill="x")

        def run_export():
            sid = None
            scope_val = state["scope"].get()
            full_val = self.loc("export_scope_full")
            if scope_val != full_val:
                sel = state["selected_id"].get()
                if not sel:
                    self.show_error(self.loc("error"), self.loc("export_select_card"))
                    return
                sid = int(sel)

            fmt = state["format"].get().lower()
            dlg.destroy()
            if fmt == "csv":
                self.export_csv(sid)
            else:
                self.perform_export(sid)

        ctk.CTkButton(btn, text=self.loc("back"), width=120, fg_color="#7f8c8d", command=dlg.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn, text=self.loc("exp"), width=160, fg_color="#2980b9", hover_color="#3498db", command=run_export).pack(side="right")

        def update_single_visibility():
            scope_val = state["scope"].get()
            full_val = self.loc("export_scope_full")
            if scope_val == full_val:
                single_frame.pack_forget()
            else:
                single_frame.pack(fill="both", expand=True, pady=(0, 12))

        update_single_visibility()

    def perform_export(self, sid=None):
        self.export_selection_mode = False; filename = "full_db"
        if sid:
            with sqlite3.connect(DB_NAME) as conn:
                r = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (sid,)).fetchone()
                fn, ln = self.core.decrypt(r[0], "Card"), self.core.decrypt(r[1], "Data")
                filename = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}"
        path = os.path.join(EXPORT_DIR, f"{filename}.mtb")
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                c = [dict(r) for r in (conn.execute("SELECT * FROM cards WHERE id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM cards").fetchall())]
                p = [dict(r) for r in (conn.execute("SELECT * FROM photos WHERE card_id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM photos").fetchall())]
            for r in c:
                for k in r:
                    if isinstance(r[k], bytes): r[k] = r[k].hex()
            for r in p: r['photo'] = r['photo'].hex()
            with open(path, "w") as f: json.dump({"cards": c, "photos": p}, f)
            self.show_info(self.loc("exp"), self.loc("export_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))
        self.refresh_ui()

    def create_card(self):
        self.open_card(None)

    def add_photo(self, cid):
        ps = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if not ps: return
        with sqlite3.connect(DB_NAME) as conn:
            for p in ps:
                with open(p, "rb") as f: blob = f.read()
                conn.execute("INSERT INTO photos(card_id, photo, created_at) VALUES (?,?,?)", (cid, self.core.encrypt(blob), datetime.now().isoformat()))
        self.load_photos(cid)

    def del_photo(self, pid, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM photos WHERE id=?", (pid,))
        self.load_photos(cid)

    def trash_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=1 WHERE id=?", (cid,))
        self.close_card()

    def restore_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=0 WHERE id=?", (cid,))
        self.close_card()

    def perm_del_card(self, cid):
        if self.ask_yes_no(self.loc("perm_del"), self.loc("perm_del_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id=?", (cid,)); conn.execute("DELETE FROM cards WHERE id=?", (cid,))
            self.close_card()

    def close_card(self):
        self.current_edit_card_id = None
        self.details_view.pack_forget(); self.gallery_view.pack(fill="both", expand=True); self.refresh_ui()

    def empty_trash(self):
        with sqlite3.connect(DB_NAME) as conn:
            if conn.execute("SELECT COUNT(*) FROM cards WHERE deleted=1").fetchone()[0] == 0:
                self.show_info(self.loc("trash"), self.loc("trash_is_empty")); return
        if self.ask_yes_no(self.loc("trash"), self.loc("empty_trash_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id IN (SELECT id FROM cards WHERE deleted=1)")
                conn.execute("DELETE FROM cards WHERE deleted=1")
            self.refresh_ui()

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("Mentality Backup", "*.mtb")])
        if not path: return
        try:
            with open(path, "r") as f: data = json.load(f)
            with sqlite3.connect(DB_NAME) as conn:
                for c in data['cards']:
                    for k in ['first_name', 'last_name', 'first_name_en', 'last_name_en', 'country', 'city', 'address', 'phones']:
                        if c[k]: c[k] = bytes.fromhex(c[k])
                    fn, ln = self.core.decrypt(c['first_name'], "User"), self.core.decrypt(c['last_name'], "Import")
                    ex = conn.execute("SELECT id FROM cards WHERE first_name=? AND last_name=?", (c['first_name'], c['last_name'])).fetchone()
                    mode = "new"
                    if ex:
                        res = self.ask_yes_no_cancel(self.loc("duplicate_title"), self.loc("duplicate_msg").format(fn, ln))
                        if res == "yes": mode = "replace"
                        elif res == "no": mode = "new"
                        else: continue
                    if mode == "replace":
                        cid = ex[0]
                        conn.execute("UPDATE cards SET first_name_en=?, last_name_en=?, country=?, city=?, address=?, phones=? WHERE id=?", (c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], cid))
                        conn.execute("DELETE FROM photos WHERE card_id=?", (cid,))
                    else:
                        cid = conn.execute("INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c['first_name'], c['last_name'], c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], 0, datetime.now().isoformat(), datetime.now().isoformat())).lastrowid
                    for p in [ph for ph in data['photos'] if ph['card_id'] == c['id']]:
                        conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)", (cid, bytes.fromhex(p['photo']), p['created_at']))
            self.refresh_ui(); self.show_info(self.loc("success"), self.loc("import_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))

    def open_settings(self):
        sw = ctk.CTkToplevel(self); sw.title(self.loc("settings")); sw.geometry("400x300"); sw.attributes('-topmost', True)
        for label, key, vals, cmd in [
            (self.loc("settings_theme"), "theme", ["Dark", "Light"], lambda v: (self.core.cfg.update({"theme": v}), self.core.save_config(self.core.cfg), ctk.set_appearance_mode(v))),
            (self.loc("settings_language"), "language", list(self.core.languages.keys()), lambda v: (self.core.cfg.update({"language": v}), self.core.save_config(self.core.cfg), self.rebuild_ui()))
        ]:
            f = ctk.CTkFrame(sw, fg_color="transparent"); f.pack(fill="x", padx=30, pady=10)
            ctk.CTkLabel(f, text=label).pack(side="left")
            ctk.CTkOptionMenu(f, values=vals, command=cmd, variable=ctk.StringVar(value=self.core.cfg[key])).pack(side="right")

    def quit_app(self):
        if self.ask_yes_no(self.loc("exit"), self.loc("exit_confirm")): self.quit()

    def export_csv(self, sid=None):
        """Export database to CSV format"""
        try:
            initial_name = "contacts.csv"
            if sid:
                with sqlite3.connect(DB_NAME) as conn:
                    row = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (sid,)).fetchone()
                if row:
                    fn = self._to_text(self.core.decrypt(row[0], "Card")).strip() or "Card"
                    ln = self._to_text(self.core.decrypt(row[1], "Data")).strip() or "Data"
                    initial_name = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}.csv"
            path = filedialog.asksaveasfilename(initialfile=initial_name, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path: return
            with sqlite3.connect(DB_NAME) as conn:
                if sid:
                    rows = conn.execute("SELECT * FROM cards WHERE id=? AND deleted=0", (sid,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM cards WHERE deleted=0 ORDER BY first_name").fetchall()
            
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.loc("csv_headers"))
                err = self.loc("decryption_error")
                for r in rows:
                    fn = self.core.decrypt(r[1], "[Enc]")
                    ln = self.core.decrypt(r[2], "[Enc]")
                    fn_en = self.core.decrypt(r[3], "[Enc]")
                    ln_en = self.core.decrypt(r[4], "[Enc]")
                    country = self.core.decrypt(r[5], "[Enc]")
                    city = self.core.decrypt(r[6], "[Enc]")
                    address = self.core.decrypt(r[7], "[Enc]")
                    phones = self.core.decrypt(r[8], "[Enc]")
                    writer.writerow([fn, ln, fn_en, ln_en, country, city, address, phones, r[10], r[11]])
            self.show_info(self.loc("export_csv_title"), self.loc("export_csv_done").format(path))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def auto_backup(self):
        """Create automatic backup"""
        try:
            backup_path = self.core.create_backup()
            if backup_path:
                self.show_info(self.loc("success"), self.loc("backup_done").format(backup_path))
            else:
                self.show_error(self.loc("error"), self.loc("backup_fail"))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def duplicate_card(self, cid):
        """Create duplicate of contact"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                
                # Insert new card
                new_id = conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row['first_name'], row['last_name'], row['first_name_en'], row['last_name_en'], 
                     row['country'], row['city'], row['address'], row['phones'], 
                     datetime.now().isoformat(), datetime.now().isoformat())
                ).lastrowid
                
                # Copy photos
                photos = conn.execute("SELECT photo FROM photos WHERE card_id=?", (cid,)).fetchall()
                for photo in photos:
                    conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)",
                               (new_id, photo[0], datetime.now().isoformat()))
            
            self.show_info(self.loc("success"), self.loc("duplicate_success"))
            self.refresh_ui()
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def show_card_history(self, cid):
        """Show card creation and update dates"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT created_at, updated_at FROM cards WHERE id=?", (cid,)).fetchone()
            
            if row:
                created = row[0] or self.loc("history_unknown")
                updated = row[1] or self.loc("history_not_updated")
                msg = self.loc("history_created").format(created) + "\n" + self.loc("history_updated").format(updated)
                self.show_info(self.loc("history_title"), msg)
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def advanced_search(self):
        """Open advanced search window"""
        sw = ctk.CTkToplevel(self)
        sw.title(self.loc("search_advanced_title"))
        sw.geometry("500x430")
        sw.attributes('-topmost', True)

        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]
        labels = self.loc("labels")
        search_vars = {}
        entries_list = []

        f_search = ctk.CTkScrollableFrame(sw, fg_color="transparent")
        f_search.pack(fill="both", expand=True, padx=20, pady=20)

        for i, label in enumerate(labels):
            f = ctk.CTkFrame(f_search, fg_color="transparent")
            f.pack(fill="x", pady=5)
            ctk.CTkLabel(f, text=label, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=300)
            e.pack(side="left")
            search_vars[db_cols[i]] = e
            entries_list.append(e)

        def perform_search():
            query_terms = {k: v.get().strip() for k, v in search_vars.items() if v.get().strip()}
            if not query_terms:
                return
            err = self.loc("decryption_error")
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0").fetchall()
            found_ids = set()
            for row in rows:
                match = True
                for col, term in query_terms.items():
                    col_idx = db_cols.index(col)
                    decrypted = self._normalize_text(self.core.decrypt(row[col_idx + 1], err))
                    term_norm = self._normalize_text(term)
                    if col == "phones":
                        if self._normalize_phone(term_norm) not in self._normalize_phone(decrypted):
                            match = False
                            break
                    elif col == "city":
                        city_val = self._normalize_text(self.core.decrypt(row[6], err))
                        address_val = self._normalize_text(self.core.decrypt(row[7], err))
                        if term_norm not in city_val and term_norm not in address_val:
                            match = False
                            break
                    elif term_norm not in decrypted:
                        match = False
                        break
                if match:
                    found_ids.add(row[0])
            sw.destroy()
            self.current_mode = 0
            self.export_selection_mode = False
            self.search_entry.delete(0, "end")
            self.basic_search_query = ""
            self.highlighted_ids = found_ids
            self.filtered_ids = found_ids
            self.refresh_ui()

        # Enter key: navigate between fields, last field triggers search
        for idx, entry in enumerate(entries_list):
            if idx < len(entries_list) - 1:
                next_e = entries_list[idx + 1]
                entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
            else:
                entry.bind("<Return>", lambda ev: perform_search())

        ctk.CTkButton(f_search, text=self.loc("search_btn"), fg_color="#2b8a3e", command=perform_search).pack(pady=20)

if __name__ == "__main__":
    app = MentalityGUI(); app.mainloop()
import sqlite3
import os
import json
import customtkinter as ctk # type: ignore
from PIL import Image # type: ignore
import io
from datetime import datetime
from tkinter import filedialog
import re
import csv
import shutil
import unicodedata

# --- ШИФРОВАНИЕ ---
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# --- ПАТЧ ДЛЯ Python 3.13+ ---
try:
    from customtkinter.windows.widgets import ctk_scrollable_frame # type: ignore
    original_check = ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas
    def patched_check(self, widget):
        if isinstance(widget, str): return False
        return original_check(self, widget)
    ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas = patched_check
except: pass

# --- CONFIG & PATHS ---
VERSION = "0.20.2"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_NAME = os.path.join(SCRIPT_DIR, "database.db")
KEY_PATH = os.path.join(SCRIPT_DIR, ".mentality_key")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
EXPORT_DIR = os.path.join(SCRIPT_DIR, "exports")
LANG_DIR = os.path.join(SCRIPT_DIR, "languages")
OLD_DATA_DIR = os.path.join(SCRIPT_DIR, "old_data")

for d in [EXPORT_DIR, LANG_DIR, OLD_DATA_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class MentalityCore:
    def __init__(self):
        if not HAS_CRYPTO: raise ImportError("pip install cryptography")
        self.key = self.load_or_create_key()
        self.cipher = Fernet(self.key)
        self.init_db()
        self.cfg = self.load_config()
        self.languages = {}
        self.init_languages()

    def load_or_create_key(self):
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as kf: return kf.read()
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as kf: kf.write(key)
        return key

    def encrypt(self, data):
        if not data: return None
        if isinstance(data, str): data = data.encode('utf-8')
        return self.cipher.encrypt(data)

    def decrypt(self, data, err_msg="[Error]"):
        if not data: return ""
        try:
            dec = self.cipher.decrypt(data)
            try: return dec.decode('utf-8')
            except: return dec
        except: return err_msg

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name BLOB, last_name BLOB, first_name_en BLOB, last_name_en BLOB,
                country BLOB, city BLOB, address BLOB, phones BLOB,
                deleted INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER,
                photo BLOB, created_at TEXT)""")

    def load_config(self):
        default = {"language": "ru", "theme": "Dark"}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return default

    def save_config(self, cfg):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def init_languages(self):
        for file in os.listdir(LANG_DIR):
            if file.endswith(".json"):
                lang_name = file.replace(".json", "")
                with open(os.path.join(LANG_DIR, file), "r", encoding="utf-8") as f:
                    self.languages[lang_name] = json.load(f)
        if not self.languages:
            raise FileNotFoundError(f"No language files found in {LANG_DIR}")

    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        """Validate phone format (basic)"""
        if not phone:
            return True
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        return len(phone) >= 6 and any(c.isdigit() for c in phone)

    def create_backup(self):
        """Create automatic backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(EXPORT_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_NAME, backup_path)
            return backup_path
        except Exception as e:
            return None

class MentalityGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.core = None
        try: self.core = MentalityCore()
        except Exception as e:
            self.show_error("Error", str(e)); self.destroy(); return

        ctk.set_appearance_mode(self.core.cfg.get("theme", "Dark"))
        self.title(f"Mentality DB v{VERSION}")
        self.geometry("1250x850")
        self.current_mode = 0
        self.temp_images = []
        self.export_selection_mode = False
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.current_edit_card_id = None
        self.basic_search_query = ""

        self.bind("<Escape>", lambda e: self.handle_esc())
        self.rebuild_ui()

    # --- Custom dialogs (CTkToplevel, theme-aware) ---
    def _dialog(self, title, message, buttons, icon_color="#3498db"):
        result = [None]
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("420x180")
        dlg.attributes('-topmost', True)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.update_idletasks()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except Exception:
            pass

        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=15)
        ctk.CTkLabel(body, text=message, wraplength=370, justify="left", font=("Arial", 13)).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")
        for text, value, color in buttons:
            def cmd(v=value): result[0] = v; dlg.destroy()
            ctk.CTkButton(btn_frame, text=text, width=100, fg_color=color, command=cmd).pack(side="left", padx=5, expand=True)

        dlg.wait_window()
        return result[0]

    def show_info(self, title, message):
        self._dialog(title, message, [("OK", True, "#2b8a3e")])

    def show_error(self, title, message):
        self._dialog(title, message, [("OK", True, "#c0392b")], "#c0392b")

    def ask_yes_no(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        return self._dialog(title, message, [(yes, True, "#2b8a3e"), (no, False, "#c0392b")])

    def ask_yes_no_cancel(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        cancel = "Отмена" if lang == "ru" else "Cancel"
        return self._dialog(title, message, [(yes, "yes", "#2b8a3e"), (no, "no", "#3498db"), (cancel, "cancel", "#7f8c8d")])

    def loc(self, key):
        lang = self.core.cfg.get("language", "ru")
        lang_data = self.core.languages.get(lang, self.core.languages.get("ru", {}))
        return lang_data.get(key, key)

    @staticmethod
    def _to_text(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(value)

    @staticmethod
    def _normalize_phone(value):
        return "".join(ch for ch in str(value) if ch.isdigit())

    @staticmethod
    def _normalize_text(value):
        text = MentalityGUI._to_text(value)
        text = unicodedata.normalize("NFKC", text)
        return " ".join(text.strip().casefold().split())

    def handle_esc(self):
        if self.export_selection_mode:
            self.export_selection_mode = False; self.refresh_ui(); return
        if hasattr(self, 'details_view') and self.details_view.winfo_viewable(): self.close_card()

    def rebuild_ui(self):
        for widget in self.winfo_children(): widget.destroy()
        self.gallery_view = ctk.CTkFrame(self, fg_color="transparent")
        self.gallery_view.pack(fill="both", expand=True)
        self.details_view = ctk.CTkFrame(self, fg_color="transparent")

        # SIDEBAR
        side = ctk.CTkFrame(self.gallery_view, width=180)
        side.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(side, text=self.loc("menu"), font=("Arial", 18, "bold")).pack(pady=15)

        ctk.CTkButton(side, text=self.loc("base"), fg_color="#1a6b9a", hover_color="#2980b9", command=lambda: self.set_mode(0)).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("trash"), fg_color="#5d6d7e", hover_color="#7f8c8d", command=lambda: self.set_mode(1)).pack(pady=5, padx=10, fill="x")

        exp_row = ctk.CTkFrame(side, fg_color="transparent")
        exp_row.pack(pady=5, padx=10, fill="x")
        exp_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(exp_row, text=self.loc("exp"), fg_color="#2980b9", hover_color="#3498db", command=self.ask_export_type).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(exp_row, text=self.loc("imp"), fg_color="#d35400", hover_color="#e67e22", command=self.import_data).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkButton(side, text=self.loc("exp_csv"), fg_color="#16a085", hover_color="#1abc9c", command=self.export_csv).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("backup_btn"), fg_color="#7d3c98", hover_color="#9b59b6", command=self.auto_backup).pack(pady=5, padx=10, fill="x")

        ctk.CTkButton(side, text=self.loc("exit"), fg_color="#c0392b", hover_color="#e74c3c", command=self.quit_app).pack(side="bottom", pady=(5, 20), padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("settings"), command=self.open_settings).pack(side="bottom", pady=5, padx=10, fill="x")

        # CONTENT
        cont = ctk.CTkFrame(self.gallery_view, fg_color="transparent")
        cont.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(cont, height=50)
        top.pack(fill="x", pady=(0, 10))
        self.search_entry = ctk.CTkEntry(top, width=400, placeholder_text=self.loc("search_base"))
        self.search_entry.pack(side="left", padx=20, pady=10)
        self.search_entry.bind("<Return>", lambda e: self.apply_basic_search())
        ctk.CTkButton(top, text="🔎", width=36, command=self.apply_basic_search).pack(side="left", padx=(0, 8), pady=10)
        ctk.CTkButton(top, text=self.loc("search_advanced"), width=100, command=self.advanced_search).pack(side="left", padx=5, pady=10)

        self.scroll = ctk.CTkScrollableFrame(cont, label_text=self.loc("list_title"), label_font=("Arial", 20, "bold"))
        self.scroll.pack(fill="both", expand=True)
        self.refresh_ui()

    def apply_basic_search(self):
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.basic_search_query = self._normalize_text(self.search_entry.get())
        self.refresh_ui()

    def set_mode(self, mode):
        self.export_selection_mode = False; self.highlighted_ids = set(); self.filtered_ids = None; self.basic_search_query = ""; self.current_mode = mode
        if hasattr(self, "search_entry"):
            self.search_entry.delete(0, "end")
        self.refresh_ui()

    def refresh_ui(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.temp_images.clear()

        ctrl = ctk.CTkFrame(self.scroll, fg_color="transparent"); ctrl.pack(fill="x", padx=5, pady=(5, 15))
        if self.export_selection_mode:
            ctk.CTkLabel(ctrl, text=self.loc("export_ask"), text_color="#e67e22", font=("Arial", 14, "bold")).pack(side="left", padx=10)
        elif self.current_mode == 0:
            ctk.CTkButton(ctrl, text=self.loc("create"), fg_color="#2b8a3e", command=self.create_card).pack(side="left", padx=5)
        else:
            ctk.CTkButton(ctrl, text=self.loc("empty_trash"), fg_color="#7f8c8d", command=self.empty_trash).pack(side="right", padx=5)

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT * FROM cards WHERE deleted=?", (self.current_mode,)).fetchall()

        grid = ctk.CTkFrame(self.scroll, fg_color="transparent"); grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0,1,2,3,4), weight=1)

        disp = 0
        search = self.basic_search_query
        phone_search = self._normalize_phone(search)
        err = self.loc("decryption_error")

        for r in rows:
            fn = self._to_text(self.core.decrypt(r[1], err))
            ln = self._to_text(self.core.decrypt(r[2], err))
            fn_en = self._to_text(self.core.decrypt(r[3], err))
            ln_en = self._to_text(self.core.decrypt(r[4], err))
            country = self._to_text(self.core.decrypt(r[5], err))
            city = self._to_text(self.core.decrypt(r[6], err))
            address = self._to_text(self.core.decrypt(r[7], err))
            phones = self._to_text(self.core.decrypt(r[8], err))
            if self.filtered_ids is not None and r[0] not in self.filtered_ids:
                continue
            haystack = self._normalize_text(f"{fn} {ln} {fn_en} {ln_en} {country} {city} {address} {phones}")
            phone_haystack = self._normalize_phone(phones)
            if search and search not in haystack and (not phone_search or phone_search not in phone_haystack):
                continue

            color = "#e67e22" if self.export_selection_mode else ("#27ae60" if r[0] in self.highlighted_ids else "#3d3d3d")
            frame = ctk.CTkFrame(grid, fg_color="#2b2b2b", height=50, corner_radius=25, border_width=2, border_color=color)
            frame.grid(row=disp//5, column=disp%5, padx=8, pady=8, sticky="ew")
            frame.grid_propagate(False)

            name = f"{fn} {ln}".strip() or self.loc("no_name")
            cmd = (lambda c=r[0]: self.perform_export(c)) if self.export_selection_mode else (lambda c=r[0]: self.open_card(c))
            ctk.CTkButton(frame, text=name, fg_color="transparent", command=cmd).place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.8)
            disp += 1

    def open_card(self, cid):
        self.gallery_view.pack_forget(); self.details_view.pack(fill="both", expand=True)
        for w in self.details_view.winfo_children(): w.destroy()
        is_new = cid is None
        self.current_edit_card_id = cid

        top = ctk.CTkFrame(self.details_view, fg_color="transparent"); top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text=self.loc("back"), width=100, command=self.close_card).pack(side="left")
        if not is_new:
            ctk.CTkButton(top, text=self.loc("history_btn"), width=100, command=lambda: self.show_card_history(cid)).pack(side="left", padx=5)

        if self.current_mode == 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("to_trash"), fg_color="#c0392b", command=lambda: self.trash_card(cid)).pack(side="right")
            ctk.CTkButton(top, text=self.loc("duplicate_btn"), fg_color="#3498db", command=lambda: self.duplicate_card(cid)).pack(side="right", padx=5)
        elif self.current_mode != 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("perm_del"), fg_color="#922b21", command=lambda: self.perm_del_card(cid)).pack(side="right", padx=5)
            ctk.CTkButton(top, text=self.loc("restore"), fg_color="#2b8a3e", command=lambda: self.restore_card(cid)).pack(side="right", padx=5)

        tabs = ctk.CTkTabview(self.details_view); tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        t_info, t_photo = tabs.add(self.loc("tab_info")), tabs.add(self.loc("tab_photo"))

        row_data = {}
        if not is_new:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                row_data = dict(row) if row else {}

        self.entry_map = {}
        err = self.loc("decryption_error")
        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]

        f_info = ctk.CTkScrollableFrame(t_info, fg_color="transparent"); f_info.pack(fill="both", expand=True)
        entries_list = []
        for i, text in enumerate(self.loc("labels")):
            col = db_cols[i]
            f = ctk.CTkFrame(f_info, fg_color="transparent"); f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=text, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=400)
            existing = self.core.decrypt(row_data.get(col), err) if not is_new else ""
            e.insert(0, self._to_text(existing))
            if self.current_mode == 1: e.configure(state="disabled")
            else: self.entry_map[col] = e; entries_list.append(e)
            e.pack(side="left")

        # Enter: next field or save+exit on last
        if self.current_mode == 0:
            for idx, entry in enumerate(entries_list):
                if idx < len(entries_list) - 1:
                    next_e = entries_list[idx + 1]
                    entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
                else:
                    entry.bind("<Return>", lambda ev, c=cid: self.save_info(c))

        if self.current_mode == 0:
            # Кнопка Сохранить прижата влево
            ctk.CTkButton(f_info, text=self.loc("save_btn"), fg_color="#2b8a3e", command=lambda: self.save_info(self.current_edit_card_id)).pack(pady=20, padx=150, anchor="w")

        self.photo_grid = ctk.CTkScrollableFrame(t_photo, fg_color="transparent"); self.photo_grid.pack(fill="both", expand=True)
        if self.current_mode == 0 and not is_new: ctk.CTkButton(t_photo, text=self.loc("add_photo"), command=lambda: self.add_photo(cid)).pack(pady=10)
        if not is_new:
            self.load_photos(cid)

    def load_photos(self, cid):
        for w in self.photo_grid.winfo_children(): w.destroy()
        with sqlite3.connect(DB_NAME) as conn:
            photos = conn.execute("SELECT id, photo FROM photos WHERE card_id=?", (cid,)).fetchall()
        self.photo_grid.grid_columnconfigure((0,1,2,3,4), weight=1)
        for i, (pid, enc) in enumerate(photos):
            frame = ctk.CTkFrame(self.photo_grid, fg_color="#222222", corner_radius=10); frame.grid(row=i//5, column=i%5, padx=8, pady=8)
            try:
                raw = self.core.decrypt(enc, None)
                if raw is None:
                    raise ValueError("Decryption returned None")
                img = Image.open(io.BytesIO(raw)); img.thumbnail((160, 160))
                ctk_img = ctk.CTkImage(img, size=(160, 160)); self.temp_images.append(ctk_img)
                lbl = ctk.CTkLabel(frame, image=ctk_img, text="", cursor="hand2")
                lbl.pack(pady=10, padx=10)
                lbl.bind("<Button-1>", lambda e, d=raw: self.open_full_image(d))
            except Exception as err:
                error_msg = f"Error: {str(err)[:30]}"
                ctk.CTkLabel(frame, text=error_msg, text_color="#e74c3c").pack(pady=40, padx=20)
            if self.current_mode == 0:
                ctk.CTkButton(frame, text=self.loc("delete"), fg_color="#c0392b", height=20, command=lambda p=pid: self.del_photo(p, cid)).pack(pady=10)

    def open_full_image(self, data):
        top = ctk.CTkToplevel(self); top.title(self.loc("view_title")); top.attributes('-topmost', True)
        try:
            img = Image.open(io.BytesIO(data)); w, h = img.size
            ratio = min(800/w, 800/h) if w>800 or h>800 else 1
            ctk_img = ctk.CTkImage(img, size=(int(w*ratio), int(h*ratio)))
            lbl = ctk.CTkLabel(top, image=ctk_img, text=""); top.image = ctk_img; lbl.pack(padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(top, text=f"Error: {str(e)[:50]}").pack(padx=20, pady=20)

    def save_info(self, cid):
        now = datetime.now().isoformat()
        upd = {k: self.core.encrypt(v.get()) for k, v in self.entry_map.items()}
        if cid is None:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        upd.get("first_name"), upd.get("last_name"), upd.get("first_name_en"), upd.get("last_name_en"),
                        upd.get("country"), upd.get("city"), upd.get("address"), upd.get("phones"),
                        0, now, now
                    )
                )
        else:
            upd["updated_at"] = now
            sql = "UPDATE cards SET " + ", ".join([f"{k}=?" for k in upd.keys()]) + " WHERE id=?"
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(sql, list(upd.values()) + [cid])
        self.close_card()

    def ask_export_type(self):
        if self.current_mode == 1: self.set_mode(0)
        res = self.ask_yes_no_cancel(self.loc("exp"), self.loc("export_ask"))
        if res == "yes": self.perform_export(None)
        elif res == "no": self.export_selection_mode = True; self.refresh_ui()

    def perform_export(self, sid=None):
        self.export_selection_mode = False; filename = "full_db"
        if sid:
            with sqlite3.connect(DB_NAME) as conn:
                r = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (sid,)).fetchone()
                fn, ln = self.core.decrypt(r[0], "Card"), self.core.decrypt(r[1], "Data")
                filename = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}"
        path = os.path.join(EXPORT_DIR, f"{filename}.mtb")
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                c = [dict(r) for r in (conn.execute("SELECT * FROM cards WHERE id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM cards").fetchall())]
                p = [dict(r) for r in (conn.execute("SELECT * FROM photos WHERE card_id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM photos").fetchall())]
            for r in c:
                for k in r:
                    if isinstance(r[k], bytes): r[k] = r[k].hex()
            for r in p: r['photo'] = r['photo'].hex()
            with open(path, "w") as f: json.dump({"cards": c, "photos": p}, f)
            self.show_info(self.loc("exp"), self.loc("export_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))
        self.refresh_ui()

    def create_card(self):
        self.open_card(None)

    def add_photo(self, cid):
        ps = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if not ps: return
        with sqlite3.connect(DB_NAME) as conn:
            for p in ps:
                with open(p, "rb") as f: blob = f.read()
                conn.execute("INSERT INTO photos(card_id, photo, created_at) VALUES (?,?,?)", (cid, self.core.encrypt(blob), datetime.now().isoformat()))
        self.load_photos(cid)

    def del_photo(self, pid, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM photos WHERE id=?", (pid,))
        self.load_photos(cid)

    def trash_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=1 WHERE id=?", (cid,))
        self.close_card()

    def restore_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=0 WHERE id=?", (cid,))
        self.close_card()

    def perm_del_card(self, cid):
        if self.ask_yes_no(self.loc("perm_del"), self.loc("perm_del_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id=?", (cid,)); conn.execute("DELETE FROM cards WHERE id=?", (cid,))
            self.close_card()

    def close_card(self):
        self.current_edit_card_id = None
        self.details_view.pack_forget(); self.gallery_view.pack(fill="both", expand=True); self.refresh_ui()

    def empty_trash(self):
        with sqlite3.connect(DB_NAME) as conn:
            if conn.execute("SELECT COUNT(*) FROM cards WHERE deleted=1").fetchone()[0] == 0:
                self.show_info(self.loc("trash"), self.loc("trash_is_empty")); return
        if self.ask_yes_no(self.loc("trash"), self.loc("empty_trash_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id IN (SELECT id FROM cards WHERE deleted=1)")
                conn.execute("DELETE FROM cards WHERE deleted=1")
            self.refresh_ui()

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("Mentality Backup", "*.mtb")])
        if not path: return
        try:
            with open(path, "r") as f: data = json.load(f)
            with sqlite3.connect(DB_NAME) as conn:
                for c in data['cards']:
                    for k in ['first_name', 'last_name', 'first_name_en', 'last_name_en', 'country', 'city', 'address', 'phones']:
                        if c[k]: c[k] = bytes.fromhex(c[k])
                    fn, ln = self.core.decrypt(c['first_name'], "User"), self.core.decrypt(c['last_name'], "Import")
                    ex = conn.execute("SELECT id FROM cards WHERE first_name=? AND last_name=?", (c['first_name'], c['last_name'])).fetchone()
                    mode = "new"
                    if ex:
                        res = self.ask_yes_no_cancel(self.loc("duplicate_title"), self.loc("duplicate_msg").format(fn, ln))
                        if res == "yes": mode = "replace"
                        elif res == "no": mode = "new"
                        else: continue
                    if mode == "replace":
                        cid = ex[0]
                        conn.execute("UPDATE cards SET first_name_en=?, last_name_en=?, country=?, city=?, address=?, phones=? WHERE id=?", (c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], cid))
                        conn.execute("DELETE FROM photos WHERE card_id=?", (cid,))
                    else:
                        cid = conn.execute("INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c['first_name'], c['last_name'], c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], 0, datetime.now().isoformat(), datetime.now().isoformat())).lastrowid
                    for p in [ph for ph in data['photos'] if ph['card_id'] == c['id']]:
                        conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)", (cid, bytes.fromhex(p['photo']), p['created_at']))
            self.refresh_ui(); self.show_info(self.loc("success"), self.loc("import_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))

    def open_settings(self):
        sw = ctk.CTkToplevel(self); sw.title(self.loc("settings")); sw.geometry("400x300"); sw.attributes('-topmost', True)
        for label, key, vals, cmd in [
            (self.loc("settings_theme"), "theme", ["Dark", "Light"], lambda v: (self.core.cfg.update({"theme": v}), self.core.save_config(self.core.cfg), ctk.set_appearance_mode(v))),
            (self.loc("settings_language"), "language", list(self.core.languages.keys()), lambda v: (self.core.cfg.update({"language": v}), self.core.save_config(self.core.cfg), self.rebuild_ui()))
        ]:
            f = ctk.CTkFrame(sw, fg_color="transparent"); f.pack(fill="x", padx=30, pady=10)
            ctk.CTkLabel(f, text=label).pack(side="left")
            ctk.CTkOptionMenu(f, values=vals, command=cmd, variable=ctk.StringVar(value=self.core.cfg[key])).pack(side="right")

    def quit_app(self):
        if self.ask_yes_no(self.loc("exit"), self.loc("exit_confirm")): self.quit()

    def export_csv(self):
        """Export database to CSV format"""
        try:
            path = filedialog.asksaveasfilename(initialfile="contacts.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path: return
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0 ORDER BY first_name").fetchall()
            
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.loc("csv_headers"))
                err = self.loc("decryption_error")
                for r in rows:
                    fn = self.core.decrypt(r[1], "[Enc]")
                    ln = self.core.decrypt(r[2], "[Enc]")
                    fn_en = self.core.decrypt(r[3], "[Enc]")
                    ln_en = self.core.decrypt(r[4], "[Enc]")
                    country = self.core.decrypt(r[5], "[Enc]")
                    city = self.core.decrypt(r[6], "[Enc]")
                    address = self.core.decrypt(r[7], "[Enc]")
                    phones = self.core.decrypt(r[8], "[Enc]")
                    writer.writerow([fn, ln, fn_en, ln_en, country, city, address, phones, r[10], r[11]])
            self.show_info(self.loc("export_csv_title"), self.loc("export_csv_done").format(path))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def auto_backup(self):
        """Create automatic backup"""
        try:
            backup_path = self.core.create_backup()
            if backup_path:
                self.show_info(self.loc("success"), self.loc("backup_done").format(backup_path))
            else:
                self.show_error(self.loc("error"), self.loc("backup_fail"))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def duplicate_card(self, cid):
        """Create duplicate of contact"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                
                # Insert new card
                new_id = conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row['first_name'], row['last_name'], row['first_name_en'], row['last_name_en'], 
                     row['country'], row['city'], row['address'], row['phones'], 
                     datetime.now().isoformat(), datetime.now().isoformat())
                ).lastrowid
                
                # Copy photos
                photos = conn.execute("SELECT photo FROM photos WHERE card_id=?", (cid,)).fetchall()
                for photo in photos:
                    conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)",
                               (new_id, photo[0], datetime.now().isoformat()))
            
            self.show_info(self.loc("success"), self.loc("duplicate_success"))
            self.refresh_ui()
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def show_card_history(self, cid):
        """Show card creation and update dates"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT created_at, updated_at FROM cards WHERE id=?", (cid,)).fetchone()
            
            if row:
                created = row[0] or self.loc("history_unknown")
                updated = row[1] or self.loc("history_not_updated")
                msg = self.loc("history_created").format(created) + "\n" + self.loc("history_updated").format(updated)
                self.show_info(self.loc("history_title"), msg)
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def advanced_search(self):
        """Open advanced search window"""
        sw = ctk.CTkToplevel(self)
        sw.title(self.loc("search_advanced_title"))
        sw.geometry("500x430")
        sw.attributes('-topmost', True)

        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]
        labels = self.loc("labels")
        search_vars = {}
        entries_list = []

        f_search = ctk.CTkScrollableFrame(sw, fg_color="transparent")
        f_search.pack(fill="both", expand=True, padx=20, pady=20)

        for i, label in enumerate(labels):
            f = ctk.CTkFrame(f_search, fg_color="transparent")
            f.pack(fill="x", pady=5)
            ctk.CTkLabel(f, text=label, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=300)
            e.pack(side="left")
            search_vars[db_cols[i]] = e
            entries_list.append(e)

        def perform_search():
            query_terms = {k: v.get().strip() for k, v in search_vars.items() if v.get().strip()}
            if not query_terms:
                return
            err = self.loc("decryption_error")
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0").fetchall()
            found_ids = set()
            for row in rows:
                match = True
                for col, term in query_terms.items():
                    col_idx = db_cols.index(col)
                    decrypted = self._normalize_text(self.core.decrypt(row[col_idx + 1], err))
                    term_norm = self._normalize_text(term)
                    if col == "phones":
                        if self._normalize_phone(term_norm) not in self._normalize_phone(decrypted):
                            match = False
                            break
                    elif term_norm not in decrypted:
                        match = False
                        break
                if match:
                    found_ids.add(row[0])
            sw.destroy()
            self.current_mode = 0
            self.export_selection_mode = False
            self.search_entry.delete(0, "end")
            self.basic_search_query = ""
            self.highlighted_ids = found_ids
            self.filtered_ids = found_ids
            self.refresh_ui()

        # Enter key: navigate between fields, last field triggers search
        for idx, entry in enumerate(entries_list):
            if idx < len(entries_list) - 1:
                next_e = entries_list[idx + 1]
                entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
            else:
                entry.bind("<Return>", lambda ev: perform_search())

        ctk.CTkButton(f_search, text=self.loc("search_btn"), fg_color="#2b8a3e", command=perform_search).pack(pady=20)

if __name__ == "__main__":
    app = MentalityGUI(); app.mainloop()
import sqlite3
import os
import json
import customtkinter as ctk # type: ignore
from PIL import Image # type: ignore
import io
from datetime import datetime
from tkinter import filedialog, messagebox
import re
import csv
import shutil

# --- ШИФРОВАНИЕ ---
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

# --- ПАТЧ ДЛЯ Python 3.13+ ---
try:
    from customtkinter.windows.widgets import ctk_scrollable_frame # type: ignore
    original_check = ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas
    def patched_check(self, widget):
        if isinstance(widget, str): return False
        return original_check(self, widget)
    ctk_scrollable_frame.CTkScrollableFrame.check_if_master_is_canvas = patched_check
except: pass

# --- CONFIG & PATHS ---
VERSION = "0.20.1"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
DB_NAME = os.path.join(SCRIPT_DIR, "database.db")
KEY_PATH = os.path.join(SCRIPT_DIR, ".mentality_key")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
EXPORT_DIR = os.path.join(SCRIPT_DIR, "exports")
LANG_DIR = os.path.join(SCRIPT_DIR, "languages")
OLD_DATA_DIR = os.path.join(SCRIPT_DIR, "old_data")

for d in [EXPORT_DIR, LANG_DIR, OLD_DATA_DIR]:
    if not os.path.exists(d): os.makedirs(d)

class MentalityCore:
    def __init__(self):
        if not HAS_CRYPTO: raise ImportError("pip install cryptography")
        self.key = self.load_or_create_key()
        self.cipher = Fernet(self.key)
        self.init_db()
        self.cfg = self.load_config()
        self.languages = {}
        self.init_languages()

    def load_or_create_key(self):
        if os.path.exists(KEY_PATH):
            with open(KEY_PATH, "rb") as kf: return kf.read()
        key = Fernet.generate_key()
        with open(KEY_PATH, "wb") as kf: kf.write(key)
        return key

    def encrypt(self, data):
        if not data: return None
        if isinstance(data, str): data = data.encode('utf-8')
        return self.cipher.encrypt(data)

    def decrypt(self, data, err_msg="[Error]"):
        if not data: return ""
        try:
            dec = self.cipher.decrypt(data)
            try: return dec.decode('utf-8')
            except: return dec
        except: return err_msg

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name BLOB, last_name BLOB, first_name_en BLOB, last_name_en BLOB,
                country BLOB, city BLOB, address BLOB, phones BLOB,
                deleted INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT)""")
            cur.execute("""CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, card_id INTEGER,
                photo BLOB, created_at TEXT)""")

    def load_config(self):
        default = {"language": "ru", "theme": "Dark"}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
            except: pass
        return default

    def save_config(self, cfg):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)

    def init_languages(self):
        for file in os.listdir(LANG_DIR):
            if file.endswith(".json"):
                lang_name = file.replace(".json", "")
                with open(os.path.join(LANG_DIR, file), "r", encoding="utf-8") as f:
                    self.languages[lang_name] = json.load(f)
        if not self.languages:
            raise FileNotFoundError(f"No language files found in {LANG_DIR}")

    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return True
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_phone(phone):
        """Validate phone format (basic)"""
        if not phone:
            return True
        phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        return len(phone) >= 6 and any(c.isdigit() for c in phone)

    def create_backup(self):
        """Create automatic backup"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(EXPORT_DIR, f"backup_{timestamp}.db")
            shutil.copy2(DB_NAME, backup_path)
            return backup_path
        except Exception as e:
            return None

class MentalityGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        try: self.core = MentalityCore()
        except Exception as e:
            messagebox.showerror("Error", str(e)); self.destroy(); return

        ctk.set_appearance_mode(self.core.cfg.get("theme", "Dark"))
        self.title(f"Mentality DB v{VERSION}")
        self.geometry("1250x850")
        self.current_mode = 0
        self.temp_images = []
        self.export_selection_mode = False
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.current_edit_card_id = None

        self.bind("<Escape>", lambda e: self.handle_esc())
        self.rebuild_ui()

    # --- Custom dialogs (CTkToplevel, theme-aware) ---
    def _dialog(self, title, message, buttons, icon_color="#3498db"):
        result = [None]
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("420x180")
        dlg.attributes('-topmost', True)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.update_idletasks()
        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except Exception:
            pass

        body = ctk.CTkFrame(dlg, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=25, pady=15)
        ctk.CTkLabel(body, text=message, wraplength=370, justify="left", font=("Arial", 13)).pack(pady=(10, 20))

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")
        for text, value, color in buttons:
            def cmd(v=value): result[0] = v; dlg.destroy()
            ctk.CTkButton(btn_frame, text=text, width=100, fg_color=color, command=cmd).pack(side="left", padx=5, expand=True)

        dlg.wait_window()
        return result[0]

    def show_info(self, title, message):
        self._dialog(title, message, [("OK", True, "#2b8a3e")])

    def show_error(self, title, message):
        self._dialog(title, message, [("OK", True, "#c0392b")], "#c0392b")

    def ask_yes_no(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        return self._dialog(title, message, [(yes, True, "#2b8a3e"), (no, False, "#c0392b")])

    def ask_yes_no_cancel(self, title, message):
        lang = self.core.cfg.get("language", "ru")
        yes = "Да" if lang == "ru" else "Yes"
        no = "Нет" if lang == "ru" else "No"
        cancel = "Отмена" if lang == "ru" else "Cancel"
        return self._dialog(title, message, [(yes, "yes", "#2b8a3e"), (no, "no", "#3498db"), (cancel, "cancel", "#7f8c8d")])

    def loc(self, key):
        lang = self.core.cfg.get("language", "ru")
        lang_data = self.core.languages.get(lang, self.core.languages.get("ru", {}))
        return lang_data.get(key, key)

    @staticmethod
    def _to_text(value):
        if value is None:
            return ""
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return ""
        return str(value)

    @staticmethod
    def _normalize_phone(value):
        return "".join(ch for ch in str(value) if ch.isdigit())

    def handle_esc(self):
        if self.export_selection_mode:
            self.export_selection_mode = False; self.refresh_ui(); return
        if hasattr(self, 'details_view') and self.details_view.winfo_viewable(): self.close_card()

    def rebuild_ui(self):
        for widget in self.winfo_children(): widget.destroy()
        self.gallery_view = ctk.CTkFrame(self, fg_color="transparent")
        self.gallery_view.pack(fill="both", expand=True)
        self.details_view = ctk.CTkFrame(self, fg_color="transparent")

        # SIDEBAR
        side = ctk.CTkFrame(self.gallery_view, width=180)
        side.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(side, text=self.loc("menu"), font=("Arial", 18, "bold")).pack(pady=15)

        ctk.CTkButton(side, text=self.loc("base"), fg_color="#1a6b9a", hover_color="#2980b9", command=lambda: self.set_mode(0)).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("trash"), fg_color="#5d6d7e", hover_color="#7f8c8d", command=lambda: self.set_mode(1)).pack(pady=5, padx=10, fill="x")

        exp_row = ctk.CTkFrame(side, fg_color="transparent")
        exp_row.pack(pady=5, padx=10, fill="x")
        exp_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(exp_row, text=self.loc("exp"), fg_color="#2980b9", hover_color="#3498db", command=self.ask_export_type).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(exp_row, text=self.loc("imp"), fg_color="#d35400", hover_color="#e67e22", command=self.import_data).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkButton(side, text=self.loc("exp_csv"), fg_color="#16a085", hover_color="#1abc9c", command=self.export_csv).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("backup_btn"), fg_color="#7d3c98", hover_color="#9b59b6", command=self.auto_backup).pack(pady=5, padx=10, fill="x")

        ctk.CTkButton(side, text=self.loc("exit"), fg_color="#c0392b", hover_color="#e74c3c", command=self.quit_app).pack(side="bottom", pady=(5, 20), padx=10, fill="x")
        ctk.CTkButton(side, text=self.loc("settings"), command=self.open_settings).pack(side="bottom", pady=5, padx=10, fill="x")

        # CONTENT
        cont = ctk.CTkFrame(self.gallery_view, fg_color="transparent")
        cont.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(cont, height=50)
        top.pack(fill="x", pady=(0, 10))
        self.search_entry = ctk.CTkEntry(top, width=400, placeholder_text=self.loc("search_base"))
        self.search_entry.pack(side="left", padx=20, pady=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_basic_search())
        ctk.CTkButton(top, text=self.loc("search_advanced"), width=100, command=self.advanced_search).pack(side="left", padx=5, pady=10)

        self.scroll = ctk.CTkScrollableFrame(cont, label_text=self.loc("list_title"), label_font=("Arial", 20, "bold"))
        self.scroll.pack(fill="both", expand=True)
        self.refresh_ui()

    def _on_basic_search(self):
        self.highlighted_ids = set()
        self.filtered_ids = None
        self.refresh_ui()

    def set_mode(self, mode):
        self.export_selection_mode = False; self.highlighted_ids = set(); self.filtered_ids = None; self.current_mode = mode; self.refresh_ui()

    def refresh_ui(self):
        for w in self.scroll.winfo_children(): w.destroy()
        self.temp_images.clear()

        ctrl = ctk.CTkFrame(self.scroll, fg_color="transparent"); ctrl.pack(fill="x", padx=5, pady=(5, 15))
        if self.export_selection_mode:
            ctk.CTkLabel(ctrl, text=self.loc("export_ask"), text_color="#e67e22", font=("Arial", 14, "bold")).pack(side="left", padx=10)
        elif self.current_mode == 0:
            ctk.CTkButton(ctrl, text=self.loc("create"), fg_color="#2b8a3e", command=self.create_card).pack(side="left", padx=5)
        else:
            ctk.CTkButton(ctrl, text=self.loc("empty_trash"), fg_color="#7f8c8d", command=self.empty_trash).pack(side="right", padx=5)

        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT * FROM cards WHERE deleted=?", (self.current_mode,)).fetchall()

        grid = ctk.CTkFrame(self.scroll, fg_color="transparent"); grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure((0,1,2,3,4), weight=1)

        disp = 0
        search = self.search_entry.get().strip().casefold()
        phone_search = self._normalize_phone(search)
        err = self.loc("decryption_error")

        for r in rows:
            fn = self._to_text(self.core.decrypt(r[1], err))
            ln = self._to_text(self.core.decrypt(r[2], err))
            fn_en = self._to_text(self.core.decrypt(r[3], err))
            ln_en = self._to_text(self.core.decrypt(r[4], err))
            country = self._to_text(self.core.decrypt(r[5], err))
            city = self._to_text(self.core.decrypt(r[6], err))
            address = self._to_text(self.core.decrypt(r[7], err))
            phones = self._to_text(self.core.decrypt(r[8], err))
            if self.filtered_ids is not None and r[0] not in self.filtered_ids:
                continue
            haystack = f"{fn} {ln} {fn_en} {ln_en} {country} {city} {address} {phones}".casefold()
            phone_haystack = self._normalize_phone(phones)
            if search and search not in haystack and (not phone_search or phone_search not in phone_haystack):
                continue

            color = "#e67e22" if self.export_selection_mode else ("#27ae60" if r[0] in self.highlighted_ids else "#3d3d3d")
            frame = ctk.CTkFrame(grid, fg_color="#2b2b2b", height=50, corner_radius=25, border_width=2, border_color=color)
            frame.grid(row=disp//5, column=disp%5, padx=8, pady=8, sticky="ew")
            frame.grid_propagate(False)

            name = f"{fn} {ln}".strip() or self.loc("no_name")
            cmd = (lambda c=r[0]: self.perform_export(c)) if self.export_selection_mode else (lambda c=r[0]: self.open_card(c))
            ctk.CTkButton(frame, text=name, fg_color="transparent", command=cmd).place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.8)
            disp += 1

    def open_card(self, cid):
        self.gallery_view.pack_forget(); self.details_view.pack(fill="both", expand=True)
        for w in self.details_view.winfo_children(): w.destroy()
        is_new = cid is None
        self.current_edit_card_id = cid

        top = ctk.CTkFrame(self.details_view, fg_color="transparent"); top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text=self.loc("back"), width=100, command=self.close_card).pack(side="left")
        if not is_new:
            ctk.CTkButton(top, text=self.loc("history_btn"), width=100, command=lambda: self.show_card_history(cid)).pack(side="left", padx=5)

        if self.current_mode == 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("to_trash"), fg_color="#c0392b", command=lambda: self.trash_card(cid)).pack(side="right")
            ctk.CTkButton(top, text=self.loc("duplicate_btn"), fg_color="#3498db", command=lambda: self.duplicate_card(cid)).pack(side="right", padx=5)
        elif self.current_mode != 0 and not is_new:
            ctk.CTkButton(top, text=self.loc("perm_del"), fg_color="#922b21", command=lambda: self.perm_del_card(cid)).pack(side="right", padx=5)
            ctk.CTkButton(top, text=self.loc("restore"), fg_color="#2b8a3e", command=lambda: self.restore_card(cid)).pack(side="right", padx=5)

        tabs = ctk.CTkTabview(self.details_view); tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        t_info, t_photo = tabs.add(self.loc("tab_info")), tabs.add(self.loc("tab_photo"))

        row_data = {}
        if not is_new:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                row_data = dict(row) if row else {}

        self.entry_map = {}
        err = self.loc("decryption_error")
        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]

        f_info = ctk.CTkScrollableFrame(t_info, fg_color="transparent"); f_info.pack(fill="both", expand=True)
        entries_list = []
        for i, text in enumerate(self.loc("labels")):
            col = db_cols[i]
            f = ctk.CTkFrame(f_info, fg_color="transparent"); f.pack(fill="x", pady=4)
            ctk.CTkLabel(f, text=text, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=400)
            existing = self.core.decrypt(row_data.get(col), err) if not is_new else ""
            e.insert(0, self._to_text(existing))
            if self.current_mode == 1: e.configure(state="disabled")
            else: self.entry_map[col] = e; entries_list.append(e)
            e.pack(side="left")

        # Enter: next field or save+exit on last
        if self.current_mode == 0:
            for idx, entry in enumerate(entries_list):
                if idx < len(entries_list) - 1:
                    next_e = entries_list[idx + 1]
                    entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
                else:
                    entry.bind("<Return>", lambda ev, c=cid: self.save_info(c))

        if self.current_mode == 0:
            # Кнопка Сохранить прижата влево
            ctk.CTkButton(f_info, text=self.loc("save_btn"), fg_color="#2b8a3e", command=lambda: self.save_info(self.current_edit_card_id)).pack(pady=20, padx=150, anchor="w")

        self.photo_grid = ctk.CTkScrollableFrame(t_photo, fg_color="transparent"); self.photo_grid.pack(fill="both", expand=True)
        if self.current_mode == 0 and not is_new: ctk.CTkButton(t_photo, text=self.loc("add_photo"), command=lambda: self.add_photo(cid)).pack(pady=10)
        if not is_new:
            self.load_photos(cid)

    def load_photos(self, cid):
        for w in self.photo_grid.winfo_children(): w.destroy()
        with sqlite3.connect(DB_NAME) as conn:
            photos = conn.execute("SELECT id, photo FROM photos WHERE card_id=?", (cid,)).fetchall()
        self.photo_grid.grid_columnconfigure((0,1,2,3,4), weight=1)
        for i, (pid, enc) in enumerate(photos):
            frame = ctk.CTkFrame(self.photo_grid, fg_color="#222222", corner_radius=10); frame.grid(row=i//5, column=i%5, padx=8, pady=8)
            try:
                raw = self.core.decrypt(enc, None)
                if raw is None:
                    raise ValueError("Decryption returned None")
                img = Image.open(io.BytesIO(raw)); img.thumbnail((160, 160))
                ctk_img = ctk.CTkImage(img, size=(160, 160)); self.temp_images.append(ctk_img)
                lbl = ctk.CTkLabel(frame, image=ctk_img, text="", cursor="hand2")
                lbl.pack(pady=10, padx=10)
                lbl.bind("<Button-1>", lambda e, d=raw: self.open_full_image(d))
            except Exception as err:
                error_msg = f"Error: {str(err)[:30]}"
                ctk.CTkLabel(frame, text=error_msg, text_color="#e74c3c").pack(pady=40, padx=20)
            if self.current_mode == 0:
                ctk.CTkButton(frame, text=self.loc("delete"), fg_color="#c0392b", height=20, command=lambda p=pid: self.del_photo(p, cid)).pack(pady=10)

    def open_full_image(self, data):
        top = ctk.CTkToplevel(self); top.title(self.loc("view_title")); top.attributes('-topmost', True)
        try:
            img = Image.open(io.BytesIO(data)); w, h = img.size
            ratio = min(800/w, 800/h) if w>800 or h>800 else 1
            ctk_img = ctk.CTkImage(img, size=(int(w*ratio), int(h*ratio)))
            lbl = ctk.CTkLabel(top, image=ctk_img, text=""); top.image = ctk_img; lbl.pack(padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(top, text=f"Error: {str(e)[:50]}").pack(padx=20, pady=20)

    def save_info(self, cid):
        now = datetime.now().isoformat()
        upd = {k: self.core.encrypt(v.get()) for k, v in self.entry_map.items()}
        if cid is None:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        upd.get("first_name"), upd.get("last_name"), upd.get("first_name_en"), upd.get("last_name_en"),
                        upd.get("country"), upd.get("city"), upd.get("address"), upd.get("phones"),
                        0, now, now
                    )
                )
        else:
            upd["updated_at"] = now
            sql = "UPDATE cards SET " + ", ".join([f"{k}=?" for k in upd.keys()]) + " WHERE id=?"
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(sql, list(upd.values()) + [cid])
        self.close_card()

    def ask_export_type(self):
        if self.current_mode == 1: self.set_mode(0)
        res = self.ask_yes_no_cancel(self.loc("exp"), self.loc("export_ask"))
        if res == "yes": self.perform_export(None)
        elif res == "no": self.export_selection_mode = True; self.refresh_ui()

    def perform_export(self, sid=None):
        self.export_selection_mode = False; filename = "full_db"
        if sid:
            with sqlite3.connect(DB_NAME) as conn:
                r = conn.execute("SELECT first_name, last_name FROM cards WHERE id=?", (sid,)).fetchone()
                fn, ln = self.core.decrypt(r[0], "Card"), self.core.decrypt(r[1], "Data")
                filename = f"{fn}_{ln}_{datetime.now().strftime('%Y%m%d')}"
        path = os.path.join(EXPORT_DIR, f"{filename}.mtb")
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                c = [dict(r) for r in (conn.execute("SELECT * FROM cards WHERE id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM cards").fetchall())]
                p = [dict(r) for r in (conn.execute("SELECT * FROM photos WHERE card_id=?", (sid,)).fetchall() if sid else conn.execute("SELECT * FROM photos").fetchall())]
            for r in c:
                for k in r:
                    if isinstance(r[k], bytes): r[k] = r[k].hex()
            for r in p: r['photo'] = r['photo'].hex()
            with open(path, "w") as f: json.dump({"cards": c, "photos": p}, f)
            self.show_info(self.loc("exp"), self.loc("export_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))
        self.refresh_ui()

    def create_card(self):
        self.open_card(None)

    def add_photo(self, cid):
        ps = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if not ps: return
        with sqlite3.connect(DB_NAME) as conn:
            for p in ps:
                with open(p, "rb") as f: blob = f.read()
                conn.execute("INSERT INTO photos(card_id, photo, created_at) VALUES (?,?,?)", (cid, self.core.encrypt(blob), datetime.now().isoformat()))
        self.load_photos(cid)

    def del_photo(self, pid, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM photos WHERE id=?", (pid,))
        self.load_photos(cid)

    def trash_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=1 WHERE id=?", (cid,))
        self.close_card()

    def restore_card(self, cid):
        with sqlite3.connect(DB_NAME) as conn: conn.execute("UPDATE cards SET deleted=0 WHERE id=?", (cid,))
        self.close_card()

    def perm_del_card(self, cid):
        if self.ask_yes_no(self.loc("perm_del"), self.loc("perm_del_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id=?", (cid,)); conn.execute("DELETE FROM cards WHERE id=?", (cid,))
            self.close_card()

    def close_card(self):
        self.current_edit_card_id = None
        self.details_view.pack_forget(); self.gallery_view.pack(fill="both", expand=True); self.refresh_ui()

    def empty_trash(self):
        with sqlite3.connect(DB_NAME) as conn:
            if conn.execute("SELECT COUNT(*) FROM cards WHERE deleted=1").fetchone()[0] == 0:
                self.show_info(self.loc("trash"), self.loc("trash_is_empty")); return
        if self.ask_yes_no(self.loc("trash"), self.loc("empty_trash_confirm")):
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute("DELETE FROM photos WHERE card_id IN (SELECT id FROM cards WHERE deleted=1)")
                conn.execute("DELETE FROM cards WHERE deleted=1")
            self.refresh_ui()

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("Mentality Backup", "*.mtb")])
        if not path: return
        try:
            with open(path, "r") as f: data = json.load(f)
            with sqlite3.connect(DB_NAME) as conn:
                for c in data['cards']:
                    for k in ['first_name', 'last_name', 'first_name_en', 'last_name_en', 'country', 'city', 'address', 'phones']:
                        if c[k]: c[k] = bytes.fromhex(c[k])
                    fn, ln = self.core.decrypt(c['first_name'], "User"), self.core.decrypt(c['last_name'], "Import")
                    ex = conn.execute("SELECT id FROM cards WHERE first_name=? AND last_name=?", (c['first_name'], c['last_name'])).fetchone()
                    mode = "new"
                    if ex:
                        res = self.ask_yes_no_cancel(self.loc("duplicate_title"), self.loc("duplicate_msg").format(fn, ln))
                        if res == "yes": mode = "replace"
                        elif res == "no": mode = "new"
                        else: continue
                    if mode == "replace":
                        cid = ex[0]
                        conn.execute("UPDATE cards SET first_name_en=?, last_name_en=?, country=?, city=?, address=?, phones=? WHERE id=?", (c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], cid))
                        conn.execute("DELETE FROM photos WHERE card_id=?", (cid,))
                    else:
                        cid = conn.execute("INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, deleted, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (c['first_name'], c['last_name'], c['first_name_en'], c['last_name_en'], c['country'], c['city'], c['address'], c['phones'], 0, datetime.now().isoformat(), datetime.now().isoformat())).lastrowid
                    for p in [ph for ph in data['photos'] if ph['card_id'] == c['id']]:
                        conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)", (cid, bytes.fromhex(p['photo']), p['created_at']))
            self.refresh_ui(); self.show_info(self.loc("success"), self.loc("import_done"))
        except Exception as e: self.show_error(self.loc("error"), str(e))

    def open_settings(self):
        sw = ctk.CTkToplevel(self); sw.title(self.loc("settings")); sw.geometry("400x300"); sw.attributes('-topmost', True)
        for label, key, vals, cmd in [
            (self.loc("settings_theme"), "theme", ["Dark", "Light"], lambda v: (self.core.cfg.update({"theme": v}), self.core.save_config(self.core.cfg), ctk.set_appearance_mode(v))),
            (self.loc("settings_language"), "language", list(self.core.languages.keys()), lambda v: (self.core.cfg.update({"language": v}), self.core.save_config(self.core.cfg), self.rebuild_ui()))
        ]:
            f = ctk.CTkFrame(sw, fg_color="transparent"); f.pack(fill="x", padx=30, pady=10)
            ctk.CTkLabel(f, text=label).pack(side="left")
            ctk.CTkOptionMenu(f, values=vals, command=cmd, variable=ctk.StringVar(value=self.core.cfg[key])).pack(side="right")

    def quit_app(self):
        if self.ask_yes_no(self.loc("exit"), self.loc("exit_confirm")): self.quit()

    def export_csv(self):
        """Export database to CSV format"""
        try:
            path = filedialog.asksaveasfilename(initialfile="contacts.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not path: return
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0 ORDER BY first_name").fetchall()
            
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.loc("csv_headers"))
                err = self.loc("decryption_error")
                for r in rows:
                    fn = self.core.decrypt(r[1], "[Enc]")
                    ln = self.core.decrypt(r[2], "[Enc]")
                    fn_en = self.core.decrypt(r[3], "[Enc]")
                    ln_en = self.core.decrypt(r[4], "[Enc]")
                    country = self.core.decrypt(r[5], "[Enc]")
                    city = self.core.decrypt(r[6], "[Enc]")
                    address = self.core.decrypt(r[7], "[Enc]")
                    phones = self.core.decrypt(r[8], "[Enc]")
                    writer.writerow([fn, ln, fn_en, ln_en, country, city, address, phones, r[10], r[11]])
            self.show_info(self.loc("export_csv_title"), self.loc("export_csv_done").format(path))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def auto_backup(self):
        """Create automatic backup"""
        try:
            backup_path = self.core.create_backup()
            if backup_path:
                self.show_info(self.loc("success"), self.loc("backup_done").format(backup_path))
            else:
                self.show_error(self.loc("error"), self.loc("backup_fail"))
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def duplicate_card(self, cid):
        """Create duplicate of contact"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
                
                # Insert new card
                new_id = conn.execute(
                    "INSERT INTO cards (first_name, last_name, first_name_en, last_name_en, country, city, address, phones, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row['first_name'], row['last_name'], row['first_name_en'], row['last_name_en'], 
                     row['country'], row['city'], row['address'], row['phones'], 
                     datetime.now().isoformat(), datetime.now().isoformat())
                ).lastrowid
                
                # Copy photos
                photos = conn.execute("SELECT photo FROM photos WHERE card_id=?", (cid,)).fetchall()
                for photo in photos:
                    conn.execute("INSERT INTO photos (card_id, photo, created_at) VALUES (?,?,?)",
                               (new_id, photo[0], datetime.now().isoformat()))
            
            self.show_info(self.loc("success"), self.loc("duplicate_success"))
            self.refresh_ui()
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def show_card_history(self, cid):
        """Show card creation and update dates"""
        try:
            with sqlite3.connect(DB_NAME) as conn:
                row = conn.execute("SELECT created_at, updated_at FROM cards WHERE id=?", (cid,)).fetchone()
            
            if row:
                created = row[0] or self.loc("history_unknown")
                updated = row[1] or self.loc("history_not_updated")
                msg = self.loc("history_created").format(created) + "\n" + self.loc("history_updated").format(updated)
                self.show_info(self.loc("history_title"), msg)
        except Exception as e:
            self.show_error(self.loc("error"), str(e))

    def advanced_search(self):
        """Open advanced search window"""
        sw = ctk.CTkToplevel(self)
        sw.title(self.loc("search_advanced_title"))
        sw.geometry("500x430")
        sw.attributes('-topmost', True)

        db_cols = ["first_name", "last_name", "first_name_en", "last_name_en", "country", "city", "address", "phones"]
        labels = self.loc("labels")
        search_vars = {}
        entries_list = []

        f_search = ctk.CTkScrollableFrame(sw, fg_color="transparent")
        f_search.pack(fill="both", expand=True, padx=20, pady=20)

        for i, label in enumerate(labels):
            f = ctk.CTkFrame(f_search, fg_color="transparent")
            f.pack(fill="x", pady=5)
            ctk.CTkLabel(f, text=label, width=150, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f, width=300)
            e.pack(side="left")
            search_vars[db_cols[i]] = e
            entries_list.append(e)

        def perform_search():
            query_terms = {k: v.get().strip() for k, v in search_vars.items() if v.get().strip()}
            if not query_terms:
                return
            err = self.loc("decryption_error")
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute("SELECT * FROM cards WHERE deleted=0").fetchall()
            found_ids = set()
            for row in rows:
                match = True
                for col, term in query_terms.items():
                    col_idx = db_cols.index(col)
                    decrypted = self._to_text(self.core.decrypt(row[col_idx + 1], err)).casefold()
                    term_norm = term.casefold()
                    if col == "phones":
                        if self._normalize_phone(term_norm) not in self._normalize_phone(decrypted):
                            match = False
                            break
                    elif term_norm not in decrypted:
                        match = False
                        break
                if match:
                    found_ids.add(row[0])
            sw.destroy()
            self.current_mode = 0
            self.export_selection_mode = False
            self.search_entry.delete(0, "end")
            self.highlighted_ids = found_ids
            self.filtered_ids = found_ids
            self.refresh_ui()

        # Enter key: navigate between fields, last field triggers search
        for idx, entry in enumerate(entries_list):
            if idx < len(entries_list) - 1:
                next_e = entries_list[idx + 1]
                entry.bind("<Return>", lambda ev, ne=next_e: ne.focus_set())
            else:
                entry.bind("<Return>", lambda ev: perform_search())

        ctk.CTkButton(f_search, text=self.loc("search_btn"), fg_color="#2b8a3e", command=perform_search).pack(pady=20)

if __name__ == "__main__":
    app = MentalityGUI(); app.mainloop()
