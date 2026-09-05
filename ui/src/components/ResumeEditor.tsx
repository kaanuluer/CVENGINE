import type { ReactNode } from "react";
import type {
  CertificateItem,
  EducationItem,
  LanguageItem,
  ProjectItem,
  Resume,
  SkillItem,
  WorkItem,
} from "../types";

export function ResumeEditor({ resume, onChange }: { resume: Resume; onChange: (next: Resume) => void }) {
  const set = (patch: Partial<Resume>) => onChange({ ...resume, ...patch });
  const basics = resume.basics;

  return (
    <div className="space-y-6">
      <Section title="İletişim">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Ad soyad" value={basics.name} onChange={(name) => set({ basics: { ...basics, name } })} />
          <Field label="Ünvan" value={basics.label} onChange={(label) => set({ basics: { ...basics, label } })} />
          <Field label="E-posta" value={basics.email} onChange={(email) => set({ basics: { ...basics, email } })} />
          <Field label="Telefon" value={basics.phone} onChange={(phone) => set({ basics: { ...basics, phone } })} />
          <Field label="LinkedIn / site" value={basics.url} onChange={(url) => set({ basics: { ...basics, url } })} />
          <Field
            label="Şehir"
            value={basics.location?.city ?? ""}
            onChange={(city) => set({ basics: { ...basics, location: { ...basics.location, city } } })}
          />
        </div>
        <label className="mt-3 block">
          <span className="text-xs font-medium text-muted">Özet</span>
          <textarea
            rows={4}
            value={basics.summary}
            onChange={(e) => set({ basics: { ...basics, summary: e.target.value } })}
            className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm leading-6"
            placeholder="3–4 cümle, ölçülebilir etki."
          />
        </label>
      </Section>

      <Section
        title="İş deneyimi"
        action={
          <AddButton
            label="İş ekle"
            onClick={() => set({ work: [...resume.work, blankWork()] })}
          />
        }
      >
        {resume.work.length === 0 && <Empty>Henüz iş yok. İstediğiniz kadar ekleyin.</Empty>}
        {resume.work.map((job, index) => (
          <Card
            key={index}
            title={job.name || job.position || `Rol ${index + 1}`}
            onRemove={() => set({ work: resume.work.filter((_, i) => i !== index) })}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Şirket"
                value={job.name}
                onChange={(name) => patchWork(resume, set, index, { name })}
              />
              <Field
                label="Ünvan"
                value={job.position}
                onChange={(position) => patchWork(resume, set, index, { position })}
              />
              <MonthField
                label="Başlangıç"
                value={job.startDate}
                onChange={(startDate) => patchWork(resume, set, index, { startDate })}
              />
              <MonthField
                label="Bitiş"
                value={job.endDate}
                onChange={(endDate) => patchWork(resume, set, index, { endDate })}
                allowPresent
              />
              <Field
                label="Lokasyon"
                value={job.location ?? ""}
                onChange={(location) => patchWork(resume, set, index, { location })}
              />
            </div>
            <label className="mt-3 block">
              <span className="text-xs font-medium text-muted">Başarılar (her satır bir madde)</span>
              <textarea
                rows={5}
                value={(job.highlights ?? []).join("\n")}
                onChange={(e) =>
                  patchWork(resume, set, index, {
                    highlights: e.target.value.split("\n"),
                  })
                }
                className="mt-1 w-full rounded-lg border border-line px-3 py-2 font-sans text-sm leading-6"
                placeholder={"Ödeme API gecikmesini %40 düşürdüm.\n4 kişilik ekibi yönettim."}
              />
            </label>
          </Card>
        ))}
      </Section>

      <Section
        title="Eğitim"
        action={<AddButton label="Eğitim ekle" onClick={() => set({ education: [...resume.education, blankEdu()] })} />}
      >
        {resume.education.length === 0 && <Empty>Okul, bölüm ve tarih ekleyin.</Empty>}
        {resume.education.map((edu, index) => (
          <Card
            key={index}
            title={edu.institution || `Okul ${index + 1}`}
            onRemove={() => set({ education: resume.education.filter((_, i) => i !== index) })}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Kurum"
                value={edu.institution}
                onChange={(institution) => patchEdu(resume, set, index, { institution })}
              />
              <Field
                label="Derece"
                value={edu.studyType}
                onChange={(studyType) => patchEdu(resume, set, index, { studyType })}
              />
              <Field label="Bölüm" value={edu.area} onChange={(area) => patchEdu(resume, set, index, { area })} />
              <MonthField
                label="Başlangıç"
                value={edu.startDate}
                onChange={(startDate) => patchEdu(resume, set, index, { startDate })}
              />
              <MonthField
                label="Bitiş"
                value={edu.endDate}
                onChange={(endDate) => patchEdu(resume, set, index, { endDate })}
              />
            </div>
          </Card>
        ))}
      </Section>

      <Section
        title="Sertifikalar"
        action={
          <AddButton
            label="Sertifika ekle"
            onClick={() => set({ certificates: [...(resume.certificates ?? []), blankCert()] })}
          />
        }
      >
        {(resume.certificates ?? []).length === 0 && <Empty>Sınırsız sertifika ekleyebilirsiniz.</Empty>}
        {(resume.certificates ?? []).map((cert, index) => (
          <Card
            key={index}
            title={cert.name || `Sertifika ${index + 1}`}
            onRemove={() =>
              set({ certificates: (resume.certificates ?? []).filter((_, i) => i !== index) })
            }
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Field
                label="Ad"
                value={cert.name}
                onChange={(name) => patchCert(resume, set, index, { name })}
              />
              <Field
                label="Kurum"
                value={cert.issuer ?? ""}
                onChange={(issuer) => patchCert(resume, set, index, { issuer })}
              />
              <MonthField
                label="Tarih"
                value={cert.date ?? ""}
                onChange={(date) => patchCert(resume, set, index, { date })}
              />
              <Field
                label="URL"
                value={cert.url ?? ""}
                onChange={(url) => patchCert(resume, set, index, { url })}
              />
            </div>
          </Card>
        ))}
      </Section>

      <Section
        title="Yetenekler"
        action={
          <AddButton label="Grup ekle" onClick={() => set({ skills: [...resume.skills, blankSkill()] })} />
        }
      >
        {resume.skills.map((skill, index) => (
          <Card
            key={index}
            title={skill.name || `Grup ${index + 1}`}
            onRemove={() => set({ skills: resume.skills.filter((_, i) => i !== index) })}
          >
            <Field
              label="Grup adı"
              value={skill.name}
              onChange={(name) => patchSkill(resume, set, index, { name })}
            />
            <label className="mt-3 block">
              <span className="text-xs font-medium text-muted">Yetenekler (virgülle)</span>
              <textarea
                rows={2}
                value={skill.keywords.join(", ")}
                onChange={(e) =>
                  patchSkill(resume, set, index, {
                    keywords: e.target.value.split(",").map((k) => k.trim()).filter(Boolean),
                  })
                }
                className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm"
                placeholder="Python, PostgreSQL, Docker"
              />
            </label>
          </Card>
        ))}
      </Section>

      <Section
        title="Projeler"
        action={
          <AddButton
            label="Proje ekle"
            onClick={() => set({ projects: [...(resume.projects ?? []), blankProject()] })}
          />
        }
      >
        {(resume.projects ?? []).map((project, index) => (
          <Card
            key={index}
            title={project.name || `Proje ${index + 1}`}
            onRemove={() => set({ projects: (resume.projects ?? []).filter((_, i) => i !== index) })}
          >
            <Field
              label="Ad"
              value={project.name}
              onChange={(name) => patchProject(resume, set, index, { name })}
            />
            <label className="mt-3 block">
              <span className="text-xs font-medium text-muted">Açıklama</span>
              <input
                value={project.description ?? ""}
                onChange={(e) => patchProject(resume, set, index, { description: e.target.value })}
                className="mt-1 h-10 w-full rounded-lg border border-line px-3 text-sm"
              />
            </label>
            <label className="mt-3 block">
              <span className="text-xs font-medium text-muted">Maddeler (her satır bir madde)</span>
              <textarea
                rows={3}
                value={(project.highlights ?? []).join("\n")}
                onChange={(e) => patchProject(resume, set, index, { highlights: e.target.value.split("\n") })}
                className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm leading-6"
              />
            </label>
          </Card>
        ))}
      </Section>

      <Section
        title="Diller"
        action={
          <AddButton
            label="Dil ekle"
            onClick={() => set({ languages: [...(resume.languages ?? []), blankLang()] })}
          />
        }
      >
        {(resume.languages ?? []).map((lang, index) => (
          <div key={index} className="mb-2 grid grid-cols-[1fr_1fr_auto] gap-2">
            <input
              value={lang.language}
              placeholder="Dil"
              onChange={(e) => patchLang(resume, set, index, { language: e.target.value })}
              className="h-10 rounded-lg border border-line px-3 text-sm"
            />
            <input
              value={lang.fluency}
              placeholder="Seviye"
              onChange={(e) => patchLang(resume, set, index, { fluency: e.target.value })}
              className="h-10 rounded-lg border border-line px-3 text-sm"
            />
            <button
              type="button"
              className="h-10 rounded-lg px-3 text-sm text-danger hover:bg-red-50"
              onClick={() => set({ languages: (resume.languages ?? []).filter((_, i) => i !== index) })}
            >
              Sil
            </button>
          </div>
        ))}
      </Section>
    </div>
  );
}

