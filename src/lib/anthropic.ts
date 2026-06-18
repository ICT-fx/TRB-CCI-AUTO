import Anthropic from "@anthropic-ai/sdk";
import { EXTRACT_ORDER_TOOL, EXTRACTION_SYSTEM_PROMPT } from "./schema";
import type { OrderExtraction } from "./types";

const MODEL = process.env.ANTHROPIC_MODEL ?? "claude-sonnet-4-6";

let client: Anthropic | null = null;

function getClient(): Anthropic {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error(
      "ANTHROPIC_API_KEY is not set. Copy .env.local.example to .env.local and add your key.",
    );
  }
  if (!client) {
    client = new Anthropic();
  }
  return client;
}

/** Anthropic-supported source for a document content block. */
export type DocumentSource =
  | { kind: "pdf"; base64: string }
  | { kind: "image"; mediaType: "image/png" | "image/jpeg"; base64: string };

function buildContentBlock(
  source: DocumentSource,
): Anthropic.ContentBlockParam {
  if (source.kind === "pdf") {
    return {
      type: "document",
      source: { type: "base64", media_type: "application/pdf", data: source.base64 },
    };
  }
  return {
    type: "image",
    source: { type: "base64", media_type: source.mediaType, data: source.base64 },
  };
}

/**
 * Send one document to Claude and return the structured extraction.
 * Uses a forced tool call so the result is always typed JSON.
 */
export async function extractOrder(source: DocumentSource): Promise<OrderExtraction> {
  const anthropic = getClient();

  const response = await anthropic.messages.create({
    model: MODEL,
    max_tokens: 8000,
    system: EXTRACTION_SYSTEM_PROMPT,
    tools: [EXTRACT_ORDER_TOOL],
    tool_choice: { type: "tool", name: "extract_order" },
    messages: [
      {
        role: "user",
        content: [
          buildContentBlock(source),
          {
            type: "text",
            text: "Extract all order information from this document using the extract_order tool.",
          },
        ],
      },
    ],
  });

  const toolUse = response.content.find(
    (block): block is Anthropic.ToolUseBlock => block.type === "tool_use",
  );

  if (!toolUse) {
    if (response.stop_reason === "refusal") {
      throw new Error("The request was declined by the safety system.");
    }
    throw new Error("Claude did not return structured data for this document.");
  }

  return normalize(toolUse.input as Partial<OrderExtraction>);
}

/** Defensive normalization so the UI always receives a well-formed object. */
function normalize(raw: Partial<OrderExtraction>): OrderExtraction {
  return {
    customer_name: raw.customer_name ?? null,
    document_number: raw.document_number ?? null,
    supplier_code: raw.supplier_code ?? null,
    delivery_address: raw.delivery_address ?? null,
    country: raw.country ?? null,
    requested_delivery_date: raw.requested_delivery_date ?? null,
    payment_terms_days:
      typeof raw.payment_terms_days === "number" ? raw.payment_terms_days : null,
    currency: raw.currency ?? null,
    comments: raw.comments ?? null,
    products: Array.isArray(raw.products)
      ? raw.products.map((p) => ({
          product_name: p?.product_name ?? null,
          sku: p?.sku ?? null,
          quantity: typeof p?.quantity === "number" ? p.quantity : null,
          unit_price: typeof p?.unit_price === "number" ? p.unit_price : null,
          currency: p?.currency ?? null,
        }))
      : [],
    confidence:
      typeof raw.confidence === "number"
        ? Math.max(0, Math.min(1, raw.confidence))
        : 0,
    is_readable: raw.is_readable !== false,
    quality_note: raw.quality_note ?? null,
  };
}
