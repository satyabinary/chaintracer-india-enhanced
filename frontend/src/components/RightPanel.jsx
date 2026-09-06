import React from "react";
import RiskScorePanel from "./RiskScorePanel";
import ExchangeMatchCard from "./ExchangeMatchCard";
import EvidenceTable from "./EvidenceTable";

export default function RightPanel({ caseDetail, onSimulateAlert, alertBusy }) {
  if (!caseDetail) {
    return <aside className="w-[380px] flex-shrink-0 border-l border-line-700 bg-ink-900" />;
  }

  if (caseDetail.status === "TRACING") {
    return (
      <aside className="w-[380px] flex-shrink-0 overflow-y-auto border-l border-line-700 bg-ink-900 px-4 py-6 text-sm text-parchment-500">
        Waiting for the trace to finish before risk scoring can run.
      </aside>
    );
  }

  if (caseDetail.status === "FAILED") {
    return (
      <aside className="w-[380px] flex-shrink-0 overflow-y-auto border-l border-line-700 bg-ink-900 px-4 py-6 text-sm text-risk-high">
        {caseDetail.error_message || "This case failed to trace."}
      </aside>
    );
  }

  return (
    <aside className="w-[380px] flex-shrink-0 overflow-y-auto border-l border-line-700 bg-ink-900">
      <RiskScorePanel riskBreakdown={caseDetail.risk_breakdown} />
      <ExchangeMatchCard caseDetail={caseDetail} onSimulateAlert={onSimulateAlert} alertBusy={alertBusy} />
      <EvidenceTable evidence={caseDetail.evidence} />
    </aside>
  );
}
