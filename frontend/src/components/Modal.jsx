import React from "react";
import { useEffect } from "react";

export default function Modal({ title, onClose, children, width = "max-w-lg" }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className={`w-full ${width} rounded-lg border border-line-700 bg-ink-900 shadow-2xl`}>
        <div className="flex items-center justify-between border-b border-line-700 px-5 py-3.5">
          <h2 className="text-sm font-semibold text-parchment-100">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-parchment-500 hover:bg-ink-800 hover:text-parchment-100"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
