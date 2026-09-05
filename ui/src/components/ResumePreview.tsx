import type { ReactNode } from "react";
import type { Resume, ResumeLanguage, TemplateName } from "../types";

const HEADINGS = {
  en: {
    summary: "Summary",
    experience: "Experience",
    education: "Education",
    skills: "Skills",
    projects: "Projects",
    certificates: "Certificates",
    languages: "Languages",
    present: "Present",
  },
  tr: {
    summary: "Özet",
    experience: "İş Deneyimi",
    education: "Eğitim",
    skills: "Yetenekler",
    projects: "Projeler",
    certificates: "Sertifikalar",
    languages: "Diller",
    present: "Günümüz",
  },
};

const MONTHS = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  tr: ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"],
};

function fmt(value: string, language: ResumeLanguage) {
  if (!value) return "";
  const match = /^(\d{4})(?:-(\d{2}))?/.exec(value);
  if (!match) return value;
  const year = match[1];
  const month = match[2];
  if (!month) return year;
  return `${MONTHS[language][Math.max(0, Number(month) - 1)]} ${year}`;
}

function range(start: string, end: string, language: ResumeLanguage, present: string) {
  const left = fmt(start, language);
  const right = fmt(end, language) || (start ? present : "");
  return [left, right].filter(Boolean).join(" – ");
}

function bullets(items: string[] | undefined) {
  return (items ?? []).map((item) => item.trim()).filter((item) => item.length >= 3);
}

function localeUpper(text: string, language: ResumeLanguage) {
  return text.toLocaleUpperCase(language === "tr" ? "tr" : "en-US");
}

export function ResumePreview({
  resume,
  template,
  language = "en",
}: {
  resume: Resume;
  template: TemplateName;
  language?: ResumeLanguage;
}) {
  const h = HEADINGS[language];
  const b = resume.basics;
  const contact = [b.email, b.phone, b.url, b.location?.city].filter(Boolean);
  const nameSize =
    template === "executive" ? "text-[26px] tracking-[-0.03em]" : template === "compact" ? "text-[20px]" : "text-[22px] tracking-[-0.02em]";

  return (
    <article
      className={`paper paper-${template} w-full max-w-[794px] text-ink`}
      lang={language}
      style={{ minHeight: template === "compact" ? 900 : 1000 }}
    >
      <header className="text-center">
        <h1 className={`font-semibold text-ink ${nameSize}`}>{b.name || "Ad Soyad"}</h1>
        {b.label && (
          <p className={`mt-1 text-[12px] ${template === "executive" ? "text-primary" : "text-muted"}`}>{b.label}</p>
        )}
        {contact.length > 0 && (
          <p className="mt-2 text-[10.5px] leading-4 text-muted">{contact.join("  ·  ")}</p>
        )}
      </header>

      {b.summary && (
        <Section title={h.summary} template={template} language={language}>
          <p className="text-justify leading-[1.45]">{b.summary}</p>
        </Section>
      )}

      {(resume.work?.length ?? 0) > 0 && (
        <Section title={h.experience} template={template} language={language}>
          {resume.work.map((work, index) => {
            const items = bullets(work.highlights);
            return (
              <div key={`${work.name}-${index}`} className="mb-3 last:mb-0">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="font-semibold leading-snug">
                    {work.position || "Ünvan"}
                    {work.name ? <span className="font-normal text-muted"> · {work.name}</span> : null}
                  </p>
                  <p className="shrink-0 text-[10.5px] text-muted">{range(work.startDate, work.endDate, language, h.present)}</p>
                </div>
                {work.location && <p className="text-[10.5px] text-muted">{work.location}</p>}
                {items.length > 0 && (
                  <ul className="mt-1.5 space-y-[3px]">
                    {items.map((item, i) => (
                      <li key={i} className="grid grid-cols-[10px_1fr] gap-x-1.5 leading-[1.4]">
                        <span aria-hidden className="mt-[1px] text-[9px]">●</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </Section>
      )}

      {(resume.education?.length ?? 0) > 0 && (
        <Section title={h.education} template={template} language={language}>
          {resume.education.map((edu, index) => (
            <div key={index} className="mb-1.5 flex items-baseline justify-between gap-4 last:mb-0">
              <p>
                <span className="font-semibold">{[edu.studyType, edu.area].filter(Boolean).join(" ")}</span>
                {edu.institution ? <span className="text-muted"> · {edu.institution}</span> : null}
              </p>
              <p className="shrink-0 text-[10.5px] text-muted">{range(edu.startDate, edu.endDate, language, h.present)}</p>
            </div>
          ))}
        </Section>
      )}

      {(resume.skills?.some((s) => s.keywords.length) ?? false) && (
        <Section title={h.skills} template={template} language={language}>
          {resume.skills.filter((s) => s.keywords.length).map((skill) => (
            <p key={skill.name} className="leading-[1.45]">
              {skill.name ? <span className="font-semibold">{skill.name}: </span> : null}
              {skill.keywords.join(" · ")}
            </p>
          ))}
        </Section>
      )}

      {(resume.projects?.length ?? 0) > 0 && (
        <Section title={h.projects} template={template} language={language}>
          {resume.projects!.map((project) => (
            <div key={project.name} className="mb-2 last:mb-0">
              <p className="font-semibold">{project.name}</p>
              {project.description && <p className="text-muted">{project.description}</p>}
              {bullets(project.highlights).length > 0 && (
                <ul className="mt-1 space-y-[3px]">
                  {bullets(project.highlights).map((item, i) => (
                    <li key={i} className="grid grid-cols-[10px_1fr] gap-x-1.5">
                      <span aria-hidden className="text-[9px]">●</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </Section>
      )}

      {(resume.certificates?.length ?? 0) > 0 && (
        <Section title={h.certificates} template={template} language={language}>
          {resume.certificates!.map((cert, index) => (
            <p key={index} className="mb-0.5">
              <span className="font-semibold">{cert.name}</span>
              {cert.issuer ? <span className="text-muted"> · {cert.issuer}</span> : null}
              {cert.date ? <span className="text-muted"> · {fmt(cert.date, language)}</span> : null}
            </p>
          ))}
        </Section>
      )}

      {(resume.languages?.length ?? 0) > 0 && (
        <Section title={h.languages} template={template} language={language}>
          <p>{resume.languages!.map((lang) => [lang.language, lang.fluency].filter(Boolean).join(" — ")).join("  ·  ")}</p>
        </Section>
      )}
    </article>
  );
}

function Section({
  title,
  template,
  language,
  children,
}: {
  title: string;
  template: TemplateName;
  language: ResumeLanguage;
  children: ReactNode;
}) {
  return (
    <section className={template === "compact" ? "mt-3" : "mt-[18px]"}>
      <h2
        className={`border-b pb-[3px] text-[10px] font-semibold tracking-[0.16em] ${
          template === "executive" ? "border-primary" : "border-ink/20"
        }`}
      >
        {localeUpper(title, language)}
      </h2>
      <div className="mt-2">{children}</div>
    </section>
  );
}
