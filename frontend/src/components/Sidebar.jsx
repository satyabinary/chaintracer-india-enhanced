import React from "react";
import PriorityBadge from "./PriorityBadge";
import StatusPill from "./StatusPill";
import { formatUsdt } from "../lib/statusMeta";

export default function Sidebar({ cases, selectedCaseNumber, onSelect, loading }) {
  return (
    <aside className="flex w-[300px] flex-shrink-0 flex-col border-r border-line-700 bg-ink-900">
      <div className="flex flex-shrink-0 items-center justify-between border-b border-line-700 px-4 py-3">
        <span className="text-sm font-medium text-parchment-100">Cases</span>
        <span className="text-xs text-parchment-500">{cases.length} filed</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && <div className="px-4 py-6 text-sm text-parchment-500">Loading cases…</div>}

        {!loading && cases.length === 0 && (
          <div className="px-4 py-6 text-sm leading-relaxed text-parchment-500">
            No cases filed yet. Use "New case" to start a trace.
          </div>
        )}

        {cases.map((c) => {
          const active = c.case_number === selectedCaseNumber;
          const pillStatus = c.status === "TRACING" ? "TRACING" : c.status === "FAILED" ? "TRACE_FAILED" : c.match_status;
          return (
            <button
              key={c.case_number}
              type="button"
              onClick={() => onSelect(c.case_number)}
              className={`block w-full border-b border-line-700/60 px-4 py-3 text-left transition ${
                active ? "bg-ink-800" : "hover:bg-ink-850"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-parchment-400">{c.case_number}</span>
                {c.priority && <PriorityBadge priority={c.priority} size="sm" />}
              </div>
              <div className="mt-1.5 truncate text-sm font-medium text-parchment-100">{c.victim_name}</div>
              <div className="mt-1.5 flex items-center justify-between gap-2">
                <span className="tabular-nums text-xs text-parchment-400">{formatUsdt(c.amount_usdt)} USDT</span>
                <StatusPill status={pillStatus} size="sm" />
              </div>
              {c.is_seed ? (
                <div className="mt-1.5 text-[11px] text-parchment-500">Sample case</div>
              ) : null}
            </button>
          );
        })}
      </div>
    </aside>
  );
}
