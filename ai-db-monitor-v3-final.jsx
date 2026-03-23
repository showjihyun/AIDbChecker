import { useState } from "react";

/* ─── v3.0 신규 추가 기능 (IBM/Dynatrace/Datadog/Instana/DBmarlin/Chat2DB 참조) ─── */
const V3_ADDITIONS = [
  {
    id: "baseline",
    tag: "Auto-Baselining",
    title: "AI 자동 베이스라인 학습 (Dynamic Baselining)",
    layer: "Monitoring Agent → AI Engine",
    color: "#06b6d4",
    icon: "📈",
    ref: "IBM Instana, Dynatrace Davis AI",
    desc: "수동 임계값 설정 없이 AI가 DB의 정상 행동 패턴(CPU, 메모리, 쿼리 속도, 커넥션 수)을 자동 학습하고, 동적 베이스라인에서 벗어나는 이상(anomaly)을 실시간 탐지합니다. 시간대별, 요일별, 시즌별 패턴을 구분하여 오탐을 최소화합니다.",
    how: [
      "Monitoring Agent가 최소 2주간 메트릭을 수집하여 정상 패턴 학습",
      "시계열 분해(STL) + Isolation Forest로 시간대/요일별 동적 임계값 생성",
      "수동 임계값은 '안전 상한선'으로 유지, AI 베이스라인은 '미세 이상 탐지'로 병행",
      "새로운 배포/마이그레이션 후 자동으로 베이스라인 재학습 (Change-Point Detection)",
    ],
  },
  {
    id: "fullstack",
    tag: "Full-Stack Observability",
    title: "풀스택 옵저버빌리티 (토폴로지 자동 발견)",
    layer: "Monitoring Agent + Infrastructure",
    color: "#8b5cf6",
    icon: "🗺️",
    ref: "Dynatrace Smartscape, Datadog Service Map",
    desc: "DB만 단독 모니터링하지 않고, 애플리케이션 → 미들웨어 → DB → 인프라 간 의존성을 자동으로 발견하여 토폴로지 맵을 생성합니다. 장애 발생 시 영향 범위를 즉시 파악하고, 근본원인이 DB인지 인프라인지 애플리케이션인지 크로스 스택으로 분석합니다.",
    how: [
      "OpenTelemetry 기반 분산 트레이싱으로 서비스 → DB 호출 자동 추적",
      "Adapter가 DB 커넥션 메타데이터(client_addr, application_name)를 수집하여 의존성 맵 구축",
      "Kubernetes/Docker 메타데이터 연동으로 컨테이너-서비스-DB 관계 자동 발견",
      "Diagnosis Agent가 RCA 수행 시 토폴로지 맵을 참조하여 크로스 스택 상관 분석",
    ],
  },
  {
    id: "ash",
    tag: "Active Session History",
    title: "ASH & Wait Event 분석 (세션 레벨 심층 분석)",
    layer: "Query Analyzer + Adapter",
    color: "#f59e0b",
    icon: "⏱️",
    ref: "Oracle ASH, Datadog Wait Events",
    desc: "Oracle의 Active Session History(ASH)에서 영감을 받아, 1초 단위로 활성 세션 샘플링을 수행합니다. Wait Event(Lock, I/O, CPU, Network)별 병목 지점을 시각화하고, 특정 시점의 세션 상태를 타임라인으로 드릴다운할 수 있습니다.",
    how: [
      "PostgreSQL: pg_stat_activity를 1초 간격으로 샘플링하여 ASH 테이블 구축",
      "Wait Event를 카테고리별 분류: CPU, LWLock, Lock, I/O, IPC, Network, Timeout 등",
      "TimescaleDB에 1초 단위 세션 스냅샷 저장 (연속 집계로 자동 다운샘플링)",
      "대시보드에서 시간축 드릴다운: 분 → 초 단위로 세션 상태 추적 가능",
    ],
  },
  {
    id: "schema",
    tag: "Schema Change Tracking",
    title: "스키마 변경 추적 & 영향도 분석",
    layer: "Adapter + Audit Logger",
    color: "#ef4444",
    icon: "🔄",
    ref: "DBmarlin",
    desc: "DDL 변경(테이블 생성/삭제, 컬럼 추가, 인덱스 변경, 파라미터 변경)을 자동 감지하고, 변경 전후 성능 메트릭을 비교하여 영향도를 분석합니다. 성능이 저하된 경우 AI가 자동으로 상관관계를 추론하여 변경 롤백을 추천합니다.",
    how: [
      "PostgreSQL: event trigger + DDL 로깅으로 모든 스키마 변경 실시간 캡처",
      "변경 이벤트를 대시보드 타임라인에 Annotation으로 자동 표시",
      "변경 전후 30분 성능 메트릭 자동 비교 (Before/After Analysis)",
      "AI가 DDL 변경과 성능 저하 사이의 상관관계를 자동 추론 (Causal Inference)",
    ],
  },
  {
    id: "autotuning",
    tag: "Auto Query Tuning",
    title: "AI 자동 쿼리 튜닝 (추천 + 자동 적용)",
    layer: "Query Analyzer + Remediation Agent",
    color: "#10b981",
    icon: "🔧",
    ref: "Oracle Auto Index, SQL Server IQP",
    desc: "단순 추천을 넘어, AI가 쿼리 실행 계획을 분석하여 인덱스 생성, 쿼리 구조 수정, 파라미터 튜닝을 자동 적용합니다. Adaptive Autonomy Level에 따라 추천만/승인 후 적용/자동 적용을 결정합니다.",
    how: [
      "Query Analyzer가 실행 계획(EXPLAIN ANALYZE)을 LLM으로 분석하여 병목 식별",
      "인덱스 추천: Missing Index 감지 → SQL 자동 생성 → Playbook으로 실행",
      "쿼리 리라이트 제안: LLM이 비효율 패턴을 식별하고 최적화된 SQL 제안",
      "파라미터 튜닝: work_mem, shared_buffers 등 워크로드 기반 최적값 추천",
      "Autonomy Level 2(승인 후) 또는 Level 3(자동) 모드에서 자동 적용",
    ],
  },
  {
    id: "chat2db",
    tag: "Chat2DB-Style AIGC",
    title: "AIGC 인터페이스 (자연어 DB 관리 + 리포트 자동 생성)",
    layer: "Presentation + AI Engine",
    color: "#3b82f6",
    icon: "💬",
    ref: "Chat2DB",
    desc: "Chat2DB에서 영감을 받아, 모니터링 데이터 조회뿐 아니라 SQL 생성, 쿼리 최적화 제안, 실행 계획 해석, 데이터 리포트 자동 생성까지 AIGC(AI Generated Content) 전 기능을 대시보드에 통합합니다.",
    how: [
      "NL2SQL 확장: 모니터링 질의 + 실제 비즈니스 데이터 질의 모두 지원",
      "SQL 최적화 어시스턴트: 사용자 SQL 입력 → AI가 최적화 버전 + 실행 계획 비교 제공",
      "AI 리포트 생성: '이번 주 DB 건강 리포트 만들어줘' → 자동 차트 + 분석 + PDF 생성",
      "실행 계획 자연어 해석: EXPLAIN 결과를 비기술자도 이해할 수 있는 자연어로 번역",
      "커스텀 AI 데이터셋: 사용자가 비즈니스 용어를 등록하면 AI 질의 정확도 향상",
    ],
  },
  {
    id: "granularity",
    tag: "1-Second Granularity",
    title: "1초 단위 고해상도 모니터링",
    layer: "Metric Collector + TimescaleDB",
    color: "#ec4899",
    icon: "⚡",
    ref: "IBM Instana",
    desc: "IBM Instana의 1초 단위 실시간 관측에서 착안하여, 핵심 메트릭을 1초 간격으로 수집합니다. 순간적인 스파이크나 마이크로 버스트를 놓치지 않으며, 장기 보관 시에는 자동 다운샘플링으로 저장 비용을 최적화합니다.",
    how: [
      "Hot 메트릭(CPU, 커넥션 수, 활성 쿼리): 1초 간격 수집 → 7일 보관",
      "Warm 메트릭(디스크, 테이블 크기): 10초 간격 수집 → 90일 보관",
      "Cold 메트릭(백업 상태, 인증서 만료): 1분 간격 수집 → 1년 보관",
      "TimescaleDB Continuous Aggregate로 1초→10초→1분→1시간 자동 다운샘플링",
      "이상 탐지 시 자동으로 해당 시간대의 1초 데이터 보존 기간 연장",
    ],
  },
];

