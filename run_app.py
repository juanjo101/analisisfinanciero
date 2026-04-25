import os
import sys
import threading
import webbrowser
import time
from app import app

def open_browser():
    # Esperar un momento a que el servidor Flask inicie
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    # Iniciar el hilo del navegador
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar la app de Flask
    # El puerto 5000 es el predeterminado
    app.run(host="127.0.0.1", port=5000, debug=False)
