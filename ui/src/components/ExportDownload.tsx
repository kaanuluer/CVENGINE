import { useCallback, useState } from "react";
import { sleep, triggerDownload } from "../lib/download";

type Format = "pdf" | "docx";

type Phase = "preparing" | "ready" | "error";

type ExportState = {
  format: Format;
  label: string;
  phase: Phase;
  message?: string;
};

const MIN_PREPARE_MS = 1100;
const SUCCESS_HOLD_MS = 450;

/**
 * Runs a short prepare animation, then starts the file download.
 */
export function useExportDownload() {
  const [state, setState] = useState<ExportState | null>(null);

  const runExport = useCallback(
    async (opts: {
      format: Format;
      label?: string;
      filename: string;
      fetchBlob: () => Promise<Blob>;
    }) => {
      const label = opts.label ?? (opts.format === "pdf" ? "PDF" : "DOCX");
      setState({ format: opts.format, label, phase: "preparing" });
      const started = Date.now();
      try {
        const blob = await opts.fetchBlob();
        const wait = Math.max(0, MIN_PREPARE_MS - (Date.now() - started));
        if (wait) await sleep(wait);
        setState({ format: opts.format, label, phase: "ready" });
        triggerDownload(blob, opts.filename);
        await sleep(SUCCESS_HOLD_MS);
      } catch (err) {
        setState({
          format: opts.format,
          label,
          phase: "error",
          message: err instanceof Error ? err.message : "Export başarısız",
        });
        await sleep(1600);
      } finally {
        setState(null);
      }
    },
    [],
  );

  return { exportState: state, runExport };
}

export function ExportOverlay({ state }: { state: ExportState | null }) {
  if (!state) return null;
  const { format, label, phase, message } = state;
  const title =
    phase === "preparing"
      ? `${label} hazırlanıyor`
      : phase === "ready"
        ? "İndirme başladı"
        : "Bir sorun oluştu";
  const subtitle =
    phase === "preparing"
      ? "Dosya oluşturuluyor, birazdan indirilecek…"
      : phase === "ready"
        ? `${label} dosyanız indirilmeye başladı.`
        : message || "Tekrar deneyin.";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-4 backdrop-blur-[2px]"
      role="status"
      aria-live="polite"
    >
      <div className="export-card w-full max-w-sm rounded-card border border-line bg-white p-6 shadow-card">
        <div className="flex items-start gap-4">
          <div
            className={`export-icon flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${
              phase === "error" ? "bg-red-50 text-danger" : "bg-canvas text-ink"
            }`}
          >
            {phase === "preparing" ? (
              <span className="export-spinner" aria-hidden />
            ) : phase === "ready" ? (
              <CheckIcon />
            ) : (
              <AlertIcon />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold tracking-tight text-ink">{title}</p>
            <p className="mt-1 text-xs leading-5 text-muted">{subtitle}</p>
            {phase === "preparing" && (
              <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-canvas">
                <div className={`export-bar h-full rounded-full ${format === "pdf" ? "bg-primary" : "bg-ink"}`} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M5 12.5 9.5 17 19 7.5"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 8v5m0 3h.01M12 3 2.5 20h19L12 3Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