/* ─── 업그레이드된 통합 레이어 구조 ─── */
const LAYERS_V3 = [
  {
    id: "presentation",
    title: "Presentation Layer",
    subtitle: "AIGC 인터페이스 & 풀스택 대시보드",
    color: "#0ea5e9",
    bgColor: "#0c4a6e",
    items: [
      { name: "풀스택 대시보드", desc: "DB + 인프라 + 앱 토폴로지 맵, 리소스/성능 실시간 시각화", t: "UP" },
      { name: "AIGC Chat 패널", desc: "Chat2DB 스타일 자연어 DB 관리: NL2SQL + SQL 최적화 + 리포트 생성", t: "UP" },
      { name: "ASH Timeline", desc: "Active Session History 1초 단위 드릴다운, Wait Event 시각화", t: "NEW" },
      { name: "Schema Change Timeline", desc: "DDL 변경 이벤트와 성능 메트릭 오버레이 비교 뷰", t: "NEW" },
      { name: "알람 센터", desc: "AI 동적 베이스라인 기반 알림, 에스컬레이션 정책, Autonomy Level 표시" },
      { name: "Task Queue & Playbook", desc: "Task 관리 + YAML Playbook 에디터 + Git 연동" },
      { name: "사용자/권한 관리", desc: "RBAC, SSO/LDAP, 감사 로그 뷰어" },
    ],
  },
  {
    id: "api",
    title: "API Gateway & Integration Layer",
    subtitle: "MCP Server · A2A Gateway · OTel Collector",
    color: "#06b6d4",
    bgColor: "#164e63",
    items: [
      { name: "REST / GraphQL API", desc: "프론트엔드 & 외부 시스템 통합 API (OpenAPI 3.0)" },
      { name: "WebSocket Server", desc: "1초 단위 메트릭 스트리밍, 라이브 알림 푸시" },
      { name: "MCP Server", desc: "외부 AI 도구(Claude, Copilot)가 메트릭/쿼리/알림 조회", t: "v2" },
      { name: "A2A Gateway", desc: "내부/외부 에이전트 간 Agent Card 발견 및 Task 라우팅", t: "v2" },
      { name: "OTel Collector", desc: "OpenTelemetry 수집기: 앱 트레이스 → DB 호출 의존성 추출", t: "NEW" },
      { name: "Auth Service", desc: "JWT/OAuth2, MCP/A2A 인증, Rate Limiting 통합" },
    ],
  },
  {
    id: "core",
    title: "Core Engine Layer (Multi-Agent)",
    subtitle: "AI 에이전트 + Auto-Tuning + Full-Stack RCA",
    color: "#f59e0b",
    bgColor: "#78350f",
    items: [
      { name: "Monitoring Agent", desc: "1초 메트릭 수집 + AI 자동 베이스라인 학습 + 동적 이상 탐지", t: "UP" },
      { name: "Diagnosis Agent", desc: "RAG 기반 RCA + 토폴로지 크로스 스택 분석 + Causal Inference", t: "UP" },
      { name: "Remediation Agent", desc: "Playbook + Self-Healing + Auto Query Tuning 실행", t: "UP" },
      { name: "Reporting Agent", desc: "AIGC 리포트 생성 + NL2SQL + 실행계획 자연어 해석", t: "UP" },
      { name: "Query Analyzer", desc: "ASH 분석 + Wait Event 분류 + 자동 튜닝 추천/적용", t: "UP" },
      { name: "Alert Engine", desc: "동적 베이스라인 알림 + 노이즈 90% 제거 + Schema Change 연동" },
      { name: "Topology Engine", desc: "OTel 트레이스 기반 서비스 의존성 자동 발견 및 토폴로지 맵 관리", t: "NEW" },
      { name: "Task Orchestrator", desc: "Adaptive Autonomy 5단계 + Playbook Engine + 롤백 관리" },
      { name: "Audit Logger", desc: "AI Reasoning + Self-Healing + Schema Change + 전 과정 상세 로깅" },
    ],
  },
  {
    id: "adapter",
    title: "Database Adapter Layer (Plugin)",
    subtitle: "멀티 DB 어댑터 + ASH + Schema Tracker",
    color: "#10b981",
    bgColor: "#064e3b",
    items: [
      { name: "PostgreSQL Adapter", desc: "pg_stat_* + 1초 ASH 샘플링 + DDL Event Trigger + pgBouncer" , t: "UP" },
      { name: "MySQL Adapter", desc: "performance_schema + slow_query_log + InnoDB + Wait Events" },
      { name: "MS-SQL Adapter", desc: "DMV + Extended Events + Query Store + Wait Stats" },
      { name: "Schema Change Tracker", desc: "DDL 변경 실시간 캡처 + Before/After 성능 비교 자동화", t: "NEW" },
      { name: "Plugin Interface (SPI)", desc: "새 DB 추가를 위한 표준 인터페이스 (ASH/Schema 포함 확장)" },
    ],
  },
  {
    id: "infra",
    title: "Infrastructure Layer",
    subtitle: "시계열 DB · Vector Store · OTel · Git",
    color: "#ef4444",
    bgColor: "#7f1d1d",
    items: [
      { name: "TimescaleDB", desc: "1초 고해상도 메트릭 + ASH + 자동 다운샘플링 (Continuous Aggregate)", t: "UP" },
      { name: "PostgreSQL (메타)", desc: "설정, 사용자, 규칙, Task, Playbook 메타, 토폴로지 그래프" },
      { name: "Redis", desc: "실시간 캐시, Agent 상태, 동적 베이스라인 캐시" },
      { name: "Kafka", desc: "A2A 메시지 + 이벤트 스트리밍 + 1초 메트릭 파이프라인" },
      { name: "pgvector + RAG", desc: "DB 문서/이력 임베딩 + 유사도 검색 + 피드백 루프" },
      { name: "Playbook Git Repo", desc: "YAML Playbook 버전 관리 + LLM 자동 생성 + CI/CD" },
    ],
  },
];

