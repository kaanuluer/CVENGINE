import type { ScoreBlock } from "../types";

const METRICS: { key: keyof Pick<ScoreBlock, "parse" | "keyword" | "semantic" | "evidence" | "groundedness">; label: string }[] = [
  { key: "parse", label: "Parse" },
  { key: "keyword", label: "Keyword" },
  { key: "semantic", label: "Semantic" },
  { key: "evidence", label: "Evidence" },
  { key: "groundedness", label: "Groundedness" },
];

function tone(value: number) {
  if (value >= 80) return "text-success";
  if (value >= 60) return "text-warning";
  return "text-danger";
}

function bar(value: number) {
  return value >= 80 ? "bg-success" : value >= 60 ? "bg-warning" : "bg-danger";
}

export function atsOf(scores: ScoreBlock) {
  if (scores.ats && scores.ats > 0) return scores.ats;
  return Math.round(0.55 * scores.keyword + 0.45 * scores.semantic);
}

export function ScorePanel({
  scores,
  baseline,
}: {
  scores: ScoreBlock;
  baseline?: ScoreBlock | null;
}) {
  const tailoredAts = atsOf(scores);
  const masterAts = baseline ? atsOf(baseline) : null;
  const delta = masterAts != null ? Math.round(tailoredAts - masterAts) : null;

  return (
    <section className="rounded-card border border-line bg-white p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wide text-muted">ATS uyumu</p>
      <div className={`mt-3 grid gap-4 ${baseline ? "grid-cols-2" : "grid-cols-1"}`}>
        {baseline && (
          <div>
            <p className="text-sm text-muted">Master CV × ilan</p>
            <p className={`mt-1 text-4xl font-semibold tracking-tight ${tone(masterAts ?? 0)}`}>
              {Math.round(masterAts ?? 0)}
            </p>
            <p className="mt-1 text-[11px] text-muted">
              Keyword {Math.round(baseline.keyword)} · Semantic {Math.round(baseline.semantic)}
            </p>
          </div>
        )}
        <div>
          <p className="text-sm text-muted">Üretilen CV × ilan</p>
          <div className="mt-1 flex items-end gap-2">
            <p className={`text-4xl font-semibold tracking-tight ${tone(tailoredAts)}`}>
              {Math.round(tailoredAts)}
            </p>
            {delta != null && (
              <span
                className={`mb-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  delta > 0 ? "bg-green-50 text-success" : delta < 0 ? "bg-red-50 text-danger" : "bg-canvas text-muted"
                }`}
              >
                {delta > 0 ? `+${delta}` : delta}
              </span>
            )}
          </div>
          <p className="mt-1 text-[11px] text-muted">
            Keyword {Math.round(scores.keyword)} · Semantic {Math.round(scores.semantic)}
          </p>
        </div>
      </div>

      <div className="mt-5 flex items-start justify-between gap-4 border-t border-line pt-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Üretilen CV — ATS / AI-HR kapıları</p>
          <p className={`mt-1 text-2xl font-semibold tracking-tight ${tone(scores.overall)}`}>
            {Math.round(scores.overall)}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            scores.passed ? "bg-green-50 text-success" : "bg-red-50 text-danger"
          }`}
        >
          {scores.passed ? "Kapılar geçti" : "Kapı açık değil"}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-5 gap-3">
        {METRICS.map((metric) => {
          const value = scores[metric.key];
          return (
            <div key={metric.key}>
              <div className="mb-1 flex justify-between text-[11px] text-muted">
                <span>{metric.label}</span>
                <span className={tone(value)}>{Math.round(value)}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-canvas">
                <div className={`h-full rounded-full ${bar(value)}`} style={{ width: `${Math.min(100, value)}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {scores.issues.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {scores.issues.slice(0, 8).map((issue, index) => (
            <li key={`${issue.code}-${index}`} className="flex gap-2 text-xs">
              <span className={issue.severity === "block" ? "text-danger" : "text-warning"}>
                {issue.severity === "block" ? "Blok" : "Uyarı"}
              </span>
              <span className="text-ink">{issue.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
