const BASE = "";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json();
}

export function getHealth() {
  return apiFetch("/api/health");
}

export function getSettings() {
  return apiFetch("/api/settings");
}

export function postEstimate(overrides) {
  return apiFetch("/api/estimate", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export function postRun(overrides) {
  return apiFetch("/api/run", {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export function getJob(jobId) {
  return apiFetch(`/api/jobs/${jobId}`);
}

export function listRuns() {
  return apiFetch("/api/runs");
}

export function getInitCity(city, country, radius) {
  const params = new URLSearchParams({ city, country });
  if (radius != null && radius !== "") {
    params.set("radius", String(radius));
  }
  return apiFetch(`/api/init-city?${params}`);
}

export function getShortlist(runId) {
  return apiFetch(`/api/runs/${encodeURIComponent(runId)}/shortlist`);
}
