"use client";

import { useMemo, useState } from "react";
import { UploadZone } from "@/components/UploadZone";
import { ResultsTable } from "@/components/ResultsTable";
import { useExtraction } from "@/hooks/useExtraction";
import { exportToExcel } from "@/lib/excel";

const STEPS = [
  { n: "1", title: "Drop documents", desc: "PDF, scans, photos or TIFF — drag in up to 50 at once." },
  { n: "2", title: "Claude reads them", desc: "Printed, handwritten and crossed-out values, in any language." },
  { n: "3", title: "Export to Excel", desc: "Review, correct, and download an ERP-ready workbook." },
];

export default function Home() {
  const { files, isProcessing, addFiles, retry, removeFile, clearAll, updateData } =
    useExtraction();
  const [exporting, setExporting] = useState(false);
  const [logoFailed, setLogoFailed] = useState(false);

  const stats = useMemo(() => {
    const total = files.length;
    const done = files.filter((f) => f.status === "done").length;
    const errored = files.filter((f) => f.status === "error").length;
    const lines = files.reduce((sum, f) => sum + (f.data?.products.length ?? 0), 0);
    return { total, done, errored, lines };
  }, [files]);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportToExcel(files);
    } finally {
      setExporting(false);
    }
  };

  const hasResults = files.length > 0;
  const canExport = stats.done > 0 && !isProcessing;

  return (
    <div className="flex min-h-full flex-col">
      {/* ---------------- HERO ---------------- */}
      <section className="hero-atmosphere relative overflow-hidden border-b border-trb-line">
        <div className="hero-grid pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-trb-blue via-trb-blue-dark to-trb-blue" />

        <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-6 py-14 md:py-20 lg:grid-cols-[minmax(0,auto)_1fr] lg:gap-16">
          {/* Logo plate */}
          <div className="animate-rise flex justify-center lg:justify-start">
            <div className="rounded-3xl bg-white p-6 shadow-[0_24px_60px_-24px_rgba(15,67,112,0.45)] ring-1 ring-trb-line sm:p-8">
              {logoFailed ? (
                <div className="flex h-36 w-36 items-center justify-center rounded-2xl bg-trb-blue text-4xl font-bold tracking-tight text-white">
                  TRB
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src="/trb-logo.webp"
                  alt="TRB Chemedica"
                  className="h-36 w-auto sm:h-44"
                  onError={() => setLogoFailed(true)}
                />
              )}
            </div>
          </div>

          {/* Headline */}
          <div className="animate-rise" style={{ animationDelay: "120ms" }}>
            <span className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-trb-blue ring-1 ring-inset ring-trb-line backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-trb-blue" />
              TRB Chemedica · Geneva
            </span>

            <h1 className="mt-5 font-display text-5xl leading-[1.02] tracking-tight text-trb-blue-darker sm:text-6xl lg:text-7xl">
              AI Order
              <br />
              Extraction
            </h1>

            <p className="mt-5 max-w-xl text-lg leading-relaxed text-trb-muted">
              Turn customer purchase orders into structured, ERP-ready data in
              seconds. Drag your documents into the panel below — Claude reads
              every line, including handwritten corrections, and you export
              straight to Excel.
            </p>

            {/* How it works */}
            <ol className="mt-8 grid gap-4 sm:grid-cols-3">
              {STEPS.map((s) => (
                <li key={s.n} className="flex gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-trb-blue text-sm font-semibold text-white">
                    {s.n}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-trb-ink">{s.title}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-trb-muted">{s.desc}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* ---------------- WORKSPACE ---------------- */}
      <main className="relative z-10 mx-auto -mt-8 w-full max-w-7xl flex-1 px-6 pb-20">
        <div className="rounded-2xl border border-trb-line bg-white p-5 shadow-[0_20px_50px_-30px_rgba(15,67,112,0.4)] sm:p-6">
          <UploadZone onFiles={addFiles} />
        </div>

        {hasResults && (
          <section className="mt-8">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-trb-muted">
                <span>
                  <strong className="text-trb-ink">{stats.total}</strong> documents
                </span>
                <span>
                  <strong className="text-trb-ink">{stats.done}</strong> extracted
                </span>
                {stats.errored > 0 && (
                  <span className="text-status-low">
                    <strong>{stats.errored}</strong> failed
                  </span>
                )}
                <span>
                  <strong className="text-trb-ink">{stats.lines}</strong> order lines
                </span>
                {isProcessing && (
                  <span className="inline-flex items-center gap-1.5 text-trb-blue">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-trb-blue" />
                    Processing…
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={clearAll}
                  disabled={isProcessing}
                  className="rounded-lg border border-trb-line bg-white px-3 py-2 text-sm font-medium text-trb-muted transition-colors hover:bg-trb-blue-tint disabled:opacity-50"
                >
                  Clear all
                </button>
                <button
                  onClick={handleExport}
                  disabled={!canExport || exporting}
                  className="inline-flex items-center gap-2 rounded-lg bg-trb-blue px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-trb-blue-dark disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <path d="M7 10l5 5 5-5" />
                    <path d="M12 15V3" />
                  </svg>
                  {exporting ? "Exporting…" : "Export to Excel"}
                </button>
              </div>
            </div>

            <ResultsTable
              files={files}
              onChange={updateData}
              onRetry={retry}
              onRemove={removeFile}
            />

            <p className="mt-3 text-xs text-trb-muted">
              Every product line is shown with its document details. Use the
              <span className="font-medium text-trb-blue"> Edit </span>
              button on any order to correct values before exporting — crossed-out
              handwritten corrections are read automatically.
            </p>
          </section>
        )}
      </main>

      <footer className="border-t border-trb-line bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5 text-xs text-trb-muted">
          TRB Chemedica · AI Order Extraction — documents are processed in memory
          and never stored.
        </div>
      </footer>
    </div>
  );
}
