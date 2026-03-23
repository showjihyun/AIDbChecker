import { useState } from "react";

const LICENSE_AUDIT = [
  // ── Frontend ──
  { area: "Frontend", tech: "React 18+", license: "MIT", status: "ok", note: "Meta 오픈소스" },
  { area: "Frontend", tech: "Next.js 14+", license: "MIT", status: "ok", note: "Vercel" },
  { area: "Frontend", tech: "TailwindCSS", license: "MIT", status: "ok", note: "" },
  { area: "Frontend", tech: "Recharts", license: "MIT", status: "ok", note: "React 차트 라이브러리" },
  { area: "Frontend", tech: "Apache ECharts", license: "Apache 2.0", status: "ok", note: "고급 시각화 (토폴로지 맵, ASH 히트맵)" },
  // ── API ──
  { area: "API", tech: "NestJS", license: "MIT", status: "ok", note: "TypeScript 서버 프레임워크" },
  { area: "API", tech: "Apollo GraphQL", license: "MIT", status: "ok", note: "Elide MIT License" },
  { area: "API", tech: "Socket.io", license: "MIT", status: "ok", note: "WebSocket 라이브러리" },
  { area: "API", tech: "MCP SDK (@modelcontextprotocol/sdk)", license: "MIT", status: "ok", note: "Anthropic/Linux Foundation" },
  { area: "API", tech: "A2A SDK", license: "Apache 2.0", status: "ok", note: "Google/Linux Foundation" },
  // ── Core Engine ──
  { area: "Core Engine", tech: "Python 3.11+", license: "PSF (MIT계열)", status: "ok", note: "" },
  { area: "Core Engine", tech: "FastAPI", license: "MIT", status: "ok", note: "비동기 Python 웹 프레임워크" },
  { area: "Core Engine", tech: "Celery", license: "BSD 3-Clause", status: "ok", note: "비동기 태스크 큐" },
  { area: "Core Engine", tech: "LangChain", license: "MIT", status: "ok", note: "LLM 프레임워크" },
  { area: "Core Engine", tech: "LangGraph", license: "MIT", status: "ok", note: "에이전트 상태 머신" },
  { area: "Core Engine", tech: "CrewAI", license: "MIT", status: "ok", note: "멀티 에이전트 프레임워크" },
  { area: "Core Engine", tech: "SQLAlchemy", license: "MIT", status: "ok", note: "Python ORM" },
  // ── AI/ML ──
  { area: "AI/ML", tech: "OpenAI API (GPT-4o)", license: "상용 API", status: "ok", note: "사용량 과금, 코드 배포 아님" },
  { area: "AI/ML", tech: "Claude API (Sonnet)", license: "상용 API", status: "ok", note: "사용량 과금, 코드 배포 아님" },
  { area: "AI/ML", tech: "Ollama", license: "MIT", status: "ok", note: "로컬 LLM 런타임" },
  { area: "AI/ML", tech: "vLLM", license: "Apache 2.0", status: "ok", note: "고성능 LLM 서빙" },
  { area: "AI/ML", tech: "Prophet (시계열 예측)", license: "MIT", status: "ok", note: "Meta 오픈소스" },
  { area: "AI/ML", tech: "scikit-learn", license: "BSD 3-Clause", status: "ok", note: "Isolation Forest 등" },
  // ── Infrastructure ──
  { area: "Infra", tech: "PostgreSQL", license: "PostgreSQL (MIT계열)", status: "ok", note: "메타 DB + 대상 DB" },
  { area: "Infra", tech: "pgvector", license: "PostgreSQL License", status: "ok", note: "벡터 검색 확장" },
  { area: "Infra", tech: "Apache Kafka", license: "Apache 2.0", status: "ok", note: "이벤트 스트리밍" },
  { area: "Infra", tech: "Docker", license: "Apache 2.0", status: "ok", note: "컨테이너 런타임" },
  { area: "Infra", tech: "Kubernetes", license: "Apache 2.0", status: "ok", note: "오케스트레이션" },
  // ── Observability ──
  { area: "Observability", tech: "OpenTelemetry", license: "Apache 2.0", status: "ok", note: "CNCF 표준" },
  { area: "Observability", tech: "Prometheus", license: "Apache 2.0", status: "ok", note: "메트릭 수집/저장" },
  // ── 🔴 변경 필요 항목 ──
  { area: "Infra ⚠️", tech: "Grafana", license: "AGPL v3 ❌", status: "danger", note: "수정 배포 시 전체 소스 공개 의무", old: true },
  { area: "Infra ⚠️", tech: "TimescaleDB Community", license: "TSL ⚠️", status: "warn", note: "SaaS 제공 불가 (Continuous Aggregate 등 핵심 기능 TSL)", old: true },
  { area: "Infra ⚠️", tech: "Redis 7.4+", license: "RSALv2 + SSPL ❌", status: "danger", note: "경쟁 제품에 사용 불가, SaaS 제한", old: true },
];

