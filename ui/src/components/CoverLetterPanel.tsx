type Props = {
  value: string;
  onChange: (value: string) => void;
  onDownload: (format: "pdf" | "docx") => void;
  usedOllama?: boolean;
  ollamaAvailable?: boolean;
  busy?: boolean;
};

export function CoverLetterPanel({
  value,
  onChange,
  onDownload,
  usedOllama = false,
  ollamaAvailable = false,
  busy = false,
}: Props) {
  return (
    <div className="rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Ön yazı</p>
          <p className="mt-1 text-sm text-muted">
            {usedOllama
              ? "Ollama ile yazıldı; yalnızca özgeçmişteki kanıtlar kullanıldı. İndirmeden önce düzenleyebilirsiniz."
              : ollamaAvailable
                ? "Ollama yanıt vermediği için kural motoru taslağı kullanıldı. Tekrar çalıştırmayı deneyin."
                : "Ollama kapalı — kural motoru taslağı. Daha akıcı anlatım için Ayarlar’dan Ollama’yı açın."}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!value.trim() || busy}
            onClick={() => onDownload("pdf")}
            className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-40"
          >
            PDF
          </button>
          <button
            type="button"
            disabled={!value.trim() || busy}
            onClick={() => onDownload("docx")}
            className="rounded-lg bg-ink px-3 py-2 text-sm text-white disabled:opacity-40"
          >
            DOCX
          </button>
        </div>
      </div>
      {usedOllama && (
        <p className="mt-3 text-xs text-success">Ön yazı Ollama ile üretildi.</p>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={16}
        className="mt-4 w-full rounded-lg border border-line px-3 py-2 font-mono text-xs leading-5"
      />
    </div>
  );
}
