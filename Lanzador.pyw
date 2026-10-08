import tkinter as tk
from tkinter import messagebox
import subprocess
import webbrowser
import os
import sys
import threading

# Proceso global para mantener la referencia del servidor
server_process = None
pinggy_process = None

def server_running():
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:5000/api/status", timeout=1)
        return True
    except Exception:
        return False

def toggle_server():
    global server_process
    if server_process is None and server_running():
        # Ya hay un servidor andando (por ejemplo de otra ventana): solo abrir el panel
        webbrowser.open("http://localhost:5000")
        return
    if server_process is None:
        try:
            # Iniciar el servidor de Flask de forma oculta (sin terminal)
            # creationflags=0x08000000 es CREATE_NO_WINDOW en Windows
            
            # Intentar usar el mismo python que Lanzador, pero si no tiene las librerías, usar el de WindowsApps
            try:
                import flask
                python_exe = sys.executable.replace("pythonw.exe", "python.exe")
            except ImportError:
                python_exe = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe")
            
            log_file = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_log.txt"), "w", encoding="utf-8")
            log_file.write(f"Lanzador sys.executable: {sys.executable}\n")
            log_file.write(f"Using python_exe: {python_exe}\n")
            log_file.flush()
            
            server_process = subprocess.Popen(
                [python_exe, "server.py"], 
                creationflags=subprocess.CREATE_NO_WINDOW,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            btn_server.config(text="Detener Servidor", bg="#ef4444", activebackground="#dc2626")
            lbl_status.config(text="Estado: EN LÍNEA", fg="#10b981")
            
            # Hacer polling para esperar a que el servidor esté activo antes de abrir el navegador
            def check_server():
                import urllib.request
                if server_process.poll() is not None:
                    # El proceso murió
                    messagebox.showerror("Error", "El servidor se cerró inesperadamente al iniciar. Revisa server_log.txt para más detalles.")
                    # Revertir UI
                    btn_server.config(text="Iniciar Servidor", bg="#3b82f6", activebackground="#2563eb")
                    lbl_status.config(text="Estado: APAGADO", fg="#ef4444")
                    return
                
                try:
                    urllib.request.urlopen("http://localhost:5000/api/status", timeout=1)
                    webbrowser.open("http://localhost:5000")
                except:
                    root.after(1000, check_server)

            root.after(1000, check_server)
            
            # Habilitar el botón de Pinggy
            btn_pinggy.config(state="normal", bg="#8b5cf6")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar el servidor:\n{str(e)}")
    else:
        # Detener el servidor
        try:
            server_process.terminate()
            server_process = None
            btn_server.config(text="Iniciar Servidor", bg="#3b82f6", activebackground="#2563eb")
            lbl_status.config(text="Estado: APAGADO", fg="#ef4444")
            
            # Si el túnel de Pinggy está encendido, apagarlo también
            if pinggy_process is not None:
                toggle_pinggy()
                
            # Deshabilitar el botón de Pinggy
            btn_pinggy.config(state="disabled", bg="#475569")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo detener el servidor:\n{str(e)}")

def find_cloudflared():
    import shutil, glob
    portable = os.path.join(os.path.dirname(os.path.abspath(__file__)), "herramientas", "cloudflared.exe")
    if os.path.exists(portable):
        return portable
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    candidatos = [r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe",
                  os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe")]
    candidatos += glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Cloudflare.cloudflared*\*.exe"))
    return next((c for c in candidatos if os.path.exists(c)), None)

def show_link(url):
    link_var.set(url)
    entry_link.pack(pady=(4, 0))
    btn_copy.pack(pady=4)
    lbl_hint.config(text="Abrilo en el celular e ingresá con tu contraseña")

def toggle_pinggy():
    """Enlace para el celular. Usa Cloudflare (sin límite de tiempo); si no está instalado, Pinggy."""
    global pinggy_process
    if pinggy_process is None:
        cf = find_cloudflared()
        try:
            if cf:
                pinggy_process = subprocess.Popen(
                    [cf, "tunnel", "--no-autoupdate", "--url", "http://localhost:5000"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="ignore", creationflags=subprocess.CREATE_NO_WINDOW)
                lbl_hint.config(text="Generando enlace...")

                def leer_salida(proc):
                    import re
                    for line in proc.stdout:
                        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                        if m:
                            root.after(0, show_link, m.group(0))
                threading.Thread(target=leer_salida, args=(pinggy_process,), daemon=True).start()
            else:
                # Pinggy: el enlace gratis dura 60 minutos y se ve en la consola que se abre
                pinggy_process = subprocess.Popen(
                    ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=no", "-R0:localhost:5000", "a.pinggy.io"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
                lbl_hint.config(text="Copiá el enlace pinggy.link de la consola (dura 60 min)")
            btn_pinggy.config(text="Detener Enlace Celular", bg="#ef4444", activebackground="#dc2626")
        except Exception as e:
            pinggy_process = None
            messagebox.showerror("Error", f"No se pudo crear el enlace:\n{str(e)}")
    else:
        try:
            pinggy_process.terminate()
        except Exception:
            pass
        pinggy_process = None
        link_var.set("")
        entry_link.pack_forget()
        btn_copy.pack_forget()
        lbl_hint.config(text="")
        btn_pinggy.config(text="Activar Enlace Celular", bg="#8b5cf6", activebackground="#7c3aed")

def copy_link():
    root.clipboard_clear()
    root.clipboard_append(link_var.get())
    btn_copy.config(text="¡Copiado!")
    root.after(1500, lambda: btn_copy.config(text="Copiar enlace"))

def on_closing():
    # Asegurarnos de cerrar los procesos si el usuario cierra la ventana
    if server_process is not None:
        server_process.terminate()
    if pinggy_process is not None:
        pinggy_process.terminate()
    root.destroy()

# Configuración de la interfaz gráfica (Ventana)
root = tk.Tk()
root.title("Prospector Pro - Lanzador")
root.geometry("380x340")
root.configure(bg="#0f172a") # Fondo oscuro premium
root.resizable(False, False)

# Centrar ventana en la pantalla
root.eval('tk::PlaceWindow . center')

root.protocol("WM_DELETE_WINDOW", on_closing)

# Título
lbl_title = tk.Label(root, text="Prospector Pro", fg="#f8fafc", bg="#0f172a", font=("Inter", 16, "bold"))
lbl_title.pack(pady=(20, 5))

# Estado
lbl_status = tk.Label(root, text="Estado: APAGADO", fg="#ef4444", bg="#0f172a", font=("Inter", 10, "bold"))
lbl_status.pack(pady=(0, 20))

# Botón Principal (Servidor)
btn_server = tk.Button(
    root, text="Iniciar Servidor", bg="#3b82f6", fg="white", 
    font=("Inter", 12, "bold"), command=toggle_server, 
    relief="flat", cursor="hand2", width=25, pady=8,
    activebackground="#2563eb", activeforeground="white"
)
btn_server.pack(pady=5)

# Botón Secundario (Pinggy)
btn_pinggy = tk.Button(
    root, text="Activar Enlace Celular", bg="#475569", fg="white", 
    font=("Inter", 10, "bold"), command=toggle_pinggy, 
    relief="flat", cursor="hand2", width=30, pady=5,
    state="disabled", activebackground="#7c3aed", activeforeground="white"
)
btn_pinggy.pack(pady=10)

link_var = tk.StringVar()
entry_link = tk.Entry(root, textvariable=link_var, width=42, justify="center", readonlybackground="#1e293b",
                      fg="#f8fafc", relief="flat", state="readonly", font=("Inter", 9))
btn_copy = tk.Button(root, text="Copiar enlace", bg="#10b981", fg="white", relief="flat", cursor="hand2",
                     font=("Inter", 9, "bold"), command=copy_link, activebackground="#059669", activeforeground="white")
lbl_hint = tk.Label(root, text="", fg="#94a3b8", bg="#0f172a", font=("Inter", 8))
lbl_hint.pack()

# Encender el servidor automáticamente al abrir el lanzador
root.after(300, toggle_server)

root.mainloop()
