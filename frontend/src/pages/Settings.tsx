import { useEffect, useState } from 'react';
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
  ArrowPathIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { SparklesIcon } from '@heroicons/react/24/solid';
import PageHeader from '../components/ui/PageHeader';
import AppDialog from '../components/ui/AppDialog';
import { Button, IconButton } from '../components/ui/Button';
import { ErrorPanel, LoadingPanel } from '../components/ui/StatePanel';
import { PROVIDERS } from '../config/providers';

type ProviderId = 'openrouter' | 'gemini' | 'openai' | 'xai';
type KeyId = 'openrouter' | 'google' | 'openai' | 'xai';

interface SettingsState {
  has_openrouter: boolean;
  has_google: boolean;
  has_openai: boolean;
  has_xai: boolean;
  openrouter_api_key_masked: string | null;
  google_api_key_masked: string | null;
  openai_api_key_masked: string | null;
  xai_api_key_masked: string | null;
  preferred_provider: ProviderId;
  text_model: string;
  image_model: string;
  gemini_model: string;
  openai_model: string;
  xai_model: string;
}

interface HealthEntry {
  status: 'ok' | 'invalid' | 'missing' | 'quota' | 'no_credit' | 'error';
  detail: string;
}

const selectClass =
  'w-full px-3 py-2 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100';

const keyInputClass =
  'w-full px-3 py-2.5 pr-12 border border-gray-200 dark:border-gray-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500';

const providerNames: Record<KeyId, string> = {
  openrouter: 'OpenRouter',
  google: 'Google Gemini',
  openai: 'OpenAI',
  xai: 'xAI (Grok)',
};

