import React from "react";
import Modal from "./Modal";
import { reportUrl } from "../api/client";
import PriorityBadge from "./PriorityBadge";
import StatusPill from "./StatusPill";
import { formatUsdt } from "../lib/statusMeta";

export default function ReportModal({ caseDetail, onClose }) {
  const url = reportUrl(caseDetail.case_number);

  return (
    <Modal title={`Case report — ${caseDetail.case_number}`} onClose={onClose} width="max-w-3xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-line-700 bg-ink-850 p-3">
        <div>
          <div className="text-sm font-medium text-parchment-100">{caseDetail.victim_name}</div>
          <div className="text-xs text-parchment-500">
            {formatUsdt(caseDetail.amount_usdt)} USDT reported · filed {caseDetail.created_at}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <PriorityBadge priority={caseDetail.priority} size="sm" />
          <StatusPill status={caseDetail.match_status} size="sm" />
        </div>
      </div>

      <div className="mb-4 h-[55vh] overflow-hidden rounded-md border border-line-700 bg-parchment-100">
        <object data={url} type="application/pdf" className="h-full w-full">
          <p className="p-4 text-sm text-ink-950">
            Your browser can't preview PDFs inline. Use the download button below instead.
          </p>
        </object>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-parchment-500">
          Investigative aid only — this report doesn't freeze funds or notify anyone by itself.
        </p>
        <a href={url} download={`${caseDetail.case_number}_report.pdf`} className="btn-primary">
          Download PDF
        </a>
      </div>
    </Modal>
  );
}
