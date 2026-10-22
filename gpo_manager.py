import sys
import os
import winreg
import subprocess
import ctypes
import urllib.request
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox

# 1. Elevación automática de permisos UAC
def ensure_admin():
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if not is_admin:
        ctypes.windll.shell32.ShellExecuteW(
            None, 
            "runas", 
            sys.executable, 
            " ".join([f'"{arg}"' for arg in sys.argv]), 
            None, 
            1
        )
        sys.exit(0)

# Configuración exacta de Directivas (4 directivas finales)
LGPO_TEXT_CONFIG = """Computer
SOFTWARE\\Policies\\Microsoft\\Windows NT\\SystemRestore
DisableConfig
DWORD:1

Computer
SOFTWARE\\Policies\\Microsoft\\Windows NT\\SystemRestore
DisableSR
DWORD:1

Computer
SOFTWARE\\Policies\\Microsoft\\WindowsStore
RemoveWindowsStore
DWORD:1

Computer
SOFTWARE\\Policies\\Microsoft\\WindowsStore
RequirePrivateStoreOnly
DWORD:1
"""

POLICIES_INFO = [
    {
        "key": "disable_config",
        "name": "Desactivar configuración de Restaurar sistema",
        "path": "Plantillas administrativas / Sistema / Restaurar sistema",
        "target_state": "Habilitada",
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore",
        "value_name": "DisableConfig",
        "target_value": 1
    },
    {
        "key": "system_restore",
        "name": "Desactivar Restaurar sistema",
        "path": "Plantillas administrativas / Sistema / Restaurar sistema",
        "target_state": "Habilitada",
        "key_path": r"SOFTWARE\Policies\Microsoft\Windows NT\SystemRestore",
        "value_name": "DisableSR",
        "target_value": 1
    },
    {
        "key": "disable_store",
        "name": "Desactivar la aplicación Microsoft Store",
        "path": "Componentes de Windows / Tienda",
        "target_state": "Habilitada",
        "key_path": r"SOFTWARE\Policies\Microsoft\WindowsStore",
        "value_name": "RemoveWindowsStore",
        "target_value": 1
    },
    {
        "key": "private_store",
        "name": "Mostrar solo la tienda privada en Microsoft Store",
        "path": "Componentes de Windows / Tienda",
        "target_state": "Habilitada",
        "key_path": r"SOFTWARE\Policies\Microsoft\WindowsStore",
        "value_name": "RequirePrivateStoreOnly",
        "target_value": 1
    }
]

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def ensure_lgpo_exists(log_func):
    base_dir = get_base_dir()
    lgpo_path = os.path.join(base_dir, "LGPO.exe")

    if os.path.exists(lgpo_path):
        return lgpo_path

    current_dir_lgpo = os.path.join(os.getcwd(), "LGPO.exe")
    if os.path.exists(current_dir_lgpo):
        return current_dir_lgpo

    log_func("[!] LGPO.exe no presente localmente. Obteniendo desde Microsoft...")
    url = "https://download.microsoft.com/download/8/5/C/85C25433-A1B0-4CCE-9B2A-3A39828236A3/LGPO.zip"
    zip_path = os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp"), "LGPO.zip")

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            out_file.write(response.read())

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith("LGPO.exe"):
                    file_info.filename = os.path.basename(file_info.filename)
                    zip_ref.extract(file_info, base_dir)
                    break

        if os.path.exists(lgpo_path):
            log_func("[OK] LGPO.exe descargado e instalado correctamente.")
            return lgpo_path
        else:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith("LGPO.exe"):
                        file_info.filename = os.path.basename(file_info.filename)
                        zip_ref.extract(file_info, os.getcwd())
                        break
            return os.path.join(os.getcwd(), "LGPO.exe")

    except Exception as e:
        log_func(f"[ERROR] No se pudo obtener LGPO.exe automáticamente: {e}")
        return None

def read_registry_value(key_path, value_name):
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        val, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return val
    except Exception:
        return None

class GPOManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GPO Policy Suite - Windows Administrator")
        self.root.geometry("820x540")
        self.root.minsize(780, 500)
        self.root.configure(bg="#f1f5f9")

        # Cargar icono si existe
        icon_path = os.path.join(get_base_dir(), "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.status_widgets = {}
        self.setup_styles()
        self.setup_ui()
        self.check_status()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.style.configure("TNotebook", background="#f1f5f9", borderwidth=0)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 8], background="#e2e8f0", foreground="#475569")
        self.style.map("TNotebook.Tab", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])

    def setup_ui(self):
        header = tk.Frame(self.root, bg="#0f172a", height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg="#0f172a")
        title_frame.pack(side="left", padx=20, pady=12)

        main_title = tk.Label(
            title_frame, 
            text="GPO Policy Manager", 
            font=("Segoe UI", 15, "bold"), 
            fg="#ffffff", 
            bg="#0f172a"
        )
        main_title.pack(anchor="w")

        sub_title = tk.Label(
            title_frame, 
            text="Configurador Automático de Directivas Locales (gpedit.msc)", 
            font=("Segoe UI", 8), 
            fg="#94a3b8", 
            bg="#0f172a"
        )
        sub_title.pack(anchor="w")

        admin_badge = tk.Label(
            header, 
            text="🛡️ Modo Administrador", 
            font=("Segoe UI", 9, "bold"), 
            fg="#4ade80", 
            bg="#1e293b", 
            padx=12, 
            pady=6,
            relief="flat"
        )
        admin_badge.pack(side="right", padx=20)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=20, pady=15)

        self.tab_config = tk.Frame(notebook, bg="#f1f5f9")
        notebook.add(self.tab_config, text="Panel de Directivas")

        self.tab_log = tk.Frame(notebook, bg="#f1f5f9")
        notebook.add(self.tab_log, text="Consola de Estado")

        self.build_config_tab()
        self.build_log_tab()

    def build_config_tab(self):
        action_bar = tk.Frame(self.tab_config, bg="#f1f5f9")
        action_bar.pack(fill="x", pady=(10, 15))

        btn_apply = tk.Button(
            action_bar, 
            text="🚀 Aplicar y Sincronizar (gpedit.msc)", 
            command=self.apply_policies, 
            bg="#2563eb", 
            fg="#ffffff", 
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"), 
            padx=18, 
            pady=7, 
            bd=0,
            cursor="hand2"
        )
        btn_apply.pack(side="left")

        btn_refresh = tk.Button(
            action_bar, 
            text="🔄 Comprobar Estado", 
            command=self.check_status, 
            bg="#ffffff", 
            fg="#334155", 
            activebackground="#e2e8f0",
            activeforeground="#0f172a",
            font=("Segoe UI", 10, "bold"), 
            padx=15, 
            pady=7, 
            bd=1,
            relief="solid",
            cursor="hand2"
        )
        btn_refresh.pack(side="left", padx=10)

        canvas = tk.Canvas(self.tab_config, bg="#f1f5f9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_config, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#f1f5f9")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for pol in POLICIES_INFO:
            card = tk.Frame(scrollable_frame, bg="#ffffff", bd=1, relief="solid")
            card.pack(fill="x", expand=True, pady=4, ipady=6, padx=2)

            info_frame = tk.Frame(card, bg="#ffffff")
            info_frame.pack(side="left", fill="both", expand=True, padx=12)

            title_lbl = tk.Label(info_frame, text=pol["name"], font=("Segoe UI", 9, "bold"), fg="#0f172a", bg="#ffffff", anchor="w")
            title_lbl.pack(fill="x")

            path_lbl = tk.Label(info_frame, text=f"Ruta: {pol['path']}  |  Estado objetivo: [{pol['target_state']}]", font=("Segoe UI", 8), fg="#64748b", bg="#ffffff", anchor="w")
            path_lbl.pack(fill="x", pady=(2, 0))

            status_badge = tk.Label(
                card, 
                text="Verificando...", 
                font=("Segoe UI", 8, "bold"), 
                bg="#e2e8f0", 
                fg="#475569", 
                padx=12, 
                pady=4
            )
            status_badge.pack(side="right", padx=12)
            
            self.status_widgets[pol["key"]] = status_badge

    def build_log_tab(self):
        log_frame = tk.Frame(self.tab_log, bg="#1e293b", bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True, pady=10)

        self.log_text = tk.Text(
            log_frame, 
            bg="#0f172a", 
            fg="#38bdf8", 
            insertbackground="#ffffff",
            font=("Consolas", 9), 
            wrap="word",
            bd=0,
            padx=10,
            pady=10
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def check_status(self):
        self.log("--- Verificando estado en el Registro de Windows ---")
        for pol in POLICIES_INFO:
            val = read_registry_value(pol["key_path"], pol["value_name"])
            badge = self.status_widgets[pol["key"]]
            
            if val == pol["target_value"]:
                badge.config(text="Aplicada", bg="#dcfce7", fg="#15803d")
                self.log(f"[OK] {pol['name']}: Configurada ({val})")
            else:
                badge.config(text="No Aplicada", bg="#fee2e2", fg="#b91c1c")
                self.log(f"[PENDIENTE] {pol['name']}: Valor actual = {val}")

    def apply_policies(self):
        self.log("\n--- Iniciando proceso de sincronización con LGPO ---")
        
        lgpo_exe = ensure_lgpo_exists(self.log)
        if not lgpo_exe or not os.path.exists(lgpo_exe):
            messagebox.showerror("Error de Ejecución", "No se pudo obtener el motor LGPO.exe.")
            return

        txt_path = os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp"), "gpo_import.txt")

        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(LGPO_TEXT_CONFIG)
        except Exception as e:
            self.log(f"[ERROR] Fallo al escribir archivo temporal: {e}")
            messagebox.showerror("Error", f"Error de archivo temporal: {e}")
            return

        self.log("Inyectando políticas en registry.pol con LGPO.exe...")
        try:
            res = subprocess.run(
                [lgpo_exe, "/t", txt_path], 
                capture_output=True, 
                text=True, 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if res.returncode == 0:
                self.log("[ÉXITO] Objeto de directiva guardado correctamente.")
                self.log("Forzando actualización inmediata (gpupdate /force)...")
                
                subprocess.run(
                    ["gpupdate", "/force"], 
                    capture_output=True, 
                    text=True, 
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.log("[OK] Directivas sincronizadas con el sistema operativo.")

                messagebox.showinfo(
                    "Operación Exitosa", 
                    "Directivas sincronizadas correctamente.\n\nCierra y reabre 'gpedit.msc' para observar los cambios actualizados."
                )
            else:
                self.log(f"[ERROR] LGPO finalizó con errores: {res.stderr or res.stdout}")
                messagebox.showerror("Error en LGPO", f"Detalle de error:\n{res.stderr or res.stdout}")

        except Exception as e:
            self.log(f"[ERROR] Excepción de ejecución: {e}")
            messagebox.showerror("Error", str(e))

        self.check_status()

if __name__ == "__main__":
    ensure_admin()
    root = tk.Tk()
    app = GPOManagerApp(root)
    root.mainloop()