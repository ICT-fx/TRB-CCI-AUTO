// Shared data shapes for the order-extraction pipeline.
// These mirror the JSON schema sent to Claude (see schema.ts) plus client-side
// processing state.

export interface ProductLine {
  product_name: string | null;
  sku: string | null;
  quantity: number | null;
  unit_price: number | null;
  currency: string | null;
}

/** The structured result Claude returns for a single document. */
export interface OrderExtraction {
  customer_name: string | null;
  document_number: string | null;
  supplier_code: string | null;
  delivery_address: string | null;
  country: string | null;
  requested_delivery_date: string | null;
  payment_terms_days: number | null;
  currency: string | null;
  comments: string | null;
  products: ProductLine[];
  /** Overall extraction confidence, 0..1. */
  confidence: number;
  /** false when the document is too poor / unreadable to extract reliably. */
  is_readable: boolean;
  /** Free-text note from Claude about quality issues or ambiguities. */
  quality_note: string | null;
}

export type ProcessingStatus =
  | "queued"
  | "processing"
  | "done"
  | "error";

/** One uploaded document and its processing lifecycle on the client. */
export interface ProcessedFile {
  id: string;
  fileName: string;
  sizeBytes: number;
  status: ProcessingStatus;
  /** Populated when status === "done". User edits mutate this in place. */
  data: OrderExtraction | null;
  /** Populated when status === "error". */
  error: string | null;
}

export interface ExtractApiResponse {
  data?: OrderExtraction;
  error?: string;
}
