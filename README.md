# Dashboard Financiero

Sistema de analisis financiero con backend en Python y frontend web (sin Gradio):
- Flask (API + servidor web)
- HTML/CSS/JavaScript
- Graficos con Chart.js
- Motor financiero reutilizable en Python

## Requisitos

```bash
python3 -m pip install -r requirements.txt
```

## Ejecutar sistema web

```bash
cd /Users/juanjo/Downloads/finanzas
python3 app.py
```

Abrir en navegador:

`http://127.0.0.1:7863`

## Funcionalidades actuales

- Carga de Excel
- Ratios financieros (tabla + grafico)
- Analisis vertical (balance y E.R.)
- Analisis horizontal (API lista)
- Heatmap de correlaciones (vista tabla)
- Actualizacion de factores externos (WDI)
- Regresion OLS por API

## Archivos principales

- `app.py` (servidor Flask)
- `core_engine.py` (motor de calculo financiero)
- `templates/index.html` (UI)
- `static/style.css` y `static/app.js` (frontend)
