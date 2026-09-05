import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { Application, AppStatus } from "../types";
import { STATUS_LABEL } from "../types";

export function Dashboard() {
  const [apps, setApps] = useState<Application[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<AppStatus | "all">("all");
  const [error, setError] = useState("");

  async function load() {
    try {
      setApps(await api.applications());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Yüklenemedi");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const filtered = apps.filter((app) => {
    const hay = `${app.company} ${app.role}`.toLowerCase();
    const q = query.toLowerCase();
    const okQ = !q || hay.includes(q);
    const okS = status === "all" || app.status === status;
    return okQ && okS;
  });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-[30px] font-semibold tracking-tight">Başvurular</h1>
          <p className="mt-1 text-sm text-muted">Geçmiş tailor çıktıları bu makinede, SQLite içinde durur.</p>
        </div>
        <Link
          to="/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
        >
          Yeni başvuru
        </Link>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Şirket veya rol ara"
          className="h-10 w-72 rounded-lg border border-line bg-white px-3 text-sm"
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as AppStatus | "all")}
          className="h-10 rounded-lg border border-line bg-white px-3 text-sm"
        >
          <option value="all">Tüm durumlar</option>
          {Object.entries(STATUS_LABEL).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-6 overflow-hidden rounded-card border border-line bg-white shadow-card">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-canvas/80 text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Şirket</th>
              <th className="px-4 py-3 font-medium">Rol</th>
              <th className="px-4 py-3 font-medium">Durum</th>
              <th className="px-4 py-3 font-medium">ATS</th>
              <th className="px-4 py-3 font-medium">Güncelleme</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-16 text-center text-sm text-muted">
                  Henüz başvuru yok. Master CV yükleyip bir ilan yapıştırın.
                </td>
              </tr>
            )}
            {filtered.map((app) => (
              <tr key={app.id} className="border-b border-line last:border-0 hover:bg-canvas/60">
                <td className="px-4 py-3">
                  <Link to={`/applications/${app.id}`} className="font-medium text-ink hover:text-primary">
                    {app.company || "İsimsiz şirket"}
                  </Link>
                </td>
                <td className="px-4 py-3 text-muted">{app.role || "—"}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={app.status} />
                </td>
                <td className="px-4 py-3 font-medium">
                  <DashboardAts app={app} />
                </td>
                <td className="px-4 py-3 text-muted">
                  {new Date(app.updated_at).toLocaleString("tr-TR")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DashboardAts({ app }: { app: Application }) {
  const from = app.baseline_ats;
  const to = app.tailored_ats ?? app.overall_score;
  if (to == null) return "—";
  if (from == null) return <>{Math.round(to)}</>;
  return (
    <span>
      {Math.round(from)}
      <span className="mx-1 text-muted">→</span>
      {Math.round(to)}
    </span>
  );
}
