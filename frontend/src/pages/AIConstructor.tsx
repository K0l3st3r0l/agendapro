import { useState, useEffect } from 'react';
import { constructorAPI, settingsAPI } from '../services/api';
import type { DocType, DocumentContent } from '../types';
import { DOC_TYPE_CONFIG, SUBJECTS, GRADE_LEVELS } from '../types';
import toast from 'react-hot-toast';
import {
  SparklesIcon,
  DocumentArrowDownIcon,
  BookmarkIcon,
  ArrowPathIcon,
  PhotoIcon,
  CalendarDaysIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';

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
  provider: 'gemini' | 'openai' | 'xai' | 'auto';
}

const defaultForm: GenerateForm = {
  doc_type: 'prueba',
  subject: 'Matemática',
  grade_level: '5° Básico',
  topic: '',
  instructions: '',
  num_questions: 10,
  difficulty: 'medio',
  include_images: false,
  include_answers: true,
  provider: 'auto',
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

  useEffect(() => {
    settingsAPI.get().then(r => setPreferredProvider(r.data.preferred_provider || 'gemini')).catch(() => {});
  }, []);

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
      setImageUrl(null);
      setActivityImages({});
      // Don't switch to result step yet — load images first
      toast.success('¡Documento generado! Generando ilustraciones...');

      // Load activity images before showing the document
      const hasImages = res.data.content?.sections?.some((s: any) =>
        Array.isArray(s.content) && s.content.some((item: any) =>
          item && typeof item === 'object' && Array.isArray(item.image_words) && item.image_words.length > 0
        )
      );

      if (hasImages) {
        await loadActivityImages(res.data.content.sections);
      }

      // Now show the result
      setStep('result');

      // Load header image in background (non-blocking)
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

  const handleDownload = () => {
    if (!result) return;
    const el = document.getElementById('doc-print-content');
    if (!el) return;
    const title = result.content.title || 'documento';
    const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    @page { size: Letter; margin: 15mm 18mm; }
    body { font-family: Arial, sans-serif; color: #111; background: white; margin: 0; padding: 24px; }
    h1 { font-size: 18pt; font-weight: bold; text-align: center; text-transform: uppercase; }
    h3 { font-size: 11pt; font-weight: 600; border-bottom: 1px solid #aaa; padding-bottom: 4px; margin-top: 20px; }
    p, li { font-size: 10pt; line-height: 1.5; }
    .meta { text-align: center; font-size: 10pt; color: #444; margin: 4px 0 12px; }
    .student-row { display: flex; gap: 32px; border: 1px solid #ccc; padding: 8px 12px; border-radius: 4px; margin: 12px 0; font-size: 10pt; }
    .instructions-box { background: #f9f9f9; border: 1px solid #ccc; padding: 8px 12px; border-radius: 4px; margin: 12px 0; font-size: 10pt; }
    .question { background: #f5f5f5; border: 1px solid #ddd; padding: 8px 12px; border-radius: 4px; margin: 8px 0; }
    .answer { color: #059669; font-size: 9pt; font-weight: 600; }
    img { max-height: 120mm; display: block; margin: 8px auto; }
    .section { margin-bottom: 20px; page-break-inside: avoid; }
  </style>
</head>
<body>
${el.innerHTML}
</body>
</html>`;
    const win = window.open('', '_blank');
    if (!win) { toast.error('Permite ventanas emergentes para descargar PDF'); return; }
    win.document.write(html);
    win.document.close();
    win.onload = () => { win.focus(); win.print(); };
    toast.success('Selecciona "Guardar como PDF" en el diálogo de impresión');
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

  const handleSaveToCalendar = async () => {
    if (!result) return;
    setSaving(true);
    try {
      await constructorAPI.saveToCalendar({
        title: result.content.title || `${DOC_TYPE_CONFIG[form.doc_type].label} - ${form.topic}`,
        doc_type: form.doc_type,
        subject: form.subject,
        grade_level: form.grade_level,
        content: result.content,
        ai_prompt: result.prompt,
        images: result.images,
        event_date: calendarDate,
      });
      setShowCalendarModal(false);
      toast.success('¡Guardado y agregado al calendario!');
    } catch {
      toast.error('Error al guardar en el calendario');
    } finally {
      setSaving(false);
    }
  };

  const handlePrint = () => window.print();

  // ── Activity image fetching (backend search-images with Wikimedia + Pixabay + Wikipedia) ──
  const loadActivityImages = async (sections: any[]) => {
    const wordStyleMap: Record<string, string> = {};
    sections.forEach(sec => {
      const items = sec.content;
      if (!Array.isArray(items)) return;
      items.forEach((item: any) => {
        if (item && typeof item === 'object' && Array.isArray(item.image_words)) {
          const style = item.image_style || 'photo';
          item.image_words.forEach((w: string) => {
            const key = w.toLowerCase().trim();
            if (key.length > 1) wordStyleMap[key] = style;
          });
        }
      });
    });

    const allWords = Object.keys(wordStyleMap);
    if (!allWords.length) return;
    setLoadingActivityImages(true);
    setImageProgress({ current: 0, total: allWords.length });

    const merged: Record<string, string> = {};

    // Group words by style
    const photoWords = allWords.filter(w => wordStyleMap[w] !== 'coloring');
    const colorWords = allWords.filter(w => wordStyleMap[w] === 'coloring');

    // Process in small batches of 3 to avoid timeouts
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

  const renderMarkdown = (text: string): string => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>');
  };

  const getItemText = (item: any): string => {
    return item.text || item.question || item.activity || item.description || item.content || item.title || JSON.stringify(item);
  };

  const getItemImageWords = (item: any): string[] => {
    if (item && typeof item === 'object' && Array.isArray(item.image_words)) {
      return item.image_words.map((w: string) => w.toLowerCase().trim()).filter((w: string) => w.length > 1);
    }
    return [];
  };

  const ImageGrid = ({ words }: { words: string[] }) => {
    if (!words.length) return null;
    return (
      <div className="mt-3 flex flex-wrap gap-3 justify-center">
        {words.map(word => {
          const imgUrl = activityImages[word];
          return (
            <div key={word} className="text-center">
              {imgUrl ? (
                <img src={imgUrl} alt={word} className="w-24 h-24 object-cover rounded-lg border border-gray-200 mx-auto shadow-sm" />
              ) : (
                <div className="w-24 h-24 bg-gray-100 rounded-lg border border-dashed border-gray-300 flex items-center justify-center">
                  {loadingActivityImages
                    ? <ArrowPathIcon className="w-4 h-4 text-gray-300 animate-spin" />
                    : <PhotoIcon className="w-6 h-6 text-gray-300" />}
                </div>
              )}
              <p className="text-xs text-gray-600 mt-1 capitalize font-medium">{word}</p>
            </div>
          );
        })}
      </div>
    );
  };

  const renderSection = (section: any, idx: number) => {
    const content = section.content;
    return (
      <div key={idx} className="mb-6">
        {section.title && <h3 className="text-base font-semibold text-gray-900 mb-2 border-b border-gray-300 pb-1">{section.title}</h3>}
        {typeof content === 'string' && (
          <p className="text-sm text-gray-900 whitespace-pre-line" dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} />
        )}
        {Array.isArray(content) && content.map((item: any, i: number) => {
          const imgWords = getItemImageWords(item);
          return (
            <div key={i} className="mb-3">
              {typeof item === 'string' ? (
                <p className="text-sm text-gray-900" dangerouslySetInnerHTML={{ __html: `${i + 1}. ${renderMarkdown(item)}` }} />
              ) : (
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-sm font-medium text-gray-900">
                    <span dangerouslySetInnerHTML={{ __html: `${item.number || i + 1}. ${renderMarkdown(getItemText(item))}` }} />
                    {item.points && <span className="ml-2 text-xs text-gray-600">({item.points} pts)</span>}
                  </p>
                  <ImageGrid words={imgWords} />
                  {item.options && (
                    <ul className="mt-2 space-y-1 ml-4">
                      {item.options.map((opt: string, j: number) => (
                        <li key={j} className="text-sm text-gray-800">
                          {String.fromCharCode(65 + j)}) {opt}
                        </li>
                      ))}
                    </ul>
                  )}
                  {item.answer && (
                    <p className="mt-1 text-xs text-emerald-600 font-medium">✓ {item.answer}</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="px-6 py-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Constructor IA</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400">Genera pruebas, guías, planificaciones y más con inteligencia artificial</p>
        </div>
        {step === 'result' && (
          <button onClick={() => { setStep('form'); setResult(null); }}
            className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 flex items-center gap-1.5">
            <ArrowPathIcon className="w-4 h-4" /> Nueva generación
          </button>
        )}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {step === 'form' ? (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 space-y-5">
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <SparklesIcon className="w-5 h-5 text-primary-600" />
                Configura tu documento
              </h3>

              {/* Doc type */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">Tipo de documento</label>
                <div className="grid grid-cols-5 gap-2">
                  {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
                    <button
                      key={type}
                      onClick={() => setForm(f => ({ ...f, doc_type: type }))}
                      className={`p-3 rounded-xl border-2 text-center transition-all ${
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
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Asignatura</label>
                  <select value={form.subject} onChange={set('subject')}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                    {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Nivel</label>
                  <select value={form.grade_level} onChange={set('grade_level')}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                    {GRADE_LEVELS.map(g => <option key={g}>{g}</option>)}
                  </select>
                </div>
              </div>

              {/* Topic */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Tema principal *</label>
                <input
                  value={form.topic}
                  onChange={set('topic')}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder="Ej: Fracciones, La célula, Segunda Guerra Mundial..."
                />
              </div>

              {/* Num questions & Difficulty */}
              {['prueba', 'evaluacion', 'guia'].includes(form.doc_type) && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">N° de preguntas</label>
                    <input type="number" min={1} max={30} value={form.num_questions} onChange={set('num_questions')}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Dificultad</label>
                    <select value={form.difficulty} onChange={set('difficulty')}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                      <option value="fácil">Fácil</option>
                      <option value="medio">Medio</option>
                      <option value="difícil">Difícil</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Instructions */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Instrucciones adicionales (opcional)</label>
                  <button
                    type="button"
                    onClick={handleOptimizeInstructions}
                    disabled={optimizing || !form.instructions.trim()}
                    className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-700 hover:bg-purple-100 dark:hover:bg-purple-900/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all font-medium"
                    title="Optimiza tu texto para obtener mejores resultados con la IA"
                  >
                    {optimizing
                      ? <><ArrowPathIcon className="w-3 h-3 animate-spin" /> Optimizando...</>
                      : <><SparklesIcon className="w-3 h-3" /> Optimizar con IA</>}
                  </button>
                </div>
                <textarea
                  value={form.instructions}
                  onChange={set('instructions')}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none resize-none bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder="Ej: Incluir contextualización, énfasis en pensamiento crítico, formato específico..."
                />
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Escribe en lenguaje simple y el botón ✨ lo convertirá en un prompt técnico optimizado.</p>
              </div>

              {/* Provider selector */}
              <div>
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-2">Proveedor de IA</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'auto', label: 'Auto', desc: `Usa ${preferredProvider === 'gemini' ? 'Google Gemini' : 'OpenAI'} (preferido)`, emoji: '⚡' },
                    { id: 'gemini', label: 'Google Gemini', desc: 'Gratis · Gemini 3 Flash', emoji: '🌐' },
                    { id: 'openai', label: 'OpenAI', desc: 'GPT-4o · Mayor calidad', emoji: '🤖' },
                  ].map(p => (
                    <button
                      key={p.id}
                      onClick={() => setForm(f => ({ ...f, provider: p.id as any }))}
                      className={`p-3 rounded-xl border-2 text-left transition-all ${
                        form.provider === p.id
                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500'
                      }`}
                    >
                      <span className="text-lg">{p.emoji}</span>
                      <p className="text-xs font-semibold text-gray-800 dark:text-gray-200 mt-1">{p.label}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{p.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Options */}
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.include_answers} onChange={set('include_answers')} className="rounded" />
                  Incluir pauta / respuestas
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.include_images} onChange={set('include_images')} className="rounded" />
                  <PhotoIcon className="w-4 h-4 text-gray-500" />
                  Generar imagen ilustrativa
                </label>
              </div>

              {/* Generate button */}
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full py-3 bg-primary-600 hover:bg-primary-700 text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-60"
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
              </button>

              {loading && (
                <div className="text-center -mt-3 space-y-2">
                  {imageProgress.total > 0 ? (
                    <>
                      <p className="text-sm font-medium text-primary-700 dark:text-primary-400">
                        Generando ilustraciones: {imageProgress.current} de {imageProgress.total}
                      </p>
                      <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5 overflow-hidden">
                        <div
                          className="bg-primary-600 h-2.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.round((imageProgress.current / imageProgress.total) * 100)}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-400">
                        Cada imagen se genera con IA para máxima calidad...
                      </p>
                    </>
                  ) : (
                    <p className="text-xs text-gray-500">
                      Generando contenido del documento...
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          result && (
            <div className="max-w-3xl mx-auto">
              {/* Actions bar */}
              <div className="flex items-center justify-between mb-4 no-print">
                <div>
                  <h3 className="font-semibold text-gray-900">{result.content.title}</h3>
                  {result.provider_used && (
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      Generado con {result.provider_used === 'gemini' ? '🌐 Google Gemini' : '🤖 OpenAI'}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setShowDownloadModal(true)}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    Descargar
                  </button>
                  <button onClick={handlePrint}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-700 text-white rounded-lg hover:bg-gray-800">
                    <DocumentArrowDownIcon className="w-4 h-4" />
                    Imprimir / PDF
                  </button>
                  <button onClick={() => setShowCalendarModal(true)}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700">
                    <CalendarDaysIcon className="w-4 h-4" />
                    Cargar en Calendario
                  </button>
                </div>
              </div>

              {/* Download modal */}
              {showDownloadModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 no-print">
                  <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <ArrowDownTrayIcon className="w-5 h-5 text-blue-600" />
                        Descargar documento
                      </h3>
                      <button onClick={() => setShowDownloadModal(false)} className="text-gray-400 hover:text-gray-600">
                        <XMarkIcon className="w-5 h-5" />
                      </button>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-5">Selecciona el formato de descarga:</p>
                    <div className="flex flex-col gap-3">
                      <button onClick={() => handleExport('pdf')} disabled={exporting}
                        className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-red-200 dark:border-red-800 hover:border-red-400 dark:hover:border-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-60 transition-colors">
                        <span className="text-2xl">📄</span>
                        <div className="text-left">
                          <p className="font-semibold text-gray-900 dark:text-white text-sm">PDF</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">Ideal para imprimir o compartir</p>
                        </div>
                      </button>
                      <button onClick={() => handleExport('docx')} disabled={exporting}
                        className="flex items-center gap-3 px-4 py-3 rounded-xl border-2 border-blue-200 dark:border-blue-800 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-60 transition-colors">
                        <span className="text-2xl">📝</span>
                        <div className="text-left">
                          <p className="font-semibold text-gray-900 dark:text-white text-sm">Word (.docx)</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">Para editar en Word o Google Docs</p>
                        </div>
                      </button>
                    </div>
                    {exporting && (
                      <p className="text-center text-xs text-gray-400 mt-3 flex items-center justify-center gap-1">
                        <ArrowPathIcon className="w-3 h-3 animate-spin" /> Generando archivo...
                      </p>
                    )}
                    <button onClick={() => setShowDownloadModal(false)}
                      className="mt-4 w-full px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300">
                      Cancelar
                    </button>
                  </div>
                </div>
              )}

              {/* Calendar modal */}
              {showCalendarModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 no-print">
                  <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                        <CalendarDaysIcon className="w-5 h-5 text-emerald-600" />
                        Cargar en Calendario
                      </h3>
                      <button onClick={() => setShowCalendarModal(false)} className="text-gray-400 hover:text-gray-600">
                        <XMarkIcon className="w-5 h-5" />
                      </button>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      Selecciona el día en que usarás este documento. Se guardará en el VPS y aparecerá en tu calendario.
                    </p>
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300 block mb-1">Fecha</label>
                    <input
                      type="date"
                      value={calendarDate}
                      onChange={e => setCalendarDate(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm mb-4 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                    />
                    <div className="flex gap-2">
                      <button onClick={() => setShowCalendarModal(false)}
                        className="flex-1 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300">
                        Cancelar
                      </button>
                      <button onClick={handleSaveToCalendar} disabled={saving}
                        className="flex-1 px-4 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-60 font-medium">
                        {saving ? 'Guardando...' : 'Confirmar'}
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Document preview */}
              <div id="doc-print-content" className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 print-content">
                {/* Header */}
                <div className="text-center mb-6 pb-4 border-b-2 border-gray-900">
                  <h1 className="text-xl font-bold text-gray-900 uppercase">{result.content.title}</h1>
                  {result.content.metadata && (
                    <div className="flex justify-center gap-6 mt-2 text-sm text-gray-700 font-medium">
                      <span><strong>Asignatura:</strong> {result.content.metadata.subject}</span>
                      <span><strong>Nivel:</strong> {result.content.metadata.grade}</span>
                      {result.content.metadata.total_points && (
                        <span><strong>Puntaje:</strong> {result.content.metadata.total_points} pts</span>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-4 mt-4 text-left border border-gray-300 rounded p-3">
                    <div className="text-sm"><strong>Nombre:</strong> _________________</div>
                    <div className="text-sm"><strong>Curso:</strong> _______________</div>
                    <div className="text-sm"><strong>Fecha:</strong> _______________</div>
                  </div>
                </div>

                {/* AI Image */}
                {imageLoading && (
                  <div className="mb-4 flex justify-center items-center gap-2 text-sm text-gray-400">
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    Generando ilustración...
                  </div>
                )}
                {!imageLoading && imageUrl && (
                  <div className="mb-4 flex justify-center">
                    <img
                      src={imageUrl}
                      alt="Ilustración generada por IA"
                      className="max-h-48 rounded-lg border border-gray-200"
                      onError={(e) => {
                        // If the image fails to load, hide it gracefully
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}

                {/* Instructions */}
                {result.content.instructions && (
                  <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <p className="text-sm text-gray-900"><strong>Instrucciones:</strong> {result.content.instructions}</p>
                  </div>
                )}

                {/* Sections */}
                {result.content.sections?.map((section: any, idx: number) => renderSection(section, idx))}
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
}
