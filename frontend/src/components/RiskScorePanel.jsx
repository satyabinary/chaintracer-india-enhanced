import React from "react";
import PriorityBadge from "./PriorityBadge";

const FACTOR_ORDER = [
  "taint_level",
  "hop_depth_score",
  "sweep_timing_match",
  "bot_speed_flag",
  "threat_intel_hit",
];

const FACTOR_BAR_COLORS = {
  taint_level: "bg-brass-500",
  hop_depth_score: "bg-steel-500",
  sweep_timing_match: "bg-confirmed",
  bot_speed_flag: "bg-risk-med",
  threat_intel_hit: "bg-risk-high",
};

function formatRaw(key, factor) {
  if (key === "hop_depth_score" || key === "taint_level") {
    return factor.raw_value.toFixed(2);
  }
  return factor.raw_value >= 1 ? "Yes" : "No";
}

export default function RiskScorePanel({ riskBreakdown }) {
  if (!riskBreakdown) return null;
  const { total_score, priority, factors } = riskBreakdown;

  return (
    <section className="border-b border-line-700 px-4 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-medium text-parchment-100">Risk score</h2>
        <PriorityBadge priority={priority} />
      </div>

      <div className="mb-3 flex items-baseline gap-2">
        <span className="tabular-nums text-3xl font-semibold text-parchment-100">{total_score.toFixed(2)}</span>
        <span className="text-sm text-parchment-500">/ 1.00</span>
      </div>

      <div className="mb-4 flex h-2 overflow-hidden rounded-full bg-ink-800">
        {FACTOR_ORDER.map((key) => {
          const f = factors[key];
          const widthPct = Math.max(f.weighted, 0) * 100;
          return (
            <div
              key={key}
              style={{ width: `${widthPct}%` }}
              className={FACTOR_BAR_COLORS[key]}
              title={`${f.label}: ${f.weighted.toFixed(3)}`}
            />
          );
        })}
      </div>

      <p className="mb-4 text-xs leading-relaxed text-parchment-500">
        Fixed weighted formula, not a machine-learning prediction — every factor below adds up to the total
        score above.
      </p>

      <div className="space-y-2.5">
        {FACTOR_ORDER.map((key) => {
          const f = factors[key];
          return (
            <div key={key} className="rounded-md border border-line-700 bg-ink-850 p-3">
              <div className="flex flex-wrap items-center justify-between gap-x-2 text-xs">
                <span className="font-medium text-parchment-100">{f.label}</span>
                <span className="tabular-nums text-parchment-400">
                  {formatRaw(key, f)} × {f.weight.toFixed(2)} ={" "}
                  <span className="text-parchment-100">{f.weighted.toFixed(3)}</span>
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-parchment-500">{f.explanation}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
