"use client";

import { useCallback, useRef, useState } from "react";

const ACCEPT = ".pdf,.jpg,.jpeg,.png,.tif,.tiff";
const FORMATS = ["PDF", "JPG", "PNG", "TIFF"];

interface Props {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function UploadZone({ onFiles, disabled }: Props) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const dropped = Array.from(e.dataTransfer.files);
      if (dropped.length) onFiles(dropped);
    },
    [onFiles, disabled],
  );

  const handlePick = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const picked = Array.from(e.target.files ?? []);
      if (picked.length) onFiles(picked);
      e.target.value = ""; // allow re-selecting the same file
    },
    [onFiles],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && !disabled) {
          inputRef.current?.click();
        }
      }}
      className={[
        "group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed px-6 py-14 text-center transition-all duration-200",
        dragging
          ? "border-trb-blue bg-trb-blue-light scale-[0.997]"
          : "border-trb-line bg-trb-blue-tint/40 hover:border-trb-blue hover:bg-trb-blue-tint",
        disabled ? "cursor-not-allowed opacity-60" : "",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={handlePick}
      />

      <div
        className={[
          "mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-trb-line transition-transform duration-200",
          dragging ? "scale-110" : "group-hover:scale-105",
        ].join(" ")}
      >
        <svg
          className="h-7 w-7 text-trb-blue"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 16V4" />
          <path d="m6 10 6-6 6 6" />
          <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
        </svg>
      </div>

      <p className="text-lg font-semibold text-trb-ink">
        {dragging ? "Drop to start extracting" : "Drag & drop order documents"}
      </p>
      <p className="mt-1 text-sm text-trb-muted">
        or <span className="font-medium text-trb-blue">browse your files</span> ·
        multiple documents supported
      </p>

      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {FORMATS.map((f) => (
          <span
            key={f}
            className="rounded-md bg-white px-2.5 py-1 text-xs font-medium tracking-wide text-trb-muted ring-1 ring-inset ring-trb-line"
          >
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}
