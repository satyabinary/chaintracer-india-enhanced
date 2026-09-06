const API_BASE =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    throw new ApiError(
      "Couldn't reach the ChainTracer backend. Check that the API is running and reachable.",
      0,
      networkErr.message
    );
  }

  if (!res.ok) {
    let detail = null;
    try {
      const body = await res.json();
      detail = body?.detail ?? JSON.stringify(body);
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(
      typeof detail === "string" && detail ? detail : `Request failed with status ${res.status}`,
      res.status,
      detail
    );
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return res;
}

export function listCases() {
  return request("/api/cases");
}

export function getCase(caseNumber) {
  return request(`/api/cases/${encodeURIComponent(caseNumber)}`);
}

export function createCase(payload) {
  return request("/api/cases", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sendAlert(caseNumber) {
  return request(`/api/cases/${encodeURIComponent(caseNumber)}/alert`, {
    method: "POST",
  });
}

export function getReferenceLists() {
  return request("/api/reference-lists");
}

export function reportUrl(caseNumber) {
  return `${API_BASE}/api/cases/${encodeURIComponent(caseNumber)}/report`;
}

export { API_BASE };
