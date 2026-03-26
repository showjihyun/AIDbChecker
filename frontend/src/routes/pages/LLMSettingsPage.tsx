// Spec: FS-AI-LLM-001 §5 — LLM Provider Settings UI
import { useState, useEffect, useCallback } from 'react';
import { Link } from '@tanstack/react-router';
import { cn } from '@/lib/cn';
import { useToastStore } from '@/components/common/Toast';
import {
  useLLMSettings,
  useLLMProviders,
  useOllamaModels,
  useUpdateLLMSettings,
  useTestLLM,
  type LLMSettingsUpdate,
  type ProviderInfo,
} from '@/api/hooks/useLLMSettings';

// Spec: FS-AI-LLM-001 §5.2 — Hardcoded model lists per provider
const PROVIDER_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  anthropic: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001'],
  google: ['gemini-2.0-flash', 'gemini-1.5-pro'],
};

const PROVIDER_DISPLAY: Record<string, string> = {
  ollama: 'Ollama (Local)',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
};

type ProviderKey = 'ollama' | 'openai' | 'anthropic' | 'google';

// --- Password field with show/hide toggle ---
function PasswordField({
  label,
  value,
  onChange,
  hasKey,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  hasKey: boolean;
  placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-on-surface-variant">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type={visible ? 'text' : 'password'}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={hasKey ? '(key is set - enter new to replace)' : placeholder ?? 'Enter API key'}
            className={cn(
              'w-full px-3 py-2 pr-10 rounded-lg text-sm',
              'bg-surface text-on-surface placeholder-on-surface-variant/50',
              'border border-outline-variant/30',
              'focus:outline-none focus:ring-1 focus:ring-primary-container/50',
              'transition-colors duration-200 ease-out'
            )}
            autoComplete="off"
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className={cn(
              'absolute right-2 top-1/2 -translate-y-1/2',
              'text-on-surface-variant hover:text-on-surface',
              'transition-colors duration-200 ease-out'
            )}
            aria-label={visible ? 'Hide API key' : 'Show API key'}
          >
            <span className="material-symbols-outlined text-lg">
              {visible ? 'visibility_off' : 'visibility'}
            </span>
          </button>
        </div>
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium whitespace-nowrap',
            hasKey
              ? 'bg-[#10b981]/10 text-[#10b981]'
              : 'bg-surface-container text-on-surface-variant'
          )}
        >
          {hasKey ? 'Set' : 'Not set'}
        </span>
      </div>
    </div>
  );
}

// --- Provider availability badge ---
function AvailabilityBadge({ available }: { available: boolean }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        available
          ? 'bg-[#10b981]/10 text-[#10b981]'
          : 'bg-error/10 text-error'
      )}
    >
      <span className="material-symbols-outlined text-sm">
        {available ? 'check_circle' : 'cancel'}
      </span>
      {available ? 'Available' : 'Unavailable'}
    </span>
  );
}

