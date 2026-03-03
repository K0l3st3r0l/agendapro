import { useState } from 'react';
import { constructorAPI } from '../services/api';
import type { DocType, DocumentContent } from '../types';
import { DOC_TYPE_CONFIG, SUBJECTS, GRADE_LEVELS } from '../types';
import toast from 'react-hot-toast';
import {
  SparklesIcon,
  DocumentArrowDownIcon,
  BookmarkIcon,
  ArrowPathIcon,
  PhotoIcon,
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
};

export default function AIConstructor() {
  const [form, setForm] = useState<GenerateForm>(defaultForm);
  const [step, setStep] = useState<Step>('form');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ content: DocumentContent; prompt: string; images: string[] } | null>(null);
  const [saving, setSaving] = useState(false);

  const set = (field: keyof GenerateForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const val = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                e.target.type === 'number' ? Number(e.target.value) : e.target.value;
    setForm(f => ({ ...f, [field]: val }));
  };

  const handleGenerate = async () => {
    if (!form.topic.trim()) { toast.error('Ingresa el tema del documento'); return; }
    setLoading(true);
    try {
      const res = await constructorAPI.generate(form);
      setResult(res.data);
      setStep('result');
      toast.success('¡Documento generado exitosamente!');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Error al generar el documento';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!result) return;
    setSaving(true);
    try {
      await constructorAPI.save({
        title: result.content.title || `${DOC_TYPE_CONFIG[form.doc_type].label} - ${form.topic}`,
        doc_type: form.doc_type,
        subject: form.subject,
        grade_level: form.grade_level,
        content: result.content,
        ai_prompt: result.prompt,
        images: result.images,
      });
      toast.success('Documento guardado en Mis Documentos');
    } catch {
      toast.error('Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handlePrint = () => window.print();

  const renderSection = (section: any, idx: number) => {
    const content = section.content;
    return (
      <div key={idx} className="mb-6">
        {section.title && <h3 className="text-base font-semibold text-gray-800 mb-2 border-b border-gray-200 pb-1">{section.title}</h3>}
        {typeof content === 'string' && <p className="text-sm text-gray-700 whitespace-pre-line">{content}</p>}
        {Array.isArray(content) && content.map((item: any, i: number) => (
          <div key={i} className="mb-3">
            {typeof item === 'string' ? (
              <p className="text-sm text-gray-700">{i + 1}. {item}</p>
            ) : (
              <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                <p className="text-sm font-medium text-gray-800">
                  {item.number || i + 1}. {item.text}
                  {item.points && <span className="ml-2 text-xs text-gray-500">({item.points} pts)</span>}
                </p>
                {item.options && (
                  <ul className="mt-2 space-y-1 ml-4">
                    {item.options.map((opt: string, j: number) => (
                      <li key={j} className="text-sm text-gray-600">
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
        ))}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Constructor IA</h2>
          <p className="text-sm text-gray-500">Genera pruebas, guías, planificaciones y más con inteligencia artificial</p>
        </div>
        {step === 'result' && (
          <button onClick={() => { setStep('form'); setResult(null); }}
            className="text-sm text-gray-600 hover:text-gray-800 flex items-center gap-1.5">
            <ArrowPathIcon className="w-4 h-4" /> Nueva generación
          </button>
        )}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {step === 'form' ? (
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-5">
              <h3 className="text-base font-semibold text-gray-800 flex items-center gap-2">
                <SparklesIcon className="w-5 h-5 text-primary-600" />
                Configura tu documento
              </h3>

              {/* Doc type */}
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-2">Tipo de documento</label>
                <div className="grid grid-cols-5 gap-2">
                  {(Object.keys(DOC_TYPE_CONFIG) as DocType[]).map(type => (
                    <button
                      key={type}
                      onClick={() => setForm(f => ({ ...f, doc_type: type }))}
                      className={`p-3 rounded-xl border-2 text-center transition-all ${
                        form.doc_type === type
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="text-xl mb-1">{DOC_TYPE_CONFIG[type].icon}</div>
                      <div className="text-xs font-medium text-gray-700">{DOC_TYPE_CONFIG[type].label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Subject & Grade */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Asignatura</label>
                  <select value={form.subject} onChange={set('subject')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none">
                    {SUBJECTS.map(s => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700 block mb-1">Nivel</label>
                  <select value={form.grade_level} onChange={set('grade_level')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none">
                    {GRADE_LEVELS.map(g => <option key={g}>{g}</option>)}
                  </select>
                </div>
              </div>

              {/* Topic */}
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Tema principal *</label>
                <input
                  value={form.topic}
                  onChange={set('topic')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none"
                  placeholder="Ej: Fracciones, La célula, Segunda Guerra Mundial..."
                />
              </div>

              {/* Num questions & Difficulty */}
              {['prueba', 'evaluacion', 'guia'].includes(form.doc_type) && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 block mb-1">N° de preguntas</label>
                    <input type="number" min={1} max={30} value={form.num_questions} onChange={set('num_questions')}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none" />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700 block mb-1">Dificultad</label>
                    <select value={form.difficulty} onChange={set('difficulty')}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none">
                      <option value="fácil">Fácil</option>
                      <option value="medio">Medio</option>
                      <option value="difícil">Difícil</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Instructions */}
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">Instrucciones adicionales (opcional)</label>
                <textarea
                  value={form.instructions}
                  onChange={set('instructions')}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 outline-none resize-none"
                  placeholder="Ej: Incluir contextualización, énfasis en pensamiento crítico, formato específico..."
                />
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
                  Generar imagen ilustrativa (DALL·E 3)
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
                <p className="text-center text-xs text-gray-500 -mt-3">
                  Esto puede tomar 15-30 segundos...
                </p>
              )}
            </div>
          </div>
        ) : (
          result && (
            <div className="max-w-3xl mx-auto">
              {/* Actions bar */}
              <div className="flex items-center justify-between mb-4 no-print">
                <h3 className="font-semibold text-gray-900">{result.content.title}</h3>
                <div className="flex gap-2">
                  <button onClick={handleSave} disabled={saving}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-60">
                    <BookmarkIcon className="w-4 h-4" />
                    {saving ? 'Guardando...' : 'Guardar'}
                  </button>
                  <button onClick={handlePrint}
                    className="flex items-center gap-1.5 px-3 py-2 text-sm bg-gray-700 text-white rounded-lg hover:bg-gray-800">
                    <DocumentArrowDownIcon className="w-4 h-4" />
                    Imprimir / PDF
                  </button>
                </div>
              </div>

              {/* Document preview */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 print-content">
                {/* Header */}
                <div className="text-center mb-6 pb-4 border-b-2 border-gray-900">
                  <h1 className="text-xl font-bold text-gray-900 uppercase">{result.content.title}</h1>
                  {result.content.metadata && (
                    <div className="flex justify-center gap-6 mt-2 text-sm text-gray-600">
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
                {result.images && result.images.length > 0 && (
                  <div className="mb-4 flex justify-center">
                    <img src={result.images[0]} alt="Ilustración generada por IA" className="max-h-48 rounded-lg border border-gray-200" />
                  </div>
                )}

                {/* Instructions */}
                {result.content.instructions && (
                  <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200">
                    <p className="text-sm text-gray-700"><strong>Instrucciones:</strong> {result.content.instructions}</p>
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
