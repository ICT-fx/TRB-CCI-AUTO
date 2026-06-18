"use client";

import type { OrderExtraction, ProcessedFile } from "@/lib/types";
import { OrderRow } from "./OrderRow";

interface Props {
  files: ProcessedFile[];
  onChange: (id: string, data: OrderExtraction) => void;
  onRetry: (id: string) => void;
  onRemove: (id: string) => void;
}

// Column order matches the <td>s emitted by OrderRow. The first group is
// document-level (one value per order), the middle group is per product line.
const HEADERS: { label: string; className?: string }[] = [
  { label: "File Name" },
  { label: "Customer" },
  { label: "Document #" },
  { label: "Supplier Code" },
  { label: "Delivery Address", className: "min-w-[15rem]" },
  { label: "Delivery Date" },
  { label: "Terms (days)" },
  { label: "Comments", className: "min-w-[18rem]" },
  { label: "Product Name", className: "min-w-[12rem] border-l border-white/25" },
  { label: "SKU" },
  { label: "Qty" },
  { label: "Unit Price" },
  { label: "Currency" },
  { label: "Confidence" },
  { label: "" },
];

export function ResultsTable({ files, onChange, onRetry, onRemove }: Props) {
  return (
    <div className="overflow-x-auto rounded-xl border border-trb-line bg-white shadow-sm">
      <table className="w-full min-w-[1240px] border-collapse">
        <thead>
          <tr className="bg-trb-blue text-left text-xs font-semibold uppercase tracking-wide text-white">
            {HEADERS.map((h, i) => (
              <th
                key={i}
                className={[
                  "px-3 py-3 align-bottom",
                  i === HEADERS.length - 1 ? "text-right" : "",
                  h.className ?? "",
                ].join(" ")}
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {files.map((file) => (
            <OrderRow
              key={file.id}
              file={file}
              onChange={onChange}
              onRetry={onRetry}
              onRemove={onRemove}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
