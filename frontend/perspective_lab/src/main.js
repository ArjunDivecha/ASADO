import perspective from "@perspective-dev/client";
import perspectiveViewer from "@perspective-dev/viewer";
import "@perspective-dev/viewer-datagrid";
import "@perspective-dev/viewer/dist/css/pro.css";
import SERVER_WASM from "@perspective-dev/server/dist/wasm/perspective-server.wasm?url";
import CLIENT_WASM from "@perspective-dev/viewer/dist/wasm/perspective-viewer.wasm?url";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "";

const el = {
  datasetSelect: document.querySelector("#dataset-select"),
  rowLimit: document.querySelector("#row-limit"),
  loadButton: document.querySelector("#load-button"),
  reloadButton: document.querySelector("#reload-button"),
  datasetList: document.querySelector("#dataset-list"),
  datasetCount: document.querySelector("#dataset-count"),
  dbStatus: document.querySelector("#db-status"),
  metricStrip: document.querySelector("#metric-strip"),
  datasetTitle: document.querySelector("#dataset-title"),
  datasetDescription: document.querySelector("#dataset-description"),
  rowCount: document.querySelector("#row-count"),
  loadState: document.querySelector("#load-state"),
  sqlPreview: document.querySelector("#sql-preview"),
  columnList: document.querySelector("#column-list"),
  viewer: document.querySelector("#viewer"),
};

let worker;
let activeTable;
let datasets = [];
let activeDatasetId = "daily_country_returns";

const datasetPresets = {
  daily_country_returns: {
    columns: ["return_value"],
    group_by: ["country"],
    split_by: ["horizon"],
    sort: [["return_value", "desc"]],
  },
  daily_factor_returns: {
    columns: ["return_value"],
    group_by: ["source", "factor"],
    sort: [["return_value", "desc"]],
  },
  monthly_factor_payoff: {
    columns: ["payoff_sum_12m", "sharpe_like_12m", "hit_rate_12m"],
    group_by: ["source", "factor"],
    sort: [["sharpe_like_12m", "desc"]],
  },
  country_attribution_latest: {
    columns: ["contribution", "factor_return", "weight"],
    group_by: ["country", "source", "factor"],
    sort: [["abs_contribution", "desc"]],
  },
  prediction_market_latest: {
    columns: ["value", "n_markets", "total_liquidity_usd", "confidence_score"],
    group_by: ["signal_name", "country"],
    sort: [["value", "desc"]],
  },
  commodity_momentum_latest: {
    columns: ["value"],
    group_by: ["feature", "category", "display_name"],
    sort: [["value", "desc"]],
  },
  unified_panel_freshness: {
    columns: ["rows", "variables", "countries"],
    group_by: ["source"],
    sort: [["rows", "desc"]],
  },
  analog_signals_latest: {
    columns: ["score", "rank"],
    group_by: ["country"],
    sort: [["rank", "asc"]],
  },
  analog_backtest: {
    columns: [],
    sort: [["date", "desc"]],
  },
};

function setState(text, kind = "neutral") {
  el.loadState.textContent = text;
  el.loadState.dataset.kind = kind;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "n/a";
  const gb = bytes / 1024 / 1024 / 1024;
  return `${gb.toFixed(2)} GB`;
}

function formatInteger(value) {
  if (!Number.isFinite(Number(value))) return "n/a";
  return Number(value).toLocaleString();
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json();
}

function renderMetrics(summary) {
  const surfaces = summary.surfaces || [];
  const primary = [
    { label: "DuckDB", value: formatBytes(summary.db_size_bytes) },
    {
      label: "Daily returns",
      value: formatInteger(surfaces.find((x) => x.surface === "t2_factors_daily")?.row_count),
    },
    {
      label: "Factor returns",
      value: formatInteger(surfaces.find((x) => x.surface === "factor_returns_daily")?.row_count),
    },
    {
      label: "Latest daily cut",
      value: surfaces.find((x) => x.surface === "factor_returns_daily")?.latest_date || "n/a",
    },
  ];

  el.metricStrip.innerHTML = primary
    .map(
      (metric) => `
        <article class="metric-card">
          <span>${metric.label}</span>
          <strong>${metric.value}</strong>
        </article>
      `
    )
    .join("");
}

