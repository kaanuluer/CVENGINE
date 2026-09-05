import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { CoverLetterPanel } from "../components/CoverLetterPanel";
import { ExportOverlay, useExportDownload } from "../components/ExportDownload";
import { ResumePreview } from "../components/ResumePreview";
import { ScorePanel } from "../components/ScorePanel";
import { StatusBadge } from "../components/StatusBadge";
import type { Application, AppStatus, TemplateName } from "../types";
import { STATUS_LABEL, TEMPLATE_LABEL } from "../types";

export function ApplicationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [app, setApp] = useState<Application | null>(null);
  const [template, setTemplate] = useState<TemplateName>("classic");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [letter, setLetter] = useState("");
  const [ollama, setOllama] = useState(false);
  const { exportState, runExport } = useExportDownload();

  async function load() {
    if (!id) return;
    const [row, settings] = await Promise.all([api.application(id), api.settings()]);
    setApp(row);
    setOllama(settings.ollama_available);
    if (row.latest) {
      setTemplate(row.latest.template);
      setLetter(row.latest.cover_letter || "");
    }
  }

  useEffect(() => {
    void load().catch((err) => setError(err.message));
  }, [id]);

  if (!app) {
    return <div className="p-10 text-sm text-muted">{error || "Yükleniyor…"}</div>;
  }

  const latest = app.latest;
  const companyName = app.company;

  async function retarget() {
    if (!id) return;
    setBusy(true);
    try {
      await api.retarget(id, template, false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yeniden üretim başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function download(format: "pdf" | "docx") {
    if (!latest) return;
    await runExport({
      format,
      label: format === "pdf" ? "PDF" : "DOCX",
      filename: `${companyName || "resume"}-${template}.${format}`,
      fetchBlob: () => api.exportBlob(latest.resume, template, format, latest.language || "en"),
    });
  }

  async function downloadCover(format: "pdf" | "docx") {
    if (!letter.trim()) return;
    await runExport({
      format,
      label: format === "pdf" ? "Ön yazı PDF" : "Ön yazı DOCX",
      filename: `${companyName || "cover"}-letter.${format}`,
      fetchBlob: () => api.exportCoverBlob(letter, format),
    });
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <ExportOverlay state={exportState} />
      <Link to="/" className="text-sm text-muted hover:text-ink">
        ← Dashboard
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-semibold tracking-tight">{app.company || "Başvuru"}</h1>
          <p className="mt-1 text-sm text-muted">{app.role}</p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={app.status} />
          <select
            value={app.status}
            onChange={(e) => {
              const status = e.target.value as AppStatus;
              void api.patchApplication(app.id, { status }).then(setApp);
            }}
            className="h-10 rounded-lg border border-line px-3 text-sm"
          >
            {Object.entries(STATUS_LABEL).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="h-10 rounded-lg border border-danger px-3 text-sm text-danger"
            onClick={() => {
              if (confirm("Bu başvuruyu sil?")) {
                void api.deleteApplication(app.id).then(() => navigate("/"));
              }
            }}
          >
            Sil
          </button>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {(Object.keys(TEMPLATE_LABEL) as TemplateName[]).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setTemplate(id)}
            className={`rounded-lg border px-3 py-2 text-sm ${
              template === id ? "border-ink bg-ink text-white" : "border-line bg-white"
            }`}
          >
            {TEMPLATE_LABEL[id]}
          </button>
        ))}
        <button
          type="button"
          disabled={busy}
          onClick={() => void retarget()}
          className="rounded-lg bg-primary px-3 py-2 text-sm text-white disabled:opacity-40"
        >
          {busy ? "Üretiliyor…" : "Bu şablonla yeniden üret"}
        </button>
        {latest && (
          <>
            <button
              type="button"
              disabled={!!exportState}
              onClick={() => void download("pdf")}
              className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-40"
            >
              PDF
            </button>
            <button
              type="button"
              disabled={!!exportState}
              onClick={() => void download("docx")}
              className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-40"
            >
              DOCX
            </button>
          </>
        )}
      </div>

      {latest && (
        <div className="mt-6 grid gap-4 lg:grid-cols-12">
          <div className="lg:col-span-5 space-y-4">
            <ScorePanel scores={latest.scores} baseline={latest.baseline_scores} />
            <div className="rounded-card border border-line bg-white p-5 shadow-card">
              <p className="text-xs font-medium uppercase tracking-wide text-muted">Diff</p>
              <ul className="mt-3 space-y-2">
                {latest.diff.map((change, i) => (
                  <li key={i} className="text-xs">
                    <span className="font-medium">{change.path}</span>
                    <span className="text-muted"> · {change.kind}</span>
                    {change.after && <p className="mt-1 text-ink">{change.after}</p>}
                  </li>
                ))}
                {latest.diff.length === 0 && <li className="text-sm text-muted">İçerik değişmedi, yalnızca sıralama.</li>}
              </ul>
            </div>
            <CoverLetterPanel
              value={letter}
              onChange={setLetter}
              onDownload={(format) => void downloadCover(format)}
              usedOllama={!!latest.cover_used_ollama}
              ollamaAvailable={ollama}
              busy={!!exportState}
            />
          </div>
          <div className="lg:col-span-7 overflow-auto rounded-card border border-line bg-canvas p-6">
            <ResumePreview resume={latest.resume} template={template} language={latest.language || "en"} />
          </div>
        </div>
      )}
    </div>
  );
}
