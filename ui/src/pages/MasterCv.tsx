import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ResumeEditor } from "../components/ResumeEditor";
import { ResumePreview } from "../components/ResumePreview";
import {
  emptyResume,
  type JobSuggestion,
  type Profile,
  type Resume,
  type ResumeLanguage,
} from "../types";

export function MasterCv() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [active, setActive] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<JobSuggestion[]>([]);
  const [suggestSource, setSuggestSource] = useState<"ollama" | "heuristic" | "">("");
  const [suggestMessage, setSuggestMessage] = useState("");
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [suggestError, setSuggestError] = useState("");

  const fetchSuggestions = useCallback(async (profile: Profile) => {
    if (!hasMeaningfulResume(profile.resume)) {
      setSuggestions([]);
      setSuggestSource("");
      setSuggestMessage("");
      setSuggestError("");
      return;
    }
    setSuggestBusy(true);
    setSuggestError("");
    try {
      const res = await api.jobSuggestions(profile.id);
      setSuggestions(res.suggestions || []);
      setSuggestSource(res.source);
      setSuggestMessage(res.message || "");
    } catch (err) {
      setSuggestError(err instanceof Error ? err.message : "Öneriler alınamadı");
      setSuggestions([]);
    } finally {
      setSuggestBusy(false);
    }
  }, []);

  async function load(selectId?: string) {
    const list = await api.profiles();
    setProfiles(list);
    const next = (selectId && list.find((p) => p.id === selectId)) || list[0] || null;
    setActive(next);
    if (!next) {
      setSuggestions([]);
      setSuggestSource("");
    }
  }

  useEffect(() => {
    void load().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!active) return;
    void fetchSuggestions(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.id]);

  async function onUpload(file: File) {
    setError("");
    setBusy(true);
    try {
      const profile = await api.parseProfile(file);
      await load(profile.id);
      setSaved("Yüklendi. Satırları kontrol edip kaydedin.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yükleme başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function createBlank() {
    setBusy(true);
    try {
      const profile = await api.createProfile("Yeni profil", emptyResume());
      await load(profile.id);
      setSaved("Boş profil oluşturuldu.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Oluşturulamadı");
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!active) return;
    setBusy(true);
    try {
      const display = active.resume.basics.name || active.name || "Master CV";
      const updated = await api.saveProfile(active.id, display, active.resume);
      setActive(updated);
      setSaved("Kaydedildi.");
      const list = await api.profiles();
      setProfiles(list);
      void fetchSuggestions(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!active || !confirm("Bu profil silinsin mi?")) return;
    await api.deleteProfile(active.id);
    await load();
    setSaved("Profil silindi.");
  }

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[30px] font-semibold tracking-tight">Master CV</h1>
          <p className="mt-1 text-sm text-muted">
            Kendiniz yazın veya dosya yükleyin. İş, eğitim ve sertifika sayısı sınırsızdır.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => void createBlank()} className="rounded-lg border border-line bg-white px-4 py-2 text-sm">
            Sıfırdan yaz
          </button>
          <label className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white">
            PDF / DOCX / JSON yükle
            <input
              type="file"
              accept=".pdf,.docx,.json,.txt,.md"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void onUpload(file);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
      {error && <p className="mt-4 text-sm text-danger">{error}</p>}
      {saved && <p className="mt-4 text-sm text-success">{saved}</p>}

      <div className="mt-6 grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)_minmax(360px,440px)]">
        <aside className="h-fit rounded-card border border-line bg-white p-3 shadow-card">
          {profiles.length === 0 && <p className="p-3 text-sm text-muted">Profil yok. Sıfırdan yazın veya dosya yükleyin.</p>}
          {profiles.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setActive(p)}
              className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm ${
                active?.id === p.id ? "bg-ink text-white" : "hover:bg-canvas"
              }`}
            >
              {p.name || p.resume.basics.name || "İsimsiz"}
            </button>
          ))}
        </aside>

        {active ? (
          <>
            <section className="space-y-4">
              <div className="rounded-card border border-line bg-white p-5 shadow-card">
                <div className="mb-4 flex items-center justify-between gap-2">
                  <input
                    value={active.name}
                    onChange={(e) => setActive({ ...active, name: e.target.value })}
                    className="h-10 max-w-xs rounded-lg border border-line px-3 text-sm"
                    placeholder="Profil adı"
                  />
                  <div className="flex gap-2">
                    <button type="button" onClick={() => void remove()} className="h-10 rounded-lg px-3 text-sm text-danger">
                      Sil
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void save()}
                      className="h-10 rounded-lg bg-ink px-4 text-sm text-white disabled:opacity-40"
                    >
                      {busy ? "Kaydediliyor…" : "Kaydet"}
                    </button>
                  </div>
                </div>
                <ResumeEditor resume={active.resume} onChange={(resume) => setActive({ ...active, resume })} />
              </div>

              <section className="rounded-card border border-line bg-white p-5 shadow-card">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h2 className="text-base font-semibold tracking-tight">Önerilen iş türleri</h2>
                    <p className="mt-0.5 text-xs text-muted">
                      Master CV deneyiminize göre — uydurma unvan yok.
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={suggestBusy || !hasMeaningfulResume(active.resume)}
                    onClick={() => void fetchSuggestions(active)}
                    className="h-9 rounded-lg border border-line px-3 text-sm disabled:opacity-40"
                  >
                    {suggestBusy ? "Yükleniyor…" : "Yenile"}
                  </button>
                </div>
                {suggestBusy && suggestions.length === 0 && (
                  <p className="mt-3 text-sm text-muted">Öneriler hazırlanıyor…</p>
                )}
                {suggestError && <p className="mt-3 text-sm text-danger">{suggestError}</p>}
                {!suggestBusy && !suggestError && !hasMeaningfulResume(active.resume) && (
                  <p className="mt-3 text-sm text-muted">
                    Öneri için özet, unvan, iş deneyimi veya beceri ekleyin.
                  </p>
                )}
                {suggestMessage && (
                  <p className="mt-3 text-xs text-muted">
                    {suggestMessage}
                    {suggestSource === "heuristic" ? " (sezgisel)" : suggestSource === "ollama" ? " (Ollama)" : ""}
                  </p>
                )}
                {suggestions.length > 0 && (
                  <ul className="mt-4 space-y-3">
                    {suggestions.map((item) => (
                      <li key={item.title} className="border-t border-line pt-3 first:border-t-0 first:pt-0">
                        <p className="text-sm font-medium text-ink">{item.title}</p>
                        <p className="mt-0.5 text-xs leading-5 text-muted">{item.rationale}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </section>
            <div className="xl:sticky xl:top-20 h-fit overflow-auto rounded-card border border-line bg-canvas p-4">
              <ResumePreview resume={active.resume} template="classic" language={masterLanguage(active.resume)} />
            </div>
          </>
        ) : (
          <div className="rounded-card border border-dashed border-line bg-white p-16 text-center text-sm text-muted xl:col-span-2">
            Sıfırdan bir CV yazın veya mevcut dosyanızı yükleyin. Parser satırları birleştirir; siz düzeltirsiniz.
          </div>
        )}
      </div>
    </div>
  );
}

function hasMeaningfulResume(resume: Resume): boolean {
  if ((resume.basics.summary || "").trim().length > 20) return true;
  if ((resume.basics.label || "").trim().length > 2) return true;
  if ((resume.work || []).some((w) => (w.position || "").trim() || (w.highlights || []).length > 0)) return true;
  if ((resume.skills || []).some((s) => (s.keywords || []).length > 0)) return true;
  return false;
}

function masterLanguage(resume: Resume): ResumeLanguage {
  const blob = [
    resume.basics.summary,
    resume.basics.label,
    ...(resume.work ?? []).flatMap((work) => [work.position, ...work.highlights]),
  ].join(" ");
  return /[çğıöşüÇĞİÖŞÜ]/.test(blob) ? "tr" : "en";
}
