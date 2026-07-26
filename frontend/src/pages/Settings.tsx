import { useState, useEffect } from 'react';
import { settingsAPI } from '../services/api';
import toast from 'react-hot-toast';
import {
  KeyIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckCircleIcon,
  XCircleIcon,
  TrashIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { SparklesIcon } from '@heroicons/react/24/solid';
import PageHeader from '../components/ui/PageHeader';
import AppDialog from '../components/ui/AppDialog';
import { Button, IconButton } from '../components/ui/Button';
import { ErrorPanel, LoadingPanel } from '../components/ui/StatePanel';
import { PROVIDERS } from '../config/providers';

type Provider = 'gemini' | 'openai' | 'xai';

interface SettingsState {
  has_openai: boolean;
  has_google: boolean;
  has_xai: boolean;
  openai_api_key_masked: string | null;
  google_api_key_masked: string | null;
  xai_api_key_masked: string | null;
  preferred_provider: Provider;
  gemini_model: string;
  gemini_image_model: string;
  openai_model: string;
  xai_model: string;
}

interface FormSnapshot {
  preferred: Provider;
  geminiModel: string;
  geminiImageModel: string;
  openaiModel: string;
  xaiModel: string;
}

const selectClass =
  'w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100';

const keyInputClass =
  'w-full px-3 py-2.5 pr-12 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500';

const providerNames: Record<'openai' | 'google' | 'xai', string> = { openai: 'OpenAI', google: 'Google', xai: 'xAI (Grok)' };

export default function Settings() {
  const [settings, setSettings] = useState<SettingsState | null>(null);
  const [fetchError, setFetchError] = useState(false);
  const [openaiKey, setOpenaiKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');
  const [xaiKey, setXaiKey] = useState('');
  const [preferred, setPreferred] = useState<Provider>('gemini');
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash');
  const [geminiImageModel, setGeminiImageModel] = useState('gemini-2.0-flash-preview-image-generation');
  const [openaiModel, setOpenaiModel] = useState('gpt-4o');
  const [xaiModel, setXaiModel] = useState('grok-3-mini');
  const [snapshot, setSnapshot] = useState<FormSnapshot | null>(null);
  const [showOpenai, setShowOpenai] = useState(false);
  const [showGoogle, setShowGoogle] = useState(false);
  const [showXai, setShowXai] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<'openai' | 'google' | 'xai' | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    setLoading(true);
    setFetchError(false);
    try {
      const res = await settingsAPI.get();
      const data = res.data;
      setSettings(data);
      const snap: FormSnapshot = {
        preferred: data.preferred_provider || 'gemini',
        geminiModel: data.gemini_model || 'gemini-2.5-flash',
        geminiImageModel: data.gemini_image_model || 'gemini-2.0-flash-preview-image-generation',
        openaiModel: data.openai_model || 'gpt-4o',
        xaiModel: data.xai_model || 'grok-3-mini',
      };
      setPreferred(snap.preferred);
      setGeminiModel(snap.geminiModel);
      setGeminiImageModel(snap.geminiImageModel);
      setOpenaiModel(snap.openaiModel);
      setXaiModel(snap.xaiModel);
      setSnapshot(snap);
    } catch {
      setFetchError(true);
      toast.error('Error al cargar configuración');
    } finally {
      setLoading(false);
    }
  };

  const dirty = !!openaiKey || !!googleKey || !!xaiKey || (snapshot != null && (
    preferred !== snapshot.preferred ||
    geminiModel !== snapshot.geminiModel ||
    geminiImageModel !== snapshot.geminiImageModel ||
    openaiModel !== snapshot.openaiModel ||
    xaiModel !== snapshot.xaiModel
  ));

  const handleSave = async () => {
    setSaving(true);
    try {
      await settingsAPI.update({
        openai_api_key: openaiKey || undefined,
        google_api_key: googleKey || undefined,
        xai_api_key: xaiKey || undefined,
        preferred_provider: preferred,
        gemini_model: geminiModel,
        gemini_image_model: geminiImageModel,
        openai_model: openaiModel,
        xai_model: xaiModel,
      });
      toast.success('Configuración guardada');
      setOpenaiKey('');
      setGoogleKey('');
      setXaiKey('');
      await fetchSettings();
    } catch {
      toast.error('Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await settingsAPI.deleteKey(deleteTarget);
      toast.success('Clave eliminada');
      setDeleteTarget(null);
      await fetchSettings();
    } catch {
      toast.error('Error al eliminar');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
        <PageHeader title="Configuración" description="Administra tus API Keys para el Constructor IA" />
        <LoadingPanel label="Cargando configuración..." />
      </div>
    );
  }

  if (fetchError || !settings) {
    return (
      <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
        <PageHeader title="Configuración" description="Administra tus API Keys para el Constructor IA" />
        <ErrorPanel message="No se pudo cargar tu configuración. Tus claves guardadas no se muestran hasta que esto funcione." onRetry={fetchSettings} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      <PageHeader title="Configuración" description="Administra tus API Keys para el Constructor IA" />

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-2xl mx-auto pb-4">
          {/* Provider selection */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 mb-6 shadow-sm">
            <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-4 flex items-center gap-2">
              <SparklesIcon className="w-5 h-5 text-primary-600" />
              Proveedor preferido de IA
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" role="radiogroup" aria-label="Proveedor preferido de IA">
              {[
                { id: 'gemini' as Provider, name: PROVIDERS.gemini.label, logo: PROVIDERS.gemini.emoji },
                { id: 'xai' as Provider, name: PROVIDERS.xai.label, logo: PROVIDERS.xai.emoji },
                { id: 'openai' as Provider, name: PROVIDERS.openai.label, logo: PROVIDERS.openai.emoji },
              ].map(p => (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={preferred === p.id}
                  onClick={() => setPreferred(p.id)}
                  className={`relative p-4 rounded-xl border-2 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 min-h-[44px] ${
                    preferred === p.id
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-700'
                  }`}
                >
                  <div className="text-2xl mb-2">{p.logo}</div>
                  <p className="font-semibold text-sm text-gray-900 dark:text-white">{p.name}</p>
                  {preferred === p.id && (
                    <CheckCircleIcon className="w-4 h-4 text-primary-600 absolute bottom-3 right-3" aria-hidden="true" />
                  )}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 flex items-start gap-1">
              <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
              Si la clave del proveedor preferido no está disponible, se usará automáticamente el otro.
            </p>
          </div>

          {/* Google Gemini API Key */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 mb-4 shadow-sm">
            <div className="flex items-center justify-between mb-4 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xl" aria-hidden="true">🌐</span>
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">Google Gemini API Key</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    <a href={PROVIDERS.gemini.docsUrl} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                      Ver disponibilidad y precios
                    </a>
                  </p>
                </div>
              </div>
              {settings.has_google
                ? <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium shrink-0"><CheckCircleIcon className="w-4 h-4" />Configurada</span>
                : <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 shrink-0"><XCircleIcon className="w-4 h-4" />No configurada</span>
              }
            </div>

            {settings.has_google && (
              <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <KeyIcon className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-600 dark:text-gray-300 font-mono flex-1 truncate">{settings.google_api_key_masked}</span>
                <IconButton label="Eliminar clave de Google" onClick={() => setDeleteTarget('google')} className="text-red-400 hover:text-red-600 shrink-0">
                  <TrashIcon className="w-4 h-4" />
                </IconButton>
              </div>
            )}

            <div className="relative">
              <label htmlFor="google-key" className="sr-only">Clave de Google Gemini</label>
              <input
                id="google-key"
                type={showGoogle ? 'text' : 'password'}
                value={googleKey}
                onChange={e => setGoogleKey(e.target.value)}
                placeholder={settings.has_google ? 'Nueva clave para reemplazar la actual' : 'AIzaSy...'}
                className={keyInputClass}
              />
              <IconButton
                label={showGoogle ? 'Ocultar clave' : 'Mostrar clave'}
                onClick={() => setShowGoogle(v => !v)}
                className="absolute right-1 top-1/2 -translate-y-1/2"
              >
                {showGoogle ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
              </IconButton>
            </div>
            <div className="mt-3">
              <label htmlFor="gemini-model" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Modelo de texto</label>
              <select id="gemini-model" value={geminiModel} onChange={e => setGeminiModel(e.target.value)} className={selectClass}>
                <option value="gemini-2.5-flash">gemini-2.5-flash — Rápido, bajo costo ⚡</option>
                <option value="gemini-2.5-pro">gemini-2.5-pro — Mayor calidad 🔵</option>
                <option value="gemini-2.5-pro-preview-03-25">gemini-2.5-pro-preview — Mejor calidad disponible ⭐</option>
              </select>
            </div>
            <div className="mt-3">
              <label htmlFor="gemini-image-model" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Modelo de imagen (si incluyes imágenes)</label>
              <select id="gemini-image-model" value={geminiImageModel} onChange={e => setGeminiImageModel(e.target.value)} className={selectClass}>
                <option value="gemini-2.0-flash-preview-image-generation">gemini-2.0-flash-preview-image-generation — Estándar ⚡</option>
                <option value="gemini-2.0-flash-exp">gemini-2.0-flash-exp — Experimental 🔵</option>
              </select>
            </div>
          </div>

          {/* xAI (Grok) API Key */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 mb-4 shadow-sm">
            <div className="flex items-center justify-between mb-4 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xl" aria-hidden="true">𝕏</span>
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">xAI Grok API Key</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    <a href={PROVIDERS.xai.docsUrl} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                      Ver disponibilidad y precios
                    </a>
                  </p>
                </div>
              </div>
              {settings.has_xai
                ? <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium shrink-0"><CheckCircleIcon className="w-4 h-4" />Configurada</span>
                : <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 shrink-0"><XCircleIcon className="w-4 h-4" />No configurada</span>
              }
            </div>

            {settings.has_xai && (
              <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <KeyIcon className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-600 dark:text-gray-300 font-mono flex-1 truncate">{settings.xai_api_key_masked}</span>
                <IconButton label="Eliminar clave de xAI" onClick={() => setDeleteTarget('xai')} className="text-red-400 hover:text-red-600 shrink-0">
                  <TrashIcon className="w-4 h-4" />
                </IconButton>
              </div>
            )}

            <div className="relative">
              <label htmlFor="xai-key" className="sr-only">Clave de xAI</label>
              <input
                id="xai-key"
                type={showXai ? 'text' : 'password'}
                value={xaiKey}
                onChange={e => setXaiKey(e.target.value)}
                placeholder={settings.has_xai ? 'Nueva clave para reemplazar la actual' : 'xai-...'}
                className={keyInputClass}
              />
              <IconButton
                label={showXai ? 'Ocultar clave' : 'Mostrar clave'}
                onClick={() => setShowXai(v => !v)}
                className="absolute right-1 top-1/2 -translate-y-1/2"
              >
                {showXai ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
              </IconButton>
            </div>
            <div className="mt-3">
              <label htmlFor="xai-model" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Modelo</label>
              <select id="xai-model" value={xaiModel} onChange={e => setXaiModel(e.target.value)} className={selectClass}>
                <option value="grok-3-mini">grok-3-mini — Rápido, bajo costo ⚡</option>
                <option value="grok-3">grok-3 — Mayor calidad ⭐</option>
              </select>
            </div>
          </div>

          {/* OpenAI API Key */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 mb-4 shadow-sm">
            <div className="flex items-center justify-between mb-4 gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xl" aria-hidden="true">🤖</span>
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">OpenAI API Key</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    <a href={PROVIDERS.openai.docsUrl} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                      Ver disponibilidad y precios
                    </a>
                  </p>
                </div>
              </div>
              {settings.has_openai
                ? <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium shrink-0"><CheckCircleIcon className="w-4 h-4" />Configurada</span>
                : <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 shrink-0"><XCircleIcon className="w-4 h-4" />No configurada</span>
              }
            </div>

            {settings.has_openai && (
              <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <KeyIcon className="w-4 h-4 text-gray-400 shrink-0" />
                <span className="text-sm text-gray-600 dark:text-gray-300 font-mono flex-1 truncate">{settings.openai_api_key_masked}</span>
                <IconButton label="Eliminar clave de OpenAI" onClick={() => setDeleteTarget('openai')} className="text-red-400 hover:text-red-600 shrink-0">
                  <TrashIcon className="w-4 h-4" />
                </IconButton>
              </div>
            )}

            <div className="relative">
              <label htmlFor="openai-key" className="sr-only">Clave de OpenAI</label>
              <input
                id="openai-key"
                type={showOpenai ? 'text' : 'password'}
                value={openaiKey}
                onChange={e => setOpenaiKey(e.target.value)}
                placeholder={settings.has_openai ? 'Nueva clave para reemplazar la actual' : 'sk-...'}
                className={keyInputClass}
              />
              <IconButton
                label={showOpenai ? 'Ocultar clave' : 'Mostrar clave'}
                onClick={() => setShowOpenai(v => !v)}
                className="absolute right-1 top-1/2 -translate-y-1/2"
              >
                {showOpenai ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
              </IconButton>
            </div>
            <div className="mt-3">
              <label htmlFor="openai-model" className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Modelo</label>
              <select id="openai-model" value={openaiModel} onChange={e => setOpenaiModel(e.target.value)} className={selectClass}>
                <option value="gpt-4o-mini">gpt-4o-mini — Rápido, menor costo ⚡</option>
                <option value="gpt-4o">gpt-4o — Equilibrio calidad/costo 🔵</option>
                <option value="o3-mini">o3-mini — Razonamiento avanzado ⭐</option>
              </select>
            </div>
          </div>

          {/* Info box */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800">
            <p className="text-xs text-blue-700 dark:text-blue-400 font-medium mb-1 flex items-center gap-1">
              <InformationCircleIcon className="w-4 h-4" /> Sobre tus claves
            </p>
            <ul className="text-xs text-blue-600 dark:text-blue-400 space-y-1 list-disc list-inside">
              <li>Cada proveedor define sus propios planes y precios — revisa su sitio (enlace arriba) para el detalle vigente.</li>
              <li>Las claves se guardan en tu cuenta y no se comparten con nadie.</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Sticky save bar */}
      <div className="shrink-0 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 sm:px-6 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between gap-3">
          <span className="text-xs text-gray-400 dark:text-gray-500">
            {dirty ? 'Tienes cambios sin guardar' : 'Sin cambios pendientes'}
          </span>
          <Button onClick={handleSave} busy={saving} disabled={!dirty}>
            {saving ? 'Guardando...' : 'Guardar configuración'}
          </Button>
        </div>
      </div>

      <AppDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title={deleteTarget ? `Eliminar clave de ${providerNames[deleteTarget]}` : ''}
        maxWidth="sm"
        footer={
          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setDeleteTarget(null)}>Cancelar</Button>
            <Button variant="danger" className="flex-1" onClick={confirmDelete} busy={deleting}>
              {deleting ? 'Eliminando...' : 'Eliminar'}
            </Button>
          </div>
        }
      >
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Esta acción no se puede deshacer. Deberás ingresar la clave nuevamente para volver a usar este proveedor.
        </p>
      </AppDialog>
    </div>
  );
}