const REPLACEMENTS = [
  {
    category: "시각화/대시보드",
    old: { name: "Grafana", license: "AGPL v3", issue: "수정 배포 시 전체 소스 공개 의무. 솔루션 내장 배포 시 AGPL 감염 위험." },
    newPrimary: { name: "Apache Superset", license: "Apache 2.0", why: "Apache 재단 프로젝트. SQL 기반 대시보드, 차트, 필터 기능. 상용 솔루션 내장 가능." },
    newAlt: { name: "자체 React 대시보드 + Apache ECharts", license: "MIT + Apache 2.0", why: "완전한 커스터마이징 가능. 솔루션 차별화에 유리. ECharts는 Apache 재단 프로젝트." },
    recommendation: "자체 React 대시보드 (PRIMARY)",
    reason: "모니터링 전용 UI를 직접 구축하면 솔루션 차별화가 극대화됩니다. Apache Superset은 범용 BI 도구로 모니터링 특화 UX에는 한계가 있습니다. Phase 1에서는 Superset으로 빠르게 시작하고, Phase 2에서 자체 대시보드로 전환하는 전략도 가능합니다.",
  },
  {
    category: "시계열 DB",
    old: { name: "TimescaleDB Community", license: "TSL (Timescale License)", issue: "Apache 2.0 에디션은 Continuous Aggregate, 압축, 보존 정책 등 핵심 기능 미포함. TSL 에디션은 SaaS 제공 불가." },
    newPrimary: { name: "QuestDB", license: "Apache 2.0", why: "고성능 시계열 DB. SQL 지원. 1초 단위 메트릭에 최적화. 완전 Apache 2.0." },
    newAlt: { name: "Apache IoTDB", license: "Apache 2.0", why: "Apache 재단 시계열 DB. IoT/산업용으로 설계되었지만 메트릭 저장에도 적합." },
    newAlt2: { name: "VictoriaMetrics (단일노드)", license: "Apache 2.0", why: "Prometheus 호환 시계열 DB. 단일노드 버전은 Apache 2.0. 클러스터 버전은 별도 라이선스." },
    recommendation: "QuestDB (PRIMARY) + VictoriaMetrics (Prometheus 호환 필요 시)",
    reason: "QuestDB는 SQL 친화적이고 1초 단위 고해상도 메트릭에 최적화되어 있습니다. TimescaleDB Apache 에디션도 기본 hypertable은 사용 가능하지만, Continuous Aggregate 없이 다운샘플링을 직접 구현해야 합니다.",
  },
  {
    category: "캐시/세션",
    old: { name: "Redis 7.4+", license: "RSALv2 + SSPL", issue: "Redis 7.4부터 라이선스 변경. 경쟁 제품에 사용 불가. SaaS 제한." },
    newPrimary: { name: "Valkey", license: "BSD 3-Clause", why: "Linux Foundation이 관리하는 Redis 포크. Redis와 100% API 호환. AWS, Google, Oracle 등 후원." },
    newAlt: { name: "DragonflyDB", license: "BSL 1.1 → Apache 2.0 전환 예정", why: "Redis 호환 고성능 캐시. 단, 현재 BSL이므로 전환 시점 확인 필요." },
    newAlt2: { name: "KeyDB", license: "BSD 3-Clause", why: "Redis 포크. 멀티스레드 지원. Snap Inc 개발." },
    recommendation: "Valkey (PRIMARY)",
    reason: "Redis와 완전 호환이면서 BSD 라이선스. Linux Foundation 관리로 장기 지속성 보장. 기존 Redis 클라이언트 라이브러리를 그대로 사용할 수 있어 마이그레이션 비용이 0입니다.",
  },
];

