// Spec: MVP-ADMIN — Settings page (instance registration, alerts, users)
import { EmptyState } from '@/components/common/EmptyState';

export function SettingsPage() {
  return (
    <div className="space-y-module-gap">
      <div>
        <h1 className="text-2xl font-display font-bold text-on-surface tracking-tight">
          Settings
        </h1>
        <p className="text-xs text-on-surface-variant mt-1">
          Instance management, alert channels, and user administration
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <SettingsSection
          title="Instance Management"
          icon="dns"
          description="PostgreSQL 인스턴스를 등록하고 연결 설정을 관리합니다."
        />
        <SettingsSection
          title="Alert Channels"
          icon="notifications"
          description="Slack, Webhook 등 알림 채널을 설정합니다."
        />
        <SettingsSection
          title="User Management"
          icon="group"
          description="사용자 계정과 RBAC 역할을 관리합니다."
        />
        <SettingsSection
          title="System Configuration"
          icon="tune"
          description="메트릭 수집 주기, AI 모델 설정 등 시스템 구성을 변경합니다."
        />
      </div>
    </div>
  );
}

interface SettingsSectionProps {
  title: string;
  icon: string;
  description: string;
}

function SettingsSection({ title, icon, description }: SettingsSectionProps) {
  return (
    <div className="bg-surface-container rounded-xl p-6 hover:bg-surface-container-high transition-colors duration-200 ease-out">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-lg bg-primary-container/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary-container">
            {icon}
          </span>
        </div>
        <h3 className="text-sm font-semibold text-on-surface">{title}</h3>
      </div>
      <p className="text-xs text-on-surface-variant">{description}</p>
      <EmptyState
        icon="construction"
        message="MVP Demo"
        description="이 섹션은 MVP 구현 단계에서 활성화됩니다."
        className="py-8"
      />
    </div>
  );
}
