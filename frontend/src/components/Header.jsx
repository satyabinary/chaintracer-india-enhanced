import React from "react";
export default function Header({ onNewCase, onShowReferenceLists }) {
  return (
    <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-line-700 bg-ink-900 px-5">
      <div className="flex items-baseline gap-2.5">
        <span className="h-2 w-2 rounded-full bg-brass-500" />
        <h1 className="text-[15px] font-semibold tracking-tight text-parchment-100">ChainTracer India</h1>
        <span className="hidden text-xs text-parchment-500 sm:inline">Cyber cell fund-tracing console</span>
      </div>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onShowReferenceLists}
          className="text-xs text-parchment-500 underline-offset-2 hover:text-parchment-100 hover:underline"
        >
          Sample watchlists
        </button>
        <button
          type="button"
          onClick={onNewCase}
          className="rounded-md bg-brass-500 px-3.5 py-1.5 text-sm font-medium text-ink-950 transition hover:bg-brass-400"
        >
          New case
        </button>
      </div>
    </header>
  );
}
