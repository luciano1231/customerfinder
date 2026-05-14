import tkinter as tk
from tkinter import messagebox
import subprocess
import webbrowser
import os
import sys

# Proceso global para mantener la referencia del servidor
server_process = None
pinggy_process = None

def toggle_server():
    global server_process
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
            
            log_file = open("server_log.txt", "w", encoding="utf-8")
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

def toggle_pinggy():
    global pinggy_process
    if pinggy_process is None:
        try:
            # Iniciar túnel a Pinggy
            cmd = ["ssh", "-p", "443", "-o", "StrictHostKeyChecking=no", "-R0:localhost:5000", "a.pinggy.io"]
            
            # Nota: Pinggy usa SSH interactivo, así que lo abrimos en una consola pequeña para que el usuario pueda ver el enlace.
            # Ocultarla completamente haría que el usuario no pueda ver el enlace "pinggy.link".
            pinggy_process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            btn_pinggy.config(text="Detener Enlace Celular", bg="#ef4444", activebackground="#dc2626")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo iniciar Pinggy:\n{str(e)}")
    else:
        try:
            pinggy_process.terminate()
            pinggy_process = None
            btn_pinggy.config(text="Activar Enlace Celular", bg="#8b5cf6", activebackground="#7c3aed")
        except Exception as e:
            pass

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
root.geometry("350x250")
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

root.mainloop()
