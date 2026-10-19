/**
 * Admin Web Dashboard Logic
 * Displays KPIs, language breakdowns, urgency distribution, anonymous logs, and CSV export.
 */

let currentAdminKey = "dev-hackathon-admin-key-2026";

function getAuthHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Admin-API-Key": currentAdminKey,
  };
}

async function loadAnalytics() {
  const syntheticFilter = document.getElementById("filter-synthetic")?.value || "all";
  const startDate = document.getElementById("filter-start-date")?.value || "";
  const endDate = document.getElementById("filter-end-date")?.value || "";

  let url = `/api/v1/admin/analytics?`;
  if (syntheticFilter === "synthetic_only") {
    url += "only_synthetic=true&";
  } else if (syntheticFilter === "live_only") {
    url += "include_synthetic=false&";
  } else {
    url += "include_synthetic=true&";
  }

  if (startDate) url += `start_date=${encodeURIComponent(startDate)}&`;
  if (endDate) url += `end_date=${encodeURIComponent(endDate)}&`;

  try {
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error("Failed to load analytics: " + res.statusText);
    const data = await res.json();
    renderKPIs(data);
    renderCharts(data);
  } catch (err) {
    console.error("Analytics fetch error:", err);
  }
}

function renderKPIs(data) {
  document.getElementById("kpi-total").textContent = data.total_interactions;
  document.getElementById("kpi-referrals").textContent = `${data.referrals.percentage}%`;
  document.getElementById("kpi-referrals-sub").textContent = `${data.referrals.recommended_count} referrals recommended`;

  document.getElementById("kpi-completion").textContent = `${data.completion.completion_rate_percentage}%`;
  document.getElementById("kpi-completion-sub").textContent = `${data.completion.completed_count} completed / ${data.completion.incomplete_count} dropped`;

  const emergCount = data.urgency_distribution.emergency || 0;
  document.getElementById("kpi-emergency").textContent = emergCount;

  document.getElementById("synthetic-count-badge").textContent = `${data.synthetic_records_count} demo / ${data.live_records_count} live`;
}

