export const TRON_ADDRESS_RE = /^T[1-9A-HJ-NP-Za-km-z]{33}$/;

export function isValidTronAddress(address) {
  return typeof address === "string" && TRON_ADDRESS_RE.test(address.trim());
}

export const PRIORITY_META = {
  HIGH: { label: "High priority", textClass: "text-risk-high", bgClass: "bg-risk-high-bg", dotClass: "bg-risk-high" },
  MEDIUM: { label: "Medium priority", textClass: "text-risk-med", bgClass: "bg-risk-med-bg", dotClass: "bg-risk-med" },
  LOW: { label: "Low priority", textClass: "text-risk-low", bgClass: "bg-risk-low-bg", dotClass: "bg-risk-low" },
};

export function priorityMeta(priority) {
  return (
    PRIORITY_META[priority] || {
      label: priority || "Unscored",
      textClass: "text-parchment-500",
      bgClass: "bg-ink-700",
      dotClass: "bg-parchment-500",
    }
  );
}

export const MATCH_STATUS_META = {
  EXCHANGE_MATCH: { label: "Exchange match", textClass: "text-confirmed", bgClass: "bg-confirmed-bg" },
  SWEEPER_MATCH: { label: "Exchange match (sweeper)", textClass: "text-confirmed", bgClass: "bg-confirmed-bg" },
  IN_TRANSIT: { label: "In transit", textClass: "text-parchment-100", bgClass: "bg-ink-700" },
  MIXER_FLAGGED: { label: "Mixer flagged", textClass: "text-risk-high", bgClass: "bg-risk-high-bg" },
  TRACE_FAILED: { label: "Trace failed", textClass: "text-risk-high", bgClass: "bg-risk-high-bg" },
  TRACING: { label: "Tracing…", textClass: "text-brass-400", bgClass: "bg-ink-700" },
};

export function matchStatusMeta(status) {
  return (
    MATCH_STATUS_META[status] || {
      label: status || "Unknown",
      textClass: "text-parchment-500",
      bgClass: "bg-ink-700",
    }
  );
}

export function shortAddress(address) {
  if (!address || address.length < 12) return address || "";
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}

const USDT_FORMATTER = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatUsdt(amount) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return "—";
  return USDT_FORMATTER.format(amount);
}
