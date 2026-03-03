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

type Provider = 'gemini' | 'openai';

interface SettingsState {
  has_openai: boolean;
  has_google: boolean;
  openai_api_key_masked: string | null;
  google_api_key_masked: string | null;
  preferred_provider: Provider;
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsState | null>(null);
  const [openaiKey, setOpenaiKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');
  const [preferred, setPreferred] = useState<Provider>('gemini');
  const [showOpenai, setShowOpenai] = useState(false);
  const [showGoogle, setShowGoogle] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { fetchSettings(); }, []);

  const fetchSettings = async () => {
    try {
      const res = await settingsAPI.get();
      setSettings(res.data);
      setPreferred(res.data.preferred_provider || 'gemini');
    } catch {
      toast.error('Error al cargar configuración');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await settingsAPI.update({
        openai_api_key: openaiKey || undefined,
        google_api_key: googleKey || undefined,
        preferred_provider: preferred,
      });
      toast.success('Configuración guardada');
      setOpenaiKey('');
      setGoogleKey('');
      await fetchSettings();
    } catch {
      toast.error('Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (provider: 'openai' | 'google') => {
    if (!confirm(`¿Eliminar la clave de ${provider === 'openai' ? 'OpenAI' : 'Google'}?`)) return;
    try {
      await settingsAPI.deleteKey(provider);
      toast.success('Clave eliminada');
      await fetchSettings();
    } catch {
      toast.error('Error al eliminar');
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
    </div>
  );

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Configuración</h1>
        <p className="text-sm text-gray-500 mt-1">Administra tus API Keys para el Constructor IA</p>
      </div>

      {/* Provider selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
        <h2 className="text-base font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <SparklesIcon className="w-5 h-5 text-primary-600" />
          Proveedor preferido de IA
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              id: 'gemini' as Provider,
              name: 'Google Gemini',
              desc: 'Gemini 3 Flash — tier gratuito disponible',
              free: true,
              logo: '🌐',
            },
            {
              id: 'openai' as Provider,
              name: 'OpenAI',
              desc: 'GPT-4o — mayor rendimiento, costo por uso',
              free: false,
              logo: '🤖',
            },
          ].map(p => (
            <button
              key={p.id}
              onClick={() => setPreferred(p.id)}
              className={`relative p-4 rounded-xl border-2 text-left transition-all ${
                preferred === p.id
                  ? 'border-primary-500 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              {p.free && (
                <span className="absolute top-2 right-2 text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">Gratis</span>
              )}
              <div className="text-2xl mb-2">{p.logo}</div>
              <p className="font-semibold text-sm text-gray-900">{p.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{p.desc}</p>
              {preferred === p.id && (
                <CheckCircleIcon className="w-4 h-4 text-primary-600 absolute bottom-3 right-3" />
              )}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3 flex items-start gap-1">
          <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
          Si la clave del proveedor preferido no está disponible, se usará automáticamente el otro.
        </p>
      </div>

      {/* Google Gemini API Key */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🌐</span>
            <div>
              <h2 className="text-sm font-semibold text-gray-800">Google Gemini API Key</h2>
              <p className="text-xs text-gray-500">
                Obtén tu clave gratis en{' '}
                <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                  aistudio.google.com/apikey
                </a>
              </p>
            </div>
          </div>
          {settings?.has_google
            ? <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium"><CheckCircleIcon className="w-4 h-4" />Configurada</span>
            : <span className="flex items-center gap-1 text-xs text-gray-400"><XCircleIcon className="w-4 h-4" />No configurada</span>
          }
        </div>

        {settings?.has_google && (
          <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 rounded-lg">
            <KeyIcon className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600 font-mono flex-1">{settings.google_api_key_masked}</span>
            <button
              onClick={() => handleDelete('google')}
              className="text-red-400 hover:text-red-600 transition-colors"
              title="Eliminar clave"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="relative">
          <input
            type={showGoogle ? 'text' : 'password'}
            value={googleKey}
            onChange={e => setGoogleKey(e.target.value)}
            placeholder={settings?.has_google ? 'Nueva clave para reemplazar la actual' : 'AIzaSy...'}
            className="w-full px-3 py-2.5 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono"
          />
          <button
            type="button"
            onClick={() => setShowGoogle(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showGoogle ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* OpenAI API Key */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-xl">🤖</span>
            <div>
              <h2 className="text-sm font-semibold text-gray-800">OpenAI API Key</h2>
              <p className="text-xs text-gray-500">
                Obtén tu clave en{' '}
                <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
                  platform.openai.com/api-keys
                </a>
              </p>
            </div>
          </div>
          {settings?.has_openai
            ? <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium"><CheckCircleIcon className="w-4 h-4" />Configurada</span>
            : <span className="flex items-center gap-1 text-xs text-gray-400"><XCircleIcon className="w-4 h-4" />No configurada</span>
          }
        </div>

        {settings?.has_openai && (
          <div className="flex items-center gap-2 mb-3 p-2.5 bg-gray-50 rounded-lg">
            <KeyIcon className="w-4 h-4 text-gray-400" />
            <span className="text-sm text-gray-600 font-mono flex-1">{settings.openai_api_key_masked}</span>
            <button
              onClick={() => handleDelete('openai')}
              className="text-red-400 hover:text-red-600 transition-colors"
              title="Eliminar clave"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="relative">
          <input
            type={showOpenai ? 'text' : 'password'}
            value={openaiKey}
            onChange={e => setOpenaiKey(e.target.value)}
            placeholder={settings?.has_openai ? 'Nueva clave para reemplazar la actual' : 'sk-...'}
            className="w-full px-3 py-2.5 pr-10 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 font-mono"
          />
          <button
            type="button"
            onClick={() => setShowOpenai(v => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            {showOpenai ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Save button */}
      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full py-3 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-colors"
      >
        {saving ? 'Guardando...' : 'Guardar configuración'}
      </button>

      {/* Info box */}
      <div className="mt-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
        <p className="text-xs text-blue-700 font-medium mb-1">ℹ️ Planes gratuitos disponibles</p>
        <ul className="text-xs text-blue-600 space-y-1 list-disc list-inside">
          <li><strong>Google Gemini:</strong> Gemini 3 Flash gratis con hasta 500 solicitudes/día</li>
          <li><strong>OpenAI:</strong> Créditos de prueba al crear una cuenta nueva</li>
          <li>Las claves se guardan en tu cuenta y no se comparten con nadie</li>
        </ul>
      </div>
    </div>
  );
}