const CANT_CHANGE = [
  {
    tech: "LLM 모델 자체 (Llama 3, Mistral 등)",
    license: "모델별 상이",
    issue: "Llama 3: Meta License (상용 가능, 단 MAU 7억 제한). Mistral: Apache 2.0. Qwen: Apache 2.0/Tongyi License.",
    recommendation: "Mistral 또는 Qwen 시리즈를 기본 오프라인 모델로 사용하면 라이선스 제약 없음. Llama 3도 일반적인 솔루션 규모에서는 문제없으나, 대규모 SaaS 시 MAU 조항 확인 필요.",
    changeable: true,
  },
  {
    tech: "PostgreSQL 확장 (pg_stat_statements 등)",
    license: "PostgreSQL License",
    issue: "PostgreSQL 내장 확장은 PostgreSQL License(MIT 계열). 서드파티 확장은 개별 확인 필요.",
    recommendation: "pg_stat_statements, pg_stat_monitor(BSD), pgBouncer(ISC License) 모두 허용적 라이선스. 문제 없음.",
    changeable: false,
  },
  {
    tech: "GitHub Actions (CI/CD)",
    license: "상용 서비스",
    issue: "GitHub Actions 자체는 상용 서비스(무료 티어 있음). 대안으로 Gitea Actions(MIT) 사용 가능.",
    recommendation: "온프레미스에서는 Gitea(MIT) + Gitea Actions 또는 Woodpecker CI(Apache 2.0) 사용 권장.",
    changeable: true,
  },
];

const FINAL_STACK = [
  { area: "Frontend", tech: "React 18+ / Next.js 14+", license: "MIT", note: "SPA + SSR" },
  { area: "Frontend", tech: "TailwindCSS", license: "MIT", note: "유틸리티 CSS" },
  { area: "Frontend", tech: "Apache ECharts", license: "Apache 2.0", note: "차트/토폴로지/히트맵" },
  { area: "Frontend", tech: "Recharts", license: "MIT", note: "React 통합 차트" },
  { area: "API", tech: "NestJS", license: "MIT", note: "TypeScript 서버" },
  { area: "API", tech: "Apollo GraphQL", license: "MIT", note: "유연한 데이터 조회" },
  { area: "API", tech: "Socket.io", license: "MIT", note: "1초 WebSocket 스트리밍" },
  { area: "Protocol", tech: "MCP SDK", license: "MIT", note: "Anthropic/Linux Foundation" },
  { area: "Protocol", tech: "A2A SDK", license: "Apache 2.0", note: "Google/Linux Foundation" },
  { area: "Protocol", tech: "OpenTelemetry", license: "Apache 2.0", note: "분산 트레이싱 수집" },
  { area: "Core", tech: "Python 3.11+ / FastAPI", license: "MIT", note: "비동기 API 서버" },
  { area: "Core", tech: "Celery", license: "BSD 3-Clause", note: "비동기 태스크 큐" },
  { area: "Agent", tech: "LangChain / LangGraph", license: "MIT", note: "에이전트 프레임워크" },
  { area: "Agent", tech: "CrewAI", license: "MIT", note: "멀티 에이전트 협업" },
  { area: "AI/LLM", tech: "OpenAI / Claude API", license: "상용 API", note: "온라인 LLM" },
  { area: "AI/LLM", tech: "Ollama + Mistral/Qwen", license: "MIT + Apache 2.0", note: "오프라인 LLM" },
  { area: "AI/LLM", tech: "vLLM", license: "Apache 2.0", note: "프로덕션 LLM 서빙" },
  { area: "AI/ML", tech: "Prophet / scikit-learn", license: "MIT / BSD", note: "시계열 예측, 이상 탐지" },
  { area: "DB", tech: "PostgreSQL 16+", license: "PostgreSQL (MIT계열)", note: "메타 DB + 대상 DB" },
  { area: "DB", tech: "pgvector", license: "PostgreSQL License", note: "RAG 벡터 검색" },
  { area: "시계열", tech: "QuestDB ✦", license: "Apache 2.0", note: "1초 메트릭 + ASH 저장" },
  { area: "캐시", tech: "Valkey ✦", license: "BSD 3-Clause", note: "Redis 호환 캐시 (Linux Foundation)" },
  { area: "메시징", tech: "Apache Kafka", license: "Apache 2.0", note: "이벤트 + A2A 메시징" },
  { area: "시각화", tech: "자체 대시보드 + ECharts ✦", license: "MIT + Apache 2.0", note: "Grafana 대체" },
  { area: "모니터링", tech: "Prometheus", license: "Apache 2.0", note: "자체 시스템 헬스" },
  { area: "모니터링", tech: "VictoriaMetrics (단일노드)", license: "Apache 2.0", note: "Prometheus 호환 저장소" },
  { area: "CI/CD", tech: "Gitea + Woodpecker CI ✦", license: "MIT + Apache 2.0", note: "온프레미스 Git/CI" },
  { area: "컨테이너", tech: "Docker / Kubernetes", license: "Apache 2.0", note: "배포 자동화" },
];

