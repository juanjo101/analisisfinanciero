# Script para construir el ejecutable de Windows (.exe)
# Basado en la configuración de Mac

# 1. Asegurarse de estar en el directorio del script
Set-Location $PSScriptRoot

# 2. Asegurarse de que PyInstaller esté instalado
Write-Host "Verificando dependencias en $($PWD.Path)..." -ForegroundColor Cyan
pip install pyinstaller
pip install -r requirements.txt

# 2. Definir variables
$APP_NAME = "AnalisisFinanciero"
$ENTRY_POINT = "run_app.py"

Write-Host "Iniciando compilación para Windows..." -ForegroundColor Green

# 3. Ejecutar PyInstaller
# Nota: En Windows usamos ';' como separador en --add-data
# Usamos 'python -m PyInstaller' y '--collect-all' para evitar errores de DLL en Conda/Python 3.13
python -m PyInstaller --noconfirm --onefile --windowed --name $APP_NAME `
    --add-data "templates;templates" `
    --add-data "static;static" `
    --collect-all "setuptools" `
    --icon "app_icon.ico" `
    --clean `
    $ENTRY_POINT

Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Compilación finalizada." -ForegroundColor Green
Write-Host "El ejecutable se encuentra en: dist\$APP_NAME.exe" -ForegroundColor Yellow
Write-Host "-------------------------------------------------------" -ForegroundColor Cyan
