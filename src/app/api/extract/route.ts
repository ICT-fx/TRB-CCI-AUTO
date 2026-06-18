import { NextResponse } from "next/server";
import sharp from "sharp";
import { extractOrder, type DocumentSource } from "@/lib/anthropic";
import type { ExtractApiResponse } from "@/lib/types";

// sharp + the Anthropic SDK need the Node.js runtime, not Edge.
export const runtime = "nodejs";
// Allow long-running vision calls on poor scans.
export const maxDuration = 120;

const MAX_BYTES = 32 * 1024 * 1024; // 32 MB per document

function detectKind(fileName: string, mimeType: string):
  | "pdf"
  | "png"
  | "jpeg"
  | "tiff"
  | null {
  const name = fileName.toLowerCase();
  const mime = mimeType.toLowerCase();
  if (mime.includes("pdf") || name.endsWith(".pdf")) return "pdf";
  if (mime.includes("png") || name.endsWith(".png")) return "png";
  if (mime.includes("jpeg") || mime.includes("jpg") || /\.jpe?g$/.test(name))
    return "jpeg";
  if (mime.includes("tiff") || /\.tiff?$/.test(name)) return "tiff";
  return null;
}

export async function POST(request: Request): Promise<NextResponse<ExtractApiResponse>> {
  try {
    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json({ error: "No file provided." }, { status: 400 });
    }
    if (file.size > MAX_BYTES) {
      return NextResponse.json(
        { error: "File exceeds the 32 MB limit." },
        { status: 413 },
      );
    }

    const kind = detectKind(file.name, file.type);
    if (!kind) {
      return NextResponse.json(
        { error: "Unsupported file type. Use PDF, JPG, PNG or TIFF." },
        { status: 415 },
      );
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    let source: DocumentSource;

    if (kind === "pdf") {
      source = { kind: "pdf", base64: buffer.toString("base64") };
    } else if (kind === "tiff") {
      // Claude vision does not accept TIFF — convert to PNG server-side.
      const png = await sharp(buffer).png().toBuffer();
      source = { kind: "image", mediaType: "image/png", base64: png.toString("base64") };
    } else {
      source = {
        kind: "image",
        mediaType: kind === "png" ? "image/png" : "image/jpeg",
        base64: buffer.toString("base64"),
      };
    }

    const data = await extractOrder(source);
    return NextResponse.json({ data });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Unexpected error during extraction.";
    console.error("[extract] failed:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
