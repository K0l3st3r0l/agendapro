import { useState, useEffect, useRef } from 'react';
import { constructorAPI, curriculumAPI, settingsAPI, eventsAPI } from '../services/api';
import type { CurriculumOA, DocType, DocumentContent, EventCategory } from '../types';
import { DOC_TYPE_CONFIG, SUBJECTS, GRADE_LEVELS } from '../types';
import { PROVIDERS, providerLabel, providerEmoji, selectableProviders } from '../config/providers';
import type { AIProvider } from '../config/providers';
import toast from 'react-hot-toast';
import {
  SparklesIcon,
  DocumentArrowDownIcon,
  BookmarkIcon,
  ArrowPathIcon,
  PhotoIcon,
  CalendarDaysIcon,
  ArrowDownTrayIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline';
import PageHeader from '../components/ui/PageHeader';
import AppDialog from '../components/ui/AppDialog';
import { Button } from '../components/ui/Button';
import DocumentPreview from '../components/DocumentPreview';

type Step = 'form' | 'result';

interface GenerateForm {
  doc_type: DocType;
  subject: string;
  grade_level: string;
  topic: string;
  instructions: string;
  num_questions: number;
  difficulty: string;
  include_images: boolean;
  include_answers: boolean;
  oa_codes: string[];
  provider: AIProvider;
}

const defaultForm: GenerateForm = {
  doc_type: 'prueba',
  subject: 'Matemática',
  grade_level: '1° Básico',
  topic: '',
  instructions: '',
  num_questions: 10,
  difficulty: 'medio',
  include_images: false,
  include_answers: true,
  oa_codes: [],
  provider: 'auto',
};

const selectClass =
  'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100';

// Mirrors backend/app/api/ai_constructor.py::save_to_calendar's category_map,
// so events created from an already-saved document land in the same category.
const DOC_TYPE_EVENT_CATEGORY: Record<DocType, EventCategory> = {
  prueba: 'evaluacion',
  evaluacion: 'evaluacion',
  planificacion: 'planificacion',
  guia: 'general',
  ficha: 'general',
};

// Mirrors the backend's `f"[doc_id:{id}] {subject} - {grade}".strip(" -")` description format.
const buildDocLinkDescription = (docId: number, subject?: string, gradeLevel?: string) =>
  `[doc_id:${docId}] ${subject || ''} - ${gradeLevel || ''}`.replace(/^[ -]+|[ -]+$/g, '');

/**
 * Recolecta {palabra: estilo} de todas las secciones, deduplicando.
 *
 * Espeja `collect_image_words` del backend. Acepta `items` (esquema nuevo) y
 * `content` como lista (documentos anteriores al esquema validado).
 */
const collectImageWords = (sections: any[] | undefined): Record<string, string> => {
  const map: Record<string, string> = {};
  (sections || []).forEach(sec => {
    const items = Array.isArray(sec?.items) ? sec.items : Array.isArray(sec?.content) ? sec.content : [];
    items.forEach((item: any) => {
      if (!item || typeof item !== 'object' || !Array.isArray(item.image_words)) return;
      const style = item.image_style && item.image_style !== 'none' ? item.image_style : 'photo';
      item.image_words.forEach((w: string) => {
        const key = String(w).toLowerCase().trim();
        if (key.length > 1 && !(key in map)) map[key] = style;
      });
    });
  });
  return map;
};

export default function AIConstructor() {
  const [form, setForm] = useState<GenerateForm>(defaultForm);
  const [step, setStep] = useState<Step>('form');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ content: DocumentContent; prompt: string; images: string[]; provider_used?: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [preferredProvider, setPreferredProvider] = useState<string>('gemini');
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [calendarDate, setCalendarDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [activityImages, setActivityImages] = useState<Record<string, string>>({});
  const [loadingActivityImages, setLoadingActivityImages] = useState(false);
  const [imageProgress, setImageProgress] = useState({ current: 0, total: 0 });
  const [savedDocumentId, setSavedDocumentId] = useState<number | null>(null);
  const [savingDocument, setSavingDocument] = useState(false);
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null);
  const [oaList, setOaList] = useState<CurriculumOA[]>([]);
  const [loadingOa, setLoadingOa] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    settingsAPI.get()
      .then(r => {
        setSettings(r.data);
        setPreferredProvider(r.data.preferred_provider || 'openrouter');
      })
      .catch(() => {});
  }, []);

  // Los OA disponibles dependen del par nivel + asignatura. Si ese par no tiene
  // currículum cargado el selector no aparece y la generación sigue igual.
  useEffect(() => {
    let cancelled = false;
    setLoadingOa(true);
    curriculumAPI.getOA(form.grade_level, form.subject)
      .then(r => { if (!cancelled) setOaList(r.data.oa || []); })
      .catch(() => { if (!cancelled) setOaList([]); })
      .finally(() => { if (!cancelled) setLoadingOa(false); });
    // Cambiar de nivel o asignatura invalida los OA marcados: pertenecen al par anterior.
    setForm(f => (f.oa_codes.length ? { ...f, oa_codes: [] } : f));
    return () => { cancelled = true; };
  }, [form.grade_level, form.subject]);

  const toggleOa = (code: string) =>
    setForm(f => ({
      ...f,
      oa_codes: f.oa_codes.includes(code)
        ? f.oa_codes.filter(c => c !== code)
        : [...f.oa_codes, code],
    }));

  // Vuelve al inicio del panel scrolleable tanto al mostrar el resultado como al volver al formulario.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [step]);

  const set = (field: keyof GenerateForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const val = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                e.target.type === 'number' ? Number(e.target.value) : e.target.value;
    setForm(f => ({ ...f, [field]: val }));
  };

  const handleOptimizeInstructions = async () => {
    if (!form.instructions.trim()) { toast.error('Escribe algo en las instrucciones primero'); return; }
    setOptimizing(true);
    try {
      const res = await constructorAPI.optimizeInstructions({
        instructions: form.instructions,
        doc_type: form.doc_type,
        subject: form.subject,
        grade_level: form.grade_level,
        topic: form.topic,
      });
      setForm(f => ({ ...f, instructions: res.data.optimized }));
      toast.success('Instrucciones optimizadas ✨');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Error al optimizar');
    } finally {
      setOptimizing(false);
    }
  };

  const handleGenerate = async () => {
    if (!form.topic.trim()) { toast.error('Ingresa el tema del documento'); return; }
    setLoading(true);
    try {
      const res = await constructorAPI.generate(form);
      setResult(res.data);
      setSavedDocumentId(null);
      setImageUrl(null);
      setActivityImages({});
      setImageProgress({ current: 0, total: 0 });

      // Show the document immediately; illustrations load progressively in the background.
      setStep('result');
      toast.success('¡Documento generado!');

      if (Object.keys(collectImageWords(res.data.content?.sections)).length > 0) {
        loadActivityImages(res.data.content.sections);
      }

      if (res.data.images && res.data.images.length > 0) {
        setImageUrl(res.data.images[0]);
      } else if (form.include_images) {
        setImageLoading(true);
        constructorAPI.generateImage({
          subject: form.subject,
          grade_level: form.grade_level,
          topic: form.topic,
        }).then(r => setImageUrl(r.data.image_url))
          .catch(() => {})
          .finally(() => setImageLoading(false));
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Error al generar el documento';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!result) return;
    setExporting(true);
    try {
      const res = format === 'pdf'
        ? await constructorAPI.exportPdf({ content: result.content, activity_images: activityImages })
        : await constructorAPI.exportDocx({ content: result.content, activity_images: activityImages });
      const blob = new Blob([res.data], {
        type: format === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const title = (result.content.title || 'documento').replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ ]/g, '_');
      a.href = url;
      a.download = `${title}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      setShowDownloadModal(false);
      toast.success(`Documento descargado como .${format.toUpperCase()}`);
    } catch {
      toast.error('Error al exportar el documento');
    } finally {
      setExporting(false);
    }
  };

  const handleSaveDocument = async () => {
    if (!result || savedDocumentId || savingDocument) return;
    setSavingDocument(true);
    try {
      const res = await constructorAPI.save({
        title: result.content.title || `${DOC_TYPE_CONFIG[form.doc_type].label} - ${form.topic}`,
        doc_type: form.doc_type,
        subject: form.subject,
        grade_level: form.grade_level,
        content: result.content,
        ai_prompt: result.prompt,
        images: result.images,
      });
      setSavedDocumentId(res.data?.id ?? null);
      toast.success('Documento guardado en Mis Documentos');
    } catch {
      toast.error('Error al guardar el documento');
    } finally {
      setSavingDocument(false);
    }
  };

  const handleSaveToCalendar = async () => {
    if (!result) return;
    setSaving(true);
    try {
      if (savedDocumentId) {
        // El documento ya existe: solo crear el evento para no duplicarlo,
        // preservando la misma categoría y el vínculo [doc_id:N] que usa el backend.
        await eventsAPI.create({
          title: result.content.title || `${DOC_TYPE_CONFIG[form.doc_type].label} - ${form.topic}`,
          description: buildDocLinkDescription(savedDocumentId, form.subject, form.grade_level),
          start_datetime: calendarDate,
          all_day: true,
          category: DOC_TYPE_EVENT_CATEGORY[form.doc_type] || 'general',
        });
      } else {
        const res = await constructorAPI.saveToCalendar({
          title: result.content.title || `${DOC_TYPE_CONFIG[form.doc_type].label} - ${form.topic}`,
          doc_type: form.doc_type,
          subject: form.subject,
          grade_level: form.grade_level,
          content: result.content,
          ai_prompt: result.prompt,
          images: result.images,
          event_date: calendarDate,
        });
        setSavedDocumentId(res.data?.doc_id ?? null);
      }
      setShowCalendarModal(false);
      toast.success('¡Guardado y agregado al calendario!');
    } catch {
      toast.error('Error al guardar en el calendario');
    } finally {
      setSaving(false);
    }
  };

  const handlePrint = () => window.print();

  // ── Ilustraciones de las actividades (backend → OpenRouter, con caché) ──
  const loadActivityImages = async (sections: any[]) => {
    const wordStyleMap = collectImageWords(sections);

    const allWords = Object.keys(wordStyleMap);
    if (!allWords.length) return;
    setLoadingActivityImages(true);
    setImageProgress({ current: 0, total: allWords.length });

    const merged: Record<string, string> = {};

    const photoWords = allWords.filter(w => wordStyleMap[w] !== 'coloring');
    const colorWords = allWords.filter(w => wordStyleMap[w] === 'coloring');

    const processBatch = async (words: string[], style: string) => {
      const batchSize = 3;
      for (let i = 0; i < words.length; i += batchSize) {
        const batch = words.slice(i, i + batchSize);
        try {
          const res = await constructorAPI.searchImages({ words: batch, style });
          const imgs = res.data?.images || {};
          Object.entries(imgs).forEach(([w, url]) => { merged[w.toLowerCase()] = url as string; });
          setActivityImages(prev => ({ ...prev, ...merged }));
        } catch (err) {
          console.warn(`Error generating images for batch [${batch.join(', ')}]:`, err);
        }
        setImageProgress(prev => ({ ...prev, current: Math.min(prev.current + batch.length, prev.total) }));
      }
    };

    try {
      await processBatch(photoWords, 'photo');
      await processBatch(colorWords, 'coloring');
    } catch (err) {
      console.warn('Error loading activity images:', err);
    }
    setLoadingActivityImages(false);
  };
  // ─────────────────────────────────────────────────────────────────────────

  // Los modelos concretos salen de Configuración, así que aquí no se
  // hardcodean nombres: antes decía "Gemini 3 Flash" mientras el modelo real
  // era otro, y un documento generado con Grok se anunciaba como "OpenAI".
  const providerOptions = selectableProviders(settings).map(id => ({
    id,
    desc: id === 'auto'
      ? `Usa ${providerLabel(preferredProvider)}`
      : id === 'openrouter'
        ? String(settings?.text_model || 'Modelo configurado')
        : 'Con tu propia API Key',
  }));

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      <PageHeader
        title="Constructor IA"
        description="Genera pruebas, guías, planificaciones y más con inteligencia artificial"
        actions={step === 'result' && (
          <Button variant="ghost" onClick={() => { setStep('form'); setResult(null); setSavedDocumentId(null); }}>
            <ArrowPathIcon className="w-4 h-4" /> Nueva generación
          </Button>
        )}
      />

      <div ref={scrollRef} className="flex-1 overflow-auto p-4 sm:p-6">
        {step === 'form' ? (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-4 sm:p-6 space-y-5">
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <SparklesIcon className="w-5 h-5 text-primary-600" />
                Configura tu documento
              </h3>

              {/* Doc type */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">Tipo de documento</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, doc_type: type }))}
                      aria-pressed={form.doc_type === type}
                      className={`p-3 rounded-xl border-2 text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                        form.doc_type === type
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <div className="text-xl mb-1">{DOC_TYPE_CONFIG[type].icon}</div>
                      <div className="text-xs font-medium text-gray-700 dark:text-gray-300">{DOC_TYPE_CONFIG[type].label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Subject & Grade */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="ac-subject" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Asignatura</label>
                  <select id="ac-subject" value={form.subject} onChange={set('subject')} className={selectClass}>
                    {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="ac-grade" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Nivel</label>
                  <select id="ac-grade" value={form.grade_level} onChange={set('grade_level')} className={selectClass}>
                    {GRADE_LEVELS.map(g => <option key={g}>{g}</option>)}
                  </select>
                </div>
              </div>

              {/* Topic */}
              <div>
                <label htmlFor="ac-topic" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Tema principal *</label>
                <input
                  id="ac-topic"
                  value={form.topic}
                  onChange={set('topic')}
                  className={selectClass}
                  placeholder="Ej: Fracciones, La célula, Segunda Guerra Mundial..."
                />
              </div>

              {/* Objetivos de Aprendizaje MINEDUC */}
              {oaList.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2 gap-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Objetivos de Aprendizaje (MINEDUC)
                    </label>
                    {form.oa_codes.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setForm(f => ({ ...f, oa_codes: [] }))}
                        className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded"
                      >
                        Quitar selección ({form.oa_codes.length})
                      </button>
                    )}
                  </div>
                  <div className="max-h-56 overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-600 divide-y divide-gray-100 dark:divide-gray-700">
                    {oaList.map(oa => {
                      const checked = form.oa_codes.includes(oa.code);
                      return (
                        <label
                          key={oa.code}
                          className={`flex gap-3 p-3 cursor-pointer transition-colors ${
                            checked ? 'bg-primary-50 dark:bg-primary-900/30' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleOa(oa.code)}
                            className="w-4 h-4 rounded mt-0.5 shrink-0"
                          />
                          <span className="text-xs">
                            <span className="font-semibold text-primary-700 dark:text-primary-400">{oa.code}</span>
                            <span className="text-gray-600 dark:text-gray-400"> — {oa.description}</span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                    Sin selección, la IA se guía por todos los OA del nivel. Marcar OA específicos enfoca el documento.
                  </p>
                </div>
              )}
              {loadingOa && oaList.length === 0 && (
                <p className="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
                  <ArrowPathIcon className="w-3 h-3 animate-spin" /> Buscando objetivos del currículum...
                </p>
              )}

              {/* Num questions & Difficulty */}
              {['prueba', 'evaluacion', 'guia'].includes(form.doc_type) && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="ac-num-questions" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">N° de preguntas</label>
                    <input id="ac-num-questions" type="number" min={1} max={30} value={form.num_questions} onChange={set('num_questions')} className={selectClass} />
                  </div>
                  <div>
                    <label htmlFor="ac-difficulty" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Dificultad</label>
                    <select id="ac-difficulty" value={form.difficulty} onChange={set('difficulty')} className={selectClass}>
                      <option value="fácil">Fácil</option>
                      <option value="medio">Medio</option>
                      <option value="difícil">Difícil</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Instructions */}
              <div>
                <div className="flex items-center justify-between mb-1 gap-2">
                  <label htmlFor="ac-instructions" className="text-sm font-medium text-gray-700 dark:text-gray-300">Instrucciones adicionales (opcional)</label>
                  <button
                    type="button"
                    onClick={handleOptimizeInstructions}
                    disabled={optimizing || !form.instructions.trim()}
                    aria-busy={optimizing}
                    className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-700 hover:bg-purple-100 dark:hover:bg-purple-900/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 shrink-0"
                    title="Optimiza tu texto para obtener mejores resultados con la IA"
                  >
                    {optimizing
                      ? <><ArrowPathIcon className="w-3 h-3 animate-spin" /> Optimizando...</>
                      : <><SparklesIcon className="w-3 h-3" /> Optimizar con IA</>}
                  </button>
                </div>
                <textarea
                  id="ac-instructions"
                  value={form.instructions}
                  onChange={set('instructions')}
                  rows={3}
                  className={`${selectClass} resize-none`}
                  placeholder="Ej: Incluir contextualización, énfasis en pensamiento crítico, formato específico..."
                />
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Escribe en lenguaje simple y el botón ✨ lo convertirá en un prompt técnico optimizado.</p>
              </div>

              {/* Provider selector */}
              {providerOptions.length === 0 ? (
                <div className="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    No hay ninguna API Key configurada. Ve a <strong>Configuración</strong> y agrega tu clave de
                    OpenRouter para poder generar documentos.
                  </p>
                </div>
              ) : (
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">Proveedor de IA</label>
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  {providerOptions.map(p => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setForm(f => ({ ...f, provider: p.id }))}
                      aria-pressed={form.provider === p.id}
                      className={`p-3 rounded-xl border-2 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                        form.provider === p.id
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <span className="text-lg">{PROVIDERS[p.id].emoji}</span>
                      <p className="text-xs font-semibold text-gray-800 dark:text-gray-200 mt-1">{PROVIDERS[p.id].label}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{p.desc}</p>
                    </button>
                  ))}
                </div>
              </div>
              )}

              {/* Options */}
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  <input type="checkbox" checked={form.include_answers} onChange={set('include_answers')} className="w-4 h-4 rounded" />
                  Incluir pauta / respuestas
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  <input type="checkbox" checked={form.include_images} onChange={set('include_images')} className="w-4 h-4 rounded" />
                  <PhotoIcon className="w-4 h-4 text-gray-500" />
                  Generar imagen ilustrativa
                </label>
              </div>

              {/* Generate button */}
              <Button
                onClick={handleGenerate}
                busy={loading}
                className="w-full py-3 text-base font-semibold"
              >
                {loading ? (
                  <>
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                    Generando con IA...
                  </>
                ) : (
                  <>
                    <SparklesIcon className="w-5 h-5" />
                    Generar {DOC_TYPE_CONFIG[form.doc_type].label}
                  </>
                )}
              </Button>

              {loading && (
                <p className="text-xs text-gray-500 dark:text-gray-400 text-center -mt-3">
                  Generando contenido del documento...
                </p>
              )}
            </div>
          </div>
        ) : (
          result && (
            <div className="max-w-3xl mx-auto">
              {/* Actions bar */}
              <div className="flex flex-col gap-3 mb-4 no-print">
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white">{result.content.title}</h3>
                  {result.provider_used && (
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      Generado con {providerEmoji(result.provider_used)} {providerLabel(result.provider_used)}
                    </span>
                  )}
                  {loadingActivityImages && imageProgress.total > 0 && (
                    <div className="mt-2 max-w-xs">
                      <p className="text-xs font-medium text-primary-700 dark:text-primary-400">
                        Generando ilustraciones: {imageProgress.current} de {imageProgress.total}
                      </p>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 overflow-hidden mt-1">
                        <div
                          className="bg-primary-600 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.round((imageProgress.current / imageProgress.total) * 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={handleSaveDocument}
                    busy={savingDocument}
                    disabled={!!savedDocumentId}
                  >
                    {savedDocumentId ? <CheckCircleIcon className="w-4 h-4 text-emerald-600" /> : <BookmarkIcon className="w-4 h-4" />}
                    {savedDocumentId ? 'Guardado' : 'Guardar documento'}
                  </Button>
                  <Button onClick={() => setShowDownloadModal(true)} className="bg-blue-600 hover:bg-blue-700">
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    Descargar
                  </Button>
                  <Button variant="secondary" onClick={handlePrint}>
                    <DocumentArrowDownIcon className="w-4 h-4" />
                    Imprimir / PDF
                  </Button>
                  <Button onClick={() => setShowCalendarModal(true)} className="bg-emerald-600 hover:bg-emerald-700">
                    <CalendarDaysIcon className="w-4 h-4" />
                    Cargar en Calendario
                  </Button>
                </div>
              </div>

              <AppDialog
                open={showDownloadModal}
                onClose={() => setShowDownloadModal(false)}
                title="Descargar documento"
                description="Selecciona el formato de descarga"
                maxWidth="sm"
                footer={
                  <Button variant="secondary" className="w-full" onClick={() => setShowDownloadModal(false)}>
                    Cancelar
                  </Button>
                }
              >
                <div className="flex flex-col gap-3">
                  <button
                    onClick={() => handleExport('pdf')}
                    disabled={exporting}
                    className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-red-200 dark:border-red-800 hover:border-red-400 dark:hover:border-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 min-h-[44px]"
                  >
                    <span className="text-2xl">📄</span>
                    <div className="text-left">
                      <p className="font-semibold text-gray-900 dark:text-white text-sm">PDF</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Ideal para imprimir o compartir</p>
                    </div>
                  </button>
                  <button
                    onClick={() => handleExport('docx')}
                    disabled={exporting}
                    className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-blue-200 dark:border-blue-800 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 min-h-[44px]"
                  >
                    <span className="text-2xl">📝</span>
                    <div className="text-left">
                      <p className="font-semibold text-gray-900 dark:text-white text-sm">Word (.docx)</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">Para editar en Word o Google Docs</p>
                    </div>
                  </button>
                </div>
                {exporting && (
                  <p className="text-center text-xs text-gray-400 mt-3 flex items-center justify-center gap-1" role="status" aria-live="polite">
                    <ArrowPathIcon className="w-3 h-3 animate-spin" /> Generando archivo...
                  </p>
                )}
              </AppDialog>

              <AppDialog
                open={showCalendarModal}
                onClose={() => setShowCalendarModal(false)}
                title="Cargar en Calendario"
                maxWidth="sm"
                footer={
                  <div className="flex gap-2">
                    <Button variant="secondary" className="flex-1" onClick={() => setShowCalendarModal(false)}>
                      Cancelar
                    </Button>
                    <Button className="flex-1 bg-emerald-600 hover:bg-emerald-700" onClick={handleSaveToCalendar} busy={saving}>
                      {saving ? 'Guardando...' : 'Confirmar'}
                    </Button>
                  </div>
                }
              >
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  Selecciona el día en que usarás este documento. Se guardará en el VPS y aparecerá en tu calendario.
                </p>
                <label htmlFor="ac-calendar-date" className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Fecha</label>
                <input
                  id="ac-calendar-date"
                  type="date"
                  value={calendarDate}
                  onChange={e => setCalendarDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                />
              </AppDialog>

              <DocumentPreview
                id="doc-print-content"
                content={result.content}
                imageUrl={imageUrl}
                imageLoading={imageLoading}
                activityImages={activityImages}
                activityImagesLoading={loadingActivityImages}
                showStudentRow
              />
            </div>
          )
        )}
      </div>
    </div>
  );
}