function renderDatasetControls() {
  const available = datasets.filter((dataset) => dataset.available);
  el.datasetCount.textContent = String(available.length);

  el.datasetSelect.innerHTML = available
    .map((dataset) => `<option value="${dataset.id}">${dataset.title}</option>`)
    .join("");
  el.datasetSelect.value = activeDatasetId;

  el.datasetList.innerHTML = datasets
    .map((dataset) => {
      const active = dataset.id === activeDatasetId ? "active" : "";
      const unavailable = dataset.available ? "" : "unavailable";
      const status = dataset.available ? "ready" : "missing";
      return `
        <button class="dataset-card ${active} ${unavailable}" data-id="${dataset.id}" type="button">
          <span>${dataset.title}</span>
          <small>${status}</small>
        </button>
      `;
    })
    .join("");

  for (const button of el.datasetList.querySelectorAll("button")) {
    button.addEventListener("click", () => {
      const dataset = datasets.find((item) => item.id === button.dataset.id);
      if (!dataset || !dataset.available) return;
      activeDatasetId = dataset.id;
      el.datasetSelect.value = activeDatasetId;
      el.rowLimit.value = dataset.default_limit;
      renderDatasetControls();
      loadDataset();
    });
  }
}

function updateDatasetHeader(dataset, payload) {
  el.datasetTitle.textContent = dataset.title;
  el.datasetDescription.textContent = dataset.description;
  el.rowCount.textContent = `${formatInteger(payload.row_count)} rows`;
  el.columnList.innerHTML = payload.columns
    .map((column) => `<span>${column}</span>`)
    .join("");
}

async function loadSql(datasetId) {
  try {
    const payload = await fetchJson(`/api/sql/${datasetId}`);
    el.sqlPreview.textContent = payload.sql;
  } catch (error) {
    el.sqlPreview.textContent = error.message;
  }
}

async function loadDataset() {
  const dataset = datasets.find((item) => item.id === activeDatasetId);
  if (!dataset) return;

  setState("Loading", "busy");
  el.loadButton.disabled = true;
  el.reloadButton.disabled = true;
  updateDatasetHeader(dataset, { row_count: 0, columns: dataset.columns || [] });
  await loadSql(dataset.id);

  try {
    const limit = Number(el.rowLimit.value || dataset.default_limit);
    const payload = await fetchJson(`/api/dataset/${dataset.id}?limit=${limit}`);
    const tableName = `${dataset.id}_${Date.now()}`;

    activeTable = await worker.table(payload.rows, { name: tableName });
    await el.viewer.load(worker);
    await el.viewer.restore({
      table: tableName,
      ...(datasetPresets[dataset.id] || {}),
    });

    updateDatasetHeader(dataset, payload);
    setState("Ready", "ok");
  } catch (error) {
    setState("Failed", "error");
    el.datasetDescription.textContent = error.message;
    console.error(error);
  } finally {
    el.loadButton.disabled = false;
    el.reloadButton.disabled = false;
  }
}

async function initPerspective() {
  setState("Starting engine", "busy");
  await Promise.all([
    perspective.init_server(fetch(SERVER_WASM)),
    perspectiveViewer.init_client(fetch(CLIENT_WASM)),
  ]);
  worker = await perspective.worker();
}

async function init() {
  await initPerspective();

  const [health, summary, datasetPayload] = await Promise.all([
    fetchJson("/api/health"),
    fetchJson("/api/summary"),
    fetchJson("/api/datasets"),
  ]);

  el.dbStatus.textContent = health.ok ? `DuckDB ${formatBytes(health.db_size_bytes)}` : "DuckDB unavailable";
  datasets = datasetPayload.datasets || [];

  if (!datasets.some((dataset) => dataset.id === activeDatasetId && dataset.available)) {
    activeDatasetId = datasets.find((dataset) => dataset.available)?.id || "";
  }

  const activeDataset = datasets.find((dataset) => dataset.id === activeDatasetId);
  if (activeDataset) {
    el.rowLimit.value = activeDataset.default_limit;
  }

  renderMetrics(summary);
  renderDatasetControls();
  if (activeDatasetId) {
    el.datasetSelect.value = activeDatasetId;
    await loadDataset();
  } else {
    setState("No datasets", "error");
  }
}

el.datasetSelect.addEventListener("change", () => {
  activeDatasetId = el.datasetSelect.value;
  const dataset = datasets.find((item) => item.id === activeDatasetId);
  if (dataset) {
    el.rowLimit.value = dataset.default_limit;
  }
  renderDatasetControls();
  loadDataset();
});

el.loadButton.addEventListener("click", loadDataset);
el.reloadButton.addEventListener("click", loadDataset);

init().catch((error) => {
  setState("Failed", "error");
  el.dbStatus.textContent = error.message;
  console.error(error);
});
