const excelPath = document.getElementById("excelPath");
const statusEl = document.getElementById("status");

const ratioSelect = document.getElementById("ratioSelect");
const yearBalSelect = document.getElementById("yearBalSelect");
const yearErSelect = document.getElementById("yearErSelect");

let ratioChart;
let balChart;
let erChart;

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
  const data = await apiPost("/api/load", { excel_path: excelPath.value.trim() });
  if (!data.ok) {
    setStatus(data.error || "Error cargando", true);
    return;
  }
  setStatus("Archivo cargado correctamente");

  ratioSelect.innerHTML = data.ratios.map((x) => `<option value="${x}">${x}</option>`).join("");
  yearBalSelect.innerHTML = data.bal_years.map((x) => `<option value="${x}">${x}</option>`).join("");
  yearErSelect.innerHTML = data.er_years.map((x) => `<option value="${x}">${x}</option>`).join("");

  await refreshRatiosTable();
  await refreshRatio();
  await refreshVertical("balance");
  await refreshVertical("er");
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
    return;
  }
  const rows = data.kpis.map((k, i) => {
    const cols = data.matrix[i].map((x) => `<td>${x === null ? "" : Number(x).toFixed(3)}</td>`).join("");
    return `<tr><th>${k}</th>${cols}</tr>`;
  });
  const head = `<tr><th>KPI \\ Factor</th>${data.factors.map((f) => `<th>${f}</th>`).join("")}</tr>`;
  document.getElementById("heatTable").innerHTML = `<table><thead>${head}</thead><tbody>${rows.join("")}</tbody></table>`;
}

window.addEventListener("DOMContentLoaded", () => {
  excelPath.value = "PlantillaBC_2Grupo No. 1.xlsx";

  ratioChart = { ctx: document.getElementById("ratioChart").getContext("2d"), chart: null };
  balChart = { ctx: document.getElementById("balChart").getContext("2d"), chart: null };
  erChart = { ctx: document.getElementById("erChart").getContext("2d"), chart: null };

  document.getElementById("loadBtn").addEventListener("click", loadAll);
  document.getElementById("ratioBtn").addEventListener("click", refreshRatio);
  document.getElementById("balBtn").addEventListener("click", () => refreshVertical("balance"));
  document.getElementById("erBtn").addEventListener("click", () => refreshVertical("er"));
  document.getElementById("heatBtn").addEventListener("click", refreshHeatmap);
});
