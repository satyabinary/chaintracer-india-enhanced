import React from "react";
import CopyableAddress from "./CopyableAddress";
import StatusPill from "./StatusPill";

export default function ExchangeMatchCard({ caseDetail, onSimulateAlert, alertBusy }) {
  const { match_status, matched_exchange, matched_wallet, alert_sent, error_message } = caseDetail;
  const isExchangeHit = match_status === "EXCHANGE_MATCH" || match_status === "SWEEPER_MATCH";

  return (
    <section className="border-b border-line-700 px-4 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-parchment-100">Exchange attribution</h2>
        <StatusPill status={match_status} />
      </div>

      {isExchangeHit && (
        <div className="rounded-md border border-line-700 bg-ink-850 p-3">
          <div className="text-sm font-medium text-parchment-100">{matched_exchange}</div>
          <div className="mt-1.5">
            <CopyableAddress address={matched_wallet} full className="text-xs" />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-parchment-500">
            {match_status === "SWEEPER_MATCH"
              ? "Detected by behaviour, not an exact address match: this wallet forwarded 95%+ of the traced funds to a known exchange wallet within 24 hours of receiving them."
              : "This wallet address is on the known exchange hot-wallet list."}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={alertBusy}
              onClick={onSimulateAlert}
              className="rounded-md border border-brass-500 px-3 py-1.5 text-xs font-medium text-brass-400 transition hover:bg-brass-500 hover:text-ink-950 disabled:opacity-50"
            >
              {alertBusy ? "Sending…" : "Simulate exchange alert"}
            </button>
            {alert_sent && <span className="text-xs text-parchment-500">Alert simulated — no real message sent</span>}
          </div>
        </div>
      )}

      {match_status === "IN_TRANSIT" && (
        <div className="rounded-md border border-line-700 bg-ink-850 p-3 text-xs leading-relaxed text-parchment-400">
          Funds haven't reached a known exchange wallet within the traced hops. This is an open case, not a
          failure — re-run the trace later, since the trail may keep moving.
        </div>
      )}

      {match_status === "MIXER_FLAGGED" && (
        <div className="rounded-md border border-line-700 bg-ink-850 p-3 text-xs leading-relaxed text-parchment-400">
          The trail entered a wallet on the known mixer/tumbler list. This tool doesn't trace through
          mixers, so tracing stopped here.
        </div>
      )}

      {match_status === "TRACE_FAILED" && (
        <div className="rounded-md border border-risk-high/40 bg-risk-high-bg p-3 text-xs leading-relaxed text-risk-high">
          {error_message || "The trace could not complete."}
        </div>
      )}
    </section>
  );
}
