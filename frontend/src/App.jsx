import React from "react";
import { useCallback, useEffect, useState } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import CenterPanel from "./components/CenterPanel";
import RightPanel from "./components/RightPanel";
import NewCaseModal from "./components/NewCaseModal";
import ReportModal from "./components/ReportModal";
import ReferenceListsModal from "./components/ReferenceListsModal";
import { listCases, getCase, sendAlert, ApiError } from "./api/client";

export default function App() {
  const [cases, setCases] = useState([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [selectedCaseNumber, setSelectedCaseNumber] = useState(null);
  const [caseDetail, setCaseDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [modal, setModal] = useState(null); // null | "new-case" | "report" | "reference-lists"
  const [alertBusy, setAlertBusy] = useState(false);
  const [globalError, setGlobalError] = useState(null);

  const refreshCases = useCallback(async () => {
    setCasesLoading(true);
    try {
      const data = await listCases();
      setCases(data);
      return data;
    } catch (err) {
      setGlobalError(
        err instanceof ApiError
          ? `Couldn't reach the ChainTracer backend: ${err.message}`
          : "Couldn't reach the ChainTracer backend."
      );
      return [];
    } finally {
      setCasesLoading(false);
    }
  }, []);

  const loadCaseDetail = useCallback(async (caseNumber) => {
    if (!caseNumber) {
      setCaseDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const detail = await getCase(caseNumber);
      setCaseDetail(detail);
    } catch (err) {
      setGlobalError(err instanceof ApiError ? err.message : "Couldn't load that case.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const data = await refreshCases();
      if (data.length > 0) {
        setSelectedCaseNumber(data[0].case_number);
      }
    })();
  }, [refreshCases]);

  useEffect(() => {
    loadCaseDetail(selectedCaseNumber);
  }, [selectedCaseNumber, loadCaseDetail]);

  function handleSelectCase(caseNumber) {
    setSelectedCaseNumber(caseNumber);
  }

  function handleCaseCreated(created) {
    setModal(null);
    refreshCases();
    setSelectedCaseNumber(created.case_number);
    setCaseDetail(created);
  }

  async function handleSimulateAlert() {
    if (!caseDetail) return;
    setAlertBusy(true);
    try {
      await sendAlert(caseDetail.case_number);
      const refreshed = await getCase(caseDetail.case_number);
      setCaseDetail(refreshed);
    } catch (err) {
      setGlobalError(err instanceof ApiError ? err.message : "Couldn't simulate the alert.");
    } finally {
      setAlertBusy(false);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-ink-950">
      <Header onNewCase={() => setModal("new-case")} onShowReferenceLists={() => setModal("reference-lists")} />

      {globalError && (
        <div className="flex flex-shrink-0 items-center justify-between border-b border-risk-high/30 bg-risk-high-bg px-5 py-2 text-xs text-risk-high">
          <span>{globalError}</span>
          <button type="button" onClick={() => setGlobalError(null)} className="ml-4 underline">
            Dismiss
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <Sidebar
          cases={cases}
          selectedCaseNumber={selectedCaseNumber}
          onSelect={handleSelectCase}
          loading={casesLoading}
        />

        {detailLoading && !caseDetail ? (
          <div className="flex flex-1 items-center justify-center text-sm text-parchment-500">Loading case…</div>
        ) : (
          <CenterPanel caseDetail={caseDetail} onOpenReport={() => setModal("report")} />
        )}

        <RightPanel caseDetail={caseDetail} onSimulateAlert={handleSimulateAlert} alertBusy={alertBusy} />
      </div>

      {modal === "new-case" && <NewCaseModal onClose={() => setModal(null)} onCreated={handleCaseCreated} />}
      {modal === "report" && caseDetail && <ReportModal caseDetail={caseDetail} onClose={() => setModal(null)} />}
      {modal === "reference-lists" && <ReferenceListsModal onClose={() => setModal(null)} />}
    </div>
  );
}
