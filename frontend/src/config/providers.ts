export type AIProvider = 'auto' | 'openrouter' | 'gemini' | 'xai' | 'openai';

interface ProviderInfo {
  id: AIProvider;
  label: string;
  emoji: string;
  /** Clave en la respuesta de /api/settings/ que indica si es utilizable. */
  hasKeyField?: string;
  docsUrl?: string;
}

export const PROVIDERS: Record<AIProvider, ProviderInfo> = {
  auto: { id: 'auto', label: 'Automático', emoji: '⚡' },
  openrouter: {
    id: 'openrouter',
    label: 'OpenRouter',
    emoji: '🛰️',
    hasKeyField: 'has_openrouter',
    docsUrl: 'https://openrouter.ai/keys',
  },
  gemini: {
    id: 'gemini',
    label: 'Google Gemini',
    emoji: '🌐',
    hasKeyField: 'has_google',
    docsUrl: 'https://aistudio.google.com/apikey',
  },
  xai: {
    id: 'xai',
    label: 'xAI (Grok)',
    emoji: '𝕏',
    hasKeyField: 'has_xai',
    docsUrl: 'https://console.x.ai',
  },
  openai: {
    id: 'openai',
    label: 'OpenAI',
    emoji: '🤖',
    hasKeyField: 'has_openai',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
};

export function providerLabel(id: string | undefined | null): string {
  if (!id) return 'IA';
  return PROVIDERS[id as AIProvider]?.label ?? id;
}

export function providerEmoji(id: string | undefined | null): string {
  if (!id) return '✨';
  return PROVIDERS[id as AIProvider]?.emoji ?? '✨';
}

/**
 * Proveedores que el usuario puede elegir de verdad.
 *
 * Antes el selector ofrecía OpenAI y xAI aunque no hubiera ninguna clave
 * configurada: elegirlos fallaba con un error genérico y sin explicación.
 */
export function selectableProviders(settings: Record<string, unknown> | null): AIProvider[] {
  const ids: AIProvider[] = ['openrouter', 'gemini', 'xai', 'openai'];
  const withKey = ids.filter(id => {
    const field = PROVIDERS[id].hasKeyField;
    return field ? Boolean(settings?.[field]) : false;
  });
  return withKey.length > 1 ? ['auto', ...withKey] : withKey;
}
