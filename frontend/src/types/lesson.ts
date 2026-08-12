// Espejo de `backend/app/schemas/lesson.py`. Si cambia allá, cambia acá.

export type SceneType = 'concept' | 'example' | 'process' | 'quiz' | 'recap';
export type MotionPreset = 'none' | 'gentle-reveal' | 'step-by-step' | 'answer-reveal' | 'static';
export type AssetStatus = 'pending' | 'ready' | 'failed';

export interface Asset {
  id: string;
  kind: 'image' | 'svg_diagram' | 'icon';
  role: string;
  query: string;
  style: 'none' | 'photo' | 'coloring';
  alt: string;
  uri: string;
  source: 'builtin' | 'arasaac' | 'generated';
  status: AssetStatus;
  credit: string;
  fallback: 'alt_text' | 'static_diagram' | 'label';
}

export interface Step {
  id: string;
  label: string;
  description: string;
  asset_ids: string[];
}

export interface Example {
  id: string;
  label: string;
  text: string;
  asset_ids: string[];
}

export interface SceneData {
  goal: string;
  examples: Example[];
  steps: Step[];
  question_ref: string;
  key_points: string[];
  prompt: string;
}

export interface Scene {
  id: string;
  type: SceneType;
  title: string;
  body: string;
  /** Guion hablado. Nunca se proyecta: ver DESIGN.md. */
  narration: string;
  duration_seconds: number;
  asset_ids: string[];
  motion: { preset: MotionPreset; duration_ms: number; stagger_ms: number };
  data: SceneData;
  /** Instrucción operativa para la profesora. Nunca se proyecta. */
  teacher_note: string;
}

export interface Option {
  id: string;
  label: string;
  asset_id: string;
}

export interface Question {
  id: string;
  kind: 'single_choice';
  prompt: string;
  options: Option[];
  correct_option_ids: string[];
  explanation: string;
  feedback_correct: string;
  feedback_incorrect: string;
}

export interface LessonSpec {
  schema_version: string;
  spec_type: string;
  curriculum: {
    grade_level: string;
    subject: string;
    unit: string;
    oa_refs: string[];
    indicator_refs: string[];
    resolved_oas: { oa_id: number; code: string; text: string }[];
    resolved_indicators: {
      indicator_id: number; ref: string; oa_code: string;
      ordinal: number; text: string; source_ref: string;
    }[];
  };
  metadata: { title: string; topic: string; lesson_kind: string };
  duration_minutes: number;
  audience: string;
  assets: Asset[];
  motion_defaults: { enabled: boolean; preset: MotionPreset; max_duration_ms: number };
  scenes: Scene[];
  questions: Question[];
  teacher_notes: { before_class: string; during_class: string; after_class: string };
  exit_assessment: {
    enabled: boolean; prompt: string; response_mode: string;
    expected_evidence: string; rubric: { level: string; evidence: string }[];
  };
  accessibility: Record<string, unknown>;
  fallbacks: Record<string, string>;
  privacy: { student_data_allowed: boolean; response_storage: string };
}

export interface LessonSummary {
  id: number;
  title: string;
  subject: string;
  grade_level: string;
  status: string;
  scenes: number;
  created_at: string;
  updated_at: string;
}

/** 1° y 2° Básico toleran menos densidad. Espeja `nivel_de()` del backend. */
export function esNivelInicial(gradeLevel: string): boolean {
  const n = /(\d+)/.exec(gradeLevel || '');
  if (!n) return false;
  return Number(n[1]) <= 2 && /básico/i.test(gradeLevel);
}

/** Espeja `LIMITES` de `backend/app/schemas/lesson.py`.
 *
 * Duplicado a propósito: sirve para avisar en el editor antes de que el
 * servidor rechace. La autoridad sigue siendo el backend. */
export const LIMITES = {
  inicial:  { title: 45, body: 90,  keyPoint: 80,  optionLabel: 25 },
  estandar: { title: 60, body: 140, keyPoint: 110, optionLabel: 40 },
} as const;

export function limitesDe(gradeLevel: string) {
  return esNivelInicial(gradeLevel) ? LIMITES.inicial : LIMITES.estandar;
}
