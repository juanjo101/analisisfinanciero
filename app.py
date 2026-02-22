import os
from datetime import datetime
import io
import base64

from flask import Flask, jsonify, render_template, request, send_from_directory
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from core_engine import FinancialEngine


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL = os.path.join(BASE_DIR, "PlantillaBC_2Grupo No. 1.xlsx")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
engine = None


def _df_records(df, max_rows=500):
    if df is None:
        return []
    view = df.head(max_rows).copy()
    return view.replace({float("inf"): None, float("-inf"): None}).where(view.notna(), None).to_dict(orient="records")


def _scale_to_score(x, lo, hi, pos_good=True):
    if x is None:
        return None
    try:
        xf = float(x)
    except Exception:
        return None
    if xf != xf:
        return None
    x_clip = min(max(xf, lo), hi)
    u = (x_clip - lo) / (hi - lo + 1e-9)
    if not pos_good:
        u = 1 - u
    return (u * 2 - 1) * 100


def _classify(score):
    if score <= -15:
        return "Muy crítico"
    if score <= -5:
        return "Crítico"
    if score <= 5:
        return "Neutral"
    if score <= 15:
        return "Bueno"
    return "Excelente"


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _line_chart_base64(x_labels, y_values, title, y_label="Valor"):
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    ax.plot(x_labels, y_values, marker="o", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel("Año")
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.25)
    return _fig_to_base64(fig)


def _barh_chart_base64(labels, values, title, x_label="Valor"):
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    pos = np.arange(len(labels))
    ax.barh(pos, values)
    ax.set_yticks(pos)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.grid(axis="x", alpha=0.2)
    return _fig_to_base64(fig)


def _heatmap_base64(matrix, row_labels, col_labels, title):
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    m = np.array([[np.nan if v is None else float(v) for v in row] for row in matrix], dtype=float)
    im = ax.imshow(m, vmin=-1, vmax=1, cmap="RdBu")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8)
    ax.set_title(title)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            txt = "N/D" if np.isnan(m[i, j]) else f"{m[i, j]:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    return _fig_to_base64(fig)


@app.route("/")
def home():
    app_js = os.path.join(BASE_DIR, "static", "app.js")
    css = os.path.join(BASE_DIR, "static", "style.css")
    asset_v = int(max(os.path.getmtime(app_js), os.path.getmtime(css)))
    return render_template("index.html", asset_v=asset_v)


@app.route("/outputs/<path:filename>")
def outputs_file(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/api/upload", methods=["POST"])
def upload_excel():
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "No se recibió archivo"}), 400
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in [".xlsx", ".xls"]:
        return jsonify({"ok": False, "error": "Solo se permiten .xlsx o .xls"}), 400
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"upload_{stamp}{ext}"
    out_path = os.path.join(UPLOAD_DIR, safe_name)
    f.save(out_path)
    return jsonify({"ok": True, "excel_path": out_path})


@app.route("/api/discover", methods=["POST"])
def discover():
    payload = request.get_json(silent=True) or {}
    excel_path = payload.get("excel_path", DEFAULT_EXCEL)
    if not os.path.exists(excel_path):
        return jsonify({"ok": False, "error": f"No existe el archivo: {excel_path}"}), 400
    try:
        sheets = FinancialEngine.list_sheets(excel_path)
        bal, er = FinancialEngine.detect_core_sheets(excel_path)
        return jsonify({"ok": True, "excel_path": excel_path, "sheets": sheets, "suggested_balance": bal, "suggested_er": er})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/load", methods=["POST"])