/* ─── 참조 솔루션 매핑 ─── */
const TOOL_MAP = [
  { tool: "Oracle Autonomous AI DB", features: ["Auto-Tuning", "Self-Healing", "AI Agent 내장"], applied: "Auto Query Tuning, Self-Healing, A2A Agent" },
  { tool: "Dynatrace Davis AI", features: ["Smartscape 토폴로지", "크로스 스택 RCA", "자동 발견"], applied: "Full-Stack Observability, Topology Engine" },
  { tool: "IBM Instana", features: ["1초 단위 메트릭", "자동 의존성 맵", "실시간 RCA"], applied: "1-Second Granularity, Auto-Baselining" },
  { tool: "Datadog DB Monitoring", features: ["Wait Event 분석", "실행 계획", "서비스 맵"], applied: "ASH & Wait Events, Full-Stack Observability" },
  { tool: "LogicMonitor Edwin AI", features: ["AI 이상 탐지", "트렌드 분석", "자연어 요약"], applied: "Auto-Baselining, AIGC Reporting" },
  { tool: "DBmarlin", features: ["스키마 변경 추적", "Before/After 분석"], applied: "Schema Change Tracking" },
  { tool: "Chat2DB", features: ["NL2SQL", "AI SQL 최적화", "BI 대시보드 생성"], applied: "AIGC Interface, NL2SQL" },
  { tool: "Percona PMM 3.x", features: ["오픈소스", "오프라인 Advisor", "멀티 DB"], applied: "Plugin Architecture, Offline Mode" },
  { tool: "Xata Agent", features: ["LLM Playbook", "PostgreSQL 전문 에이전트"], applied: "Playbook-as-Code, Multi-Agent" },
  { tool: "pganalyze + MCP", features: ["MCP 서버", "쿼리 분석", "EXPLAIN 추적"], applied: "MCP Server, Query Analyzer" },
];

