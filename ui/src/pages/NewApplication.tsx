import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { CoverLetterPanel } from "../components/CoverLetterPanel";
import { ExportOverlay, useExportDownload } from "../components/ExportDownload";
import { ResumePreview } from "../components/ResumePreview";
import { ScorePanel } from "../components/ScorePanel";
import type { Profile, RunResponse, TemplateName } from "../types";
import { TEMPLATE_LABEL } from "../types";

export function NewApplication() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileId, setProfileId] = useState("");
  const [jobText, setJobText] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [template, setTemplate] = useState<TemplateName>("classic");
  const [useOllama, setUseOllama] = useState(false);
  const [ollama, setOllama] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RunResponse | null>(null);
  const [letter, setLetter] = useState("");
  const { exportState, runExport } = useExportDownload();

  useEffect(() => {
    void (async () => {
      const [list, settings] = await Promise.all([api.profiles(), api.settings()]);
      setProfiles(list);
      if (list[0]) setProfileId(list[0].id);
      setTemplate(settings.default_template);
      setOllama(settings.ollama_available);
    })();
  }, []);

  const tailor = result?.result;

  async function run() {
    setBusy(true);
    setError("");
    try {
      const body = await api.run({
        profile_id: profileId,
        job_text: jobText,
        company,
        role,
        template,
        use_ollama: useOllama,
        save: true,
      });
      setResult(body);
      setLetter(body.result.cover_letter || "");
      setCompany(body.job.company);
      setRole(body.job.title);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Çalıştırılamadı");
    } finally {
      setBusy(false);
    }
  }

  async function download(format: "pdf" | "docx") {
    if (!tailor) return;
    await runExport({
      format,
      label: format === "pdf" ? "PDF" : "DOCX",
      filename: `resume-${template}.${format}`,
      fetchBlob: () => api.exportBlob(tailor.resume, template, format, tailor.language),
    });
  }

  async function downloadCover(format: "pdf" | "docx") {
    if (!letter.trim()) return;
    await runExport({
      format,
      label: format === "pdf" ? "Ön yazı PDF" : "Ön yazı DOCX",
      filename: `cover-letter.${format}`,
      fetchBlob: () => api.exportCoverBlob(letter, format),
    });
  }

  const missing = useMemo(
    () => (tailor ? tailor.match.gaps.filter((g) => !g.in_resume) : []),
    [tailor],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <ExportOverlay state={exportState} />
      <h1 className="text-[30px] font-semibold tracking-tight">Yeni başvuru</h1>
      <p className="mt-1 text-sm text-muted">
        İlanı yapıştırın. Motor uydurma yapmadan, mevcut kanıtlardan ATS uyumlu bir CV ve ön yazı üretir.
      </p>

      <div className="mt-6 grid gap-4 lg:grid-cols-12">
        <section className="rounded-card border border-line bg-white p-5 shadow-card lg:col-span-5">
          <label className="text-xs font-medium text-muted">Master CV</label>
          <select
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            className="mt-1 h-10 w-full rounded-lg border border-line px-3 text-sm"
          >
            {profiles.length === 0 && <option value="">Önce Master CV yükleyin</option>}
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted">Şirket</label>
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="mt-1 h-10 w-full rounded-lg border border-line px-3 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted">Rol</label>
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="mt-1 h-10 w-full rounded-lg border border-line px-3 text-sm"
              />
            </div>
          </div>
          <label className="mt-4 block text-xs font-medium text-muted">İş ilanı</label>
          <textarea
            value={jobText}
            onChange={(e) => setJobText(e.target.value)}
            rows={14}
            placeholder="İlan metnini buraya yapıştırın…"
            className="mt-1 w-full rounded-lg border border-line px-3 py-2 font-mono text-xs leading-5"
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={useOllama}
                disabled={!ollama}
                onChange={(e) => setUseOllama(e.target.checked)}
              />
              Ollama ile CV cümle cilası {ollama ? "" : "(kapalı)"}
            </label>
            <p className="basis-full text-[11px] text-muted">
              Ön yazı, Ollama açıksa her zaman yapay zekâ ile yazılır (CV kutusundan bağımsız).
            </p>
            <button
              type="button"
              disabled={!profileId || jobText.trim().length < 40 || busy}
              onClick={() => void run()}
              className="ml-auto h-10 rounded-lg bg-primary px-4 text-sm font-medium text-white disabled:opacity-40"
            >
              {busy ? "İşleniyor…" : "Analiz et ve güncelle"}
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        </section>

        <section className="lg:col-span-7 space-y-4">
          <div className="flex gap-2">
            {(Object.keys(TEMPLATE_LABEL) as TemplateName[]).map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => setTemplate(id)}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  template === id ? "border-ink bg-ink text-white" : "border-line bg-white text-ink"
                }`}
              >
                {TEMPLATE_LABEL[id]}
              </button>
            ))}
          </div>

          {tailor ? (
            <>
              <ScorePanel scores={tailor.scores} baseline={tailor.baseline_scores} />
              <div className="rounded-card border border-line bg-white p-5 shadow-card">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Eksik yetenekler</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {missing.length === 0 && <span className="text-sm text-success">Kritik boşluk yok</span>}
                  {missing.map((gap) => (
                    <span key={gap.skill} className="rounded-full bg-red-50 px-2.5 py-1 text-xs text-danger">
                      {gap.skill}
                    </span>
                  ))}
                </div>
                {tailor.diff.length > 0 && (
                  <ul className="mt-4 space-y-2 border-t border-line pt-4">
                    {tailor.diff.slice(0, 8).map((change, i) => (
                      <li key={i} className="text-xs">
                        <span className="font-medium text-ink">{change.path}</span>
                        <span className="text-muted"> · {change.kind}</span>
                        {change.after && <p className="mt-0.5 text-ink">{change.after}</p>}
                      </li>
                    ))}
                  </ul>
                )}
                {tailor.used_ollama && (
                  <p className="mt-3 text-xs text-success">Ollama, mevcut kanıtları koruyarak cümleleri cilaladı.</p>
                )}
                {tailor.ollama_rolled_back && (
                  <p className="mt-3 text-xs text-warning">
                    Ollama cümleleri master CV kanıtlarıyla örtüşmediği için kural motoruna dönüldü. Uydurma madde eklenmedi.
                  </p>
                )}
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    disabled={!!exportState}
                    onClick={() => void download("pdf")}
                    className="rounded-lg border border-line px-3 py-2 text-sm disabled:opacity-40"
                  >
                    PDF indir
                  </button>
                  <button
                    type="button"
                    disabled={!!exportState}
                    onClick={() => void download("docx")}
                    className="rounded-lg bg-ink px-3 py-2 text-sm text-white disabled:opacity-40"
                  >
                    DOCX indir (ATS önerilen)
                  </button>
                </div>
              </div>
              <div className="overflow-auto rounded-card border border-line bg-canvas p-6">
                <ResumePreview resume={tailor.resume} template={template} language={tailor.language} />
              </div>
              <CoverLetterPanel
                value={letter}
                onChange={setLetter}
                onDownload={(format) => void downloadCover(format)}
                usedOllama={!!tailor.cover_used_ollama}
                ollamaAvailable={ollama}
                busy={!!exportState}
              />
            </>
          ) : (
            <div className="rounded-card border border-dashed border-line bg-white p-12 text-center text-sm text-muted">
              İlanı yapıştırıp çalıştırın. Skorlar, diff, önizleme ve ön yazı burada görünür.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