def load_data():
    global engine
    payload = request.get_json(silent=True) or {}
    excel_path = payload.get("excel_path", DEFAULT_EXCEL)
    if not os.path.exists(excel_path):
        return jsonify({"ok": False, "error": f"No existe el archivo: {excel_path}"}), 400
    balance_sheet = payload.get("balance_sheet")
    er_sheet = payload.get("er_sheet")
    try:
        engine = FinancialEngine(excel_path, balance_sheet=balance_sheet, er_sheet=er_sheet)
        st = engine.state
        return jsonify(
            {
                "ok": True,
                "excel_path": excel_path,
                "balance_sheet": balance_sheet,
                "er_sheet": er_sheet,
                "bal_years": st.bal_years,
                "er_years": st.er_years,
                "ratios": list(st.ratios.columns),
                "kpis": [c for c in ["Ventas_YoY_%", "UtilNeta_YoY_%", "Margen Neto", "ROE", "ROA", "Rotación de Activos"] if c in st.panel.columns],
                "factors": [c for c in engine.FACTOR_CANDIDATES if c in st.panel.columns],
                "panel_years": [int(y) for y in st.panel.index.tolist()],
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _require_engine():
    if engine is None:
        return jsonify({"ok": False, "error": "Carga primero el Excel en /api/load"}), 400
    return None


@app.route("/api/ratios")
def get_ratios():
    err = _require_engine()
    if err:
        return err
    st = engine.state
    return jsonify({"ok": True, "table": _df_records(st.ratios.rename_axis("Año").reset_index())})


@app.route("/api/ratio/<name>")
def get_ratio_series(name):
    err = _require_engine()
    if err:
        return err
    st = engine.state
    if name not in st.ratios.columns:
        return jsonify({"ok": False, "error": "Ratio inválido"}), 400
    s = st.ratios[name]
    return jsonify({"ok": True, "labels": [str(x) for x in s.index.tolist()], "values": [None if x != x else float(x) for x in s.values.tolist()]})


@app.route("/api/vertical/<report>/<year>")
def get_vertical(report, year):
    err = _require_engine()
    if err:
        return err
    st = engine.state
    source = st.balance_vertical if report == "balance" else st.er_vertical if report == "er" else None
    if source is None:
        return jsonify({"ok": False, "error": "Reporte inválido"}), 400
    if year not in source:
        return jsonify({"ok": False, "error": "Año inválido"}), 400
    df = source[year]
    pct_col = f"%_{year}"
    top = df[["Cuenta", pct_col]].dropna()
    top = top[~top["Cuenta"].astype(str).str.contains("TOTAL", case=False, na=False)]
    top = top.sort_values(pct_col, ascending=False).head(10)
    return jsonify(
        {
            "ok": True,
            "labels": top["Cuenta"].astype(str).tolist(),
            "values": [float(x) for x in top[pct_col].tolist()],
            "table": _df_records(df),
        }
    )


@app.route("/api/horizontal/<report>")
def get_horizontal(report):
    err = _require_engine()
    if err:
        return err
    st = engine.state
    df = st.balance_horizontal if report == "balance" else st.er_horizontal if report == "er" else None
    if df is None:
        return jsonify({"ok": False, "error": "Reporte inválido"}), 400
    rows = _df_records(df)
    return jsonify({"ok": True, "rows": len(rows), "table": rows})


@app.route("/api/panel")
def get_panel():
    err = _require_engine()
    if err:
        return err
    return jsonify({"ok": True, "table": _df_records(engine.state.panel.rename_axis("Año").reset_index())})


@app.route("/api/external")
def get_external():
    err = _require_engine()
    if err:
        return err
    return jsonify({"ok": True, "table": _df_records(engine.state.external.rename_axis("Año").reset_index())})


@app.route("/api/heatmap")
def get_heatmap():
    err = _require_engine()
    if err:
        return err
    st = engine.state
    lag = int(request.args.get("lag", 0))
    kpis = [c for c in ["Ventas_YoY_%", "UtilNeta_YoY_%", "Margen Neto", "ROE", "ROA", "Rotación de Activos"] if c in st.panel.columns]
    factors = [c for c in engine.FACTOR_CANDIDATES if c in st.panel.columns]
    if not kpis or not factors:
        return jsonify({"ok": True, "matrix": [], "kpis": [], "factors": []})
    matrix = []
    n_obs = []
    for k in kpis:
        row = []
        row_n = []
        for f in factors:
            comp = st.panel[[k, f]].copy()
            if lag:
                comp[f] = comp[f].shift(lag)
            comp = comp.dropna()
            row_n.append(int(len(comp)))
            row.append(None if len(comp) < 2 else float(comp[k].corr(comp[f])))
        matrix.append(row)
        n_obs.append(row_n)
    return jsonify({"ok": True, "matrix": matrix, "n_obs": n_obs, "kpis": kpis, "factors": factors})


@app.route("/api/ols", methods=["POST"])
def ols():
    err = _require_engine()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    dep = payload.get("dep")
    indeps = payload.get("indeps", [])
    result = engine.run_ols(dep, indeps)
    if "error" in result:
        return jsonify({"ok": False, "error": result["error"]}), 400
    return jsonify({"ok": True, **result})


@app.route("/api/wdi", methods=["POST"])
def refresh_wdi():
    err = _require_engine()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    country = payload.get("country", "DOM")
    try:
        engine.update_wdi(country)
        return jsonify({"ok": True, "external": _df_records(engine.state.external.rename_axis("Año").reset_index()), "panel": _df_records(engine.state.panel.rename_axis("Año").reset_index())})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/external/upsert", methods=["POST"])
def upsert_external():
    err = _require_engine()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    year = int(payload.get("year"))
    st = engine.state
    if year not in st.external.index:
        st.external.loc[year] = [np.nan] * len(st.external.columns)
    for col in ["Inflación_%", "PIB_real_%", "USD/DOP", "TPM_%"]:
        if col in payload and payload[col] not in (None, ""):
            st.external.loc[year, col] = float(payload[col])
    years_all = sorted(set(st.panel.index.astype(int).tolist()))
    st.panel = engine._build_panel(years_all, st.er_wide, st.ratios, st.external.sort_index())
    return jsonify({"ok": True, "external": _df_records(st.external.rename_axis("Año").reset_index()), "panel": _df_records(st.panel.rename_axis("Año").reset_index())})


@app.route("/api/fx-impact", methods=["POST"])
def fx_impact():
    err = _require_engine()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    st = engine.state
    kpi = payload.get("kpi", "Ventas")
    years_ahead = int(payload.get("years_ahead", 3))
    shock_pct = float(payload.get("shock_pct", 10))

    if kpi not in st.panel.columns:
        return jsonify({"ok": False, "error": f"KPI inválido: {kpi}"}), 400
    if "USD/DOP" not in st.panel.columns:
        return jsonify({"ok": False, "error": "No hay columna USD/DOP en panel"}), 400

    panel = st.panel.copy().sort_index()
    fx_yoy = panel["USD/DOP"].pct_change(fill_method=None) * 100
    kpi_yoy = panel[kpi].astype(float).pct_change(fill_method=None) * 100
    comp = np.vstack([fx_yoy.values, kpi_yoy.values]).T
    comp = comp[~np.isnan(comp).any(axis=1)]
    if len(comp) >= 2:
        beta = float(np.polyfit(comp[:, 0], comp[:, 1], 1)[0])
    else:
        beta = -0.25 if kpi in ["Ventas", "Utilidad Neta"] else -0.10

    hist_growth = kpi_yoy.replace([np.inf, -np.inf], np.nan).dropna()
    base_growth = float(hist_growth.mean()) if not hist_growth.empty else 3.0
    last_year = int(panel.index.max())
    last_val = float(panel.loc[last_year, kpi])

    labels = [str(y) for y in panel.index.tolist()]
    baseline_hist = [None if x != x else float(x) for x in panel[kpi].tolist()]

    proj_years = [last_year + i for i in range(1, years_ahead + 1)]
    labels += [str(y) for y in proj_years]
    base_vals = []
    stress_vals = []
    opt_vals = []
    v_base = last_val
    v_stress = last_val
    v_opt = last_val

    stress_adj = beta * abs(shock_pct)
    opt_adj = -beta * abs(shock_pct)
    for _ in proj_years:
        v_base *= 1 + base_growth / 100.0
        v_stress *= 1 + (base_growth + stress_adj) / 100.0
        v_opt *= 1 + (base_growth + opt_adj) / 100.0
        base_vals.append(float(v_base))
        stress_vals.append(float(v_stress))
        opt_vals.append(float(v_opt))

    return jsonify(
        {
            "ok": True,
            "labels": labels,
            "historico": baseline_hist + [None] * len(proj_years),
            "base": [None] * len(panel.index) + base_vals,
            "estres": [None] * len(panel.index) + stress_vals,
            "optimista": [None] * len(panel.index) + opt_vals,
            "meta": {
                "elasticidad_fx": round(beta, 4),
                "crecimiento_base_pct": round(base_growth, 2),
                "shock_pct": shock_pct,
            },
        }
    )


@app.route("/api/report", methods=["POST"])
def generate_report():
    err = _require_engine()
    if err:
        return err
    st = engine.state
    report_name = f"reporte_financiero_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    report_path = os.path.join(OUTPUT_DIR, report_name)

    ratios_df = st.ratios.rename_axis("Año").reset_index()
    ratios = ratios_df.to_html(index=False)
    balance_h = st.balance_horizontal.head(80).to_html(index=False)
    er_h = st.er_horizontal.head(80).to_html(index=False)
    external_df = st.external.rename_axis("Año").reset_index()
    external = external_df.to_html(index=False)

    chart_imgs = []

    # Ratios: un gráfico por ratio
    for col in st.ratios.columns:
        s = st.ratios[col].dropna()
        if len(s) >= 1:
            img = _line_chart_base64([str(x) for x in s.index.tolist()], [float(v) for v in s.values.tolist()], f"Ratio: {col}", "Valor")
            chart_imgs.append((f"Ratio: {col}", img))

    # Vertical balance y ER (último año)
    if st.bal_years:
        y = st.bal_years[-1]
        df = st.balance_vertical[y]
        pct = f"%_{y}"
        top = df[["Cuenta", pct]].dropna()
        top = top[~top["Cuenta"].astype(str).str.contains("TOTAL", case=False, na=False)].sort_values(pct, ascending=False).head(12)
        if not top.empty:
            img = _barh_chart_base64(top["Cuenta"].astype(str).tolist(), [float(v) for v in top[pct].tolist()], f"Vertical Balance {y}", "%")
            chart_imgs.append((f"Vertical Balance {y}", img))

    if st.er_years:
        y = st.er_years[-1]
        df = st.er_vertical[y]
        pct = f"%_{y}"
        top = df[["Cuenta", pct]].dropna()
        top = top[~top["Cuenta"].astype(str).str.contains("TOTAL", case=False, na=False)].sort_values(pct, ascending=False).head(12)
        if not top.empty:
            img = _barh_chart_base64(top["Cuenta"].astype(str).tolist(), [float(v) for v in top[pct].tolist()], f"Vertical E.R. {y}", "%")
            chart_imgs.append((f"Vertical E.R. {y}", img))

    # Factores externos clave
    ext = external_df.copy().sort_values("Año")
    for col in ["USD/DOP", "Inflación_%", "PIB_real_%", "TPM_%"]:
        if col in ext.columns:
            ser = ext[["Año", col]].dropna()
            if len(ser) >= 1:
                img = _line_chart_base64([str(int(x)) for x in ser["Año"].tolist()], [float(v) for v in ser[col].tolist()], f"{col} - Histórico", col)
                chart_imgs.append((f"{col} - Histórico", img))

    # Heatmap correlación (lag 0)
    kpis = [c for c in ["Ventas_YoY_%", "UtilNeta_YoY_%", "Margen Neto", "ROE", "ROA", "Rotación de Activos"] if c in st.panel.columns]
    factors = [c for c in ["Inflación_%", "PIB_real_%", "USD/DOP", "TPM_%"] if c in st.panel.columns]
    if kpis and factors:
        matrix = []
        for k in kpis:
            row = []
            for f in factors:
                comp = st.panel[[k, f]].dropna()
                row.append(None if len(comp) < 2 else float(comp[k].corr(comp[f])))
            matrix.append(row)
        chart_imgs.append(("Heatmap correlaciones (lag=0)", _heatmap_base64(matrix, kpis, factors, "Correlaciones KPI vs Factores")))

    # Escenarios FX (KPI Ventas)
    fx_block = ""
    try:
        panel = st.panel.copy().sort_index()
        if "USD/DOP" in panel.columns and "Ventas" in panel.columns and len(panel) >= 2:
            fx_yoy = panel["USD/DOP"].pct_change(fill_method=None) * 100
            kpi_yoy = panel["Ventas"].astype(float).pct_change(fill_method=None) * 100
            comp = np.vstack([fx_yoy.values, kpi_yoy.values]).T
            comp = comp[~np.isnan(comp).any(axis=1)]
            beta = float(np.polyfit(comp[:, 0], comp[:, 1], 1)[0]) if len(comp) >= 2 else -0.25
            growth = kpi_yoy.replace([np.inf, -np.inf], np.nan).dropna()
            g = float(growth.mean()) if not growth.empty else 3.0
            last_year = int(panel.index.max())
            last_val = float(panel.loc[last_year, "Ventas"])
            years = [last_year + 1, last_year + 2, last_year + 3]
            base = []
            est = []
            opt = []
            vb, vs, vo = last_val, last_val, last_val
            shock = 10.0
            for _ in years:
                vb *= 1 + g / 100.0
                vs *= 1 + (g + beta * shock) / 100.0
                vo *= 1 + (g - beta * shock) / 100.0
                base.append(vb)
                est.append(vs)
                opt.append(vo)
            fig, ax = plt.subplots(figsize=(8.2, 3.8))
            hx = [str(int(y)) for y in panel.index.tolist()]
            ax.plot(hx, panel["Ventas"].tolist(), marker="o", label="Histórico")
            px = [str(y) for y in years]
            ax.plot(px, base, marker="o", linestyle="--", label="Base")
            ax.plot(px, est, marker="o", linestyle="--", label="Estrés")
            ax.plot(px, opt, marker="o", linestyle="--", label="Optimista")
            ax.set_title("Escenarios FX para Ventas (shock 10%)")
            ax.set_xlabel("Año")
            ax.set_ylabel("Ventas")
            ax.grid(True, alpha=0.25)
            ax.legend()
            fx_img = _fig_to_base64(fig)
            fx_block = f"<h2>Escenarios FX</h2><p>Elasticidad estimada Ventas vs USD/DOP: <b>{beta:.4f}</b></p><img src='data:image/png;base64,{fx_img}' />"
    except Exception:
        fx_block = ""

    charts_html = "".join([f"<section class='chart'><h3>{title}</h3><img src='data:image/png;base64,{img}' /></section>" for title, img in chart_imgs])

    html = f"""<!doctype html>
<html lang='es'>
<head>
  <meta charset='utf-8'>
  <title>Reporte Financiero</title>
  <style>
    @page {{ size: letter; margin: 0.5in; }}
    body {{ font-family: Arial, sans-serif; color:#111827; }}
    h1 {{ margin: 0 0 8px 0; }}
    h2 {{ margin: 14px 0 8px 0; page-break-after: avoid; }}
    h3 {{ margin: 8px 0; font-size: 14px; }}
    p {{ margin: 6px 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 10px; table-layout: fixed; }}
    th, td {{ border: 1px solid #d1d5db; padding: 4px; word-wrap: break-word; }}
    th {{ background: #eef2ff; }}
    .page-break {{ page-break-before: always; }}
    .chart {{ margin-bottom: 12px; page-break-inside: avoid; }}
    img {{ width: 100%; max-width: 7.8in; height: auto; border: 1px solid #e5e7eb; }}
    .small-note {{ color:#374151; font-size:11px; }}
  </style>
</head>
<body>
  <h1>Reporte Financiero Completo</h1>
  <p class='small-note'>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
  <p class='small-note'>Archivo: {os.path.basename(engine.excel_path)}</p>

  <h2>Ratios</h2>
  {ratios}

  <div class='page-break'></div>
  <h2>Gráficos</h2>
  {charts_html}
  {fx_block}

  <div class='page-break'></div>
  <h2>Análisis Horizontal Balance</h2>
  {balance_h}

  <h2>Análisis Horizontal E.R.</h2>
  {er_h}

  <h2>Factores Externos</h2>
  {external}
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return jsonify({"ok": True, "download_url": f"/outputs/{report_name}"})


@app.route("/api/pestel", methods=["POST"])
def pestel():
    err = _require_engine()
    if err:
        return err
    payload = request.get_json(silent=True) or {}
    st = engine.state

    year = int(payload.get("year"))
    weights = {
        "Económico": float(payload.get("econ_w", 25)),
        "Social": float(payload.get("soc_w", 10)),
        "Geográfico": float(payload.get("geo_w", 5)),
        "Político": float(payload.get("pol_w", 25)),
        "Tecnológico": float(payload.get("tec_w", 25)),
        "Cultural": float(payload.get("cul_w", 10)),
    }

    auto_econ = bool(payload.get("auto_econ", True))
    econ_manual = float(payload.get("econ_manual", 0))
    res_manual = {
        "Social": float(payload.get("soc_res", 0)),
        "Geográfico": float(payload.get("geo_res", 0)),
        "Político": float(payload.get("pol_res", 0)),
        "Tecnológico": float(payload.get("tec_res", 0)),
        "Cultural": float(payload.get("cul_res", 0)),
    }

    ext = st.external.copy()
    econ_auto = None
    if auto_econ and (year in ext.index):
        gdp = ext.at[year, "PIB_real_%"] if "PIB_real_%" in ext.columns else None
        inf = ext.at[year, "Inflación_%"] if "Inflación_%" in ext.columns else None
        tpm = ext.at[year, "TPM_%"] if "TPM_%" in ext.columns else None
        fx_score = None
        if "USD/DOP" in ext.columns and (year - 1) in ext.index:
            fx = ext.at[year, "USD/DOP"]
            fx_prev = ext.at[year - 1, "USD/DOP"]
            if fx_prev not in (0, None) and fx_prev == fx_prev and fx == fx:
                dep_yoy = (fx / fx_prev - 1) * 100
                fx_score = _scale_to_score(dep_yoy, lo=-5, hi=30, pos_good=False)
        scores = [
            _scale_to_score(gdp, lo=-5, hi=10, pos_good=True),
            _scale_to_score(inf, lo=0, hi=20, pos_good=False),
            _scale_to_score(tpm, lo=0, hi=20, pos_good=False),
            fx_score,
        ]
        scores = [s for s in scores if s is not None]
        econ_auto = float(sum(scores) / len(scores)) if scores else None

    econ_val = econ_auto if (auto_econ and econ_auto is not None) else econ_manual
    responses = {"Económico": float(econ_val), **res_manual}

    sum_w = sum(weights.values()) or 1.0
    rows = []
    total = 0.0
    for k in ["Económico", "Social", "Geográfico", "Político", "Tecnológico", "Cultural"]:
        wn = float(weights[k]) / sum_w
        resv = float(responses[k])
        aporte = wn * resv
        total += aporte
        rows.append(
            {
                "Categoría": k,
                "Peso % (input)": round(weights[k], 2),
                "Peso % (normalizado)": round(wn * 100, 2),
                "Resultado %": round(resv, 2),
                "Aporte ponderado %": round(aporte, 2),
            }
        )
    clas = _classify(total)
    return jsonify({"ok": True, "score": round(total, 2), "clasificacion": clas, "econ_auto": econ_auto, "table": rows})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7863, debug=True)
