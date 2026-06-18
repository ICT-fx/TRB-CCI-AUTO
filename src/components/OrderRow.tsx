"use client";

import { useState } from "react";
import type { OrderExtraction, ProcessedFile, ProductLine } from "@/lib/types";
import { display } from "@/lib/format";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface Props {
  file: ProcessedFile;
  onChange: (id: string, data: OrderExtraction) => void;
  onRetry: (id: string) => void;
  onRemove: (id: string) => void;
}

// Total number of columns in the results table (keep in sync with ResultsTable).
export const TABLE_COLS = 15;

function StatusPill({ file, onRetry }: { file: ProcessedFile; onRetry: (id: string) => void }) {
  switch (file.status) {
    case "queued":
      return <span className="text-xs text-trb-muted">Queued…</span>;
    case "processing":
      return (
        <span className="inline-flex items-center gap-1.5 text-xs text-trb-blue">
          <span className="h-2 w-2 animate-pulse rounded-full bg-trb-blue" />
          Processing…
        </span>
      );
    case "error":
      return (
        <button
          onClick={() => onRetry(file.id)}
          className="text-xs font-medium text-status-low underline-offset-2 hover:underline"
          title={file.error ?? "Extraction failed"}
        >
          Failed — retry
        </button>
      );
    case "done":
      return <span className="text-xs font-medium text-status-high">Done</span>;
  }
}

export function OrderRow({ file, onChange, onRetry, onRemove }: Props) {
  const [editing, setEditing] = useState(false);
  const d = file.data;

  // --- Non-completed documents: a single status row ---
  if (file.status !== "done" || !d) {
    return (
      <tr className="border-t-2 border-trb-line">
        <td className="border-l-2 border-l-trb-blue/30 px-3 py-3 align-top">
          <FileNameCell name={file.fileName} />
        </td>
        <td colSpan={TABLE_COLS - 2} className="px-3 py-3">
          <StatusPill file={file} onRetry={onRetry} />
        </td>
        <td className="px-3 py-3 text-right align-top">
          <RemoveButton onClick={() => onRemove(file.id)} />
        </td>
      </tr>
    );
  }

  const products = d.products.length > 0 ? d.products : [PLACEHOLDER_LINE];
  const rows = products.length;

  // --- Document-level cells, rendered once and spanning all product rows ---
  const docCells = (
    <>
      <td rowSpan={rows} className="border-l-2 border-l-trb-blue/30 px-3 py-2.5 align-top">
        <FileNameCell name={file.fileName} />
      </td>
      <td rowSpan={rows} className="px-3 py-2.5 align-top text-sm">{display(d.customer_name)}</td>
      <td rowSpan={rows} className="px-3 py-2.5 align-top text-sm">{display(d.document_number)}</td>
      <td rowSpan={rows} className="px-3 py-2.5 align-top text-sm tabular-nums">{display(d.supplier_code)}</td>
      <td rowSpan={rows} className="max-w-[15rem] px-3 py-2.5 align-top text-sm">
        <span className="block whitespace-pre-line break-words text-trb-ink">
          {display(d.delivery_address)}
        </span>
      </td>
      <td rowSpan={rows} className="px-3 py-2.5 align-top text-sm tabular-nums">{display(d.requested_delivery_date)}</td>
      <td rowSpan={rows} className="px-3 py-2.5 align-top text-sm tabular-nums">{display(d.payment_terms_days)}</td>
      <td rowSpan={rows} className="max-w-[18rem] px-3 py-2.5 align-top text-sm">
        <span className="block whitespace-pre-line break-words text-trb-muted">
          {display(d.comments)}
        </span>
      </td>
    </>
  );

  const trailingCells = (
    <>
      <td rowSpan={rows} className="px-3 py-2.5 align-top">
        {d.is_readable ? (
          <ConfidenceBadge confidence={d.confidence} />
        ) : (
          <span className="text-xs font-medium text-status-low">Unreadable</span>
        )}
      </td>
      <td rowSpan={rows} className="px-3 py-2.5 text-right align-top">
        <div className="flex items-center justify-end gap-2">
          <button
            onClick={() => setEditing((v) => !v)}
            className={[
              "rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset transition-colors",
              editing
                ? "bg-trb-blue text-white ring-trb-blue"
                : "text-trb-blue ring-trb-line hover:bg-trb-blue-light",
            ].join(" ")}
          >
            {editing ? "Close" : "Edit"}
          </button>
          <RemoveButton onClick={() => onRemove(file.id)} />
        </div>
      </td>
    </>
  );

  return (
    <>
      {products.map((p, i) => (
        <tr
          key={i}
          className={
            i === 0
              ? "border-t-2 border-trb-line hover:bg-trb-blue-tint/50"
              : "border-t border-trb-line/50 hover:bg-trb-blue-tint/50"
          }
        >
          {i === 0 && docCells}
          <td className="border-l border-trb-line px-3 py-2.5 align-top text-sm">
            {display(p.product_name)}
          </td>
          <td className="px-3 py-2.5 align-top text-sm tabular-nums">{display(p.sku)}</td>
          <td className="px-3 py-2.5 align-top text-sm tabular-nums">{display(p.quantity)}</td>
          <td className="px-3 py-2.5 align-top text-sm tabular-nums">{display(p.unit_price)}</td>
          <td className="px-3 py-2.5 align-top text-sm">{display(p.currency ?? d.currency)}</td>
          {i === 0 && trailingCells}
        </tr>
      ))}

      {editing && (
        <tr className="border-t border-trb-line bg-trb-blue-tint/60">
          <td colSpan={TABLE_COLS} className="px-6 py-5">
            <OrderEditor file={file} onChange={onChange} />
          </td>
        </tr>
      )}
    </>
  );
}