// Modelos verificados contra la API el 2026-08-06. Los que estaban antes
// (gemini-2.5-pro-preview-03-25, gemini-2.0-flash-exp y el de imágenes
// gemini-2.0-flash-preview-image-generation) ya no existen: elegirlos fallaba.
const TEXT_MODELS = [
  { value: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash — el más barato ⚡' },
  { value: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro — mayor calidad 🔵' },
  { value: 'google/gemini-3.6-flash', label: 'Gemini 3.6 Flash — rápido y capaz 🔵' },
  { value: 'anthropic/claude-sonnet-5', label: 'Claude Sonnet 5 — mejor redacción ⭐' },
  { value: 'openai/gpt-5.6', label: 'GPT-5.6 ⭐' },
];

const IMAGE_MODELS = [
  { value: 'google/gemini-3.1-flash-lite-image', label: 'Nano Banana 2 Lite — el más barato ⚡' },
  { value: 'google/gemini-3.1-flash-image', label: 'Nano Banana 2 — mejor calidad 🔵' },
  { value: 'black-forest-labs/flux.2-klein-4b', label: 'FLUX.2 klein — precio fijo por imagen' },
  { value: 'black-forest-labs/flux.2-pro', label: 'FLUX.2 pro — máxima fidelidad ⭐' },
  { value: 'openai/gpt-image-2', label: 'GPT Image 2 — el más caro 💰' },
];

const GEMINI_MODELS = [
  { value: 'gemini-2.5-flash', label: 'gemini-2.5-flash — rápido, bajo costo ⚡' },
  { value: 'gemini-2.5-pro', label: 'gemini-2.5-pro — mayor calidad 🔵' },
  { value: 'gemini-3.6-flash', label: 'gemini-3.6-flash — última generación ⭐' },
];

const OPENAI_MODELS = [
  { value: 'gpt-4o-mini', label: 'gpt-4o-mini — rápido, menor costo ⚡' },
  { value: 'gpt-4o', label: 'gpt-4o — equilibrio calidad/costo 🔵' },
];

const XAI_MODELS = [
  { value: 'grok-3-mini', label: 'grok-3-mini — rápido, bajo costo ⚡' },
  { value: 'grok-3', label: 'grok-3 — mayor calidad ⭐' },
];

const HEALTH_STYLES: Record<HealthEntry['status'], { label: string; className: string }> = {
  ok: { label: 'Funcionando', className: 'text-emerald-600 dark:text-emerald-400' },
  invalid: { label: 'Clave inválida', className: 'text-red-600 dark:text-red-400' },
  no_credit: { label: 'Sin créditos', className: 'text-red-600 dark:text-red-400' },
  quota: { label: 'Cuota agotada', className: 'text-amber-600 dark:text-amber-400' },
  error: { label: 'Error', className: 'text-amber-600 dark:text-amber-400' },
  missing: { label: 'Sin configurar', className: 'text-gray-400 dark:text-gray-500' },
};

interface ProviderCardProps {
  keyId: KeyId;
  emoji: string;
  title: string;
  docsUrl?: string;
  placeholder: string;
  configured: boolean;
  masked: string | null;
  value: string;
  onChange: (v: string) => void;
  onDelete: () => void;
  health?: HealthEntry;
  children?: React.ReactNode;
  highlight?: boolean;
}

function ProviderCard({
  keyId, emoji, title, docsUrl, placeholder, configured, masked,
  value, onChange, onDelete, health, children, highlight,
}: ProviderCardProps) {
  const [visible, setVisible] = useState(false);
  const style = health ? HEALTH_STYLES[health.status] : null;

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-xl border p-4 sm:p-6 mb-4 shadow-sm ${
        highlight ? 'border-primary-300 dark:border-primary-700' : 'border-gray-200 dark:border-gray-700'
      }`}
    >
      <div className="flex items-center justify-between mb-4 gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xl" aria-hidden="true">{emoji}</span>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-200">{title}</h2>
            {docsUrl && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                <a href={docsUrl} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                  Obtener clave y ver precios
                </a>
              </p>
            )}
          </div>
        </div>
        {configured ? (
          <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium shrink-0">
            <CheckCircleIcon className="w-4 h-4" />Configurada
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 shrink-0">
            <XCircleIcon className="w-4 h-4" />No configurada
          </span>
        )}
      </div>

      {style && health && health.status !== 'missing' && (
        <p className={`text-xs mb-3 flex items-start gap-1 ${style.className}`} role="status">
          {health.status === 'ok'
            ? <CheckCircleIcon className="w-4 h-4 shrink-0" />
            : <ExclamationTriangleIcon className="w-4 h-4 shrink-0" />}
          <span><strong>{style.label}.</strong> {health.detail}</span>
        </p>
      )}

      {masked && (
        <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
          <KeyIcon className="w-4 h-4 text-gray-400 shrink-0" />
          <span className="text-sm text-gray-600 dark:text-gray-300 font-mono flex-1 truncate">{masked}</span>
          <IconButton label={`Eliminar clave de ${title}`} onClick={onDelete} className="text-red-400 hover:text-red-600 shrink-0">
            <TrashIcon className="w-4 h-4" />
          </IconButton>
        </div>
      )}

      <div className="relative">
        <label htmlFor={`${keyId}-key`} className="sr-only">Clave de {title}</label>
        <input
          id={`${keyId}-key`}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={configured ? 'Nueva clave para reemplazar la actual' : placeholder}
          className={keyInputClass}
        />
        <IconButton
          label={visible ? 'Ocultar clave' : 'Mostrar clave'}
          onClick={() => setVisible(v => !v)}
          className="absolute right-1 top-1/2 -translate-y-1/2"
        >
          {visible ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
        </IconButton>
      </div>

      {children}
    </div>
  );
}

function ModelSelect({ id, label, value, onChange, options }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  // Un modelo guardado que ya no está en la lista debe seguir visible, o al
  // abrir Configuración el <select> mostraría otro valor y lo pisaría al guardar.
  const known = options.some(o => o.value === value);
  return (
    <div className="mt-3">
      <label htmlFor={id} className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{label}</label>
      <select id={id} value={value} onChange={e => onChange(e.target.value)} className={selectClass}>
        {!known && value && <option value={value}>{value} (actual)</option>}
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsState | null>(null);
  const [fetchError, setFetchError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [keys, setKeys] = useState<Record<KeyId, string>>({ openrouter: '', google: '', openai: '', xai: '' });
  const [preferred, setPreferred] = useState<ProviderId>('openrouter');
  const [textModel, setTextModel] = useState(TEXT_MODELS[0].value);
  const [imageModel, setImageModel] = useState(IMAGE_MODELS[0].value);
  const [geminiModel, setGeminiModel] = useState('gemini-2.5-flash');
  const [openaiModel, setOpenaiModel] = useState('gpt-4o');
  const [xaiModel, setXaiModel] = useState('grok-3-mini');
  const [snapshot, setSnapshot] = useState<string>('');

  const [health, setHealth] = useState<Record<string, HealthEntry> | null>(null);
  const [checking, setChecking] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<KeyId | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => { fetchSettings(); }, []);

  const snapshotOf = (s: SettingsState) =>
    JSON.stringify([s.preferred_provider, s.text_model, s.image_model, s.gemini_model, s.openai_model, s.xai_model]);

  const fetchSettings = async () => {
    setLoading(true);
    setFetchError(false);
    try {
      const { data } = await settingsAPI.get();
      setSettings(data);
      setPreferred(data.preferred_provider || 'openrouter');
      setTextModel(data.text_model || TEXT_MODELS[0].value);
      setImageModel(data.image_model || IMAGE_MODELS[0].value);
      setGeminiModel(data.gemini_model || 'gemini-2.5-flash');
      setOpenaiModel(data.openai_model || 'gpt-4o');
      setXaiModel(data.xai_model || 'grok-3-mini');
      setSnapshot(snapshotOf(data));
    } catch {
      setFetchError(true);
      toast.error('Error al cargar configuración');
    } finally {
      setLoading(false);
    }
  };

  const runHealthCheck = async () => {
    setChecking(true);
    try {
      const { data } = await settingsAPI.health();
      setHealth(data.providers);
      if (data.any_usable) toast.success('Prueba completa');
      else toast.error('Ninguna clave está funcionando');
    } catch {
      toast.error('No se pudo probar las claves');
    } finally {
      setChecking(false);
    }
  };

  const currentSnapshot = JSON.stringify([preferred, textModel, imageModel, geminiModel, openaiModel, xaiModel]);
  const dirty = Object.values(keys).some(Boolean) || currentSnapshot !== snapshot;

  const handleSave = async () => {
    setSaving(true);
    try {
      await settingsAPI.update({
        openrouter_api_key: keys.openrouter || undefined,
        google_api_key: keys.google || undefined,
        openai_api_key: keys.openai || undefined,
        xai_api_key: keys.xai || undefined,
        preferred_provider: preferred,
        text_model: textModel,
        image_model: imageModel,
        gemini_model: geminiModel,
        openai_model: openaiModel,
        xai_model: xaiModel,
      });
      toast.success('Configuración guardada');
      setKeys({ openrouter: '', google: '', openai: '', xai: '' });
      setHealth(null);
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
      setHealth(null);
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
        <ErrorPanel
          message="No se pudo cargar tu configuración. Tus claves guardadas no se muestran hasta que esto funcione."
          onRetry={fetchSettings}
        />
      </div>
    );
  }

  const setKey = (id: KeyId) => (v: string) => setKeys(k => ({ ...k, [id]: v }));
  const preferredOptions: ProviderId[] = ['openrouter', 'gemini', 'openai', 'xai'];

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
      <PageHeader title="Configuración" description="Administra tus API Keys para el Constructor IA" />

      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <div className="max-w-2xl mx-auto pb-4">

          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-6 mb-6 shadow-sm">
            <div className="flex items-center justify-between gap-2 mb-4">
              <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                <SparklesIcon className="w-5 h-5 text-primary-600" />
                Proveedor preferido
              </h2>
              <Button variant="secondary" onClick={runHealthCheck} busy={checking}>
                {checking ? <ArrowPathIcon className="w-4 h-4 animate-spin" /> : <KeyIcon className="w-4 h-4" />}
                Probar claves
              </Button>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" role="radiogroup" aria-label="Proveedor preferido de IA">
              {preferredOptions.map(id => (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={preferred === id}
                  onClick={() => setPreferred(id)}
                  className={`relative p-4 rounded-xl border-2 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 min-h-[44px] ${
                    preferred === id
                      ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                      : 'border-gray-200 dark:border-gray-600 hover:border-gray-300 dark:hover:border-gray-500 bg-white dark:bg-gray-700'
                  }`}
                >
                  <div className="text-2xl mb-2">{PROVIDERS[id].emoji}</div>
                  <p className="font-semibold text-sm text-gray-900 dark:text-white">{PROVIDERS[id].label}</p>
                  {preferred === id && (
                    <CheckCircleIcon className="w-4 h-4 text-primary-600 absolute bottom-3 right-3" aria-hidden="true" />
                  )}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 flex items-start gap-1">
              <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
              Si el proveedor preferido no tiene clave, se usa automáticamente otro que sí la tenga.
            </p>
          </div>

          <ProviderCard
            keyId="openrouter"
            emoji={PROVIDERS.openrouter.emoji}
            title="OpenRouter"
            docsUrl={PROVIDERS.openrouter.docsUrl}
            placeholder="sk-or-v1-..."
            configured={settings.has_openrouter}
            masked={settings.openrouter_api_key_masked}
            value={keys.openrouter}
            onChange={setKey('openrouter')}
            onDelete={() => setDeleteTarget('openrouter')}
            health={health?.openrouter}
            highlight
          >
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
              Una sola clave cubre el texto y las imágenes del constructor.
            </p>
            <ModelSelect id="text-model" label="Modelo de texto" value={textModel} onChange={setTextModel} options={TEXT_MODELS} />
            <ModelSelect id="image-model" label="Modelo de imágenes" value={imageModel} onChange={setImageModel} options={IMAGE_MODELS} />
          </ProviderCard>

          <ProviderCard
            keyId="google"
            emoji={PROVIDERS.gemini.emoji}
            title="Google Gemini"
            docsUrl={PROVIDERS.gemini.docsUrl}
            placeholder="AIzaSy..."
            configured={settings.has_google}
            masked={settings.google_api_key_masked}
            value={keys.google}
            onChange={setKey('google')}
            onDelete={() => setDeleteTarget('google')}
            health={health?.gemini}
          >
            <ModelSelect id="gemini-model" label="Modelo de texto" value={geminiModel} onChange={setGeminiModel} options={GEMINI_MODELS} />
          </ProviderCard>

          <ProviderCard
            keyId="openai"
            emoji={PROVIDERS.openai.emoji}
            title="OpenAI"
            docsUrl={PROVIDERS.openai.docsUrl}
            placeholder="sk-..."
            configured={settings.has_openai}
            masked={settings.openai_api_key_masked}
            value={keys.openai}
            onChange={setKey('openai')}
            onDelete={() => setDeleteTarget('openai')}
            health={health?.openai}
          >
            <ModelSelect id="openai-model" label="Modelo" value={openaiModel} onChange={setOpenaiModel} options={OPENAI_MODELS} />
          </ProviderCard>

          <ProviderCard
            keyId="xai"
            emoji={PROVIDERS.xai.emoji}
            title="xAI (Grok)"
            docsUrl={PROVIDERS.xai.docsUrl}
            placeholder="xai-..."
            configured={settings.has_xai}
            masked={settings.xai_api_key_masked}
            value={keys.xai}
            onChange={setKey('xai')}
            onDelete={() => setDeleteTarget('xai')}
            health={health?.xai}
          >
            <ModelSelect id="xai-model" label="Modelo" value={xaiModel} onChange={setXaiModel} options={XAI_MODELS} />
          </ProviderCard>

          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800">
            <p className="text-xs text-blue-700 dark:text-blue-400 font-medium mb-1 flex items-center gap-1">
              <InformationCircleIcon className="w-4 h-4" /> Sobre tus claves
            </p>
            <ul className="text-xs text-blue-600 dark:text-blue-400 space-y-1 list-disc list-inside">
              <li>Las claves se guardan en tu cuenta y no se comparten con nadie.</li>
              <li>Usa <strong>Probar claves</strong> para saber si alguna caducó antes de que falle una generación.</li>
              <li>Cada proveedor define sus propios precios — revisa su sitio con el enlace de cada tarjeta.</li>
            </ul>
          </div>
        </div>
      </div>

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
