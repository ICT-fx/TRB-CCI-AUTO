import { confidenceLevel } from "@/lib/format";

const STYLES: Record<string, string> = {
  high: "bg-emerald-50 text-status-high ring-emerald-200",
  medium: "bg-amber-50 text-status-medium ring-amber-200",
  low: "bg-red-50 text-status-low ring-red-200",
};

const LABEL: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function ConfidenceBadge({ confidence }: { confidence: number }) {
  const level = confidenceLevel(confidence);
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STYLES[level]}`}
      title={`Extraction confidence: ${Math.round(confidence * 100)}%`}
    >
      {LABEL[level]} · {Math.round(confidence * 100)}%
    </span>
  );
}
