import React from "react";
import { useState } from "react";
import { shortAddress } from "../lib/statusMeta";

export default function CopyableAddress({ address, full = false, className = "" }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy(e) {
    e.stopPropagation();
    if (!address) return;
    try {
      await navigator.clipboard.writeText(address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // Clipboard API can be unavailable (older browser, insecure context) —
      // the address is still visible and selectable, so fail quietly.
    }
  }

  if (!address) {
    return <span className={`font-mono text-parchment-500 ${className}`}>—</span>;
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={address}
      className={`group inline-flex items-center gap-1.5 font-mono text-parchment-100 hover:text-brass-400 ${className}`}
    >
      <span>{full ? address : shortAddress(address)}</span>
      <span className="text-[10px] text-parchment-500 group-hover:text-brass-400">
        {copied ? "copied" : "copy"}
      </span>
    </button>
  );
}
