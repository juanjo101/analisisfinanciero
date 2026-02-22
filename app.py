import os

from flask import Flask, jsonify, render_template, request

from core_engine import FinancialEngine


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXCEL = os.path.join(BASE_DIR, "PlantillaBC_2Grupo No. 1.xlsx")

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


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/load", methods=["POST"])
def load_data():
    global engine
    payload = request.get_json(silent=True) or {}
    excel_path = payload.get("excel_path", DEFAULT_EXCEL)
    if not os.path.exists(excel_path):
        return jsonify({"ok": False, "error": f"No existe el archivo: {excel_path}"}), 400
    try:
        engine = FinancialEngine(excel_path)
        st = engine.state
        return jsonify(
            {
                "ok": True,
                "excel_path": excel_path,
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
    return jsonify({"ok": True, "table": _df_records(df)})


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
    for k in kpis:
        row = []
        for f in factors:
            comp = st.panel[[k, f]].copy()
            if lag:
                comp[f] = comp[f].shift(lag)
            comp = comp.dropna()
            row.append(None if comp.empty else float(comp[k].corr(comp[f])))
        matrix.append(row)
    return jsonify({"ok": True, "matrix": matrix, "kpis": kpis, "factors": factors})


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