const PLACEHOLDER_LINE: ProductLine = {
  product_name: null,
  sku: null,
  quantity: null,
  unit_price: null,
  currency: null,
};

function FileNameCell({ name }: { name: string }) {
  return (
    <span className="block max-w-[13rem] truncate text-sm font-medium text-trb-ink" title={name}>
      {name}
    </span>
  );
}

function RemoveButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-trb-muted transition-colors hover:text-status-low"
      aria-label="Remove"
      title="Remove"
    >
      ✕
    </button>
  );
}

// ---------------- Editable correction panel ----------------

function OrderEditor({
  file,
  onChange,
}: {
  file: ProcessedFile;
  onChange: (id: string, data: OrderExtraction) => void;
}) {
  const d = file.data!;
  const num = (v: string): number | null => (v.trim() === "" ? null : Number(v));
  const str = (v: string): string | null => (v.trim() === "" ? null : v);

  const setField = <K extends keyof OrderExtraction>(key: K, value: OrderExtraction[K]) =>
    onChange(file.id, { ...d, [key]: value });

  const setProduct = (index: number, key: keyof ProductLine, value: string) => {
    const productsList = d.products.map((p, i) =>
      i === index
        ? { ...p, [key]: key === "quantity" || key === "unit_price" ? num(value) : str(value) }
        : p,
    );
    onChange(file.id, { ...d, products: productsList });
  };

  const addProduct = () =>
    onChange(file.id, { ...d, products: [...d.products, { ...PLACEHOLDER_LINE }] });

  const removeProduct = (index: number) =>
    onChange(file.id, { ...d, products: d.products.filter((_, i) => i !== index) });

  return (
    <>
      {d.quality_note && (
        <p className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-status-medium ring-1 ring-inset ring-amber-200">
          Note: {d.quality_note}
        </p>
      )}

      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-trb-muted">
        Order details — editable before export
      </h4>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        <Field label="Customer Name" value={d.customer_name} onChange={(v) => setField("customer_name", str(v))} />
        <Field label="Document Number" value={d.document_number} onChange={(v) => setField("document_number", str(v))} />
        <Field label="Supplier Code" value={d.supplier_code} onChange={(v) => setField("supplier_code", str(v))} />
        <Field label="Delivery Date" value={d.requested_delivery_date} onChange={(v) => setField("requested_delivery_date", str(v))} />
        <Field label="Currency" value={d.currency} onChange={(v) => setField("currency", str(v))} />
        <Field label="Payment Terms (days)" type="number" value={d.payment_terms_days} onChange={(v) => setField("payment_terms_days", num(v))} />
        <Field label="Delivery Address" value={d.delivery_address} onChange={(v) => setField("delivery_address", str(v))} />
      </div>

      <div className="mt-3">
        <Field label="Comments" value={d.comments} onChange={(v) => setField("comments", str(v))} />
      </div>

      <div className="mt-5 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-trb-muted">
          Order lines ({d.products.length})
        </h4>
        <button
          onClick={addProduct}
          className="rounded-md border border-trb-blue px-2.5 py-1 text-xs font-medium text-trb-blue hover:bg-trb-blue-light"
        >
          + Add line
        </button>
      </div>

      <div className="mt-2 overflow-x-auto rounded-lg border border-trb-line bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs font-semibold text-trb-muted">
              <th className="px-3 py-2">Product Name</th>
              <th className="w-28 px-3 py-2">SKU</th>
              <th className="w-24 px-3 py-2">Quantity</th>
              <th className="w-28 px-3 py-2">Unit Price</th>
              <th className="w-24 px-3 py-2">Currency</th>
              <th className="w-10 px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {d.products.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-3 text-center text-xs text-trb-muted">
                  No product lines detected. Add one if needed.
                </td>
              </tr>
            )}
            {d.products.map((p, i) => (
              <tr key={i} className="border-t border-trb-line">
                <td className="px-2 py-1.5">
                  <ProductInput value={p.product_name} onChange={(v) => setProduct(i, "product_name", v)} />
                </td>
                <td className="px-2 py-1.5">
                  <ProductInput value={p.sku} onChange={(v) => setProduct(i, "sku", v)} />
                </td>
                <td className="px-2 py-1.5">
                  <ProductInput type="number" value={p.quantity} onChange={(v) => setProduct(i, "quantity", v)} />
                </td>
                <td className="px-2 py-1.5">
                  <ProductInput type="number" value={p.unit_price} onChange={(v) => setProduct(i, "unit_price", v)} />
                </td>
                <td className="px-2 py-1.5">
                  <ProductInput value={p.currency} onChange={(v) => setProduct(i, "currency", v)} />
                </td>
                <td className="px-2 py-1.5 text-center">
                  <button
                    onClick={() => removeProduct(i)}
                    className="text-trb-muted hover:text-status-low"
                    aria-label="Remove line"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string | number | null;
  onChange: (v: string) => void;
  type?: "text" | "number";
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-trb-muted">{label}</span>
      <input
        type={type}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-trb-line bg-white px-2.5 py-1.5 text-sm text-trb-ink focus:border-trb-blue focus:outline-none focus:ring-1 focus:ring-trb-blue"
      />
    </label>
  );
}

function ProductInput({
  value,
  onChange,
  type = "text",
}: {
  value: string | number | null;
  onChange: (v: string) => void;
  type?: "text" | "number";
}) {
  return (
    <input
      type={type}
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-sm text-trb-ink hover:border-trb-line focus:border-trb-blue focus:bg-white focus:outline-none"
    />
  );
}
