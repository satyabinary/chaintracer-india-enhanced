import React from "react";
import CopyableAddress from "./CopyableAddress";
import { formatUsdt } from "../lib/statusMeta";

const ROLE_LABELS = {
  victim_payment: "Victim payment",
  main_trail: "Main trail",
  sweeper_match: "Sweeper match",
  decoy: "Decoy",
};

export default function EvidenceTable({ evidence }) {
  if (!evidence || evidence.length === 0) {
    return (
      <section className="px-4 py-4">
        <h2 className="mb-3 text-sm font-medium text-parchment-100">Transaction evidence</h2>
        <p className="text-xs text-parchment-500">No transactions recorded for this case yet.</p>
      </section>
    );
  }

  return (
    <section className="px-4 py-4">
      <h2 className="mb-3 text-sm font-medium text-parchment-100">Transaction evidence</h2>
      <div className="overflow-x-auto rounded-md border border-line-700">
        <table className="w-full min-w-[640px] text-left text-xs">
          <thead>
            <tr className="border-b border-line-700 bg-ink-850 text-parchment-500">
              <th className="whitespace-nowrap px-3 py-2 font-medium">Hop</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Role</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Tx hash</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">From</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">To</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Amount</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Timestamp (UTC)</th>
            </tr>
          </thead>
          <tbody>
            {evidence.map((row, i) => (
              <tr key={`${row.hash}-${i}`} className="border-b border-line-700/60 last:border-0">
                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-parchment-400">
                  {row.hop_index >= 0 ? row.hop_index : "—"}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-parchment-400">
                  {ROLE_LABELS[row.role] || row.role}
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <CopyableAddress address={row.hash} />
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <CopyableAddress address={row.from_address} />
                </td>
                <td className="whitespace-nowrap px-3 py-2">
                  <CopyableAddress address={row.to_address} />
                </td>
                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-parchment-100">
                  {formatUsdt(row.amount)}
                </td>
                <td className="whitespace-nowrap px-3 py-2 tabular-nums text-parchment-400">
                  {row.timestamp_iso || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
