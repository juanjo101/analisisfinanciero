#!/bin/bash

# Asegurarse de estar en el directorio correcto
cd "/Users/juanjo/Downloads/finanzas"

# Ruta al ejecutable de PyInstaller (ajustada según la instalación previa)
PYINSTALLER="python3 -m PyInstaller"

echo "Iniciando compilación para Mac..."

$PYINSTALLER --noconfirm --windowed --name "AnalisisFinanciero" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --add-data "PlantillaBC_2Grupo No. 1.xlsx:." \
    --clean \
    run_app.py

echo "-------------------------------------------------------"
echo "Compilación finalizada."
echo "La aplicación se encuentra en: dist/AnalisisFinanciero.app"
echo "-------------------------------------------------------"
