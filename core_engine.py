import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm


def _to_number(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float, np.number)):
        return float(x)
    s = str(x).strip().replace("\xa0", " ").replace("%", "")
    s = s.replace(" ", "")
    if s.count(",") > 1 and "." in s:
        s = s.replace(",", "")
    elif s.count(".") > 1 and "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return np.nan


def parse_multi_year_sheet(path: str, sheet_name: str) -> Tuple[pd.DataFrame, List[str]]:
    df = pd.read_excel(path, sheet_name=sheet_name, header=None)
    hdr = None
    for r in range(min(60, df.shape[0])):
        if str(df.iat[r, 0]).strip().upper() == "CONCEPTOS":
            hdr = r
            break
    if hdr is None:
        raise ValueError(f"No se encontró 'CONCEPTOS' en la hoja {sheet_name}")

    date_row = hdr + 1

    def _get_year_from(cell):
        dt = pd.to_datetime(cell, errors="coerce")
        if pd.isna(dt):
            return None
        return int(dt.year)

    amount_cols, year_labels = [], []
    for c in range(1, df.shape[1]):
        top = df.iat[hdr, c]
        below = df.iat[date_row, c] if date_row < df.shape[0] else None
        y = _get_year_from(below) if (isinstance(top, str) and top.strip().upper() == "FECHA") else _get_year_from(top)
        if y is not None:
            amount_cols.append(c)
            year_labels.append(str(y))

    if not amount_cols:
        raise ValueError(f"No se detectaron columnas de año en {sheet_name}")

    start = hdr + 2
    sub = df.iloc[start:, [0] + amount_cols].copy()
    temp_cols = ["Cuenta"] + [f"Y{i}_{y}" for i, y in enumerate(year_labels)]
    sub.columns = temp_cols
    sub["Cuenta"] = sub["Cuenta"].astype(str).str.strip()
    for c in temp_cols[1:]:
        sub[c] = sub[c].apply(_to_number)

    uniq_years = sorted(set(year_labels))
    out = pd.DataFrame({"Cuenta": sub["Cuenta"]})
    for y in uniq_years:
        cols_y = [c for c in temp_cols[1:] if c.endswith(f"_{y}")]
        out[y] = sub[cols_y].sum(axis=1, skipna=True)
    out = out.dropna(how="all", subset=uniq_years).reset_index(drop=True)
    return out, uniq_years


def vertical_analysis_exact(df: pd.DataFrame, year: str, total_patterns: List[str], prefer_max: bool = True):
    out = df[["Cuenta", year]].copy()
    mask = False
    for pat in total_patterns:
        mask = mask | out["Cuenta"].str.contains(pat, case=False, regex=True, na=False)
    matches = out.loc[mask, year]
    if not matches.empty:
        total = matches.max(skipna=True) if prefer_max else matches.sum(skipna=True)
    else:
        total = out[year].sum(skipna=True)
    out[f"%_{year}"] = np.where(total == 0, np.nan, out[year] / total * 100.0)
    return out, total


def horizontal_analysis(df: pd.DataFrame, years_sorted: List[str]) -> pd.DataFrame:
    out = df[["Cuenta"] + years_sorted].copy()
    for i in range(1, len(years_sorted)):
        a, b = years_sorted[i - 1], years_sorted[i]
        out[f"Var% {a}->{b}"] = np.where(out[a].fillna(0) == 0, np.nan, (out[b] - out[a]) / out[a] * 100.0)
    return out


def pick_value(df: pd.DataFrame, patterns: List[str], year: str, prefer_max: bool = True):
    mask = pd.Series(False, index=df.index)
    for pat in patterns:
        looks_regex = bool(re.search(r"[.\^$\*\+\?{\[\]|()]", pat))
        if looks_regex:
            pat_nc = re.sub(r"\((?!\?)", "(?:", pat)
            m = df["Cuenta"].str.contains(pat_nc, case=False, regex=True, na=False)
        else:
            m = df["Cuenta"].str.contains(pat, case=False, regex=False, na=False)
        mask = mask | m
    vals = df.loc[mask, year]
    if vals.empty:
        return np.nan
    return vals.max(skipna=True) if prefer_max else vals.sum(skipna=True)


def sdiv(n, d):
    return np.nan if (d in [0, None] or pd.isna(d) or pd.isna(n)) else n / d


def fetch_wb_series(country_code: str, indicator_code: str, timeout_sec: int = 6):
    url = f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}?format=json&per_page=20000"
    try:
        r = requests.get(url, timeout=timeout_sec)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return pd.Series(dtype=float)
    if not isinstance(data, list) or len(data) < 2 or data[1] is None:
        return pd.Series(dtype=float)
    out = {}
    for row in data[1]:
        yr, val = row.get("date"), row.get("value")
        if yr and val is not None:
            out[int(yr)] = float(val)
    return pd.Series(out).sort_index()


