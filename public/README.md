# public/

The TRB Chemedica logo lives here as **`trb-logo.webp`**.

The header (`src/components/Header.tsx`) renders `/trb-logo.webp`. If the file is
absent, it falls back to a styled "TRB" wordmark, so the app still runs without
it. To swap the logo, replace this file (keep the name, or update the `src` in
`Header.tsx`).

The application color palette is derived from the logo's blue and is defined in
`src/app/globals.css` under the `@theme` block (`--color-trb-blue` etc.).
