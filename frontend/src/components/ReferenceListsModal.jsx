import React from "react";
import { useEffect, useState } from "react";
import Modal from "./Modal";
import CopyableAddress from "./CopyableAddress";
import { getReferenceLists, ApiError } from "../api/client";

export default function ReferenceListsModal({ onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getReferenceLists()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load reference lists."));
  }, []);

  return (
    <Modal title="Sample threat-intel lists" onClose={onClose} width="max-w-2xl">
      {error && <p className="text-sm text-risk-high">{error}</p>}
      {!data && !error && <p className="text-sm text-parchment-500">Loading…</p>}
      {data && (
        <div className="space-y-5">
          <p className="rounded-md border border-brass-500/30 bg-brass-500/10 px-3 py-2 text-xs leading-relaxed text-brass-400">
            {data.disclaimer}
          </p>
          <ListBlock title="Known exchange hot wallets" entries={data.known_exchange_wallets} />
          <ListBlock title="Known scam wallets (prior reports)" entries={data.known_scam_wallets} />
          <ListBlock title="Known mixer / tumbler wallets" entries={data.known_mixer_wallets} />
        </div>
      )}
    </Modal>
  );
}

function ListBlock({ title, entries }) {
  const items = Object.entries(entries || {});
  return (
    <div>
      <h3 className="mb-2 text-xs font-medium text-parchment-100">{title}</h3>
      <div className="space-y-1.5">
        {items.map(([address, label]) => (
          <div
            key={address}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line-700 bg-ink-850 px-3 py-2"
          >
            <CopyableAddress address={address} className="text-xs" />
            <span className="text-xs text-parchment-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
