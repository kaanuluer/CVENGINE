export type TemplateName = "classic" | "executive" | "compact";
export type AppStatus = "draft" | "applied" | "interview" | "offer" | "rejected";
export type ResumeLanguage = "en" | "tr";

export interface Location {
  address?: string;
  postalCode?: string;
  city?: string;
  countryCode?: string;
  region?: string;
}

export interface Basics {
  name: string;
  label: string;
  email: string;
  phone: string;
  url: string;
  summary: string;
  location?: Location;
}

export interface WorkItem {
  name: string;
  position: string;
  url?: string;
  startDate: string;
  endDate: string;
  summary?: string;
  highlights: string[];
  location?: string;
}

export interface EducationItem {
  institution: string;
  area: string;
  studyType: string;
  startDate: string;
  endDate: string;
  score?: string;
}

export interface SkillItem {
  name: string;
  level?: string;
  keywords: string[];
}

export interface ProjectItem {
  name: string;
  description?: string;
  highlights: string[];
}

export interface CertificateItem {
  name: string;
  issuer?: string;
  date?: string;
  url?: string;
}

export interface LanguageItem {
  language: string;
  fluency: string;
}

export interface Resume {
  basics: Basics;
  work: WorkItem[];
  education: EducationItem[];
  skills: SkillItem[];
  projects?: ProjectItem[];
  certificates?: CertificateItem[];
  languages?: LanguageItem[];
}

export function emptyResume(): Resume {
  return {
    basics: { name: "", label: "", email: "", phone: "", url: "", summary: "", location: { city: "" } },
    work: [],
    education: [],
    skills: [{ name: "Yetenekler", keywords: [] }],
    projects: [],
    certificates: [],
    languages: [],
  };
}

export interface GateIssue {
  code: string;
  message: string;
  severity: "block" | "warn";
}

export interface ScoreBlock {
  parse: number;
  keyword: number;
  semantic: number;
  evidence: number;
  groundedness: number;
  consistency?: number;
  overall: number;
  ats?: number;
  passed: boolean;
  issues: GateIssue[];
}

export interface JobAnalysis {
  language: ResumeLanguage;
  title: string;
  company: string;
  seniority: string;
  keywords: string[];
  required_skills: string[];
  preferred_skills: string[];
  surface_forms: Record<string, string>;
}

export interface GapItem {
  skill: string;
  in_resume: boolean;
  weight: "required" | "preferred";
}

export interface MatchResult {
  overall: number;
  keyword_coverage: number;
  semantic: number;
  gaps: GapItem[];
}

export interface DiffChange {
  path: string;
  kind: "added" | "removed" | "changed" | "moved";
  before?: string | null;
  after?: string | null;
}

export interface TailorResult {
  resume: Resume;
  analysis: JobAnalysis;
  match: MatchResult;
  scores: ScoreBlock;
  diff: DiffChange[];
  fact_map: Record<string, string[]>;
  template: TemplateName;
  used_ollama: boolean;
  ollama_rolled_back: boolean;
  language: ResumeLanguage;
  cover_letter: string;
  cover_used_ollama?: boolean;
  baseline_scores?: ScoreBlock | null;
}

export interface Profile {
  id: string;
  name: string;
  resume: Resume;
  created_at: string;
  updated_at: string;
}

export interface JobOut {
  id: string;
  title: string;
  company: string;
  raw_text: string;
  analysis: JobAnalysis;
  created_at: string;
}

export interface TailoredOut {
  id: string;
  application_id: string;
  template: TemplateName;
  resume: Resume;
  scores: ScoreBlock;
  fact_map: Record<string, string[]>;
  diff: DiffChange[];
  pdf_path?: string | null;
  docx_path?: string | null;
  cover_letter?: string;
  cover_pdf_path?: string | null;
  cover_docx_path?: string | null;
  language?: ResumeLanguage;
  used_ollama: boolean;
  created_at: string;
  baseline_scores?: ScoreBlock | null;
}

export interface Application {
  id: string;
  profile_id: string;
  job_id?: string | null;
  company: string;
  role: string;
  status: AppStatus;
  notes: string;
  created_at: string;
  updated_at: string;
  latest?: TailoredOut | null;
  keyword_score?: number | null;
  overall_score?: number | null;
  baseline_ats?: number | null;
  tailored_ats?: number | null;
}

export interface RunResponse {
  application: Application;
  job: JobOut;
  result: TailorResult;
  tailored?: TailoredOut | null;
}

export interface Settings {
  language: ResumeLanguage;
  ollama_url: string;
  ollama_model: string;
  default_template: TemplateName;
  ollama_available: boolean;
}

export const STATUS_LABEL: Record<AppStatus, string> = {
  draft: "Taslak",
  applied: "Başvuruldu",
  interview: "Mülakat",
  offer: "Teklif",
  rejected: "Red",
};

export const TEMPLATE_LABEL: Record<TemplateName, string> = {
  classic: "Classic ATS",
  executive: "Executive",
  compact: "Compact",
};
