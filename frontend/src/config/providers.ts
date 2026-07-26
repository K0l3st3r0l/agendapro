export type AIProvider = 'auto' | 'gemini' | 'xai' | 'openai';

interface ProviderInfo {
  id: AIProvider;
  label: string;
  emoji: string;
  freeTier: boolean;
  docsUrl?: string;
}

export const PROVIDERS: Record<AIProvider, ProviderInfo> = {
  auto: { id: 'auto', label: 'Auto', emoji: '⚡', freeTier: false },
  gemini: {
    id: 'gemini',
    label: 'Google Gemini',
    emoji: '🌐',
    freeTier: true,
    docsUrl: 'https://aistudio.google.com/apikey',
  },
  xai: {
    id: 'xai',
    label: 'xAI (Grok)',
    emoji: '𝕏',
    freeTier: true,
    docsUrl: 'https://console.x.ai',
  },
  openai: {
    id: 'openai',
    label: 'OpenAI',
    emoji: '🤖',
    freeTier: false,
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
