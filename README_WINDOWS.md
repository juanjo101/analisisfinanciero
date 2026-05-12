# Instrucciones para Windows

Este proyecto permite generar un archivo ejecutable (.exe) para que la aplicación corra directamente en Windows sin necesidad de instalar Python manualmente.

## Requisitos previos
1. Tener **Python 3.x** instalado.
2. (Opcional) Tener privilegios de administrador para ejecutar scripts de PowerShell si el sistema los bloquea.

## Cómo generar el ejecutable (.exe)

1. Abre una terminal (PowerShell o CMD) en la carpeta del proyecto.
2. Ejecuta el script de construcción:
   ```powershell
   .\build_windows.ps1
   ```
3. Una vez finalizado, encontrarás el archivo `AnalisisFinanciero.exe` dentro de la carpeta **`dist/`**.

## Notas sobre el funcionamiento
- El ejecutable es "standalone" (contiene todo lo necesario).
- Al abrirlo, se iniciará un servidor local y se abrirá automáticamente tu navegador web predeterminado en `http://127.0.0.1:5000`.
- Si el navegador no se abre, puedes ingresar manualmente esa dirección.

## Resolución de problemas
- **Error de ejecución de scripts**: Si PowerShell indica que la ejecución de scripts está deshabilitada, usa:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  ```
  Y vuelve a intentar.
- **Antivirus**: Algunos antivirus pueden marcar archivos generados por PyInstaller como sospechosos. Si esto sucede, añade el archivo a las exclusiones de tu antivirus.
