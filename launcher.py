import tkinter as tk
from tkinter import ttk, messagebox
import json, os, subprocess, socket, datetime, webbrowser
import threading

CONFIG_FILE = "config.json"
VERSION_FILE = "version.txt"

if not os.path.exists(VERSION_FILE):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write("1.0.0")

class SetupWizard(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Première Installation")
        self.geometry("500x650")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.grab_set()

        ttk.Label(self, text="Configuration Initiale de la Commune", font=("Segoe UI", 16, "bold")).pack(pady=15)

        form_frame = ttk.Frame(self, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="Nom de la commune (Fr):").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_nom = ttk.Entry(form_frame, width=30)
        self.ent_nom.grid(row=0, column=1, pady=5)

        ttk.Label(form_frame, text="Nom de la commune (Ar):").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_nom_ar = ttk.Entry(form_frame, width=30, justify="right")
        self.ent_nom_ar.grid(row=1, column=1, pady=5)

        ttk.Label(form_frame, text="Région:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_region = ttk.Entry(form_frame, width=30)
        self.ent_region.grid(row=2, column=1, pady=5)

        ttk.Label(form_frame, text="Province:").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_prov = ttk.Entry(form_frame, width=30)
        self.ent_prov.grid(row=3, column=1, pady=5)

        ttk.Label(form_frame, text="Code Commune:").grid(row=4, column=0, sticky="w", pady=5)
        self.ent_code = ttk.Entry(form_frame, width=30)
        self.ent_code.grid(row=4, column=1, pady=5)

        ttk.Label(form_frame, text="Modules Fiscaux à installer:", font=("Segoe UI", 11, "bold")).grid(row=5, column=0, columnspan=2, pady=15, sticky="w")

        self.modules = {
            "TNB": tk.BooleanVar(value=True),
            "DEBITS_BOISSONS": tk.BooleanVar(value=True),
            "TRANSPORT_VOYAGEURS": tk.BooleanVar(value=True),
            "STATIONNEMENT": tk.BooleanVar(value=True),
            "OCCUPATION_DOMAINE": tk.BooleanVar(value=True),
            "FOURRIERE": tk.BooleanVar(value=True),
            "LOCATION_LOCAUX": tk.BooleanVar(value=True),
            "AFFERMAGE_SOUKS": tk.BooleanVar(value=True)
        }
        
        row = 6
        for mod, var in self.modules.items():
            ttk.Checkbutton(form_frame, text=mod, variable=var).grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
            row += 1

        ttk.Label(form_frame, text="Avertissement : Les tables non sélectionnées ne seront pas pré-remplies.", font=("Segoe UI", 8), foreground="gray").grid(row=row, column=0, columnspan=2, pady=10)

        btn = ttk.Button(self, text="Terminer l'installation", command=self.save)
        btn.pack(pady=10)

    def on_close(self):
        messagebox.showerror("Erreur", "L'installation doit être complétée avant de pouvoir utiliser GFC Maroc.")

    def save(self):
        nom = self.ent_nom.get()
        if not nom:
            messagebox.showwarning("Attention", "Le nom de la commune est obligatoire.")
            return

        cfg = {
            "commune": {
                "nom": nom,
                "nom_ar": self.ent_nom_ar.get(),
                "region": self.ent_region.get(),
                "province": self.ent_prov.get(),
                "code": self.ent_code.get()
            },
            "modules": [mod for mod, var in self.modules.items() if var.get()]
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        try:
            import app
            app.init_db()
            messagebox.showinfo("Succès", "Base de données initialisée avec succès ! Le serveur est prêt.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erreur DB", f"Erreur lors de l'initialisation: {str(e)}")
            os.remove(CONFIG_FILE)

class LauncherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lanceur - GFC Maroc")
        self.geometry("500x520")
        self.configure(bg="#f0f4f8")

        self.server_process = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#f0f4f8", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1e3a5f")
        style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"))
        
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="🏛️ GFC Maroc - Contrôle du Web", style="Header.TLabel").pack(pady=10)

        # Status & IP
        self.lbl_status = ttk.Label(main_frame, text="🔴 Serveur Arrêté", foreground="red", style="Status.TLabel")
        self.lbl_status.pack(pady=5)

        self.lbl_ip = ttk.Label(main_frame, text=f"🌐 Adresse Locale: http://127.0.0.1:5000\n🌐 Accès Réseau: http://{self.get_local_ip()}:5000", justify=tk.CENTER)
        self.lbl_ip.pack(pady=5)

        # Controls
        ctrl_frame = ttk.Frame(main_frame, padding=10)
        ctrl_frame.pack(fill=tk.X)
        self.btn_start = ttk.Button(ctrl_frame, text="▶️ Démarrer Serveur", command=self.start_server, style="Primary.TButton")
        self.btn_start.pack(pady=5, fill=tk.X)

        self.btn_stop = ttk.Button(ctrl_frame, text="⏹️ Arrêter Serveur", command=self.stop_server, state=tk.DISABLED)
        self.btn_stop.pack(pady=5, fill=tk.X)

        btn_browser = ttk.Button(ctrl_frame, text="🌍 Ouvrir dans le navigateur", command=lambda: webbrowser.open(f"http://127.0.0.1:5000"))
        btn_browser.pack(pady=5, fill=tk.X)

        sep = ttk.Separator(main_frame, orient="horizontal")
        sep.pack(fill=tk.X, pady=15)

        # Version & Updates
        self.version = self.read_version()
        self.lbl_ver = ttk.Label(main_frame, text=f"📦 Version Actuelle: {self.version}")
        self.lbl_ver.pack()
        
        last_upd = "Jamais"
        if os.path.exists("last_update.txt"):
            with open("last_update.txt", "r") as f:
                last_upd = f.read().strip()
                
        self.lbl_last_upd = ttk.Label(main_frame, text=f"Dernière vérification: {last_upd}", font=("Segoe UI", 8), foreground="gray")
        self.lbl_last_upd.pack(pady=2)

        btn_update = ttk.Button(main_frame, text="🔄 Mettre à jour (GitHub Pull)", command=self.update_app)
        btn_update.pack(pady=5, fill=tk.X)

        btn_bug = ttk.Button(main_frame, text="🐛 Signaler un bug / Commentaires", command=self.report_bug)
        btn_bug.pack(pady=5, fill=tk.X)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def read_version(self):
        try:
            with open(VERSION_FILE, "r") as f:
                return f.read().strip()
        except:
            return "1.0.0"

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def start_server(self):
        if not self.server_process:
            try:
                self.server_process = subprocess.Popen(["python", "app.py"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                self.lbl_status.config(text="🟢 Serveur En Ligne", foreground="green")
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de démarrer le serveur:\n{e}")

    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None
            self.lbl_status.config(text="🔴 Serveur Arrêté", foreground="red")
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)

    def update_app(self):
        try:
            res = subprocess.run(["git", "pull"], capture_output=True, text=True)
            if "Already up to date." in res.stdout or "Déjà à jour" in res.stdout:
                messagebox.showinfo("Mise à jour", "L'application est déjà à jour avec le serveur GitHub.")
            else:
                messagebox.showinfo("Mise à jour", f"Code source mis à jour avec succès. Veuillez re-démarrer le serveur.\n\nLogs:\n{res.stdout}")
                self.version = self.read_version()
                self.lbl_ver.config(text=f"📦 Version Actuelle: {self.version}")
            
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("last_update.txt", "w") as f:
                f.write(now_str)
            self.lbl_last_upd.config(text=f"Dernière vérification: {now_str}")
        except Exception as e:
            messagebox.showerror("Erreur de mise à jour", f"Assurez-vous que git est installé et que le repo est lié.\nErreur: {str(e)}")

    def report_bug(self):
        # On essaie d'extraire l'URL du remote
        try:
            res = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True)
            remote = res.stdout.strip()
            if remote.endswith(".git"):
                remote = remote[:-4]
                
            if not remote:
                messagebox.showwarning("GitHub", "Veuillez d'abord lier ce projet à un dépôt GitHub public.\nEx: git remote add origin https://github.com/VOUS/REPO.git")
                return
                
            issue_url = f"{remote}/issues/new?title=[Bug/Commentaire]%20Nouveau%20Signalement&body=**Endroit%20du%20probl%C3%A8me%20(ou%20module):**%0A-%20%0A%0A**Description%20et%20Commentaires:**%0A-%20%0A"
            webbrowser.open(issue_url)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def on_close(self):
        self.stop_server()
        self.destroy()

if __name__ == "__main__":
    app_gui = LauncherApp()
    if not os.path.exists(CONFIG_FILE):
        # Force le setup si pas de config
        app_gui.after(100, lambda: SetupWizard(app_gui))
    app_gui.mainloop()
