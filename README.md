# TRB Chemedica — AI Order Extraction

A web application that automates extraction of structured data from customer
purchase orders and order forms using **Claude Sonnet 4.6** (vision +
multimodal OCR). Upload many documents at once (PDF, JPG, PNG, TIFF), review and
correct the results, then export to Excel for ERP entry.

It reads printed text, scanned/low-quality documents, handwritten modifications,
handwritten delivery dates, and crossed-out values replaced by handwritten ones
— always preferring the most recent handwritten correction.

## Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Add your Anthropic API key**
   ```bash
   cp .env.local.example .env.local
   # then edit .env.local and set ANTHROPIC_API_KEY=sk-ant-...
   ```
   Get a key from <https://console.anthropic.com/>.

3. **Logo**
   The brand mark is built in code (`src/components/OrbLogo.tsx`) as `ORB` — a
   circular SVG emblem plus a serif wordmark. No image asset to manage.

4. **Run**
   ```bash
   npm run dev
   ```
   Open <http://localhost:3000>.

## How it works

```
Browser (upload N files)
  └─ POST /api/extract  (one request per document, 4 concurrent)
       ├─ PDF       → sent to Claude as a `document` block
       ├─ JPG/PNG   → sent as an `image` block
       └─ TIFF      → converted to PNG via sharp, then sent as `image`
       └─ Claude Sonnet 4.6 with a forced `extract_order` tool call → typed JSON
  └─ Results table (editable) → Export to Excel (ExcelJS, 2 sheets)
```

- **Reliable JSON:** extraction uses a forced tool call (`tool_choice`), so the
  model always returns a typed object — no brittle text-JSON parsing.
- **Confidence + readability:** every document gets a confidence score and an
  `is_readable` flag; unreadable scans are flagged in the table.
- **Manual correction:** expand any row to edit document fields and order lines
  before exporting.

## Excel output

A **single sheet** ("Orders"), **one row per order**. Document-level columns
(file name, customer, document #, supplier code, delivery address, country,
delivery date, payment terms, currency, confidence, comments) come first, then
every product line is spread across columns — `Product 1 Name / SKU / Quantity /
Unit Price / Currency`, `Product 2 …`, etc. The number of product groups adapts
to the order with the most line items, so each order is fully contained on one
row.

## Tech stack

Next.js (App Router) · TypeScript · Tailwind CSS v4 · Anthropic SDK · ExcelJS ·
sharp. Deploy target: Vercel.

## Deploying to Vercel

```bash
npm i -g vercel       # if not installed
vercel                # link & deploy a preview
vercel --prod         # production
```
Set `ANTHROPIC_API_KEY` as an environment variable in the Vercel project
settings (or `vercel env add ANTHROPIC_API_KEY`).

## Configuration

| Variable            | Default            | Purpose                          |
| ------------------- | ------------------ | -------------------------------- |
| `ANTHROPIC_API_KEY` | — (required)       | Anthropic API key                |
| `ANTHROPIC_MODEL`   | `claude-sonnet-4-6`| Override the extraction model    |

## Notes & limits

- Per-document size limit: 32 MB (Claude PDF/image input ceiling).
- Word documents are not yet supported (PDF/JPG/PNG/TIFF only). Convert to PDF
  for now — see "Future enhancements" in `CLAUDE.md`.
- Files are processed in memory and never persisted to disk.