function StatusBadge({ status }) {
  const map = {
    ok: { bg: "#10b98122", color: "#10b981", border: "#10b98144", text: "✅ OK" },
    warn: { bg: "#f59e0b22", color: "#f59e0b", border: "#f59e0b44", text: "⚠️ 주의" },
    danger: { bg: "#ef444422", color: "#ef4444", border: "#ef444444", text: "❌ 변경 필요" },
  };
  const s = map[status] || map.ok;
  return <span className="text-xs px-1.5 py-0.5 rounded font-bold" style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{s.text}</span>;
}

export default function App() {
  const [tab, setTab] = useState("audit");

  const tabs = [
    { id: "audit", label: "🔍 라이선스 감사" },
    { id: "replace", label: "🔄 변경 항목 상세" },
    { id: "final", label: "✅ 최종 기술 스택" },
    { id: "caution", label: "⚠️ 유의 사항" },
  ];

  return (
    <div className="min-h-screen text-white p-4 md:p-6" style={{ background: "linear-gradient(145deg, #020617, #0f172a 50%, #020617)", fontFamily: "'Geist','Pretendard',-apple-system,sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');.mono{font-family:'Space Mono',monospace}::-webkit-scrollbar{width:6px}::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}`}</style>

      <div className="text-center mb-5">
        <div className="mono text-xs tracking-widest mb-1" style={{ color: "#64748b" }}>LICENSE AUDIT & TECHNOLOGY STACK v3.1</div>
        <h1 className="text-xl md:text-2xl font-bold" style={{ color: "#0ea5e9", textShadow: "0 0 20px rgba(14,165,233,0.5)" }}>
          기술 스택 라이선스 감사 & 변경 보고서
        </h1>
        <p className="text-xs mt-1.5" style={{ color: "#94a3b8" }}>
          모든 기술 스택을 Apache 2.0 / MIT / BSD 등 허용적(Permissive) 라이선스로 통일
        </p>
      </div>

      <div className="flex gap-1 mb-5 justify-center flex-wrap">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className="px-4 py-1.5 rounded-full text-xs font-semibold transition-all" style={{ background: tab === t.id ? "#0ea5e9" : "transparent", color: tab === t.id ? "#fff" : "#64748b", border: tab === t.id ? "none" : "1px solid #334155" }}>{t.label}</button>
        ))}
      </div>

      {/* ── Audit Tab ── */}
      {tab === "audit" && (
        <div className="max-w-5xl mx-auto">
          <div className="flex gap-4 mb-4 flex-wrap text-xs" style={{ color: "#94a3b8" }}>
            <span><StatusBadge status="ok" /> 허용적 라이선스 (상용 솔루션 가능)</span>
            <span><StatusBadge status="warn" /> 조건부 사용 가능</span>
            <span><StatusBadge status="danger" /> 변경 필요 (GPL 계열 / 제한적)</span>
          </div>
          <div className="space-y-1">
            {LICENSE_AUDIT.map((item, i) => (
              <div key={i} className="rounded px-4 py-2 flex items-center gap-3 flex-wrap" style={{ background: item.old ? "rgba(239,68,68,0.08)" : "rgba(30,41,59,0.5)", border: `1px solid ${item.old ? "#ef444433" : "#33415533"}` }}>
                <span className="text-xs font-semibold min-w-[100px]" style={{ color: "#64748b" }}>{item.area}</span>
                <span className="text-xs font-bold text-white min-w-[200px]">{item.tech}</span>
                <span className="mono text-xs min-w-[140px]" style={{ color: item.status === "ok" ? "#10b981" : item.status === "warn" ? "#f59e0b" : "#ef4444" }}>{item.license}</span>
                <StatusBadge status={item.status} />
                {item.note && <span className="text-xs" style={{ color: "#64748b" }}>{item.note}</span>}
              </div>
            ))}
          </div>
          <div className="rounded-lg p-4 mt-4" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid #ef444433" }}>
            <div className="text-xs font-bold text-white mb-2">📋 감사 결과 요약</div>
            <div className="text-xs space-y-1" style={{ color: "#94a3b8" }}>
              <p>총 <strong style={{ color: "#fff" }}>30개</strong> 기술 중 <strong style={{ color: "#ef4444" }}>3개</strong>가 변경 필요:</p>
              <p>1. <strong style={{ color: "#ef4444" }}>Grafana (AGPL v3)</strong> → 자체 React 대시보드 + Apache ECharts (또는 Apache Superset)</p>
              <p>2. <strong style={{ color: "#f59e0b" }}>TimescaleDB Community (TSL)</strong> → QuestDB (Apache 2.0)</p>
              <p>3. <strong style={{ color: "#ef4444" }}>Redis 7.4+ (RSALv2 + SSPL)</strong> → Valkey (BSD 3-Clause)</p>
              <p style={{ color: "#10b981", marginTop: "8px" }}>나머지 27개 기술은 모두 Apache 2.0 / MIT / BSD / PostgreSQL License로 상용 솔루션 개발에 문제 없습니다.</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Replace Tab ── */}
      {tab === "replace" && (
        <div className="max-w-5xl mx-auto space-y-4">
          {REPLACEMENTS.map((r, i) => (
            <div key={i} className="rounded-lg p-4" style={{ background: "rgba(30,41,59,0.7)", border: "1px solid #334155" }}>
              <div className="text-xs font-bold text-white mb-3">{r.category}</div>
              {/* Old */}
              <div className="rounded px-3 py-2 mb-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid #ef444433" }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: "#ef4444" }}>❌ 기존</span>
                  <span className="text-xs font-bold text-white">{r.old.name}</span>
                  <span className="mono text-xs" style={{ color: "#ef4444" }}>{r.old.license}</span>
                </div>
                <div className="text-xs" style={{ color: "#94a3b8" }}>{r.old.issue}</div>
              </div>
              {/* New Primary */}
              <div className="rounded px-3 py-2 mb-2" style={{ background: "rgba(16,185,129,0.1)", border: "1px solid #10b98133" }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: "#10b981" }}>✅ 대체 (주)</span>
                  <span className="text-xs font-bold text-white">{r.newPrimary.name}</span>
                  <span className="mono text-xs" style={{ color: "#10b981" }}>{r.newPrimary.license}</span>
                </div>
                <div className="text-xs" style={{ color: "#94a3b8" }}>{r.newPrimary.why}</div>
              </div>
              {/* New Alt */}
              <div className="rounded px-3 py-2 mb-2" style={{ background: "rgba(30,41,59,0.5)", border: "1px solid #33415566" }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs" style={{ color: "#64748b" }}>🔄 대체 (보조)</span>
                  <span className="text-xs font-bold text-white">{r.newAlt.name}</span>
                  <span className="mono text-xs" style={{ color: "#0ea5e9" }}>{r.newAlt.license}</span>
                </div>
                <div className="text-xs" style={{ color: "#94a3b8" }}>{r.newAlt.why}</div>
              </div>
              {/* Recommendation */}
              <div className="rounded px-3 py-2 mt-2" style={{ background: "rgba(14,165,233,0.08)", border: "1px solid #0ea5e933" }}>
                <div className="text-xs font-bold" style={{ color: "#0ea5e9" }}>💡 추천: {r.recommendation}</div>
                <div className="text-xs mt-1" style={{ color: "#94a3b8" }}>{r.reason}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Final Stack Tab ── */}
      {tab === "final" && (
        <div className="max-w-5xl mx-auto">
          <div className="text-xs mb-3" style={{ color: "#64748b" }}>✦ 표시: v3.0 대비 변경된 기술. 모든 기술이 허용적(Permissive) 라이선스입니다.</div>
          <div className="space-y-1">
            {FINAL_STACK.map((item, i) => (
              <div key={i} className="rounded px-4 py-2 flex items-center gap-3 flex-wrap" style={{ background: item.tech.includes("✦") ? "rgba(14,165,233,0.08)" : "rgba(30,41,59,0.5)", border: `1px solid ${item.tech.includes("✦") ? "#0ea5e933" : "#33415533"}` }}>
                <span className="text-xs font-semibold min-w-[80px]" style={{ color: "#64748b" }}>{item.area}</span>
                <span className="text-xs font-bold text-white min-w-[240px]">{item.tech}</span>
                <span className="mono text-xs px-2 py-0.5 rounded min-w-[120px]" style={{ background: "#10b98118", color: "#10b981" }}>{item.license}</span>
                <span className="text-xs" style={{ color: "#94a3b8" }}>{item.note}</span>
              </div>
            ))}
          </div>
          <div className="rounded-lg p-4 mt-4" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid #10b98133" }}>
            <div className="text-xs font-bold" style={{ color: "#10b981" }}>✅ 라이선스 클린 완료</div>
            <div className="text-xs mt-1" style={{ color: "#94a3b8" }}>
              전체 기술 스택이 Apache 2.0, MIT, BSD, PostgreSQL License 등 허용적 라이선스로 구성되었습니다.
              GPL/AGPL/SSPL/RSALv2 계열 기술은 모두 대체되었으며, 상용 솔루션 개발 및 SaaS 배포에 법적 제약이 없습니다.
            </div>
          </div>
        </div>
      )}

      {/* ── Caution Tab ── */}
      {tab === "caution" && (
        <div className="max-w-5xl mx-auto space-y-4">
          <div className="text-xs mb-3" style={{ color: "#64748b" }}>완전히 바꿀 수 없거나, 사용 시 유의해야 할 항목입니다.</div>
          {CANT_CHANGE.map((item, i) => (
            <div key={i} className="rounded-lg p-4" style={{ background: "rgba(30,41,59,0.7)", border: "1px solid #f59e0b33" }}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold text-white">{item.tech}</span>
                <span className="mono text-xs" style={{ color: "#f59e0b" }}>{item.license}</span>
              </div>
              <div className="text-xs mb-2" style={{ color: "#94a3b8" }}>{item.issue}</div>
              <div className="text-xs" style={{ color: "#0ea5e9" }}>💡 {item.recommendation}</div>
            </div>
          ))}

          <div className="rounded-lg p-4" style={{ background: "rgba(30,41,59,0.7)", border: "1px solid #33415566" }}>
            <div className="text-xs font-bold text-white mb-2">📌 라이선스 관리 Best Practice</div>
            <div className="text-xs space-y-1.5" style={{ color: "#94a3b8" }}>
              <p>1. <strong style={{ color: "#fff" }}>SBOM(Software Bill of Materials)</strong> 자동 생성 도구 사용 (예: Syft — Apache 2.0)</p>
              <p>2. <strong style={{ color: "#fff" }}>CI/CD에 라이선스 스캔</strong> 통합 (예: FOSSA, Licensee — MIT)</p>
              <p>3. 새 의존성 추가 시 <strong style={{ color: "#fff" }}>허용 리스트(allowlist)</strong> 방식으로 관리: Apache 2.0, MIT, BSD, ISC, PostgreSQL만 허용</p>
              <p>4. <strong style={{ color: "#fff" }}>거부 리스트(denylist)</strong>: GPL, AGPL, SSPL, EUPL, CPAL, OSL을 명시적으로 차단</p>
              <p>5. 분기별 <strong style={{ color: "#fff" }}>라이선스 감사</strong> 수행 (의존성 트리 전체 스캔)</p>
            </div>
          </div>
        </div>
      )}

      <div className="text-center mt-8 mono text-xs" style={{ color: "#334155" }}>
        License Audit Report · v3.1 · All Permissive Licenses · 2026
      </div>
    </div>
  );
}