function Badge({ text, color }) {
  const colors = { NEW: "#10b981", UP: "#f59e0b", "v2": "#8b5cf6" };
  const c = colors[text] || color || "#64748b";
  return <span className="text-xs px-1.5 py-0.5 rounded font-bold ml-1" style={{ background: c + "22", color: c, border: `1px solid ${c}44` }}>{text}</span>;
}

export default function App() {
  const [tab, setTab] = useState("additions");
  const [selAdd, setSelAdd] = useState("baseline");
  const [expLayers, setExpLayers] = useState(new Set(["core"]));

  const tabs = [
    { id: "additions", label: "🔥 v3.0 신규 기능" },
    { id: "arch", label: "📐 통합 아키텍처" },
    { id: "toolmap", label: "🧩 솔루션 참조 매핑" },
    { id: "compare", label: "📊 v1→v2→v3 비교" },
  ];

  return (
    <div className="min-h-screen text-white p-4 md:p-6" style={{ background: "linear-gradient(145deg, #020617, #0f172a 50%, #020617)", fontFamily: "'Geist','Pretendard',-apple-system,sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');.mono{font-family:'Space Mono',monospace}.glow{text-shadow:0 0 20px rgba(14,165,233,0.5)}::-webkit-scrollbar{width:6px}::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}`}</style>

      <div className="text-center mb-5">
        <div className="mono text-xs tracking-widest mb-1" style={{ color: "#64748b" }}>ARCHITECTURE BLUEPRINT v3.0 — INDUSTRY-STANDARD AI DB MONITORING</div>
        <h1 className="text-xl md:text-2xl font-bold glow" style={{ color: "#0ea5e9" }}>AI-Powered Intelligent DB Monitoring System</h1>
        <p className="text-xs mt-1.5 max-w-3xl mx-auto" style={{ color: "#94a3b8" }}>
          Auto-Baselining · Full-Stack Observability · 1s Granularity · ASH & Wait Events · Schema Change Tracking · Auto Query Tuning · AIGC Interface · MCP · A2A · Self-Healing · Playbook-as-Code · RAG · Adaptive Autonomy
        </p>
      </div>

      <div className="flex gap-1 mb-5 justify-center flex-wrap">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className="px-4 py-1.5 rounded-full text-xs font-semibold transition-all" style={{ background: tab === t.id ? "#0ea5e9" : "transparent", color: tab === t.id ? "#fff" : "#64748b", border: tab === t.id ? "none" : "1px solid #334155" }}>{t.label}</button>
        ))}
      </div>

      {/* ── v3.0 Additions Tab ── */}
      {tab === "additions" && (
        <div className="max-w-5xl mx-auto">
          <div className="flex gap-1.5 mb-4 flex-wrap">
            {V3_ADDITIONS.map((f) => (
              <button key={f.id} onClick={() => setSelAdd(f.id)} className="flex items-center gap-1 px-2.5 py-1.5 rounded-full text-xs font-semibold transition-all" style={{ background: selAdd === f.id ? f.color + "22" : "transparent", color: selAdd === f.id ? f.color : "#64748b", border: `1px solid ${selAdd === f.id ? f.color + "66" : "#334155"}` }}>
                <span>{f.icon}</span>{f.tag}
              </button>
            ))}
          </div>
          {V3_ADDITIONS.filter((f) => f.id === selAdd).map((f) => (
            <div key={f.id} className="rounded-lg p-4" style={{ background: "rgba(30,41,59,0.7)", border: `1px solid ${f.color}44` }}>
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <span className="text-xl">{f.icon}</span>
                <span className="font-bold text-sm text-white">{f.title}</span>
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: f.color + "18", color: f.color }}>{f.tag}</span>
              </div>
              <div className="flex gap-3 mb-3 flex-wrap text-xs" style={{ color: "#94a3b8" }}>
                <span>📍 {f.layer}</span>
                <span>📚 참조: <span style={{ color: f.color }}>{f.ref}</span></span>
              </div>
              <div className="text-xs mb-4" style={{ color: "#cbd5e1" }}>{f.desc}</div>
              <div className="text-xs font-semibold text-white mb-2">⚙️ 구현 방식 (아키텍처 연결)</div>
              <div className="space-y-1.5">
                {f.how.map((h, i) => (
                  <div key={i} className="flex gap-2 text-xs" style={{ color: "#94a3b8" }}>
                    <span className="font-bold" style={{ color: f.color }}>{i + 1}.</span>{h}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Architecture Tab ── */}
      {tab === "arch" && (
        <div className="max-w-5xl mx-auto space-y-2">
          <div className="text-xs mb-3 flex gap-3 flex-wrap" style={{ color: "#64748b" }}>
            <span><Badge text="NEW" /> v3.0 신규</span>
            <span><Badge text="UP" /> v3.0 업그레이드</span>
            <span><Badge text="v2" /> v2.0 도입</span>
          </div>
          {LAYERS_V3.map((layer) => (
            <div key={layer.id} className="rounded-lg border overflow-hidden cursor-pointer transition-all duration-300" style={{ borderColor: layer.color + "40", background: expLayers.has(layer.id) ? layer.bgColor + "cc" : layer.bgColor + "88" }} onClick={() => setExpLayers((p) => { const n = new Set(p); n.has(layer.id) ? n.delete(layer.id) : n.add(layer.id); return n; })}>
              <div className="flex items-center justify-between px-4 py-2.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: layer.color }} />
                  <span className="font-bold text-white text-sm">{layer.title}</span>
                  <span className="text-xs" style={{ color: layer.color + "aa" }}>{layer.subtitle}</span>
                </div>
                <span className="text-white text-xs transition-transform duration-300" style={{ transform: expLayers.has(layer.id) ? "rotate(180deg)" : "" }}>▼</span>
              </div>
              {expLayers.has(layer.id) && (
                <div className="px-4 pb-3 grid gap-1.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
                  {layer.items.map((item, i) => (
                    <div key={i} className="rounded px-3 py-2" style={{ background: "rgba(0,0,0,0.35)" }}>
                      <div className="flex items-center">
                        <span className="text-xs font-semibold text-white">{item.name}</span>
                        {item.t && <Badge text={item.t} />}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>{item.desc}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {/* Data Flow */}
          <div className="rounded-lg p-4 mt-3" style={{ background: "rgba(30,41,59,0.6)", border: "1px solid #334155" }}>
            <div className="text-xs font-bold text-white mb-2">📐 통합 데이터 흐름 (v3.0)</div>
            <div className="text-xs leading-loose" style={{ color: "#94a3b8" }}>
              <span style={{ color: "#10b981" }}>Target DB</span> → <span style={{ color: "#f59e0b" }}>Adapter (1s 수집 + ASH + DDL Trigger)</span> → <span style={{ color: "#ef4444" }}>TimescaleDB (1s 메트릭 + Auto Downsample)</span> → <span style={{ color: "#f59e0b" }}>Monitoring Agent (AI 베이스라인 학습)</span> → 이상 탐지 → <span style={{ color: "#8b5cf6" }}>Diagnosis Agent (RAG + Topology RCA)</span> → <span style={{ color: "#10b981" }}>Remediation Agent (Playbook + Auto-Tuning)</span> → 검증/롤백 → <span style={{ color: "#0ea5e9" }}>Dashboard / Slack / MCP</span>
            </div>
            <div className="text-xs mt-2" style={{ color: "#94a3b8" }}>
              <span style={{ color: "#06b6d4" }}>OTel Collector</span>: 앱 트레이스 수신 → <span style={{ color: "#8b5cf6" }}>Topology Engine</span>이 서비스→DB 의존성 자동 발견 → 대시보드 토폴로지 맵에 실시간 반영
            </div>
          </div>
        </div>
      )}

      {/* ── Tool Map Tab ── */}
      {tab === "toolmap" && (
        <div className="max-w-5xl mx-auto">
          <div className="text-xs mb-4" style={{ color: "#64748b" }}>업계 주요 솔루션의 핵심 기능이 우리 아키텍처의 어느 모듈에 적용되었는지 매핑합니다.</div>
          <div className="space-y-2">
            {TOOL_MAP.map((t, i) => (
              <div key={i} className="rounded-lg px-4 py-3 flex flex-col md:flex-row md:items-center gap-2" style={{ background: "rgba(30,41,59,0.6)", border: "1px solid #334155" }}>
                <div className="min-w-[180px]">
                  <div className="text-xs font-bold text-white">{t.tool}</div>
                </div>
                <div className="flex gap-1.5 flex-wrap min-w-[240px]">
                  {t.features.map((f, j) => (
                    <span key={j} className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(100,116,139,0.2)", color: "#94a3b8" }}>{f}</span>
                  ))}
                </div>
                <div className="text-xs" style={{ color: "#0ea5e9" }}>→ {t.applied}</div>
              </div>
            ))}
          </div>
          <div className="rounded-lg p-4 mt-4" style={{ background: "rgba(30,41,59,0.6)", border: "1px solid #06b6d444" }}>
            <div className="text-xs font-bold text-white mb-2">💡 차별화 전략</div>
            <div className="text-xs space-y-1" style={{ color: "#94a3b8" }}>
              <p>• <strong style={{ color: "#fff" }}>오픈 프로토콜 중심</strong>: MCP + A2A 표준 기반 → 특정 벤더 종속 없이 모든 AI 도구/에이전트와 연동</p>
              <p>• <strong style={{ color: "#fff" }}>온/오프라인 AI</strong>: 클라우드 LLM과 로컬 LLM(Ollama/vLLM) 모두 지원 → 보안 환경에서도 AI 기능 활용</p>
              <p>• <strong style={{ color: "#fff" }}>멀티 DB 플러그인</strong>: Adapter SPI로 PostgreSQL/MySQL/MS-SQL + 커스텀 DB 확장</p>
              <p>• <strong style={{ color: "#fff" }}>Closed-Loop Self-Healing</strong>: 감지→진단→대응→검증→학습의 완전한 자동화 + 5단계 Autonomy</p>
              <p>• <strong style={{ color: "#fff" }}>지식 자동 축적</strong>: RAG + Playbook 피드백으로 시스템이 운영될수록 더 똑똑해지는 구조</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Compare Tab ── */}
      {tab === "compare" && (
        <div className="max-w-5xl mx-auto">
          <div className="text-xs mb-4" style={{ color: "#64748b" }}>v1.0 → v2.0 → v3.0 진화 과정</div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs" style={{ borderCollapse: "separate", borderSpacing: "0 3px" }}>
              <thead>
                <tr>
                  {["영역", "v1.0 기본", "v2.0 트렌드", "v3.0 산업 표준"].map((h, i) => (
                    <th key={i} className={`text-left px-3 py-2 ${i === 0 ? "rounded-l-lg" : ""} ${i === 3 ? "rounded-r-lg" : ""}`}
                      style={{ background: "#1e293b", color: i === 3 ? "#10b981" : i === 2 ? "#f59e0b" : "#64748b" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  ["이상 탐지", "수동 임계값", "AI + 규칙 병행", "AI 자동 베이스라인 학습 (수동 임계값 불필요)"],
                  ["관측 범위", "DB 단독", "DB + 인프라", "풀스택 (App→Middleware→DB→Infra) 토폴로지 자동 발견"],
                  ["메트릭 해상도", "10초~5분", "10초~5분", "1초 고해상도 (Hot/Warm/Cold 계층형 보관)"],
                  ["세션 분석", "기본 활성 세션", "세션 목록 조회", "ASH 1초 샘플링 + Wait Event 카테고리별 분석"],
                  ["스키마 변경", "로그 저장만", "감사 로그", "DDL 실시간 감지 + Before/After 성능 영향도 자동 분석"],
                  ["쿼리 튜닝", "Slow Query 목록", "AI 인덱스 추천", "AI 자동 적용 (인덱스 생성/쿼리 리라이트/파라미터 튜닝)"],
                  ["사용자 질의", "대시보드 UI", "NL2SQL 자연어 질의", "AIGC 전면 통합 (NL2SQL + SQL 최적화 + 실행계획 해석 + 리포트 생성)"],
                  ["AI 구조", "단일 Engine", "Multi-Agent (A2A)", "Multi-Agent + Topology Engine + Auto-Baseliner"],
                  ["외부 연동", "REST API", "MCP + A2A", "MCP + A2A + OTel Collector (풀스택 트레이스 수신)"],
                  ["대응 자동화", "Auto/Manual/Queue", "5단계 Autonomy + Playbook + Self-Healing", "+ Auto Query Tuning + Schema Rollback 추천"],
                  ["참조 모델", "—", "Xata, Percona PMM", "Oracle, Dynatrace, Instana, Datadog, DBmarlin, Chat2DB"],
                ].map(([area, v1, v2, v3], i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 rounded-l-lg font-semibold text-white" style={{ background: "rgba(30,41,59,0.6)" }}>{area}</td>
                    <td className="px-3 py-2" style={{ background: "rgba(30,41,59,0.3)", color: "#64748b" }}>{v1}</td>
                    <td className="px-3 py-2" style={{ background: "rgba(30,41,59,0.4)", color: "#94a3b8" }}>{v2}</td>
                    <td className="px-3 py-2 rounded-r-lg" style={{ background: "rgba(16,185,129,0.08)", color: "#6ee7b7" }}>{v3}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="text-center mt-8 mono text-xs" style={{ color: "#334155" }}>
        AI DB Monitoring System · Architecture v3.0 · Industry-Standard Features Applied · 2026
      </div>
    </div>
  );
}
