import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json, os, subprocess, socket, datetime, webbrowser, threading, urllib.parse, shutil
from typing import Optional
import requests
from PIL import Image, ImageDraw, ImageFont
import pystray
from app import app, init_db
from werkzeug.serving import make_server

# ─────────────────────────────────────────────
#  CONFIGURATION GLOBALE
# ─────────────────────────────────────────────
CONFIG_FILE   = "config.json"
VERSION_FILE  = "version.txt"

# ➡️  URL de votre Google Apps Script
GSHEET_WEBHOOK = "https://script.google.com/macros/s/AKfycbwZlzcGcqdGdtkBhnhEnmPtSU2NcDvUny2Riz1KFMk4BruGPkOPeo0GM-eN7TOBvxWa/exec"

# Couleurs de la charte graphique
COLORS = {
    "bg":     "#0f1923",
    "card":   "#1a2535",
    "border": "#2a3a50",
    "accent": "#3b82f6",
    "accent2":"#10b981",
    "danger": "#ef4444",
    "warn":   "#f59e0b",
    "text":   "#e2e8f0",
    "muted":  "#64748b",
    "white":  "#ffffff",
}

FONT_MAIN  = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_MONO  = ("Consolas", 9)

# Drapeau Windows pour masquer la console
_WIN_FLAG: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ─────────────────────────────────────────────
#  SERVER THREAD
# ─────────────────────────────────────────────
class ServerThread(threading.Thread):
    def __init__(self, flask_app) -> None:  # type: ignore[type-arg]
        super().__init__(daemon=True)
        self.server = make_server("0.0.0.0", 5000, flask_app)
        self.server.timeout = 1          # réponse rapide au poll
        ctx = flask_app.app_context()
        ctx.push()

    def run(self) -> None:
        self.server.serve_forever(poll_interval=0.5)

    def shutdown(self) -> None:
        """Arrêt immédiat : on demande le shutdown ET on ferme le socket."""
        try:
            self.server.shutdown()       # envoie le signal d'arrêt
        except Exception:
            pass
        try:
            self.server.server_close()   # libère le port immédiatement
        except Exception:
            pass


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def read_version() -> str:
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "1.0.0"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_config() -> Optional[dict]:  # type: ignore[type-arg]
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def make_tray_icon() -> Image.Image:
    """Icône 64×64 pour le system tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, size - 4, size - 4], fill="#3b82f6")
    d.text((20, 16), "G", fill="white", font=ImageFont.load_default())
    d.ellipse([44, 44, 60, 60], fill="#10b981")
    return img


# ─────────────────────────────────────────────
#  ASSISTANT PREMIÈRE INSTALLATION
# ─────────────────────────────────────────────
class SetupWizard(tk.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("🏛️  Première Installation — JIBAYAT")
        self.geometry("580x700")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.grab_set()
        self.configure(bg=COLORS["bg"])

        # Déclaration explicite des widgets (satisfait le linter)
        self.ent_nom:     tk.Entry
        self.ent_nom_ar:  tk.Entry
        self.ent_region:  tk.Entry
        self.ent_prov:    tk.Entry
        self.ent_code:    tk.Entry
        self.modules: dict[str, tuple[str, tk.BooleanVar]] = {}

        self._build()

    def _on_close(self) -> None:
        messagebox.showerror("Erreur", "L'installation doit être complétée avant d'utiliser JIBAYAT.")

    def _build(self) -> None:
        # ── En-tête fixe (top) ──────────────────────────────────────
        hdr = tk.Frame(self, bg=COLORS["accent"], pady=18)
        hdr.pack(fill=tk.X, side=tk.TOP)
        tk.Label(hdr, text="🏛️  Configuration Initiale",
                 font=("Segoe UI", 16, "bold"), bg=COLORS["accent"], fg=COLORS["white"]).pack()
        tk.Label(hdr, text="JIBAYAT — Gestion Fiscale Communale",
                 font=FONT_MAIN, bg=COLORS["accent"], fg="#bfdbfe").pack()

        # ── Bouton fixe (bottom) — packés AVANT le canvas pour rester visible ──
        btn_frame = tk.Frame(self, bg=COLORS["bg"], pady=12, padx=30)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Button(btn_frame, text="✅  Terminer l'installation et démarrer",
                  bg=COLORS["accent2"], fg=COLORS["white"],
                  font=("Segoe UI", 11, "bold"), relief="flat",
                  padx=20, pady=12, cursor="hand2",
                  command=self._save).pack(fill=tk.X)

        # ── Canvas scrollable pour le contenu ────────────────────────
        canvas_frame = tk.Frame(self, bg=COLORS["bg"])
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        canvas = tk.Canvas(canvas_frame, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        body = tk.Frame(canvas, bg=COLORS["bg"], padx=30, pady=20)
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_configure(event: tk.Event) -> None:  # type: ignore[type-arg]
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(body_window, width=canvas.winfo_width())

        body.bind("<Configure>", _on_configure)
        canvas.bind("<Configure>", _on_configure)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # ── Champs commune ────────────────────────────────────────────
        tk.Label(body, text="INFORMATIONS DE LA COMMUNE",
                 font=("Segoe UI", 9, "bold"), bg=COLORS["bg"],
                 fg=COLORS["muted"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        fields = [
            ("Nom de la commune (Fr) :", "ent_nom"),
            ("Nom de la commune (Ar) :", "ent_nom_ar"),
            ("Région :",                 "ent_region"),
            ("Province :",               "ent_prov"),
            ("Code Commune :",           "ent_code"),
        ]
        for i, (lbl_txt, attr) in enumerate(fields, start=1):
            tk.Label(body, text=lbl_txt, font=FONT_MAIN,
                     bg=COLORS["bg"], fg=COLORS["text"]).grid(row=i, column=0, sticky="w", pady=5)
            ent = tk.Entry(body, width=32, font=FONT_MAIN,
                           bg=COLORS["card"], fg=COLORS["text"],
                           insertbackground=COLORS["text"], relief="flat", bd=6)
            ent.grid(row=i, column=1, padx=10, pady=5, sticky="ew")
            setattr(self, attr, ent)

        # ── Modules fiscaux ───────────────────────────────────────────
        tk.Frame(body, bg=COLORS["border"], height=1).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=15)
        tk.Label(body, text="MODULES FISCAUX À ACTIVER",
                 font=("Segoe UI", 9, "bold"), bg=COLORS["bg"],
                 fg=COLORS["muted"]).grid(row=8, column=0, columnspan=2, sticky="w")

        self.modules = {
            "TNB":                 ("🏗️  Taxe Terrains Non Bâtis",         tk.BooleanVar(value=True)),
            "DEBITS_BOISSONS":     ("🍺  Débits de Boissons",               tk.BooleanVar(value=True)),
            "TRANSPORT_VOYAGEURS": ("🚌  Transport Public Voyageurs",        tk.BooleanVar(value=True)),
            "STATIONNEMENT":       ("🅿️  Stationnement TPV",                 tk.BooleanVar(value=True)),
            "OCCUPATION_DOMAINE":  ("🏪  Occupation Domaine Public",         tk.BooleanVar(value=True)),
            "FOURRIERE":           ("🔒  Droits de Fourrière",               tk.BooleanVar(value=True)),
            "LOCATION_LOCAUX":     ("🏢  Location Locaux Commerciaux",       tk.BooleanVar(value=True)),
            "AFFERMAGE_SOUKS":     ("🛒  Affermage Souks Communaux",         tk.BooleanVar(value=True)),
        }
        for idx, (code, (label, var)) in enumerate(self.modules.items()):
            tk.Checkbutton(body, text=label, variable=var,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["accent"],
                           activebackground=COLORS["bg"],
                           font=FONT_MAIN, anchor="w").grid(
                row=9 + idx, column=0, columnspan=2, sticky="w", pady=2)


    def _save(self) -> None:
        nom = self.ent_nom.get().strip()
        if not nom:
            messagebox.showwarning("Attention", "Le nom de la commune est obligatoire.")
            return
        cfg = {
            "commune": {
                "nom":      nom,
                "nom_ar":   self.ent_nom_ar.get(),
                "region":   self.ent_region.get(),
                "province": self.ent_prov.get(),
                "code":     self.ent_code.get(),
            },
            "modules": [code for code, (_, var) in self.modules.items() if var.get()],
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        try:
            init_db()
            messagebox.showinfo("Succès ✅", "Base de données initialisée ! Le serveur est prêt.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erreur DB", str(e))
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)


# ─────────────────────────────────────────────
#  DIALOGUE RAPPORT
# ─────────────────────────────────────────────
class ReportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, cfg: Optional[dict]) -> None:  # type: ignore[type-arg]
        super().__init__(parent)
        self.cfg = cfg
        self.title("Envoyer un Rapport")
        self.geometry("480x560")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.grab_set()

        # Déclaration explicite des widgets
        self.var_type:  tk.StringVar
        self.cb_module: ttk.Combobox
        self.txt_desc:  tk.Text

        self._build()

    def _build(self) -> None:
        commune_name = self.cfg["commune"]["nom"] if self.cfg else "Inconnue"

        # En-tête
        hdr = tk.Frame(self, bg=COLORS["card"], pady=15)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="📝  Signalement / Amélioration",
                 font=("Segoe UI", 14, "bold"), bg=COLORS["card"], fg=COLORS["white"]).pack()
        tk.Label(hdr, text=f"Client : {commune_name}",
                 font=FONT_MAIN, bg=COLORS["card"], fg=COLORS["muted"]).pack()

        body = tk.Frame(self, bg=COLORS["bg"], padx=25, pady=15)
        body.pack(fill=tk.BOTH, expand=True)

        # Type de rapport
        tk.Label(body, text="Type de rapport :", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.var_type = tk.StringVar(value="bug")
        types_frame = tk.Frame(body, bg=COLORS["bg"])
        types_frame.pack(anchor="w", pady=(0, 12))
        for val, txt in [("bug", "🐛  Bug/Erreur"), ("amelioration", "💡  Amélioration"), ("autre", "💬  Autre")]:
            tk.Radiobutton(types_frame, text=txt, variable=self.var_type, value=val,
                           bg=COLORS["bg"], fg=COLORS["text"],
                           selectcolor=COLORS["accent"],
                           activebackground=COLORS["bg"],
                           font=FONT_MAIN).pack(side=tk.LEFT, padx=8)

        # Module
        tk.Label(body, text="Module concerné :", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.cb_module = ttk.Combobox(body, values=[
            "TNB", "Débits de Boissons", "Stationnement", "Fourrière",
            "Occupation Domaine", "Location Locaux", "Souks", "Connexion", "Autre"
        ], state="readonly", font=FONT_MAIN)
        self.cb_module.current(0)
        self.cb_module.pack(fill=tk.X, pady=(0, 12))

        # Description
        tk.Label(body, text="Description :", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.txt_desc = tk.Text(body, height=8, font=FONT_MAIN,
                                bg=COLORS["card"], fg=COLORS["text"],
                                insertbackground=COLORS["text"], relief="flat", bd=6)
        self.txt_desc.pack(fill=tk.X, pady=(0, 15))

        # Boutons
        btn_frame = tk.Frame(body, bg=COLORS["bg"])
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="📊  Envoyer vers Google Sheets",
                  bg=COLORS["accent"], fg=COLORS["white"],
                  font=FONT_BOLD, relief="flat", padx=12, pady=8,
                  cursor="hand2",
                  command=self._send_sheets).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        tk.Button(btn_frame, text="✉️  Envoyer par Email",
                  bg=COLORS["card"], fg=COLORS["text"],
                  font=FONT_BOLD, relief="flat", padx=12, pady=8,
                  cursor="hand2",
                  command=self._send_email).pack(side=tk.LEFT, expand=True, fill=tk.X)

    def _send_sheets(self) -> None:
        desc = self.txt_desc.get("1.0", tk.END).strip()
        if not desc:
            messagebox.showwarning("Attention", "Veuillez décrire le problème.")
            return
        commune_name = self.cfg["commune"]["nom"] if self.cfg else "Inconnue"
        payload = {
            "commune":     commune_name,
            "type":        self.var_type.get(),
            "module":      self.cb_module.get(),
            "description": desc,
            "date":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "version":     read_version(),
        }
        try:
            resp = requests.post(GSHEET_WEBHOOK, json=payload, timeout=10)
            if resp.status_code == 200:
                messagebox.showinfo("✅ Envoyé", "Rapport envoyé avec succès dans Google Sheets !")
                self.destroy()
            else:
                messagebox.showerror("Erreur", f"Erreur serveur : {resp.status_code}")
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Erreur réseau", "Impossible de se connecter. Vérifiez Internet.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _send_email(self) -> None:
        desc = self.txt_desc.get("1.0", tk.END).strip()
        if not desc:
            messagebox.showwarning("Attention", "Veuillez décrire le problème.")
            return
        commune_name = self.cfg["commune"]["nom"] if self.cfg else "Inconnue"
        subject = (f"[JIBAYAT] {self.var_type.get().capitalize()} — "
                   f"{commune_name} — {self.cb_module.get()}")
        body = (f"Client: {commune_name}\nType: {self.var_type.get()}\n"
                f"Module: {self.cb_module.get()}\nVersion: {read_version()}\n\n"
                f"Description:\n{desc}")
        webbrowser.open(
            f"mailto:contact@jibayat-dev.com"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        self.destroy()


# ─────────────────────────────────────────────
#  FENÊTRE PRINCIPALE
# ─────────────────────────────────────────────
class ModernLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JIBAYAT — Contrôle Serveur")
        self.geometry("540x660")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])

        # ── Attributs d'instance déclarés ici ──────────────
        self.server_thread: Optional[ServerThread] = None
        self.ip_local: str = get_local_ip()
        self.version:  str = read_version()
        self._tray_icon: Optional[pystray.Icon] = None
        self._tray_running: bool = False

        # Widgets (initialisés dans _build_ui)
        self.lbl_dot:    tk.Label
        self.lbl_status: tk.Label
        self.btn_start:  tk.Button
        self.btn_stop:   tk.Button
        self.btn_web:    tk.Button
        self.btn_tray:   tk.Button
        self.frm_update: tk.Frame
        self.lbl_update: tk.Label
        self._card_status: tk.Frame
        
        self.notebook: ttk.Notebook
        self.tab_server: tk.Frame
        self.tab_db: tk.Frame
        self.var_gdrive: tk.BooleanVar
        self.var_gd_webhook: tk.StringVar
        self.var_gd_folder: tk.StringVar
        # ───────────────────────────────────────────────────

        self._apply_styles()
        self._build_ui()
        threading.Thread(target=self._bg_fetch, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Styles ──────────────────────────────────
    def _apply_styles(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        
        # Style Onglets (Notebook)
        s.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=COLORS["card"], foreground=COLORS["text"],
                    padding=[15, 6], font=FONT_BOLD, borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", COLORS["accent"])],
              foreground=[("selected", COLORS["white"])])
        s.configure("TCombobox",
                     fieldbackground=COLORS["card"],
                     background=COLORS["card"],
                     foreground=COLORS["text"],
                     selectbackground=COLORS["accent"],
                     selectforeground=COLORS["white"])
        s.map("TCombobox", fieldbackground=[("readonly", COLORS["card"])])

    # ── Construction UI ──────────────────────────
    def _build_ui(self) -> None:
        # ── En-tête ──
        hdr = tk.Frame(self, bg=COLORS["accent"], pady=22)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="🏛️  JIBAYAT",
                 font=("Segoe UI", 22, "bold"), bg=COLORS["accent"], fg=COLORS["white"]).pack()
        tk.Label(hdr, text="Gestion Fiscale Communale — Tableau de Contrôle",
                 font=("Segoe UI", 9), bg=COLORS["accent"], fg="#bfdbfe").pack()

        # ── Bandeau mise à jour (caché par défaut) ──
        self.frm_update = tk.Frame(self, bg="#78350f", pady=8)
        self.lbl_update = tk.Label(self.frm_update,
                                   text="⚠️  Une mise à jour est disponible !",
                                   font=("Segoe UI", 10, "bold"), bg="#78350f", fg="#fef3c7")
        self.lbl_update.pack(side=tk.LEFT, padx=15)
        tk.Button(self.frm_update, text="Mettre à jour maintenant →",
                  bg="#d97706", fg="white", relief="flat", font=FONT_BOLD,
                  padx=10, pady=4, cursor="hand2",
                  command=self._do_git_pull).pack(side=tk.RIGHT, padx=15)

        # ── Corps principal (Onglets) ──
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Onglet Serveur
        self.tab_server = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_server, text="🖥️ Contrôle Serveur")
        
        main = tk.Frame(self.tab_server, bg=COLORS["bg"], padx=10, pady=5)
        main.pack(fill=tk.BOTH, expand=True)

        # Onglet Base de données
        self.tab_db = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_db, text="💾 Base de données & Sauvegarde")
        self._build_db_tab()

        # ── Carte statut ──
        self._card_status = tk.Frame(main, bg=COLORS["card"], padx=20, pady=18,
                                     highlightbackground=COLORS["border"], highlightthickness=1)
        self._card_status.pack(fill=tk.X, pady=(0, 15))

        dot_row = tk.Frame(self._card_status, bg=COLORS["card"])
        dot_row.pack()
        self.lbl_dot = tk.Label(dot_row, text="●", font=("Segoe UI", 20),
                                bg=COLORS["card"], fg=COLORS["danger"])
        self.lbl_dot.pack(side=tk.LEFT)
        self.lbl_status = tk.Label(dot_row, text="  SERVEUR ARRÊTÉ",
                                   font=("Segoe UI", 14, "bold"),
                                   bg=COLORS["card"], fg=COLORS["danger"])
        self.lbl_status.pack(side=tk.LEFT)

        tk.Frame(self._card_status, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=12)

        info_frame = tk.Frame(self._card_status, bg=COLORS["card"])
        info_frame.pack()
        for icon, label, val in [
            ("🌐", "Réseau :", f"http://{self.ip_local}:5000"),
            ("💻", "Local  :", "http://127.0.0.1:5000"),
            ("📦", "Version:", self.version),
        ]:
            row = tk.Frame(info_frame, bg=COLORS["card"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{icon} {label}", font=FONT_BOLD,
                     bg=COLORS["card"], fg=COLORS["muted"], width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=val, font=FONT_MONO,
                     bg=COLORS["card"], fg=COLORS["text"]).pack(side=tk.LEFT)

        # ── Boutons principaux ──
        btn_cfg = [
            ("▶  DÉMARRER LE SERVEUR",    COLORS["accent2"], self._start_server, "btn_start", tk.NORMAL),
            ("⏹  ARRÊTER LE SERVEUR",     COLORS["border"],  self._stop_server,  "btn_stop",  tk.DISABLED),
            ("🌍 OUVRIR L'APPLICATION",   COLORS["accent"],  self._open_browser, "btn_web",   tk.NORMAL),
            ("⬇  MINIMISER DANS LA BARRE", COLORS["card"],   self._hide_to_tray, "btn_tray",  tk.NORMAL),
        ]
        for txt, color, cmd, attr, state in btn_cfg:
            b = tk.Button(main, text=txt, bg=color, fg=COLORS["white"],
                          font=("Segoe UI", 10, "bold"), relief="flat",
                          pady=11, cursor="hand2", bd=0, state=state,
                          command=cmd,
                          disabledforeground="#555e6e",
                          activebackground=color, activeforeground=COLORS["white"])
            b.pack(fill=tk.X, pady=4)
            setattr(self, attr, b)

        # ── Séparateur + boutons secondaires ──
        tk.Frame(main, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=10)
        sec = tk.Frame(main, bg=COLORS["bg"])
        sec.pack(fill=tk.X)
        for txt, cmd, fg in [
            ("🔄  Vérifier les mises à jour", self._check_updates_manual, COLORS["accent"]),
            ("📝  Envoyer un rapport",         self._open_report,          COLORS["warn"]),
        ]:
            tk.Button(sec, text=txt, command=cmd,
                      bg=COLORS["bg"], fg=fg, font=("Segoe UI", 10, "underline"),
                      bd=0, cursor="hand2", activebackground=COLORS["bg"],
                      activeforeground=fg).pack(side=tk.LEFT, padx=8)

        # ── Pied de page ──
        footer = tk.Frame(self, bg=COLORS["card"], pady=8)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer,
                 text=f"JIBAYAT  v{self.version}  •  {self._commune_name()}",
                 font=("Segoe UI", 8), bg=COLORS["card"], fg=COLORS["muted"]).pack()

    # ── Onglet Base de données ──────────────────
    def _build_db_tab(self) -> None:
        container = tk.Frame(self.tab_db, bg=COLORS["bg"], padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        cfg = load_config() or {}
        gdrive_dir = cfg.get("gdrive_backup", "")

        # EXPORT / DRIVE
        card_ex = tk.Frame(container, bg=COLORS["card"], padx=15, pady=15, highlightbackground=COLORS["border"], highlightthickness=1)
        card_ex.pack(fill=tk.X, pady=(0, 20))

        tk.Label(card_ex, text="📤 EXPORTER & SYNCHRONISER", font=FONT_BOLD, bg=COLORS["card"], fg=COLORS["white"]).pack(anchor="w", pady=(0, 10))
        
        btn_frame = tk.Frame(card_ex, bg=COLORS["card"])
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(btn_frame, text="📦 Exporter manuellement (.db)", bg=COLORS["accent"], fg="white", font=FONT_MAIN, relief="flat", padx=10, pady=6, cursor="hand2", command=self._export_db).pack(side=tk.LEFT)

        # -- Option A : Dossier Local --
        tk.Label(card_ex, text="Acheminez dynamiquement vers un dossier Google Drive Local :", font=FONT_MAIN, bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w", pady=(10, 5))
        row_gd = tk.Frame(card_ex, bg=COLORS["card"])
        row_gd.pack(fill=tk.X)
        self.var_gdrive = tk.StringVar(value=cfg.get("gdrive_backup", ""))
        ent_gd = tk.Entry(row_gd, textvariable=self.var_gdrive, font=FONT_MAIN, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat")
        ent_gd.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        tk.Button(row_gd, text="Parcourir...", bg=COLORS["border"], fg="white", font=FONT_MAIN, relief="flat", cursor="hand2", command=self._browse_gdrive).pack(side=tk.LEFT, padx=(0, 5), ipady=2)
        tk.Button(row_gd, text="💾 Auto-Local", bg=COLORS["accent2"], fg="white", font=FONT_BOLD, relief="flat", cursor="hand2", command=self._save_gdrive_config).pack(side=tk.LEFT, ipady=2)

        # -- Option B : Direct Cloud API --
        tk.Label(card_ex, text="Sauvegarde directe vers Google Drive Connecté (Cloud API) :", font=FONT_MAIN, bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w", pady=(15, 5))
        row_api = tk.Frame(card_ex, bg=COLORS["card"])
        row_api.pack(fill=tk.X)
        
        self.var_gd_webhook = tk.StringVar(value=cfg.get("gdrive_webhook", ""))
        self.var_gd_folder = tk.StringVar(value=cfg.get("gdrive_folder_id", ""))
        
        f1 = tk.Frame(row_api, bg=COLORS["card"])
        f1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        tk.Label(f1, text="URL Webhook Apps Script", font=("Segoe UI", 8), bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w")
        ent_hook = tk.Entry(f1, textvariable=self.var_gd_webhook, font=FONT_MAIN, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat")
        ent_hook.pack(fill=tk.X, ipady=5)
        
        f2 = tk.Frame(row_api, bg=COLORS["card"])
        f2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        tk.Label(f2, text="ID Dossier (ex: 1qRS...EF9c)", font=("Segoe UI", 8), bg=COLORS["card"], fg=COLORS["muted"]).pack(anchor="w")
        ent_fid = tk.Entry(f2, textvariable=self.var_gd_folder, font=FONT_MAIN, bg=COLORS["bg"], fg=COLORS["text"], insertbackground=COLORS["text"], relief="flat")
        ent_fid.pack(fill=tk.X, ipady=5)
        
        tk.Button(row_api, text="💾 Auto-Cloud", bg=COLORS["accent2"], fg="white", font=FONT_BOLD, relief="flat", cursor="hand2", command=self._save_gdrive_api_config).pack(side=tk.RIGHT, anchor="s", ipady=2, pady=(15, 0))

        tk.Label(card_ex, text="ℹ️ La sauvegarde s'exécutera automatiquement à l'arrêt du Serveur si l'une des 2 options est configurée.", font=("Segoe UI", 8, "italic"), bg=COLORS["card"], fg=COLORS["warn"]).pack(anchor="w", pady=(10, 0))

        # IMPORT
        card_im = tk.Frame(container, bg=COLORS["card"], padx=15, pady=15, highlightbackground=COLORS["border"], highlightthickness=1)
        card_im.pack(fill=tk.X)
        tk.Label(card_im, text="📥 RESTAURER UNE SAUVEGARDE", font=FONT_BOLD, bg=COLORS["card"], fg=COLORS["danger"]).pack(anchor="w", pady=(0, 10))
        tk.Label(card_im, text="⚠️ L'importation d'une sauvegarde annulera et remplacera toutes les données actuelles.", font=FONT_MAIN, bg=COLORS["card"], fg=COLORS["warn"], justify="left").pack(anchor="w", pady=(0, 15))
        tk.Button(card_im, text="🔄 Importer un fichier .db", bg=COLORS["danger"], fg="white", font=FONT_BOLD, relief="flat", padx=10, pady=6, cursor="hand2", command=self._import_db).pack(anchor="w")

    def _browse_gdrive(self) -> None:
        direction = filedialog.askdirectory(title="Sélectionner le dossier Google Drive")
        if direction:
            self.var_gdrive.set(direction)

    def _save_gdrive_config(self) -> None:
        cfg = load_config() or {}
        cfg["gdrive_backup"] = self.var_gdrive.get().strip()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("OK", "Dossier automatique local configuré. La sauvegarde se fera à l'arrêt du serveur.")
    
    def _save_gdrive_api_config(self) -> None:
        cfg = load_config() or {}
        cfg["gdrive_webhook"] = self.var_gd_webhook.get().strip()
        cfg["gdrive_folder_id"] = self.var_gd_folder.get().strip()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("OK", "Connexion automatique API Cloud configurée. La sauvegarde directe se fera à l'arrêt du serveur.")
        
    def _auto_backup(self) -> None:
        if not os.path.exists("fiscalite.db"): return
        
        cfg = load_config() or {}
        dt = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"fiscalite_Sauvegarde_{dt}.db"
        
        # 1. Option Local Folder
        dest = cfg.get("gdrive_backup")
        if dest and os.path.exists(dest):
            try:
                shutil.copy("fiscalite.db", os.path.join(dest, filename))
            except Exception: pass
            
        # 2. Option Cloud API
        webhook = cfg.get("gdrive_webhook")
        folder_id = cfg.get("gdrive_folder_id")
        if webhook and folder_id:
            try:
                import base64, urllib.request, urllib.parse
                
                with open("fiscalite.db", "rb") as f:
                    file_b64 = base64.b64encode(f.read()).decode('utf-8')
                    
                data = {
                    "filename": filename,
                    "folder_id": folder_id,
                    "mimeType": "application/x-sqlite3",
                    "file": file_b64
                }
                payload = json.dumps(data).encode("utf-8")
                
                req = urllib.request.Request(webhook, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
                urllib.request.urlopen(req, timeout=10) # Envoi bloquant (10s max)
            except Exception as e:
                print("Echec API Sauvegarde:", e)

    def _export_db(self) -> None:
        if not os.path.exists("fiscalite.db"):
            messagebox.showerror("Erreur", "Base inexistante.")
            return
        dt = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = filedialog.asksaveasfilename(defaultextension=".db", initialfile=f"fiscalite_Exporter_{dt}.db", title="Exporter la base (.db)")
        if target:
            try:
                shutil.copy("fiscalite.db", target)
                messagebox.showinfo("Export", f"Succès de l'exportation vers:\n{target}")
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

    def _import_db(self) -> None:
        if self.server_thread is not None:
            messagebox.showerror("Serveur ACTIF", "Veuillez d'abord arrêter le serveur (onglet précédent) avant d'importer une base de données, pour éviter de corrompre les données en cours d'utilisation.")
            return
        src = filedialog.askopenfilename(title="Ouvrir une sauvegarde de base de données (.db)", filetypes=[("Base SQLite", "*.db")])
        if src:
            if messagebox.askyesno("⚠ Avertissement", "Êtes-vous sûr de vouloir remplacer complètement la base actuelle ?\nToutes les modifications non sauvegardées seront perdues."):
                try:
                    if os.path.exists("fiscalite.db"):
                        shutil.copy("fiscalite.db", "fiscalite_Secours.db")
                    shutil.copy(src, "fiscalite.db")
                    messagebox.showinfo("Import Réussi", "La base de données a été restaurée.\nUne copie de précaution de l'ancienne BD se trouve sous le nom 'fiscalite_Secours.db'.")
                except Exception as e:
                    messagebox.showerror("Erreur Import", str(e))

    # ── Utilitaires ──────────────────────────────

    def _commune_name(self) -> str:
        cfg = load_config()
        return cfg["commune"]["nom"] if cfg else "—"

    # ── Gestion serveur ──────────────────────────
    def _start_server(self) -> None:
        if self.server_thread is None:
            try:
                self.server_thread = ServerThread(app)
                self.server_thread.start()
                self._set_status(True)
            except Exception as e:
                messagebox.showerror("Erreur démarrage", str(e))

    def _stop_server(self) -> None:
        if self.server_thread is not None:
            self.lbl_status.config(text="  ARRÊT EN COURS...", fg=COLORS["warn"])
            self.btn_stop.config(state=tk.DISABLED)
            self.update()
            # Arrêt dans un thread séparé pour ne pas bloquer l'UI
            t = self.server_thread
            self.server_thread = None
            def _do_stop():
                try:
                    self._auto_backup()
                except Exception:
                    pass
                t.shutdown()
                t.join(timeout=2)
                self.after(0, self._set_status, False)
            threading.Thread(target=_do_stop, daemon=True).start()

    def _set_status(self, online: bool) -> None:
        if online:
            self.lbl_dot.config(fg=COLORS["accent2"])
            self.lbl_status.config(text="  SERVEUR EN LIGNE", fg=COLORS["accent2"])
            self._card_status.config(highlightbackground=COLORS["accent2"])
            self.btn_start.config(state=tk.DISABLED, bg=COLORS["border"])
            self.btn_stop.config(state=tk.NORMAL,   bg=COLORS["danger"])
        else:
            self.lbl_dot.config(fg=COLORS["danger"])
            self.lbl_status.config(text="  SERVEUR ARRÊTÉ", fg=COLORS["danger"])
            self._card_status.config(highlightbackground=COLORS["border"])
            self.btn_start.config(state=tk.NORMAL,   bg=COLORS["accent2"])
            self.btn_stop.config(state=tk.DISABLED,  bg=COLORS["border"])

    def _open_browser(self) -> None:
        webbrowser.open(f"http://{self.ip_local}:5000")

    # ── System Tray ──────────────────────────────
    def _hide_to_tray(self) -> None:
        self.withdraw()
        if not self._tray_running:
            self._start_tray()

    def _start_tray(self) -> None:
        icon_image = make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("🖥  Ouvrir JIBAYAT",       self._show_from_tray, default=True),
            pystray.MenuItem("🌍  Ouvrir Application",
                             lambda icon, item: webbrowser.open(f"http://{self.ip_local}:5000")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("▶  Démarrer serveur",
                             lambda icon, item: self.after(0, self._start_server)),
            pystray.MenuItem("⏹  Arrêter serveur",
                             lambda icon, item: self.after(0, self._stop_server)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("✖  Quitter",                  self._quit_from_tray),
        )
        self._tray_icon = pystray.Icon("JIBAYAT", icon_image, "JIBAYAT", menu)
        self._tray_running = True
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._tray_icon is not None:
            self._tray_icon.stop()
            self._tray_running = False
            self._tray_icon = None
        self.after(0, self.deiconify)

    def _quit_from_tray(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        if self._tray_icon is not None:
            self._tray_icon.stop()
        self.after(0, self._force_quit)

    def _force_quit(self) -> None:
        self._stop_server()
        self.destroy()

    # ── Mises à jour ─────────────────────────────
    def _bg_fetch(self) -> None:
        """Vérification silencieuse des mises à jour au démarrage."""
        try:
            subprocess.run(
                ["git", "fetch"],
                capture_output=True, timeout=8,
                creationflags=_WIN_FLAG
            )
            res = subprocess.run(
                ["git", "status", "-uno"],
                capture_output=True, text=True, timeout=5,
                creationflags=_WIN_FLAG
            )
            if ("Your branch is behind" in res.stdout or
                    "Votre branche est en retard" in res.stdout):
                self.after(0, self._show_update_banner)
        except Exception:
            pass

    def _show_update_banner(self) -> None:
        """Affiche le bandeau de mise à jour si pas encore visible."""
        if not self.frm_update.winfo_ismapped():
            self.frm_update.pack(fill=tk.X, side=tk.TOP)

    def _check_updates_manual(self) -> None:
        try:
            subprocess.run(["git", "fetch"], capture_output=True, timeout=10,
                           creationflags=_WIN_FLAG)
            res = subprocess.run(["git", "status", "-uno"],
                                 capture_output=True, text=True, timeout=5,
                                 creationflags=_WIN_FLAG)
            behind = ("Your branch is behind" in res.stdout or
                      "Votre branche est en retard" in res.stdout)
            if behind:
                if messagebox.askyesno("Mise à jour disponible",
                                       "Une nouvelle version est disponible.\nMettre à jour maintenant ?"):
                    self._do_git_pull()
            else:
                messagebox.showinfo("✅ À jour", "JIBAYAT est déjà à jour !")
        except FileNotFoundError:
            messagebox.showerror("Git introuvable",
                                 "Git n'est pas installé.\nTéléchargez-le sur https://git-scm.com")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _do_git_pull(self) -> None:
        try:
            res = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30,
                                 creationflags=_WIN_FLAG)
            if "Already up to date" in res.stdout or "Déjà à jour" in res.stdout:
                messagebox.showinfo("✅", "Déjà à jour !")
            else:
                self.frm_update.pack_forget()
                messagebox.showinfo("✅ Mise à jour réussie",
                                    "Application mise à jour !\nRedémarrez le lanceur pour appliquer.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    # ── Rapport ──────────────────────────────────
    def _open_report(self) -> None:
        ReportDialog(self, load_config())

    # ── Fermeture ────────────────────────────────
    def _on_close(self) -> None:
        if messagebox.askyesno("Quitter JIBAYAT", "Voulez-vous quitter ?"):
            self._force_quit()


# ─────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    root = ModernLauncher()
    if not os.path.exists(CONFIG_FILE):
        root.after(100, lambda: SetupWizard(root))
    root.mainloop()