@dataclass
class FinancialState:
    balance_wide: pd.DataFrame
    bal_years: List[str]
    er_wide: pd.DataFrame
    er_years: List[str]
    balance_vertical: Dict[str, pd.DataFrame]
    er_vertical: Dict[str, pd.DataFrame]
    balance_horizontal: pd.DataFrame
    er_horizontal: pd.DataFrame
    ratios: pd.DataFrame
    panel: pd.DataFrame
    external: pd.DataFrame


class FinancialEngine:
    FACTOR_CANDIDATES = ["Inflación_%", "PIB_real_%", "USD/DOP", "TPM_%"]

    def __init__(self, excel_path: str, balance_sheet: str = None, er_sheet: str = None):
        self.excel_path = excel_path
        self.balance_sheet = balance_sheet
        self.er_sheet = er_sheet
        self.state = self.load()

    @staticmethod
    def list_sheets(excel_path: str) -> List[str]:
        return pd.ExcelFile(excel_path).sheet_names

    @staticmethod
    def detect_core_sheets(excel_path: str):
        sheets = FinancialEngine.list_sheets(excel_path)
        if not sheets:
            return None, None

        def score_name(s):
            u = s.upper()
            bal = 0
            er = 0
            if "FINANCIERA" in u or "BALANCE" in u:
                bal += 3
            if "ECONOMICA" in u or "RESULTADOS" in u or "RESULTADO" in u:
                er += 3
            if "ESTRUCTURA" in u:
                bal += 1
                er += 1
            return bal, er

        scored = [(s, *score_name(s)) for s in sheets]
        bal_guess = max(scored, key=lambda x: x[1])[0]
        er_guess = max(scored, key=lambda x: x[2])[0]

        # Validate parseability; fallback to first parseable sheets.
        def parseable(sheet):
            try:
                parse_multi_year_sheet(excel_path, sheet)
                return True
            except Exception:
                return False

        if not parseable(bal_guess):
            for s in sheets:
                if parseable(s):
                    bal_guess = s
                    break
        if not parseable(er_guess):
            for s in sheets:
                if s != bal_guess and parseable(s):
                    er_guess = s
                    break
        return bal_guess, er_guess

    def load(self) -> FinancialState:
        bal_sheet = self.balance_sheet
        er_sheet = self.er_sheet
        if not bal_sheet or not er_sheet:
            auto_bal, auto_er = self.detect_core_sheets(self.excel_path)
            bal_sheet = bal_sheet or auto_bal
            er_sheet = er_sheet or auto_er
        if not bal_sheet or not er_sheet:
            raise ValueError("No se pudieron identificar hojas base para Balance y Estado de Resultados.")

        balance_wide, bal_years = parse_multi_year_sheet(self.excel_path, bal_sheet)
        er_wide, er_years = parse_multi_year_sheet(self.excel_path, er_sheet)
        balance_vertical = {y: vertical_analysis_exact(balance_wide, y, [r"^TOTAL\s+ACTIVOS?$"])[0] for y in bal_years}
        er_vertical = {
            y: vertical_analysis_exact(
                er_wide, y, [r"^\s*\.?\s*=\s*INGRESOS\s+TOTALES\s*$", r"^\s*VENTAS\s*$", r"^\s*INGRESOS\s+NETOS\s*$"]
            )[0]
            for y in er_years
        }
        balance_horizontal = horizontal_analysis(balance_wide, bal_years)
        er_horizontal = horizontal_analysis(er_wide, er_years)
        ratios = self._build_ratios(balance_wide, er_wide, bal_years, er_years)
        years_all = sorted({*map(int, bal_years), *map(int, er_years)})
        external = pd.DataFrame({"Año": range(min(years_all) - 1, max(years_all) + 1)}).set_index("Año")
        for c in self.FACTOR_CANDIDATES:
            external[c] = np.nan
        panel = self._build_panel(years_all, er_wide, ratios, external)
        return FinancialState(
            balance_wide, bal_years, er_wide, er_years, balance_vertical, er_vertical, balance_horizontal, er_horizontal, ratios, panel, external
        )

    def _build_ratios(self, balance_wide: pd.DataFrame, er_wide: pd.DataFrame, bal_years: List[str], er_years: List[str]) -> pd.DataFrame:
        years_common = sorted(set(bal_years).intersection(set(er_years)))
        ratios = pd.DataFrame(index=years_common)
        for y in years_common:
            at = pick_value(balance_wide, [r"^TOTAL\s+ACTIVOS?$"], y)
            pt = pick_value(balance_wide, [r"^TOTAL\s+PASIVOS?$"], y)
            pat = pick_value(balance_wide, [r"RECURSOS\s+PROPIOS", r"^PATRIMONIO$", r"CAPITAL\s+CONTABLE", r"FONDOS\s+PROPIOS"], y)
            ac = pick_value(balance_wide, [r"^ACTIVO\s+(CIRCULANTE|CORRIENTE)$"], y)
            pc = pick_value(balance_wide, [r"^PASIVO\s+(CIRCULANTE|CORRIENTE)$"], y)
            inv = pick_value(balance_wide, [r"INVENTARIOS?$", r"^EXISTENCIAS$"], y, prefer_max=False)
            vn = pick_value(er_wide, [r"^\s*\.?\s*=\s*INGRESOS\s+TOTALES\s*$", r"^\s*VENTAS\s*$", r"^\s*INGRESOS\s+NETOS\s*$"], y)
            un = pick_value(er_wide, [r"UTILIDAD\s+NETA$", r"BENEFICIO\s+NETO$", r"GANANCIA\s+NETA$"], y)

            ratios.loc[y, "Liquidez Corriente"] = sdiv(ac, pc)
            ratios.loc[y, "Prueba Ácida"] = sdiv((ac - (0 if pd.isna(inv) else inv)), pc)
            ratios.loc[y, "Endeudamiento (Pasivo/Activo)"] = sdiv(pt, at)
            ratios.loc[y, "Apalancamiento (Activo/Patrimonio)"] = sdiv(at, pat)
            ratios.loc[y, "Margen Neto"] = sdiv(un, vn)
            ratios.loc[y, "ROA"] = sdiv(un, at)
            ratios.loc[y, "ROE"] = sdiv(un, pat)
            ratios.loc[y, "Rotación de Activos"] = sdiv(vn, at)
        return ratios

    def _pick_value_flex(self, df: pd.DataFrame, patterns: List[str], year: int, prefer_max: bool = True):
        ys = str(year)
        col = next((c for c in df.columns if str(c).strip() == ys), None)
        if col is None:
            return np.nan
        mask = False
        for pat in patterns:
            mask = mask | df["Cuenta"].astype(str).str.contains(pat, case=False, regex=True, na=False)
        vals = df.loc[mask, col]
        if vals.empty:
            return np.nan
        return vals.max(skipna=True) if prefer_max else vals.sum(skipna=True)

    def _build_panel(self, years_all: List[int], er_wide: pd.DataFrame, ratios: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
        ventas = pd.Series(
            {y: self._pick_value_flex(er_wide, [r"^\s*\.?\s*=\s*INGRESOS\s+TOTALES\s*$", r"^\s*VENTAS\s*$", r"^\s*INGRESOS\s+NETOS\s*$"], y) for y in years_all},
            name="Ventas",
        )
        util_neta = pd.Series(
            {y: self._pick_value_flex(er_wide, [r"UTILIDAD\s+NETA$", r"BENEFICIO\s+NETO$", r"GANANCIA\s+NETA$"], y) for y in years_all},
            name="Utilidad Neta",
        )
        panel = pd.DataFrame({"Ventas": ventas, "Utilidad Neta": util_neta})
        rcopy = ratios.copy()
        try:
            rcopy.index = rcopy.index.astype(int)
        except Exception:
            pass
        panel = panel.join(rcopy, how="left")
        panel = panel.join(external, how="left").sort_index()
        panel["Ventas_YoY_%"] = panel["Ventas"].astype(float).pct_change(periods=1, fill_method=None) * 100
        panel["UtilNeta_YoY_%"] = panel["Utilidad Neta"].astype(float).pct_change(periods=1, fill_method=None) * 100
        for col in self.FACTOR_CANDIDATES:
            if col in panel.columns:
                panel[f"{col}_lag1"] = panel[col].shift(1)
        return panel

    def update_wdi(self, country_code: str = "DOM"):
        st = self.state
        years_all = sorted(set(st.panel.index.astype(int).tolist()))
        ext = pd.DataFrame({"Año": range(min(years_all) - 1, max(years_all) + 1)})
        ext["Inflación_%"] = ext["Año"].map(fetch_wb_series(country_code, "FP.CPI.TOTL.ZG").to_dict())
        ext["PIB_real_%"] = ext["Año"].map(fetch_wb_series(country_code, "NY.GDP.MKTP.KD.ZG").to_dict())
        ext["USD/DOP"] = ext["Año"].map(fetch_wb_series(country_code, "PA.NUS.FCRF").to_dict())
        ext["TPM_%"] = np.nan
        st.external = ext.set_index("Año").sort_index()
        st.panel = self._build_panel(years_all, st.er_wide, st.ratios, st.external)

    def run_ols(self, dep: str, indeps: List[str]):
        st = self.state
        if dep not in st.panel.columns or not indeps:
            return {"error": "Selecciona dependiente y factores."}
        df = st.panel[[dep] + indeps].dropna().copy()
        if df.empty or df.shape[0] < len(indeps) + 2:
            return {"error": "No hay suficientes observaciones."}
        y = df[dep].astype(float)
        x = sm.add_constant(df[indeps].astype(float), has_constant="add")
        model = sm.OLS(y, x).fit()
        out = pd.DataFrame(
            {
                "Variable": ["Constante"] + indeps,
                "Coef": model.params.values.round(4),
                "StdErr": model.bse.values.round(4),
                "t": model.tvalues.values.round(3),
                "p>|t|": model.pvalues.values.round(4),
            }
        )
        return {"table": out.to_dict(orient="records"), "meta": f"R²={model.rsquared:.3f} | R² ajustado={model.rsquared_adj:.3f} | N={int(model.nobs)}"}
