const apiBaseInput = document.getElementById("apiBase");
const healthDot = document.getElementById("healthDot");

function getApiBase() {
  return (localStorage.getItem("apiBase") || apiBaseInput.value).replace(/\/$/, "");
}

apiBaseInput.value = localStorage.getItem("apiBase") || apiBaseInput.value;

document.getElementById("saveApiBase").addEventListener("click", () => {
  localStorage.setItem("apiBase", apiBaseInput.value.trim());
  checkHealth();
});

async function checkHealth() {
  try {
    const res = await fetch(`${getApiBase()}/health`);
    healthDot.className = res.ok ? "dot ok" : "dot bad";
  } catch {
    healthDot.className = "dot bad";
  }
}

function genIdempotencyKey() {
  return `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function show(el, data, isError = false) {
  el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  el.style.borderColor = isError ? "var(--bad)" : "var(--border)";
}

document.getElementById("txForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultEl = document.getElementById("txResult");
  const user_id = document.getElementById("txUserId").value.trim();
  const amount = parseFloat(document.getElementById("txAmount").value);
  const keyInput = document.getElementById("txKey").value.trim();
  const idempotency_key = keyInput || genIdempotencyKey();

  try {
    const res = await fetch(`${getApiBase()}/transaction`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id, amount, idempotency_key }),
    });
    const data = await res.json();
    show(resultEl, { status: res.status, ...data }, !res.ok);
    if (res.ok) loadRanking();
  } catch (err) {
    show(resultEl, `Request failed: ${err.message}`, true);
  }
});

document.getElementById("summaryForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const resultEl = document.getElementById("summaryResult");
  const userId = document.getElementById("summaryUserId").value.trim();
  try {
    const res = await fetch(`${getApiBase()}/summary/${encodeURIComponent(userId)}`);
    const data = await res.json();
    show(resultEl, { status: res.status, ...data }, !res.ok);
  } catch (err) {
    show(resultEl, `Request failed: ${err.message}`, true);
  }
});

async function loadRanking() {
  const tbody = document.querySelector("#rankingTable tbody");
  try {
    const res = await fetch(`${getApiBase()}/ranking`);
    const data = await res.json();
    tbody.innerHTML = "";
    if (!Array.isArray(data) || data.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">No data yet</td></tr>`;
      return;
    }
    for (const row of data) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row.rank}</td><td>${row.user_id}</td><td>${row.total_points}</td><td>${row.active_days}</td><td>${row.ranking_points}</td>`;
      tbody.appendChild(tr);
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5">Failed to load: ${err.message}</td></tr>`;
  }
}

document.getElementById("refreshRanking").addEventListener("click", loadRanking);

checkHealth();
loadRanking();
setInterval(checkHealth, 15000);
