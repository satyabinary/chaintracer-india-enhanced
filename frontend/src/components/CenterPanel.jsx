import React from "react";
import { useState } from "react";
import CopyableAddress from "./CopyableAddress";
import StatusPill from "./StatusPill";
import TraceGraph from "./TraceGraph";
import { formatUsdt } from "../lib/statusMeta";

const ROLE_LABELS = {
  victim: "Victim",
  source: "Source wallet (victim-reported)",
  intermediate: "Intermediate wallet",
  exchange: "Exchange wallet",
  mixer: "Known mixer",
  decoy: "Decoy (not followed)",
};

export default function CenterPanel({ caseDetail, onOpenReport }) {
  const [selectedNode, setSelectedNode] = useState(null);

  if (!caseDetail) {
    return (
      <div className="flex flex-1 items-center justify-center px-8 text-center text-sm text-parchment-500">
        Select a case from the list, or file a new one, to see its fund trail.
      </div>
    );
  }

  const isTracing = caseDetail.status === "TRACING";
  const isFailed = caseDetail.status === "FAILED";

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-3 border-b border-line-700 px-5 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="font-mono text-xs text-parchment-500">{caseDetail.case_number}</span>
            <StatusPill status={isTracing ? "TRACING" : caseDetail.match_status} size="sm" />
            {caseDetail.is_seed && <span className="text-[11px] text-parchment-500">Sample case</span>}
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-3">
            <h2 className="truncate text-base font-semibold text-parchment-100">{caseDetail.victim_name}</h2>
            <span className="tabular-nums text-sm text-parchment-400">
              {formatUsdt(caseDetail.amount_usdt)} USDT reported
            </span>
          </div>
          <div className="mt-1">
            <CopyableAddress address={caseDetail.wallet_address} className="text-xs" />
          </div>
        </div>
        <button
          type="button"
          disabled={isTracing || isFailed}
          onClick={onOpenReport}
          className="flex-shrink-0 rounded-md border border-line-700 px-3 py-1.5 text-xs font-medium text-parchment-100 transition hover:border-brass-500 hover:text-brass-400 disabled:opacity-40"
        >
          Generate report
        </button>
      </div>

      <div className="relative min-h-0 flex-1">
        {isTracing && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-ink-950/70 text-sm text-parchment-400">
            Tracing on-chain path…
          </div>
        )}
        {isFailed && (
          <div className="flex h-full items-center justify-center px-8 text-center text-sm text-risk-high">
            {caseDetail.error_message || "Tracing failed for this case."}
          </div>
        )}
        {!isFailed && <TraceGraph graph={caseDetail.graph} onSelectNode={setSelectedNode} />}
      </div>

      <div className="flex flex-shrink-0 flex-wrap items-center justify-between gap-3 border-t border-line-700 px-5 py-2.5 text-xs text-parchment-500">
        <div className="flex flex-wrap items-center gap-4">
          <LegendDot color="bg-brass-500" label="Source" />
          <LegendDot color="bg-ink-800 border border-line-600" label="Intermediate" />
          <LegendDot color="bg-confirmed" label="Exchange" />
          <LegendDot color="bg-risk-high" label="Mixer" />
          <LegendDot color="bg-ink-900 border border-dashed border-line-600" label="Decoy" />
        </div>
        <div className="min-w-0 truncate">
          {selectedNode ? (
            <span>
              Selected:{" "}
              <span className="font-mono text-parchment-100">
                {selectedNode.full_address || selectedNode.label}
              </span>
              {" · "}
              {ROLE_LABELS[selectedNode.role] || selectedNode.role}
              {typeof selectedNode.taint === "number" && ` · taint ${selectedNode.taint.toFixed(2)}`}
            </span>
          ) : (
            "Tap a wallet in the graph to inspect it."
          )}
        </div>
      </div>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
