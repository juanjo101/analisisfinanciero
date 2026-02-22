const excelPath = document.getElementById("excelPath");
const statusEl = document.getElementById("status");

const ratioSelect = document.getElementById("ratioSelect");
const yearBalSelect = document.getElementById("yearBalSelect");
const yearErSelect = document.getElementById("yearErSelect");
const balanceSheetSelect = document.getElementById("balanceSheet");
const erSheetSelect = document.getElementById("erSheet");

let ratioChart;
let balChart;
let erChart;
let pestelChart;
let fxChart;

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? "#fecaca" : "#bbf7d0";
}

function tableFromRecords(records) {
  if (!records || records.length === 0) return "<p>Sin datos</p>";
  const cols = Object.keys(records[0]);
  const thead = `<tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr>`;
  const tbody = records
    .map((row) => `<tr>${cols.map((c) => `<td>${row[c] ?? ""}</td>`).join("")}</tr>`)
    .join("");
  return `<table><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
}

async function apiGet(path) {
  const r = await fetch(path);
  return r.json();
}

async function apiPost(path, payload) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return r.json();
}

function renderLineChart(target, labels, values, label) {
  if (target.chart) target.chart.destroy();
  target.chart = new Chart(target.ctx, {
    type: "line",
    data: { labels, datasets: [{ label, data: values, borderColor: "#1d4ed8", backgroundColor: "rgba(29,78,216,0.2)" }] },
    options: { responsive: true },
  });
}

function renderBarChart(target, labels, values, label) {
  if (target.chart) target.chart.destroy();
  target.chart = new Chart(target.ctx, {
    type: "bar",
    data: { labels, datasets: [{ label, data: values, backgroundColor: "rgba(14,116,144,0.7)" }] },
    options: { indexAxis: "y", responsive: true },
  });
}

async function loadAll() {
  const data = await apiPost("/api/load", {
    excel_path: excelPath.value.trim(),
    balance_sheet: balanceSheetSelect.value || null,
    er_sheet: erSheetSelect.value || null,
  });
  if (!data.ok) {
    setStatus(data.error || "Error cargando", true);
    return;
  }
  setStatus("Archivo cargado correctamente");

  ratioSelect.innerHTML = data.ratios.map((x) => `<option value="${x}">${x}</option>`).join("");
  yearBalSelect.innerHTML = data.bal_years.map((x) => `<option value="${x}">${x}</option>`).join("");
  yearErSelect.innerHTML = data.er_years.map((x) => `<option value="${x}">${x}</option>`).join("");
  document.getElementById("pestelYear").innerHTML = (data.panel_years || []).map((x) => `<option value="${x}">${x}</option>`).join("");
  const fxKpis = ["Ventas", "Utilidad Neta", ...(data.kpis || [])];
  document.getElementById("fxKpi").innerHTML = fxKpis.map((x) => `<option value="${x}">${x}</option>`).join("");

  await refreshRatiosTable();
  await refreshRatio();
  await refreshVertical("balance");
  await refreshVertical("er");
  await refreshHorizontal("balance");
  await refreshHorizontal("er");
  await refreshExternal();
}

async function refreshRatiosTable() {
  const data = await apiGet("/api/ratios");
  document.getElementById("ratiosTable").innerHTML = data.ok ? tableFromRecords(data.table) : `<p>${data.error}</p>`;
}

async function refreshRatio() {
  const name = ratioSelect.value;
  const data = await apiGet(`/api/ratio/${encodeURIComponent(name)}`);
  if (!data.ok) {
    setStatus(data.error || "Error en ratio", true);
    return;
  }
  renderLineChart(ratioChart, data.labels, data.values, name);
}

async function refreshVertical(report) {
  const year = report === "balance" ? yearBalSelect.value : yearErSelect.value;
  const data = await apiGet(`/api/vertical/${report}/${year}`);
  if (!data.ok) {
    setStatus(data.error || "Error en vertical", true);
    return;
  }
  if (report === "balance") {
    renderBarChart(balChart, data.labels, data.values, `Vertical Balance ${year}`);
  } else {
    renderBarChart(erChart, data.labels, data.values, `Vertical E.R. ${year}`);
  }
}

async function refreshHeatmap() {
  const lag = document.getElementById("lag").value || 0;
  const data = await apiGet(`/api/heatmap?lag=${lag}`);
  if (!data.ok) {
    setStatus(data.error || "Error heatmap", true);
    return;
  }
  if (!data.matrix || data.matrix.length === 0) {
    document.getElementById("heatTable").innerHTML = "<p>Sin datos</p>";
    document.getElementById("heatNote").textContent = "No hay datos suficientes para calcular correlaciones.";
    return;
  }
  const rows = data.kpis.map((k, i) => {
    const cols = data.matrix[i]
      .map((x, j) => {
        const n = data.n_obs && data.n_obs[i] ? data.n_obs[i][j] : null;
        return `<td>${x === null ? `N/D${n !== null ? ` (n=${n})` : ""}` : Number(x).toFixed(3)}</td>`;
      })
      .join("");
    return `<tr><th>${k}</th>${cols}</tr>`;
  });
  const head = `<tr><th>KPI \\ Factor</th>${data.factors.map((f) => `<th>${f}</th>`).join("")}</tr>`;
  document.getElementById("heatTable").innerHTML = `<table><thead>${head}</thead><tbody>${rows.join("")}</tbody></table>`;
  document.getElementById("heatNote").textContent = "Si aparecen N/D, faltan observaciones históricas (usa Lag=0 y carga factores externos).";
}

async function refreshHorizontal(report) {
  const data = await apiGet(`/api/horizontal/${report}`);
  const target = report === "balance" ? "horizontalBalanceTable" : "horizontalErTable";
  if (!data.ok) {
    document.getElementById(target).innerHTML = `<p>${data.error || "Error horizontal"}</p>`;
    return;
  }
  document.getElementById(target).innerHTML = (data.rows || 0) > 0 ? tableFromRecords(data.table) : "<p>Sin filas para mostrar.</p>";
}

async function refreshExternal() {
  const data = await apiGet("/api/external");
  document.getElementById("externalTable").innerHTML = data.ok ? tableFromRecords(data.table) : `<p>${data.error || "Error externos"}</p>`;
}

async function updateWdi() {
  const country = (document.getElementById("country").value || "DOM").toUpperCase();
  const data = await apiPost("/api/wdi", { country });
  if (!data.ok) {
    setStatus(data.error || "Error actualizando WDI", true);
    return;
  }
  setStatus(`WDI actualizado para ${country}`);
  document.getElementById("externalTable").innerHTML = tableFromRecords(data.external || []);
}

async function saveExternalManual() {
  const payload = {
    year: Number(document.getElementById("extYear").value),
    "USD/DOP": document.getElementById("extFx").value,
    "Inflación_%": document.getElementById("extInf").value,
    "PIB_real_%": document.getElementById("extGdp").value,
    "TPM_%": document.getElementById("extTpm").value,
  };
  if (!payload.year) {
    setStatus("Indica el año para guardar dato externo.", true);
    return;
  }
  const data = await apiPost("/api/external/upsert", payload);
  if (!data.ok) {
    setStatus(data.error || "Error guardando dato externo", true);
    return;
  }
  setStatus("Dato externo guardado.");
  document.getElementById("externalTable").innerHTML = tableFromRecords(data.external || []);
}

async function uploadExcel() {
  const fileInput = document.getElementById("excelFile");
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    setStatus("Selecciona un archivo Excel antes de subir.", true);
    return;
  }
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch("/api/upload", { method: "POST", body: form });
  const data = await resp.json();
  if (!data.ok) {
    setStatus(data.error || "Error subiendo archivo", true);
    return;
  }
  excelPath.value = data.excel_path;
  setStatus("Archivo subido correctamente");
}

async function discoverSheets() {
  const data = await apiPost("/api/discover", { excel_path: excelPath.value.trim() });
  if (!data.ok) {
    setStatus(data.error || "Error detectando hojas", true);
    return;
  }
  const opts = (data.sheets || []).map((s) => `<option value="${s}">${s}</option>`).join("");
  balanceSheetSelect.innerHTML = opts;
  erSheetSelect.innerHTML = opts;
  if (data.suggested_balance) balanceSheetSelect.value = data.suggested_balance;
  if (data.suggested_er) erSheetSelect.value = data.suggested_er;
  setStatus("Hojas detectadas automáticamente. Ajusta si hace falta.");
}

function renderPestelChart(labels, values) {
  if (pestelChart.chart) pestelChart.chart.destroy();
  pestelChart.chart = new Chart(pestelChart.ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Aporte ponderado %", data: values, backgroundColor: "rgba(21,128,61,0.7)" }],
    },
    options: { responsive: true },
  });
}

async function calcPestel() {
  const payload = {
    year: Number(document.getElementById("pestelYear").value),
    auto_econ: document.getElementById("autoEcon").checked,
    econ_w: Number(document.getElementById("econW").value),
    soc_w: Number(document.getElementById("socW").value),
    geo_w: Number(document.getElementById("geoW").value),
    pol_w: Number(document.getElementById("polW").value),
    tec_w: Number(document.getElementById("tecW").value),
    cul_w: Number(document.getElementById("culW").value),
    econ_manual: Number(document.getElementById("econManual").value),
    soc_res: Number(document.getElementById("socRes").value),
    geo_res: Number(document.getElementById("geoRes").value),
    pol_res: Number(document.getElementById("polRes").value),
    tec_res: Number(document.getElementById("tecRes").value),
    cul_res: Number(document.getElementById("culRes").value),
  };
  const data = await apiPost("/api/pestel", payload);
  if (!data.ok) {
    document.getElementById("pestelStatus").textContent = data.error || "Error PESTEL";
    return;
  }
  document.getElementById("pestelStatus").textContent = `Índice: ${data.score}% - ${data.clasificacion}${data.econ_auto !== null ? ` (Econ auto: ${Number(data.econ_auto).toFixed(2)})` : ""}`;
  document.getElementById("pestelTable").innerHTML = tableFromRecords(data.table || []);
  renderPestelChart(
    (data.table || []).map((r) => r["Categoría"]),
    (data.table || []).map((r) => r["Aporte ponderado %"])
  );
}

function renderFxChart(labels, historico, base, estres, optimista) {
  if (fxChart.chart) fxChart.chart.destroy();
  fxChart.chart = new Chart(fxChart.ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Histórico", data: historico, borderColor: "#1d4ed8", backgroundColor: "transparent" },
        { label: "Base", data: base, borderColor: "#0f766e", borderDash: [4, 4], backgroundColor: "transparent" },
        { label: "Estrés (depreciación)", data: estres, borderColor: "#dc2626", borderDash: [6, 4], backgroundColor: "transparent" },
        { label: "Optimista", data: optimista, borderColor: "#16a34a", borderDash: [6, 4], backgroundColor: "transparent" },
      ],
    },
    options: { responsive: true, spanGaps: true },
  });
}

async function runFxImpact() {
  const payload = {
    kpi: document.getElementById("fxKpi").value,
    shock_pct: Number(document.getElementById("fxShock").value || 10),
    years_ahead: Number(document.getElementById("fxYears").value || 3),
  };
  const data = await apiPost("/api/fx-impact", payload);
  if (!data.ok) {
    setStatus(data.error || "Error en escenarios FX", true);
    return;
  }
  renderFxChart(data.labels, data.historico, data.base, data.estres, data.optimista);
  const m = data.meta || {};
  document.getElementById("fxMeta").textContent = `Elasticidad estimada: ${m.elasticidad_fx} | Crecimiento base: ${m.crecimiento_base_pct}% | Shock: ${m.shock_pct}%`;
}

async function generateReport() {
  const data = await apiPost("/api/report", {});
  if (!data.ok) {
    setStatus(data.error || "Error generando reporte", true);
    return;
  }
  window.open(data.download_url, "_blank");
}

window.addEventListener("DOMContentLoaded", () => {
  excelPath.value = "PlantillaBC_2Grupo No. 1.xlsx";

  ratioChart = { ctx: document.getElementById("ratioChart").getContext("2d"), chart: null };
  balChart = { ctx: document.getElementById("balChart").getContext("2d"), chart: null };
  erChart = { ctx: document.getElementById("erChart").getContext("2d"), chart: null };
  pestelChart = { ctx: document.getElementById("pestelChart").getContext("2d"), chart: null };
  fxChart = { ctx: document.getElementById("fxChart").getContext("2d"), chart: null };

  document.getElementById("loadBtn").addEventListener("click", loadAll);
  document.getElementById("uploadBtn").addEventListener("click", uploadExcel);
  document.getElementById("discoverBtn").addEventListener("click", discoverSheets);
  document.getElementById("reportBtn").addEventListener("click", generateReport);
  document.getElementById("ratioBtn").addEventListener("click", refreshRatio);
  document.getElementById("balBtn").addEventListener("click", () => refreshVertical("balance"));
  document.getElementById("erBtn").addEventListener("click", () => refreshVertical("er"));
  document.getElementById("heatBtn").addEventListener("click", refreshHeatmap);
  document.getElementById("wdiBtn").addEventListener("click", updateWdi);
  document.getElementById("saveExternalBtn").addEventListener("click", saveExternalManual);
  document.getElementById("pestelBtn").addEventListener("click", calcPestel);
  document.getElementById("fxBtn").addEventListener("click", runFxImpact);
});