function renderCharts(data) {
  const total = Math.max(data.total_interactions, 1);

  // 1. Languages Chart
  const langContainer = document.getElementById("chart-languages");
  if (langContainer) {
    langContainer.innerHTML = "";
    const langs = [
      { key: "hi", name: "Hindi (हिंदी)", class: "bar-hi" },
      { key: "mr", name: "Marathi (मराठी)", class: "bar-mr" },
      { key: "en", name: "English", class: "bar-en" },
      { key: "unselected", name: "Unselected", class: "bar-general" },
    ];

    langs.forEach((l) => {
      const count = data.languages[l.key] || 0;
      if (count > 0 || l.key !== "unselected") {
        const pct = Math.round((count / total) * 100);
        langContainer.innerHTML += `
          <div class="bar-item">
            <div class="bar-label-group">
              <span>${l.name}</span>
              <span><strong>${count}</strong> (${pct}%)</span>
            </div>
            <div class="bar-track">
              <div class="bar-fill ${l.class}" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      }
    });
  }

  // 2. Urgency Breakdown
  const urgencyContainer = document.getElementById("chart-urgency");
  if (urgencyContainer) {
    urgencyContainer.innerHTML = "";
    const urgencies = [
      { key: "emergency", name: "Emergency (Red)", class: "bar-emerg" },
      { key: "prompt_assessment", name: "Prompt Medical Assessment (Amber)", class: "bar-prompt" },
      { key: "general_guidance", name: "General Guidance (Green)", class: "bar-general" },
    ];

    urgencies.forEach((u) => {
      const count = data.urgency_distribution[u.key] || 0;
      const pct = Math.round((count / total) * 100);
      urgencyContainer.innerHTML += `
        <div class="bar-item">
          <div class="bar-label-group">
            <span>${u.name}</span>
            <span><strong>${count}</strong> (${pct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill ${u.class}" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    });
  }

  // 3. Top Symptom Categories
  const symptomsContainer = document.getElementById("chart-symptoms");
  if (symptomsContainer) {
    symptomsContainer.innerHTML = "";
    const symptoms = Object.entries(data.symptom_categories || {});
    if (symptoms.length === 0) {
      symptomsContainer.innerHTML = `<p style="color:var(--text-muted);font-size:0.85rem;">No symptoms recorded yet.</p>`;
    } else {
      symptoms.slice(0, 5).forEach(([cat, count]) => {
        const pct = Math.round((count / total) * 100);
        const formattedCat = cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        symptomsContainer.innerHTML += `
          <div class="bar-item">
            <div class="bar-label-group">
              <span>${formattedCat}</span>
              <span><strong>${count}</strong></span>
            </div>
            <div class="bar-track">
              <div class="bar-fill bar-prompt" style="width: ${pct}%"></div>
            </div>
          </div>
        `;
      });
    }
  }
}

async function loadReports() {
  const syntheticFilter = document.getElementById("filter-synthetic")?.value || "all";
  let url = `/api/v1/admin/reports?limit=25&`;

  if (syntheticFilter === "synthetic_only") {
    url += "only_synthetic=true&";
  } else if (syntheticFilter === "live_only") {
    url += "include_synthetic=false&";
  } else {
    url += "include_synthetic=true&";
  }

  try {
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error("Failed to load reports");
    const data = await res.json();

    const tbody = document.getElementById("reports-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No records found. Click "Seed Demo Data" to load sample interactions.</td></tr>`;
      return;
    }

    data.items.forEach((item) => {
      const urgencyClass = {
        emergency: "badge-emergency",
        prompt_assessment: "badge-prompt",
        general_guidance: "badge-general",
      }[item.urgency_category] || "badge-general";

      const urgencyLabel = {
        emergency: "Emergency",
        prompt_assessment: "Prompt Assessment",
        general_guidance: "General Guidance",
      }[item.urgency_category] || item.urgency_category;

      const dateStr = item.created_at ? new Date(item.created_at).toLocaleString() : "N/A";
      const sessionShort = item.session_id.substring(0, 8);
      const synthBadge = item.is_synthetic
        ? `<span class="badge badge-synthetic">Synthetic Demo</span>`
        : `<span class="badge badge-live">Live Call</span>`;

      tbody.innerHTML += `
        <tr>
          <td><code>${sessionShort}…</code></td>
          <td>${synthBadge}</td>
          <td><strong>${(item.selected_language || "N/A").toUpperCase()}</strong></td>
          <td>${item.symptom_category ? item.symptom_category.replace(/_/g, " ") : "unspecified"}</td>
          <td><span class="badge ${urgencyClass}">${urgencyLabel}</span></td>
          <td>${item.referral_recommended ? '<span style="color:var(--accent-red);font-weight:600;">Yes</span>' : '<span style="color:var(--accent-green);">No</span>'}</td>
          <td style="color:var(--text-muted);font-size:0.8rem;">${dateStr}</td>
        </tr>
      `;
    });
  } catch (err) {
    console.error("Reports error:", err);
  }
}

async function exportCSV() {
  const syntheticFilter = document.getElementById("filter-synthetic")?.value || "all";
  let url = `/api/v1/admin/reports/export?`;
  if (syntheticFilter === "synthetic_only") {
    url += "only_synthetic=true&";
  } else if (syntheticFilter === "live_only") {
    url += "include_synthetic=false&";
  } else {
    url += "include_synthetic=true&";
  }

  try {
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `helpline_anonymous_report_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    alert("Export failed: " + err.message);
  }
}

async function seedDemoData() {
  const btn = document.getElementById("btn-seed-demo");
  if (btn) btn.textContent = "Seeding demo records...";
  try {
    const res = await fetch("/api/v1/admin/seed-demo?count=50", {
      method: "POST",
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error("Seeding failed");
    await res.json();
    await loadAnalytics();
    await loadReports();
    if (btn) btn.textContent = "Seed Demo Data (50)";
  } catch (err) {
    alert("Seeding failed: " + err.message);
    if (btn) btn.textContent = "Seed Demo Data (50)";
  }
}

// Global hook for phone simulator
window.loadAnalytics = loadAnalytics;

window.addEventListener("DOMContentLoaded", () => {
  // Bind filters & buttons
  document.getElementById("filter-synthetic")?.addEventListener("change", () => {
    loadAnalytics();
    loadReports();
  });
  document.getElementById("btn-apply-filters")?.addEventListener("click", () => {
    loadAnalytics();
    loadReports();
  });
  document.getElementById("btn-export-csv")?.addEventListener("click", exportCSV);
  document.getElementById("btn-seed-demo")?.addEventListener("click", seedDemoData);

  // Initial load
  loadAnalytics();
  loadReports();
});
