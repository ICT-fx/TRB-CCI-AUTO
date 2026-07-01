# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **📖 Start here for the big picture:** [`docs/OVERVIEW.md`](docs/OVERVIEW.md) — what the
> tool does end-to-end, and where every data file / script / output lives. The repo has
> **two subsystems**: (A) this Next.js web app (`src/`, documented below) and (B) the
> **CCI Azure Function** (`cci-function/`) — the serverless pipeline that is **deployed in
> production** and where recent work happens. When the task is about the CCI pipeline,
> master data, "Clé 1", SKU correction, or Azure deployment, read `docs/OVERVIEW.md` first.

## Project

AI-powered order-document extraction for **TRB Chemedica** (Geneva). Office users
upload customer purchase orders (PDF / JPG / PNG / TIFF, up to 50 at a time),
**Claude Sonnet 4.6** reads them (printed, scanned, and handwritten — including
crossed-out values replaced by hand), the results are shown in an editable table,
and exported to a two-sheet `.xlsx` for ERP entry.

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server at http://localhost:3000
npm run build      # production build (run this to typecheck the whole app)
npm run start      # serve the production build
npm run lint       # next lint
```

There is no test suite yet. `npm run build` is the de-facto typecheck/CI gate.

Requires `ANTHROPIC_API_KEY` in `.env.local` (copy from `.env.local.example`).
The app throws a clear error at request time if it is missing.

## Architecture

The flow is **one HTTP request per document**, with the client running a bounded
concurrency pool so 1 file and 50 files behave the same way.

- **`src/hooks/useExtraction.ts`** — the heart of the client. Owns the
  `ProcessedFile[]` state machine (`queued → processing → done | error`), runs a
  pool of `CONCURRENCY` (4) workers, and holds raw `File` objects in a `useRef`
  map (kept out of React state). `updateData` applies manual corrections in place.
- **`src/app/api/extract/route.ts`** — Node runtime (needs `sharp` + the SDK).
  Accepts one file via `multipart/form-data`, detects type, **converts TIFF→PNG
  with `sharp`** (Claude vision rejects TIFF), and builds the right content block
  (PDF → `document`, image → `image`).
- **`src/lib/anthropic.ts`** — the single Claude call. Uses a **forced tool call**
  (`tool_choice: { type: "tool", name: "extract_order" }`) so the response is
  always a typed `tool_use` block. `normalize()` guarantees a well-formed object
  reaches the UI regardless of model output.
- **`src/lib/schema.ts`** — the system prompt and the `extract_order` tool's JSON
  schema. **This is where extraction behavior lives** — edit the prompt rules and
  the schema together when changing what gets extracted.
- **`src/lib/excel.ts`** — client-side ExcelJS workbook (Sheet 1 "Orders" per
  document, Sheet 2 "Order Lines" per product) + browser download.
- **`src/lib/types.ts`** — `OrderExtraction` is the contract shared by the schema,
  the API, the table, and the Excel export. Changing a field means touching all
  four; start here.

### Why these choices

- **Tool call, not "return JSON":** forcing a tool call removes brittle text
  parsing and lets fields be `null` cleanly. The schema uses non-strict types
  (`["string","null"]`) so the model can omit unknowns per the prompt rules.
- **Per-document requests + client pool:** isolates failures (one bad scan
  doesn't sink the batch), enables per-document status/retry, and keeps each
  request well under the function timeout.

## Conventions

- Path alias `@/*` → `src/*`.
- Tailwind **v4** (CSS-first). The palette is defined in `src/app/globals.css`
  under `@theme` (`--color-trb-blue` and friends, derived from the logo). Use the
  `trb-*` color utilities; don't hardcode hex in components.
- Server-only code (`sharp`, the Anthropic SDK, the API key) must stay inside
  `src/app/api/**` or `src/lib/anthropic.ts`. Never import them into client
  components.
- The model id is centralized in `src/lib/anthropic.ts` (`ANTHROPIC_MODEL` env
  override). Don't scatter model strings.

## Extending

The architecture is intentionally modular for the planned roadmap (ERP / SAP /
Dynamics integration, email-inbox monitoring, supplier validation, product
catalog matching, confidence dashboard, human-review workflow). New back-end
integrations should consume `OrderExtraction` and live behind their own API
routes rather than expanding the extraction route.
