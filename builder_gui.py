import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import sys

class BuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Instalador - Análisis Financiero")
        self.root.geometry("600x450")
        self.root.resizable(False, False)
        
        # Estilos
        style = ttk.Style()
        style.theme_use('clam')
        
        # Variables
        self.project_path = os.path.dirname(os.path.abspath(__file__))
        self.output_path = tk.StringVar(value=os.path.join(self.project_path, "dist"))
        
        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Configuración del Instalador Windows", font=("Helvetica", 14, "bold"))
        title_label.pack(pady=(0, 20))

        # Selección de carpeta de salida
        out_frame = ttk.LabelFrame(main_frame, text=" Carpeta de destino del ejecutable (.exe) ", padding="10")
        out_frame.pack(fill=tk.X, pady=10)

        ttk.Entry(out_frame, textvariable=self.output_path, width=50).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(out_frame, text="Explorar...", command=self.browse_output).pack(side=tk.LEFT)

        # Opciones
        opt_frame = ttk.LabelFrame(main_frame, text=" Opciones de compilación ", padding="10")
        opt_frame.pack(fill=tk.X, pady=10)
        
        self.onefile_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Crear un único archivo (.exe)", variable=self.onefile_var).pack(anchor=tk.W)
        
        self.windowed_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="Ocultar consola al ejecutar la app", variable=self.windowed_var).pack(anchor=tk.W)

        # Consola de salida
        self.log_text = tk.Text(main_frame, height=8, font=("Consolas", 9), state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(fill=tk.X, pady=10)

        # Botón de construcción
        self.build_btn = ttk.Button(main_frame, text="GENERAR EJECUTABLE", command=self.start_build, style="Accent.TButton")
        self.build_btn.pack(pady=10)

    def browse_output(self):
        dir = filedialog.askdirectory(initialdir=self.output_path.get())
        if dir:
            self.output_path.set(dir)

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_build(self):
        self.build_btn.config(state=tk.DISABLED)
        self.log("Iniciando proceso de construcción...")
        thread = threading.Thread(target=self.run_pyinstaller)
        thread.start()

    def run_pyinstaller(self):
        try:
            # Asegurar dependencias
            self.log("Verificando dependencias (pip install)...")
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], capture_output=True)
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], capture_output=True, cwd=self.project_path)

            # Construir comando
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--noconfirm",
                "--name", "AnalisisFinanciero",
                "--distpath", self.output_path.get(),
                "--add-data", f"templates{os.pathsep}templates",
                "--add-data", f"static{os.pathsep}static",
                "--collect-all", "setuptools",
                "--icon", "app_icon.ico",
                "--clean"
            ]
            
            if self.onefile_var.get(): cmd.append("--onefile")
            if self.windowed_var.get(): cmd.append("--windowed")
            
            cmd.append("run_app.py")

            self.log(f"Ejecutando: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                cwd=self.project_path,
                shell=True
            )

            for line in process.stdout:
                self.log(line.strip())

            process.wait()
            
            if process.returncode == 0:
                self.log("¡ÉXITO! El ejecutable ha sido generado.")
                messagebox.showinfo("Éxito", f"Compilación finalizada.\n\nArchivo guardado en:\n{self.output_path.get()}")
            else:
                self.log(f"ERROR: El proceso terminó con código {process.returncode}")
                messagebox.showerror("Error", "Hubo un problema durante la compilación. Revisa el log.")

        except Exception as e:
            self.log(f"ERROR CRÍTICO: {str(e)}")
            messagebox.showerror("Error Crítico", str(e))
        finally:
            self.build_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = BuilderApp(root)
    root.mainloop()
