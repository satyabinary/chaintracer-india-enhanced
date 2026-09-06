import React from "react";
import { useEffect, useRef, useState } from "react";
import Modal from "./Modal";
import { isValidTronAddress } from "../lib/statusMeta";
import { createCase, ApiError } from "../api/client";

const PROGRESS_MESSAGES = [
  "Fetching wallet transaction history from Tronscan…",
  "Following the largest outgoing transfer at each hop…",
  "Checking exchange and threat-intel watchlists…",
  "Calculating the risk score…",
];

export default function NewCaseModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ victim_name: "", wallet_address: "", amount_usdt: "", notes: "" });
  const [addressTouched, setAddressTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [progressIdx, setProgressIdx] = useState(0);
  const [errorMsg, setErrorMsg] = useState(null);
  const timerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const addressValid = isValidTronAddress(form.wallet_address);
  const showAddressError = addressTouched && form.wallet_address.length > 0 && !addressValid;

  const canSubmit =
    form.victim_name.trim().length >= 2 && addressValid && Number(form.amount_usdt) > 0 && !submitting;

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setErrorMsg(null);
    setProgressIdx(0);
    timerRef.current = setInterval(() => {
      setProgressIdx((i) => Math.min(i + 1, PROGRESS_MESSAGES.length - 1));
    }, 1400);

    try {
      const created = await createCase({
        victim_name: form.victim_name.trim(),
        wallet_address: form.wallet_address.trim(),
        amount_usdt: Number(form.amount_usdt),
        notes: form.notes.trim(),
      });
      clearInterval(timerRef.current);
      onCreated(created);
    } catch (err) {
      clearInterval(timerRef.current);
      setSubmitting(false);
      const detail = err instanceof ApiError ? err.detail || err.message : null;
      setErrorMsg(typeof detail === "string" && detail ? detail : "Something went wrong filing this case.");
    }
  }

  return (
    <Modal title="File a new case" onClose={submitting ? () => {} : onClose}>
      {submitting ? (
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-line-700 border-t-brass-500" />
          <p className="text-sm text-parchment-100">{PROGRESS_MESSAGES[progressIdx]}</p>
          <p className="text-xs text-parchment-500">This can take a few seconds while we walk the trail hop by hop.</p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Victim name">
            <input
              type="text"
              value={form.victim_name}
              onChange={(e) => update("victim_name", e.target.value)}
              placeholder="Full name as given in the complaint"
              className="input"
            />
          </Field>

          <Field
            label="Scammer's TRON wallet address"
            hint="Starts with T, 34 characters — copy it exactly from the victim's screenshot or receipt."
            error={showAddressError ? "This doesn't look like a valid TRON address." : null}
          >
            <input
              type="text"
              value={form.wallet_address}
              onChange={(e) => update("wallet_address", e.target.value)}
              onBlur={() => setAddressTouched(true)}
              placeholder="T..."
              className="input font-mono"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
            />
          </Field>

          <Field label="Amount reported (USDT)">
            <input
              type="number"
              min="0"
              step="0.01"
              value={form.amount_usdt}
              onChange={(e) => update("amount_usdt", e.target.value)}
              placeholder="0.00"
              className="input"
            />
          </Field>

          <Field label="Notes (optional)">
            <textarea
              value={form.notes}
              onChange={(e) => update("notes", e.target.value)}
              placeholder="How the scam happened, complaint reference number, anything else useful"
              rows={3}
              className="input resize-none"
            />
          </Field>

          {errorMsg && (
            <p className="rounded-md border border-risk-high/40 bg-risk-high-bg px-3 py-2 text-xs text-risk-high">
              {errorMsg}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost">
              Cancel
            </button>
            <button type="submit" disabled={!canSubmit} className="btn-primary">
              Start trace
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-parchment-400">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-[11px] text-parchment-500">{hint}</span>}
      {error && <span className="mt-1 block text-[11px] text-risk-high">{error}</span>}
    </label>
  );
}
