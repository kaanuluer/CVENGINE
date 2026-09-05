import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { OllamaStatus, Settings, TemplateName } from "../types";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [ollama, setOllama] = useState<OllamaStatus | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [probing, setProbing] = useState(false);

  const refreshOllama = useCallback(async (s: Settings, verify = true) => {
    setProbing(true);
    try {
      const status = await api.ollamaStatus({
        verify,
        url: s.ollama_url,
        model: s.ollama_model,
      });
      setOllama(status);
      if (status.selected) {
        setSettings((prev) => (prev ? { ...prev, ollama_model: status.selected } : prev));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ollama durumu alınamadı");
    } finally {
      setProbing(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const s = await api.settings();
        setSettings(s);
        await refreshOllama(s, true);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Yüklenemedi");
      }
    })();
  }, [refreshOllama]);

  if (!settings) {
    return <div className="p-10 text-sm text-muted">{error || "Yükleniyor…"}</div>;
  }

  async function save() {
    if (!settings) return;
    setError("");
    setSaved("");
    try {
      const next = await api.saveSettings(settings);
      const status = await api.ollamaStatus({
        verify: true,
        url: next.ollama_url,
        model: next.ollama_model,
      });
      setOllama(status);
      const model = status.selected || next.ollama_model;
      const synced =
        model !== next.ollama_model
          ? await api.saveSettings({ ...next, ollama_model: model })
          : next;
      setSettings({ ...synced, ollama_model: model });
      setSaved(
        status.healthy
          ? `Ayarlar kaydedildi. Aktif model: ${model}`
          : `Ayarlar kaydedildi. ${status.status_label_tr}${status.error ? ` — ${status.error}` : ""}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kayıt başarısız");
    }
  }

  const statusClass =
    ollama?.status === "model_ok"
      ? "text-success"
      : ollama?.status === "connected"
        ? "text-ink"
        : ollama?.status === "model_missing"
          ? "text-danger"
          : "text-muted";

  const models = ollama?.models?.length
    ? ollama.models
    : settings.ollama_model
      ? [settings.ollama_model]
      : [];

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-[30px] font-semibold tracking-tight">Ayarlar</h1>
      <p className="mt-1 text-sm text-muted">
        Tüm işlem localhost üzerindedir. Ön yazı Ollama açıksa her zaman yapay zekâ ile yazılır; CV
        cilası isteğe bağlıdır. Yalnızca yüklü ve çalışan modeller kullanılır.
      </p>

      <div className="mt-6 space-y-4 rounded-card border border-line bg-white p-6 shadow-card">
        <label className="block">
          <span className="text-xs font-medium text-muted">Varsayılan şablon</span>
          <select
            value={settings.default_template}
            onChange={(e) => setSettings({ ...settings, default_template: e.target.value as TemplateName })}
            className="mt-1 h-10 w-full rounded-lg border border-line px-3 text-sm"
          >
            <option value="classic">Classic ATS</option>
            <option value="executive">Executive</option>
            <option value="compact">Compact</option>
          </select>
        </label>
        <label className="block">
          <span className="text-xs font-medium text-muted">Ollama URL</span>
          <input
            value={settings.ollama_url}
            onChange={(e) => setSettings({ ...settings, ollama_url: e.target.value })}
            className="mt-1 h-10 w-full rounded-lg border border-line px-3 font-mono text-sm"
          />
        </label>
        <label className="block">
          <span className="text-xs font-medium text-muted">Ollama model (yüklü modeller)</span>
          <select
            value={models.includes(settings.ollama_model) ? settings.ollama_model : models[0] || ""}
            onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
            disabled={!models.length}
            className="mt-1 h-10 w-full rounded-lg border border-line px-3 font-mono text-sm disabled:opacity-50"
          >
            {!models.length && <option value="">Model yok — Ollama’da model indirin</option>}
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <p>
            Durum:{" "}
            <span className={statusClass}>
              {probing ? "Kontrol ediliyor…" : ollama?.status_label_tr || "Ollama kapalı"}
            </span>
            {ollama?.selected && ollama.status === "model_ok" && (
              <span className="text-muted"> ({ollama.selected})</span>
            )}
          </p>
          <button
            type="button"
            disabled={probing}
            onClick={() => void refreshOllama(settings, true)}
            className="h-8 rounded-lg border border-line px-3 text-xs disabled:opacity-40"
          >
            Yeniden kontrol et
          </button>
        </div>
        {ollama?.error && <p className="text-xs text-muted">{ollama.error}</p>}
        <button type="button" onClick={() => void save()} className="h-10 rounded-lg bg-ink px-4 text-sm text-white">
          Kaydet
        </button>
        {saved && <p className="text-sm text-success">{saved}</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>
    </div>
  );
}
