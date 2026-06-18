import type Anthropic from "@anthropic-ai/sdk";

// The system prompt + tool definition Claude uses to extract orders.
//
// We force a single tool call (`tool_choice: { type: "tool", name: ... }`) so the
// response always arrives as a typed `tool_use` block — far more reliable than
// asking the model to "return only JSON" as text and parsing it.

export const EXTRACTION_SYSTEM_PROMPT = `You are an expert pharmaceutical order processing assistant working for TRB Chemedica (Geneva, Switzerland).

Analyze the provided customer order document and extract all available information into the "extract_order" tool.

Important rules:
1. If a value has been crossed out and rewritten by hand, ALWAYS use the most recent handwritten corrected value. Example: if quantity "50" is crossed out and "75" is written by hand nearby, extract 75.
2. Carefully inspect handwritten notes, handwritten delivery dates, and handwritten quantity corrections.
3. Extract every product line found in the document — a single document may contain many products.
4. Never invent information. If a field cannot be identified with reasonable confidence, return null for it.
5. The supplier code is usually a 6-digit number. It may be labelled Supplier Code, Vendor Code, Supplier ID, or Account Number. Extract digits only.
6. The SKU / article code is usually a 4-digit internal product reference. Extract it when present.
7. Payment terms must be extracted as the NUMBER OF DAYS only (e.g. "Net 30", "30 days", "60 jours" -> 30, 30, 60).
8. requested_delivery_date should be returned in ISO format YYYY-MM-DD when the date is unambiguous; otherwise return the date exactly as written.
9. quantity must be the FINAL quantity after any handwritten corrections.
10. Summarize all customer remarks, delivery instructions, urgent requests, packaging requests and handwritten notes concisely into the "comments" field.
11. Documents may mix languages (e.g. French, German, English, Italian). Handle all of them.
12. Set "is_readable" to false only if the document is so poor that extraction is unreliable.
13. Set "confidence" between 0 and 1 reflecting your overall confidence in the extraction.`;

const productItemSchema = {
  type: "object",
  properties: {
    product_name: {
      type: ["string", "null"],
      description: "Product / article name if available, otherwise null.",
    },
    sku: {
      type: ["string", "null"],
      description: "SKU / article code, usually 4 digits. null if not present.",
    },
    quantity: {
      type: ["number", "null"],
      description: "Final ordered quantity after handwritten corrections. null if absent.",
    },
    unit_price: {
      type: ["number", "null"],
      description: "Unit price as a number if available, otherwise null.",
    },
    currency: {
      type: ["string", "null"],
      description: "Currency for this line if specified (e.g. EUR, CHF, USD).",
    },
  },
  required: ["product_name", "sku", "quantity", "unit_price", "currency"],
} as const;

export const EXTRACT_ORDER_TOOL: Anthropic.Tool = {
  name: "extract_order",
  description:
    "Record the structured data extracted from a single customer purchase order or order form.",
  input_schema: {
    type: "object",
    properties: {
      customer_name: { type: ["string", "null"], description: "Customer / company name." },
      document_number: {
        type: ["string", "null"],
        description: "Order / document / PO number.",
      },
      supplier_code: {
        type: ["string", "null"],
        description:
          "Supplier code (usually 6 digits). May appear as Vendor Code, Supplier ID, Account Number.",
      },
      delivery_address: {
        type: ["string", "null"],
        description: "Full delivery address as a single string.",
      },
      country: { type: ["string", "null"], description: "Delivery country." },
      requested_delivery_date: {
        type: ["string", "null"],
        description: "Requested delivery date (ISO YYYY-MM-DD when unambiguous).",
      },
      payment_terms_days: {
        type: ["number", "null"],
        description: "Payment terms in number of days only (e.g. 30, 45, 60).",
      },
      currency: { type: ["string", "null"], description: "Document-level currency." },
      comments: {
        type: ["string", "null"],
        description:
          "Concise summary of delivery instructions, remarks, urgent/packaging requests and handwritten notes.",
      },
      products: {
        type: "array",
        description: "Every product line found in the document.",
        items: productItemSchema,
      },
      confidence: {
        type: "number",
        description: "Overall extraction confidence between 0 and 1.",
      },
      is_readable: {
        type: "boolean",
        description: "false if the document is too poor to extract reliably.",
      },
      quality_note: {
        type: ["string", "null"],
        description: "Short note about any quality issues or ambiguities, else null.",
      },
    },
    required: [
      "customer_name",
      "document_number",
      "supplier_code",
      "delivery_address",
      "country",
      "requested_delivery_date",
      "payment_terms_days",
      "currency",
      "comments",
      "products",
      "confidence",
      "is_readable",
      "quality_note",
    ],
  },
};
