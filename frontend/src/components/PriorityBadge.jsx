import React from "react";
import { priorityMeta } from "../lib/statusMeta";

export default function PriorityBadge({ priority, size = "md" }) {
  const meta = priorityMeta(priority);
  const sizeClass = size === "sm" ? "text-[11px] px-2 py-0.5" : "text-xs px-2.5 py-1";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded ${sizeClass} font-medium ${meta.bgClass} ${meta.textClass}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dotClass}`} />
      {meta.label}
    </span>
  );
}
