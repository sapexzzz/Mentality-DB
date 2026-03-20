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
VERSION = "0.20.0"
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
        search = self.search_entry.get().lower()
        err = self.loc("decryption_error")

        for r in rows:
            fn = self.core.decrypt(r[1], err); ln = self.core.decrypt(r[2], err)
            fn_en = self.core.decrypt(r[3], err); ln_en = self.core.decrypt(r[4], err)
            country = self.core.decrypt(r[5], err)
            city = self.core.decrypt(r[6], err)
            address = self.core.decrypt(r[7], err)
            phones = self.core.decrypt(r[8], err)
            if self.filtered_ids is not None and r[0] not in self.filtered_ids:
                continue
            haystack = f"{fn} {ln} {fn_en} {ln_en} {country} {city} {address} {phones}".lower()
            if search and search not in haystack:
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

        top = ctk.CTkFrame(self.details_view, fg_color="transparent"); top.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(top, text=self.loc("back"), width=100, command=self.close_card).pack(side="left")
        ctk.CTkButton(top, text=self.loc("history_btn"), width=100, command=lambda: self.show_card_history(cid)).pack(side="left", padx=5)

        if self.current_mode == 0:
            ctk.CTkButton(top, text=self.loc("to_trash"), fg_color="#c0392b", command=lambda: self.trash_card(cid)).pack(side="right")
            ctk.CTkButton(top, text=self.loc("duplicate_btn"), fg_color="#3498db", command=lambda: self.duplicate_card(cid)).pack(side="right", padx=5)
        else:
            ctk.CTkButton(top, text=self.loc("perm_del"), fg_color="#922b21", command=lambda: self.perm_del_card(cid)).pack(side="right", padx=5)
            ctk.CTkButton(top, text=self.loc("restore"), fg_color="#2b8a3e", command=lambda: self.restore_card(cid)).pack(side="right", padx=5)

        tabs = ctk.CTkTabview(self.details_view); tabs.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        t_info, t_photo = tabs.add(self.loc("tab_info")), tabs.add(self.loc("tab_photo"))

        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()

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
            e.insert(0, self.core.decrypt(row[col], err))
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
            ctk.CTkButton(f_info, text=self.loc("save_btn"), fg_color="#2b8a3e", command=lambda: self.save_info(cid)).pack(pady=20, padx=150, anchor="w")

        self.photo_grid = ctk.CTkScrollableFrame(t_photo, fg_color="transparent"); self.photo_grid.pack(fill="both", expand=True)
        if self.current_mode == 0: ctk.CTkButton(t_photo, text=self.loc("add_photo"), command=lambda: self.add_photo(cid)).pack(pady=10)
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
        upd = {k: self.core.encrypt(v.get()) for k, v in self.entry_map.items()}
        upd["updated_at"] = datetime.now().isoformat()
        sql = "UPDATE cards SET " + ", ".join([f"{k}=?" for k in upd.keys()]) + " WHERE id=?"
        with sqlite3.connect(DB_NAME) as conn: conn.execute(sql, list(upd.values()) + [cid])
        self.close_card()

    def ask_export_type(self):
        if self.current_mode == 1: self.set_mode(0)
        res = messagebox.askquestion(self.loc("exp"), self.loc("export_ask"), type="yesnocancel")
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
        with sqlite3.connect(DB_NAME) as conn:
            nid = conn.execute("INSERT INTO cards (created_at) VALUES (?)", (datetime.now().isoformat(),)).lastrowid
        self.open_card(nid)

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
        self.details_view.pack_forget(); self.gallery_view.pack(fill="both", expand=True); self.refresh_ui()

    def empty_trash(self):
        with sqlite3.connect(DB_NAME) as conn:
            if conn.execute("SELECT COUNT(*) FROM cards WHERE deleted=1").fetchone()[0] == 0:
                messagebox.showinfo("!", self.loc("trash_is_empty")); return
        if messagebox.askyesno("?", self.loc("empty_trash_confirm")):
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
            query_terms = {k: v.get() for k, v in search_vars.items() if v.get()}
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
                    decrypted = self.core.decrypt(row[col_idx + 1], err).lower()
                    if term.lower() not in decrypted:
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
