import type {
  Application,
  AppStatus,
  JobSuggestionsResponse,
  OllamaStatus,
  Profile,
  Resume,
  RunResponse,
  Settings,
  TemplateName,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ ok: boolean; ollama: boolean }>("/api/health"),
  settings: () => request<Settings>("/api/settings"),
  ollamaStatus: (opts?: { verify?: boolean; url?: string; model?: string }) => {
    const verify = opts?.verify ?? true;
    const params = new URLSearchParams({ verify: verify ? "true" : "false" });
    if (opts?.url) params.set("url", opts.url);
    if (opts?.model) params.set("model", opts.model);
    return request<OllamaStatus>(`/api/settings/ollama?${params}`);
  },
  saveSettings: (body: Partial<Settings>) =>
    request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
  profiles: () => request<Profile[]>("/api/profiles"),
  profile: (id: string) => request<Profile>(`/api/profiles/${id}`),
  saveProfile: (id: string, name: string, resume: Resume) =>
    request<Profile>(`/api/profiles/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name, resume }),
    }),
  createProfile: (name: string, resume: Resume) =>
    request<Profile>("/api/profiles", { method: "POST", body: JSON.stringify({ name, resume }) }),
  deleteProfile: (id: string) => request(`/api/profiles/${id}`, { method: "DELETE" }),
  parseProfile: async (file: File, name?: string) => {
    const data = new FormData();
    data.append("file", file);
    if (name) data.append("name", name);
    return request<Profile>("/api/profiles/parse", { method: "POST", body: data });
  },
  jobSuggestions: (profileId: string) =>
    request<JobSuggestionsResponse>(`/api/profiles/${profileId}/job-suggestions`, {
      method: "POST",
    }),
  applications: () => request<Application[]>("/api/applications"),
  application: (id: string) => request<Application>(`/api/applications/${id}`),
  patchApplication: (id: string, body: { status?: AppStatus; notes?: string }) =>
    request<Application>(`/api/applications/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteApplication: (id: string) => request(`/api/applications/${id}`, { method: "DELETE" }),
  run: (body: {
    profile_id: string;
    job_text: string;
    company?: string;
    role?: string;
    template: TemplateName;
    use_ollama?: boolean;
    save?: boolean;
  }) => request<RunResponse>("/api/applications/run", { method: "POST", body: JSON.stringify(body) }),
  retarget: (id: string, template: TemplateName, use_ollama: boolean) =>
    request<{ application: Application; result: RunResponse["result"] }>(
      `/api/applications/${id}/retarget?template=${template}&use_ollama=${use_ollama}`,
      { method: "POST" },
    ),
  analyze: (profile_id: string, job_text: string) =>
    request("/api/analyze", { method: "POST", body: JSON.stringify({ profile_id, job_text }) }),
  download: (path: string) => {
    window.open(`/api/files?path=${encodeURIComponent(path)}`, "_blank");
  },
  exportBlob: async (resume: Resume, template: TemplateName, format: "pdf" | "docx", language: "en" | "tr") => {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume, template, format, language }),
    });
    if (!response.ok) throw new Error("Export başarısız");
    const buffer = await response.arrayBuffer();
    const type =
      format === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    return new Blob([buffer], { type });
  },
  exportCoverBlob: async (text: string, format: "pdf" | "docx") => {
    const response = await fetch("/api/export/cover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, format }),
    });
    if (!response.ok) throw new Error("Ön yazı export başarısız");
    const buffer = await response.arrayBuffer();
    const type =
      format === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    return new Blob([buffer], { type });
  },
};
