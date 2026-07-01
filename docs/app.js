const DATA_URL = "data/monthly_analysis.json";

const fmtMoney = (v) => (v == null ? "—" : "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 }));
const fmtPct = (v) => (v == null ? "—" : v.toFixed(1) + "%");
const fmtNum = (v) => (v == null ? "—" : Number(v).toLocaleString("en-US"));
const monthLabel = (m) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
};

let gapChart = null;

async function main() {
  const res = await fetch(DATA_URL, { cache: "no-store" });
  const report = await res.json();

  document.getElementById("definitions").textContent =
    `SQL definition: ${report.sql_definition}  ·  UGC definition: ${report.ugc_definition}`;
  document.getElementById("generated-at").textContent =
    `Data last refreshed: ${new Date(report.generated_at).toLocaleString("en-US")}`;

  const months = report.months.map((m) => m.month);
  const select = document.getElementById("month-select");
  select.innerHTML = months.map((m) => `<option value="${m}">${monthLabel(m)}</option>`).join("");
  select.value = months[months.length - 1];

  renderGapChart(report.months);
  renderMonth(report.months.find((m) => m.month === select.value));

  select.addEventListener("change", () => {
    renderMonth(report.months.find((m) => m.month === select.value));
  });
}

function renderMonth(m) {
  if (!m) return;

  const cards = [
    { value: fmtNum(m.total_sql), label: "Total SQLs" },
    { value: fmtNum(m.ugc_sql), label: "UGC SQLs" },
    { value: fmtPct(m.pct_sql_from_ugc), label: "% of SQLs from UGC" },
    { value: fmtMoney(m.total_spend), label: "Total Spend", neutral: true },
    { value: fmtPct(m.pct_spend_ugc), label: "% of Spend on UGC" },
    {
      value: (m.spend_sql_gap_pct == null ? "—" : (m.spend_sql_gap_pct > 0 ? "+" : "") + m.spend_sql_gap_pct.toFixed(1) + "pp"),
      label: "SQL-share minus Spend-share",
    },
  ];
  document.getElementById("overview-cards").innerHTML = cards
    .map((c) => `<div class="card"><div class="value ${c.neutral ? "neutral" : ""}">${c.value}</div><div class="label">${c.label}</div></div>`)
    .join("");

  document.getElementById("creatives-sub").textContent = `${monthLabel(m.month)} — ${m.creatives.length} UGC creative(s) with at least one SQL`;
  const creativesBody = document.querySelector("#creatives-table tbody");
  creativesBody.innerHTML = m.creatives.length
    ? m.creatives.map((c) => `<tr><td>${c.ad_name}</td><td class="num">${fmtNum(c.sql)}</td></tr>`).join("")
    : `<tr><td colspan="2" class="empty-state">No UGC creatives produced an SQL this month.</td></tr>`;

  const spendBody = document.querySelector("#spend-table tbody");
  spendBody.innerHTML = `
    <tr><td>Total spend</td><td class="num">${fmtMoney(m.total_spend)}</td><td class="num">100%</td></tr>
    <tr><td class="highlight">UGC spend</td><td class="num highlight">${fmtMoney(m.ugc_spend)}</td><td class="num highlight">${fmtPct(m.pct_spend_ugc)}</td></tr>
    <tr><td>Non-UGC spend</td><td class="num">${fmtMoney(m.non_ugc_spend)}</td><td class="num">${fmtPct(100 - (m.pct_spend_ugc ?? 0))}</td></tr>
  `;

  const cpsqlBody = document.querySelector("#cpsql-table tbody");
  cpsqlBody.innerHTML = `
    <tr><td class="highlight">UGC</td><td class="num">${fmtNum(m.ugc_sql)}</td><td class="num">${fmtMoney(m.ugc_spend)}</td><td class="num highlight">${fmtMoney(m.cost_per_sql_ugc)}</td></tr>
    <tr><td>Non-UGC</td><td class="num">${fmtNum(m.non_ugc_sql)}</td><td class="num">${fmtMoney(m.non_ugc_spend)}</td><td class="num">${fmtMoney(m.cost_per_sql_non_ugc)}</td></tr>
    <tr><td>Blended</td><td class="num">${fmtNum(m.total_sql)}</td><td class="num">${fmtMoney(m.total_spend)}</td><td class="num">${fmtMoney(m.cost_per_sql_blended)}</td></tr>
  `;
}

function renderGapChart(months) {
  const ctx = document.getElementById("gap-chart");
  const labels = months.map((m) => monthLabel(m.month));
  const gap = months.map((m) => m.spend_sql_gap_pct);
  const spendShare = months.map((m) => m.pct_spend_ugc);
  const sqlShare = months.map((m) => m.pct_sql_from_ugc);

  if (gapChart) gapChart.destroy();
  gapChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "% of Spend on UGC",
          data: spendShare,
          borderColor: "#8a9cae",
          backgroundColor: "#8a9cae",
          tension: 0.25,
          pointRadius: 3,
        },
        {
          type: "line",
          label: "% of SQLs from UGC",
          data: sqlShare,
          borderColor: "#ff6432",
          backgroundColor: "#ff6432",
          tension: 0.25,
          pointRadius: 3,
        },
        {
          type: "bar",
          label: "Gap (SQL-share − Spend-share, pp)",
          data: gap,
          backgroundColor: gap.map((v) => (v >= 0 ? "rgba(74,222,128,0.35)" : "rgba(248,113,113,0.35)")),
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#fef2de" } },
      },
      scales: {
        x: { ticks: { color: "#8a9cae" }, grid: { color: "#1e3a52" } },
        y: { ticks: { color: "#8a9cae" }, grid: { color: "#1e3a52" } },
      },
    },
  });
}

main().catch((err) => {
  console.error(err);
  document.getElementById("overview-cards").innerHTML =
    `<div class="empty-state">Could not load data/monthly_analysis.json — ${err.message}</div>`;
});
