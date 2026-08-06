// Event types
export type EventCategory = 'general' | 'reunion' | 'evaluacion' | 'pendiente' | 'recordatorio' | 'planificacion' | 'feriado';

export interface CalendarEvent {
  id: number;
  title: string;
  description?: string;
  start_datetime: string;
  end_datetime?: string;
  all_day: boolean;
  color: string;
  category: EventCategory;
  location?: string;
  alert_minutes?: number;
  recurrence?: string;
  created_at: string;
}

export interface EventFormData {
  title: string;
  description?: string;
  start_datetime: string;
  end_datetime?: string;
  all_day: boolean;
  color?: string;
  category: EventCategory;
  location?: string;
  alert_minutes?: number;
  recurrence?: string;
}

// Document/Constructor types
export type DocType = 'prueba' | 'evaluacion' | 'guia' | 'planificacion' | 'ficha';

export interface ContentItem {
  number: number;
  type: 'multiple_choice' | 'true_false' | 'open' | 'matching' | 'activity';
  text: string;
  options: string[];
  answer: string;
  points: number;
  image_words: string[];
  image_style: 'none' | 'photo' | 'coloring';
}

export interface ContentSection {
  type: 'header' | 'text' | 'questions' | 'activities' | 'answers';
  title?: string;
  /** Texto corrido de la sección. */
  body?: string;
  /** Preguntas o actividades. */
  items?: ContentItem[];
  /**
   * Formato antiguo, anterior al esquema validado: un único campo polimórfico.
   * El backend normaliza al leer, pero el preview lo tolera por si llega
   * un documento sin pasar por ahí.
   */
  content?: string | string[] | Record<string, unknown>[];
}

export interface DocumentContent {
  title: string;
  instructions?: string;
  sections: ContentSection[];
  metadata?: {
    subject: string;
    grade: string;
    topic: string;
    total_points?: number;
    oa_codes?: string[];
  };
}

export interface CurriculumOA {
  code: string;
  description: string;
}

export interface Document {
  id: number;
  title: string;
  doc_type: DocType;
  subject?: string;
  grade_level?: string;
  content?: DocumentContent;
  raw_html?: string;
  images?: string[];
  ai_prompt?: string;
  created_at: string;
}

// Auth types
export interface User {
  id: number;
  name: string;
  email: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

// Category labels and colors
export const CATEGORY_CONFIG: Record<EventCategory, { label: string; color: string; bg: string }> = {
  general:       { label: 'General',        color: '#6B7280', bg: 'bg-gray-500' },
  reunion:       { label: 'Reunión',         color: '#3B82F6', bg: 'bg-blue-500' },
  evaluacion:    { label: 'Evaluación',      color: '#EF4444', bg: 'bg-red-500' },
  pendiente:     { label: 'Pendiente',       color: '#F59E0B', bg: 'bg-amber-500' },
  recordatorio:  { label: 'Recordatorio',    color: '#8B5CF6', bg: 'bg-violet-500' },
  planificacion: { label: 'Planificación',   color: '#10B981', bg: 'bg-emerald-500' },
  feriado:       { label: 'Feriado',         color: '#EC4899', bg: 'bg-pink-500' },
};

export const DOC_TYPE_CONFIG: Record<DocType, { label: string; icon: string }> = {
  prueba:        { label: 'Prueba',          icon: '📝' },
  evaluacion:    { label: 'Evaluación',      icon: '✅' },
  guia:          { label: 'Guía de Trabajo', icon: '📚' },
  planificacion: { label: 'Planificación',   icon: '🗓️' },
  ficha:         { label: 'Ficha',           icon: '📋' },
};

export const SUBJECTS = [
  'Matemática', 'Lenguaje y Comunicación', 'Ciencias Naturales',
  'Historia, Geografía y Cs. Sociales', 'Inglés', 'Educación Física',
  'Artes Visuales', 'Música', 'Tecnología', 'Orientación', 'Religión'
];

export const GRADE_LEVELS = [
  '1° Básico', '2° Básico', '3° Básico', '4° Básico',
  '5° Básico', '6° Básico', '7° Básico', '8° Básico',
  '1° Medio', '2° Medio', '3° Medio', '4° Medio',
  'Educación Parvularia', 'Pre-Kinder', 'Kinder'
];