function blankWork(): WorkItem {
  return { name: "", position: "", startDate: "", endDate: "", highlights: [], location: "", url: "", summary: "" };
}
function blankEdu(): EducationItem {
  return { institution: "", area: "", studyType: "", startDate: "", endDate: "" };
}
function blankCert(): CertificateItem {
  return { name: "", issuer: "", date: "", url: "" };
}
function blankSkill(): SkillItem {
  return { name: "", keywords: [] };
}
function blankProject(): ProjectItem {
  return { name: "", description: "", highlights: [] };
}
function blankLang(): LanguageItem {
  return { language: "", fluency: "" };
}

function patchWork(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<WorkItem>) {
  set({ work: resume.work.map((item, i) => (i === index ? { ...item, ...patch } : item)) });
}
function patchEdu(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<EducationItem>) {
  set({ education: resume.education.map((item, i) => (i === index ? { ...item, ...patch } : item)) });
}
function patchCert(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<CertificateItem>) {
  const list = [...(resume.certificates ?? [])];
  list[index] = { ...list[index], ...patch };
  set({ certificates: list });
}
function patchSkill(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<SkillItem>) {
  set({ skills: resume.skills.map((item, i) => (i === index ? { ...item, ...patch } : item)) });
}
function patchProject(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<ProjectItem>) {
  const list = [...(resume.projects ?? [])];
  list[index] = { ...list[index], ...patch };
  set({ projects: list });
}
function patchLang(resume: Resume, set: (p: Partial<Resume>) => void, index: number, patch: Partial<LanguageItem>) {
  const list = [...(resume.languages ?? [])];
  list[index] = { ...list[index], ...patch };
  set({ languages: list });
}

function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Card({ title, onRemove, children }: { title: string; onRemove: () => void; children: ReactNode }) {
  return (
    <div className="mb-3 rounded-card border border-line bg-canvas/60 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="truncate text-sm font-medium">{title}</p>
        <button type="button" onClick={onRemove} className="text-xs text-danger hover:underline">
          Kaldır
        </button>
      </div>
      {children}
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted">{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm"
      />
    </label>
  );
}

function MonthField({
  label,
  value,
  onChange,
  allowPresent = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  allowPresent?: boolean;
}) {
  const month = value ? value.slice(0, 7) : "";
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted">{label}</span>
      <div className="mt-1 flex gap-2">
        <input
          type="month"
          value={month}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm"
        />
        {allowPresent && (
          <button
            type="button"
            onClick={() => onChange("")}
            className="h-10 shrink-0 rounded-lg border border-line px-2 text-xs text-muted hover:text-ink"
          >
            Devam
          </button>
        )}
      </div>
    </label>
  );
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-white">
      {label}
    </button>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="mb-3 rounded-lg border border-dashed border-line px-3 py-4 text-sm text-muted">{children}</p>;
}
