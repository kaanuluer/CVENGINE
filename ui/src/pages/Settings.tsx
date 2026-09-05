import { useEffect, useState } from "react";
import { api } from "../api";
import type { Settings, TemplateName } from "../types";

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    void api.settings().then(setSettings).catch((err) => setError(err.message));
  }, []);

  if (!settings) {
    return <div className="p-10 text-sm text-muted">{error || "Yükleniyor…"}</div>;
  }

  async function save() {
    if (!settings) return;
    const next = await api.saveSettings(settings);
    setSettings(next);
    setSaved("Ayarlar kaydedildi.");
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <h1 className="text-[30px] font-semibold tracking-tight">Ayarlar</h1>
      <p className="mt-1 text-sm text-muted">
        Tüm işlem localhost üzerindedir. Ön yazı Ollama açıksa her zaman yapay zekâ ile yazılır; CV
        cilası isteğe bağlıdır.
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
          <span className="text-xs font-medium text-muted">Ollama model</span>
          <input
            value={settings.ollama_model}
            onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
            className="mt-1 h-10 w-full rounded-lg border border-line px-3 font-mono text-sm"
          />
        </label>
        <p className="text-sm">
          Durum:{" "}
          <span className={settings.ollama_available ? "text-success" : "text-muted"}>
            {settings.ollama_available ? "Ollama erişilebilir" : "Ollama yok — deterministik motor aktif"}
          </span>
        </p>
        <button type="button" onClick={() => void save()} className="h-10 rounded-lg bg-ink px-4 text-sm text-white">
          Kaydet
        </button>
        {saved && <p className="text-sm text-success">{saved}</p>}
      </div>
    </div>
  );
}
