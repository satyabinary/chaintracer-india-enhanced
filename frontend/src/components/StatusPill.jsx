import React from "react";
import { matchStatusMeta } from "../lib/statusMeta";

export default function StatusPill({ status, size = "md" }) {
  const meta = matchStatusMeta(status);
  const sizeClass = size === "sm" ? "text-[11px] px-2 py-0.5" : "text-xs px-2.5 py-1";

  return (
    <span className={`inline-flex items-center rounded ${sizeClass} font-medium ${meta.bgClass} ${meta.textClass}`}>
      {meta.label}
    </span>
  );
}
