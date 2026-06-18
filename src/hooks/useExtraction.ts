"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type {
  ExtractApiResponse,
  OrderExtraction,
  ProcessedFile,
} from "@/lib/types";

// Process at most this many documents concurrently. A single global queue feeds
// a fixed pool of workers, so you can keep adding documents at any time — newly
// dropped files are appended and picked up as soon as a worker is free.
const CONCURRENCY = 4;

const ACCEPTED = /\.(pdf|jpe?g|png|tiff?)$/i;

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useExtraction() {
  const [files, setFiles] = useState<ProcessedFile[]>([]);

  // Raw File objects + the work queue + active-worker count live in refs so the
  // pump loop never reads stale state and concurrency is capped globally.
  const rawFiles = useRef<Map<string, File>>(new Map());
  const queue = useRef<string[]>([]);
  const active = useRef(0);

  const patch = useCallback((id: string, update: Partial<ProcessedFile>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...update } : f)));
  }, []);

  const processOne = useCallback(
    async (id: string) => {
      const raw = rawFiles.current.get(id);
      if (!raw) return;
      patch(id, { status: "processing", error: null });
      try {
        const form = new FormData();
        form.append("file", raw);
        const res = await fetch("/api/extract", { method: "POST", body: form });
        const json = (await res.json()) as ExtractApiResponse;
        if (!res.ok || json.error || !json.data) {
          throw new Error(json.error ?? `Request failed (${res.status}).`);
        }
        patch(id, { status: "done", data: json.data });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Extraction failed.";
        patch(id, { status: "error", error: message });
      }
    },
    [patch],
  );

  // Start as many workers as the queue and the concurrency budget allow.
  const pump = useCallback(() => {
    while (active.current < CONCURRENCY && queue.current.length > 0) {
      const id = queue.current.shift()!;
      active.current += 1;
      void processOne(id).finally(() => {
        active.current -= 1;
        pump();
      });
    }
  }, [processOne]);

  /** Add files and enqueue them — safe to call at any time, even mid-processing. */
  const addFiles = useCallback(
    (incoming: File[]) => {
      const accepted = incoming.filter((f) => ACCEPTED.test(f.name));
      if (accepted.length === 0) return;

      const entries: ProcessedFile[] = accepted.map((f) => {
        const id = makeId();
        rawFiles.current.set(id, f);
        return {
          id,
          fileName: f.name,
          sizeBytes: f.size,
          status: "queued",
          data: null,
          error: null,
        };
      });

      setFiles((prev) => [...prev, ...entries]);
      queue.current.push(...entries.map((e) => e.id));
      pump();
    },
    [pump],
  );

  const retry = useCallback(
    (id: string) => {
      if (!rawFiles.current.has(id)) return;
      patch(id, { status: "queued", error: null });
      queue.current.push(id);
      pump();
    },
    [patch, pump],
  );

  const removeFile = useCallback((id: string) => {
    rawFiles.current.delete(id);
    queue.current = queue.current.filter((q) => q !== id);
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    rawFiles.current.clear();
    queue.current = [];
    setFiles([]);
  }, []);

  /** Apply a manual correction to a completed result before export. */
  const updateData = useCallback(
    (id: string, data: OrderExtraction) => {
      patch(id, { data });
    },
    [patch],
  );

  // Derived from state so it always reflects what's really in flight.
  const isProcessing = useMemo(
    () => files.some((f) => f.status === "queued" || f.status === "processing"),
    [files],
  );

  return {
    files,
    isProcessing,
    addFiles,
    retry,
    removeFile,
    clearAll,
    updateData,
  };
}
