// Spec: FS-ALERT-002 — Slack Integration Settings
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/api/client';

interface SlackSettings {
  has_bot_token: boolean;
  channel_id: string;
  has_webhook_url: boolean;
}

export function SlackSettingsPage() {
  const queryClient = useQueryClient();
  const [botToken, setBotToken] = useState('');
  const [channelId, setChannelId] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');

  const { data: settings, isLoading } = useQuery({
    queryKey: ['slack-settings'],
    queryFn: () => apiClient.get<SlackSettings>('/settings/slack'),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (settings) {
      setChannelId(settings.channel_id || '');
    }
  }, [settings]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload: Record<string, string> = {};
      if (botToken) payload.bot_token = botToken;
      if (channelId) payload.channel_id = channelId;
      if (webhookUrl) payload.webhook_url = webhookUrl;
      return apiClient.put<SlackSettings>('/settings/slack', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['slack-settings'] });
      setBotToken('');
      setWebhookUrl('');
    },
  });

  const testMutation = useMutation({
    mutationFn: () => apiClient.post<{ success: boolean; error: string }>('/settings/slack/test'),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-40 text-on-surface-variant">
        Loading...
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <h1 className="text-lg font-semibold text-on-surface mb-1">Slack Integration</h1>
      <p className="text-xs text-on-surface-variant mb-6">
        Slack Bot Token + Channel ID를 설정하면 인시던트 알림, DBA 리포트가 자동 발송됩니다.
      </p>

      <div className="bg-surface-container rounded-xl p-6 space-y-5">
        {/* Status */}
        <div className="flex items-center gap-4 text-xs">
          <span className={settings?.has_bot_token ? 'text-green-400' : 'text-red-400'}>
            {settings?.has_bot_token ? '🟢 Bot Token 설정됨' : '🔴 Bot Token 미설정'}
          </span>
          <span className={settings?.channel_id ? 'text-green-400' : 'text-on-surface-variant'}>
            Channel: {settings?.channel_id || '미설정'}
          </span>
          {settings?.has_webhook_url && (
            <span className="text-blue-400">Webhook URL 설정됨</span>
          )}
        </div>

        {/* Bot Token */}
        <div>
          <label className="block text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold mb-1">
            Bot Token (xoxb-...)
          </label>
          <input
            type="password"
            value={botToken}
            onChange={(e) => setBotToken(e.target.value)}
            placeholder={settings?.has_bot_token ? '••••••••••• (변경 시 입력)' : 'xoxb-...'}
            className="w-full bg-surface text-on-surface text-xs rounded-lg px-4 py-3 border border-white/10 focus:border-primary/50 outline-none"
          />
          <p className="text-[9px] text-on-surface-variant/50 mt-1">
            Slack App → OAuth & Permissions → Bot User OAuth Token
          </p>
        </div>

        {/* Channel ID */}
        <div>
          <label className="block text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold mb-1">
            Channel ID
          </label>
          <input
            type="text"
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
            placeholder="C0APZRZ4Y7M"
            className="w-full bg-surface text-on-surface text-xs rounded-lg px-4 py-3 border border-white/10 focus:border-primary/50 outline-none"
          />
          <p className="text-[9px] text-on-surface-variant/50 mt-1">
            채널 우클릭 → 링크 복사 → URL 끝의 ID (예: C0APZRZ4Y7M)
          </p>
        </div>

        {/* Webhook URL (optional) */}
        <div>
          <label className="block text-[10px] text-on-surface-variant uppercase tracking-wider font-semibold mb-1">
            Webhook URL (선택)
          </label>
          <input
            type="text"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder={settings?.has_webhook_url ? '••••••••••• (변경 시 입력)' : 'https://hooks.slack.com/...'}
            className="w-full bg-surface text-on-surface text-xs rounded-lg px-4 py-3 border border-white/10 focus:border-primary/50 outline-none"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
            className="bg-primary hover:bg-primary/80 disabled:opacity-30 text-on-primary rounded-lg px-5 py-2.5 text-xs font-semibold transition-colors"
          >
            {saveMutation.isPending ? '저장 중...' : '저장'}
          </button>
          <button
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
            className="bg-surface-container-high hover:bg-surface-container text-on-surface rounded-lg px-5 py-2.5 text-xs font-semibold transition-colors border border-white/10"
          >
            {testMutation.isPending ? '발송 중...' : '테스트 발송'}
          </button>
        </div>

        {/* Feedback */}
        {saveMutation.isSuccess && (
          <p className="text-xs text-green-400">설정이 저장되었습니다.</p>
        )}
        {saveMutation.isError && (
          <p className="text-xs text-red-400">저장 실패</p>
        )}
        {testMutation.isSuccess && (
          <p className="text-xs text-green-400">
            {testMutation.data?.success
              ? '테스트 메시지 발송 성공!'
              : `발송 실패: ${testMutation.data?.error}`}
          </p>
        )}
      </div>

      <div className="mt-6 bg-surface-container rounded-xl p-6">
        <h3 className="text-sm font-semibold text-on-surface mb-2">설정 가이드</h3>
        <ol className="text-xs text-on-surface-variant space-y-2 list-decimal list-inside">
          <li>Slack App 생성: api.slack.com/apps → Create New App</li>
          <li>Bot Token Scopes 추가: <code className="bg-surface px-1 rounded">chat:write</code></li>
          <li>앱을 워크스페이스에 설치</li>
          <li>Bot Token (xoxb-...) 복사 → 위에 입력</li>
          <li>알림받을 채널에 Bot 초대: <code className="bg-surface px-1 rounded">/invite @봇이름</code></li>
          <li>Channel ID 입력 후 저장</li>
          <li>테스트 발송으로 확인</li>
        </ol>
      </div>
    </div>
  );
}