export function LLMSettingsPage() {
  const addToast = useToastStore((s) => s.addToast);

  // --- Queries ---
  const settingsQuery = useLLMSettings();
  const providersQuery = useLLMProviders();
  const ollamaModelsQuery = useOllamaModels();

  // --- Mutations ---
  const updateMutation = useUpdateLLMSettings();
  const testMutation = useTestLLM();

  // --- Local form state ---
  const [provider, setProvider] = useState<ProviderKey>('ollama');
  const [model, setModel] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [googleKey, setGoogleKey] = useState('');

  // Sync from server data
  useEffect(() => {
    if (settingsQuery.data) {
      setProvider(settingsQuery.data.provider as ProviderKey);
      setModel(settingsQuery.data.model);
    }
  }, [settingsQuery.data]);

  // --- Model options based on provider ---
  const getModelOptions = useCallback((): string[] => {
    if (provider === 'ollama') {
      return ollamaModelsQuery.data?.map((m) => m.name) ?? [];
    }
    return PROVIDER_MODELS[provider] ?? [];
  }, [provider, ollamaModelsQuery.data]);

  const modelOptions = getModelOptions();

  // Auto-select first model when switching provider
  useEffect(() => {
    if (modelOptions.length > 0 && !modelOptions.includes(model)) {
      setModel(modelOptions[0]);
    }
  }, [provider, modelOptions]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Refresh Ollama models ---
  const handleRefreshOllamaModels = () => {
    ollamaModelsQuery.refetch();
  };

  // --- Provider info lookup ---
  const getProviderInfo = (name: string): ProviderInfo | undefined => {
    return providersQuery.data?.find((p) => p.name === name);
  };

  // --- Save ---
  const handleSave = () => {
    const payload: LLMSettingsUpdate = {
      provider,
      model,
    };
    if (openaiKey) payload.openai_api_key = openaiKey;
    if (anthropicKey) payload.anthropic_api_key = anthropicKey;
    if (googleKey) payload.google_api_key = googleKey;

    updateMutation.mutate(payload, {
      onSuccess: () => {
        addToast({
          level: 'info',
          title: 'Settings saved',
          message: `LLM provider set to ${PROVIDER_DISPLAY[provider]} with model ${model}.`,
        });
        setOpenaiKey('');
        setAnthropicKey('');
        setGoogleKey('');
      },
      onError: (err) => {
        const message = (err as { detail?: string })?.detail ?? 'Failed to save settings.';
        addToast({
          level: 'error',
          title: 'Save failed',
          message,
        });
      },
    });
  };

  // --- Test current model ---
  const handleTestCurrent = () => {
    testMutation.mutate(
      { provider, model },
      {
        onSuccess: (res) => {
          if (res.success) {
            addToast({
              level: 'info',
              title: 'Test successful',
              message: `Response in ${res.latency_ms}ms: "${res.response?.slice(0, 80) ?? ''}"`,
            });
          } else {
            addToast({
              level: 'error',
              title: 'Test failed',
              message: res.error ?? 'Unknown error during test.',
            });
          }
        },
        onError: (err) => {
          const message = (err as { detail?: string })?.detail ?? 'Failed to run test.';
          addToast({
            level: 'error',
            title: 'Test failed',
            message,
          });
        },
      }
    );
  };

  // --- Test a specific provider's API key ---
  const handleTestProvider = (providerName: ProviderKey) => {
    const providerInfo = getProviderInfo(providerName);
    const testModel = providerInfo?.models?.[0] ?? '';
    testMutation.mutate(
      { provider: providerName, model: testModel },
      {
        onSuccess: (res) => {
          if (res.success) {
            addToast({
              level: 'info',
              title: `${PROVIDER_DISPLAY[providerName]} test passed`,
              message: `Response in ${res.latency_ms}ms.`,
            });
          } else {
            addToast({
              level: 'error',
              title: `${PROVIDER_DISPLAY[providerName]} test failed`,
              message: res.error ?? 'Unknown error.',
            });
          }
        },
        onError: (err) => {
          const message = (err as { detail?: string })?.detail ?? 'Test request failed.';
          addToast({
            level: 'error',
            title: `${PROVIDER_DISPLAY[providerName]} test failed`,
            message,
          });
        },
      }
    );
  };

  // --- Loading state ---
  if (settingsQuery.isLoading) {
    return (
      <div className="space-y-module-gap">
        <div className="flex items-center gap-3">
          <Link
            to="/settings"
            className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out"
            aria-label="Back to settings"
          >
            <span className="material-symbols-outlined text-xl">arrow_back</span>
          </Link>
          <div>
            <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
              AI Configuration
            </h1>
            <p className="text-xs text-on-surface-variant mt-1">
              Loading settings...
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-6 h-6 border-2 border-primary-container border-t-transparent rounded-full" />
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (settingsQuery.isError) {
    return (
      <div className="space-y-module-gap">
        <div className="flex items-center gap-3">
          <Link
            to="/settings"
            className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out"
            aria-label="Back to settings"
          >
            <span className="material-symbols-outlined text-xl">arrow_back</span>
          </Link>
          <div>
            <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
              AI Configuration
            </h1>
          </div>
        </div>
        <div className="bg-error/10 border border-error/30 rounded-xl p-6 text-center">
          <span className="material-symbols-outlined text-3xl text-error mb-2">error</span>
          <p className="text-sm text-error font-medium">
            Failed to load LLM settings.
          </p>
          <p className="text-xs text-on-surface-variant mt-1">
            Check that the backend is running and accessible.
          </p>
          <button
            onClick={() => settingsQuery.refetch()}
            className={cn(
              'mt-4 px-4 py-2 rounded-lg text-xs font-medium',
              'bg-error/10 text-error hover:bg-error/20',
              'transition-colors duration-200 ease-out'
            )}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const settings = settingsQuery.data;

  return (
    <div className="space-y-module-gap max-w-3xl">
      {/* Header with back link */}
      <div className="flex items-center gap-3">
        <Link
          to="/settings"
          className="text-on-surface-variant hover:text-on-surface transition-colors duration-200 ease-out"
          aria-label="Back to settings"
        >
          <span className="material-symbols-outlined text-xl">arrow_back</span>
        </Link>
        <div>
          <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
            AI Configuration
          </h1>
          <p className="text-xs text-on-surface-variant mt-1">
            Configure LLM provider, model selection, and API keys
          </p>
        </div>
      </div>

      {/* Provider Availability Overview */}
      <div className="bg-surface-container rounded-xl p-6">
        <h2 className="text-sm font-semibold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary-container">hub</span>
          Provider Status
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {(['ollama', 'openai', 'anthropic', 'google'] as const).map((pName) => {
            const info = getProviderInfo(pName);
            return (
              <div
                key={pName}
                className={cn(
                  'flex items-center justify-between px-4 py-3 rounded-lg',
                  'bg-surface/50 border border-outline-variant/20'
                )}
              >
                <span className="text-sm font-medium text-on-surface">
                  {PROVIDER_DISPLAY[pName]}
                </span>
                <AvailabilityBadge available={info?.available ?? false} />
              </div>
            );
          })}
        </div>
      </div>

      {/* Model Configuration */}
      <div className="bg-surface-container rounded-xl p-6">
        <h2 className="text-sm font-semibold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary-container">smart_toy</span>
          Model Configuration
        </h2>

        <div className="space-y-4">
          {/* Provider selector */}
          <div className="space-y-1.5">
            <label
              htmlFor="provider-select"
              className="text-xs font-medium text-on-surface-variant"
            >
              Provider
            </label>
            <select
              id="provider-select"
              value={provider}
              onChange={(e) => setProvider(e.target.value as ProviderKey)}
              className={cn(
                'w-full px-3 py-2 rounded-lg text-sm',
                'bg-surface text-on-surface',
                'border border-outline-variant/30',
                'focus:outline-none focus:ring-1 focus:ring-primary-container/50',
                'transition-colors duration-200 ease-out'
              )}
            >
              <option value="ollama">Ollama (Local / Offline)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="google">Google</option>
            </select>
          </div>

          {/* Model selector */}
          <div className="space-y-1.5">
            <label
              htmlFor="model-select"
              className="text-xs font-medium text-on-surface-variant"
            >
              Model
            </label>
            <div className="flex items-center gap-2">
              <select
                id="model-select"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className={cn(
                  'flex-1 px-3 py-2 rounded-lg text-sm',
                  'bg-surface text-on-surface',
                  'border border-outline-variant/30',
                  'focus:outline-none focus:ring-1 focus:ring-primary-container/50',
                  'transition-colors duration-200 ease-out'
                )}
              >
                {modelOptions.length === 0 && (
                  <option value="" disabled>
                    {provider === 'ollama'
                      ? 'No models found - click Refresh'
                      : 'No models available'}
                  </option>
                )}
                {modelOptions.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>

              {provider === 'ollama' && (
                <button
                  type="button"
                  onClick={handleRefreshOllamaModels}
                  disabled={ollamaModelsQuery.isFetching}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium',
                    'bg-primary-container/10 text-primary-container',
                    'hover:bg-primary-container/20',
                    'disabled:opacity-50 disabled:cursor-not-allowed',
                    'transition-colors duration-200 ease-out'
                  )}
                >
                  <span
                    className={cn(
                      'material-symbols-outlined text-base',
                      ollamaModelsQuery.isFetching && 'animate-spin'
                    )}
                  >
                    refresh
                  </span>
                  Refresh
                </button>
              )}
            </div>
            {provider === 'ollama' && ollamaModelsQuery.data && (
              <p className="text-xs text-on-surface-variant">
                {ollamaModelsQuery.data.length} model(s) available on Ollama server
                {settings?.ollama_base_url ? ` at ${settings.ollama_base_url}` : ''}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* API Keys */}
      <div className="bg-surface-container rounded-xl p-6">
        <h2 className="text-sm font-semibold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-lg text-primary-container">key</span>
          API Keys
        </h2>
        <p className="text-xs text-on-surface-variant mb-4">
          API keys are stored encrypted on the server. The actual key values are never sent to the browser.
          Enter a new key to replace the existing one.
        </p>

        <div className="space-y-5">
          {/* OpenAI */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <PasswordField
                label="OpenAI API Key"
                value={openaiKey}
                onChange={setOpenaiKey}
                hasKey={settings?.has_openai_key ?? false}
                placeholder="sk-..."
              />
            </div>
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => handleTestProvider('openai')}
                disabled={testMutation.isPending}
                className={cn(
                  'inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium',
                  'bg-surface text-on-surface-variant border border-outline-variant/30',
                  'hover:bg-surface-container-high hover:text-on-surface',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'transition-colors duration-200 ease-out'
                )}
              >
                <span className="material-symbols-outlined text-sm">science</span>
                Test OpenAI
              </button>
            </div>
          </div>

          <div className="h-px bg-outline-variant/20" />

          {/* Anthropic */}
          <div className="space-y-2">
            <PasswordField
              label="Anthropic API Key"
              value={anthropicKey}
              onChange={setAnthropicKey}
              hasKey={settings?.has_anthropic_key ?? false}
              placeholder="sk-ant-..."
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => handleTestProvider('anthropic')}
                disabled={testMutation.isPending}
                className={cn(
                  'inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium',
                  'bg-surface text-on-surface-variant border border-outline-variant/30',
                  'hover:bg-surface-container-high hover:text-on-surface',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'transition-colors duration-200 ease-out'
                )}
              >
                <span className="material-symbols-outlined text-sm">science</span>
                Test Anthropic
              </button>
            </div>
          </div>

          <div className="h-px bg-outline-variant/20" />

          {/* Google */}
          <div className="space-y-2">
            <PasswordField
              label="Google API Key"
              value={googleKey}
              onChange={setGoogleKey}
              hasKey={settings?.has_google_key ?? false}
              placeholder="AIza..."
            />
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => handleTestProvider('google')}
                disabled={testMutation.isPending}
                className={cn(
                  'inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium',
                  'bg-surface text-on-surface-variant border border-outline-variant/30',
                  'hover:bg-surface-container-high hover:text-on-surface',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                  'transition-colors duration-200 ease-out'
                )}
              >
                <span className="material-symbols-outlined text-sm">science</span>
                Test Google
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className={cn(
            'inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium',
            'bg-primary-container text-on-primary-container',
            'hover:bg-primary-container/80',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors duration-200 ease-out'
          )}
        >
          {updateMutation.isPending ? (
            <span className="animate-spin w-4 h-4 border-2 border-on-primary-container border-t-transparent rounded-full" />
          ) : (
            <span className="material-symbols-outlined text-lg">save</span>
          )}
          Save Changes
        </button>

        <button
          type="button"
          onClick={handleTestCurrent}
          disabled={testMutation.isPending || !model}
          className={cn(
            'inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium',
            'bg-surface-container text-on-surface border border-outline-variant/30',
            'hover:bg-surface-container-high',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors duration-200 ease-out'
          )}
        >
          {testMutation.isPending ? (
            <span className="animate-spin w-4 h-4 border-2 border-on-surface border-t-transparent rounded-full" />
          ) : (
            <span className="material-symbols-outlined text-lg">play_arrow</span>
          )}
          Test Current Model
        </button>
      </div>
    </div>
  );
}
