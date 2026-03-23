# NeuralDB Glossary — 도메인 용어 ↔ 코드 매핑

> PRD 1.2 용어 정의를 확장하여, 코드에서 사용되는 구체적 이름과 매핑합니다.
> AI 하네스가 변수명/클래스명/테이블명을 생성할 때 이 문서를 참조합니다.

---

## A

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **A2A** | Agent-to-Agent Protocol | `app.a2a.gateway`, `A2AMessage` dataclass |
| **Active Session** | pg_stat_activity에서 샘플링한 활성 세션 | `active_sessions` 테이블, `ActiveSession` model |
| **Adaptive Autonomy** | 5단계 자율 등급 시스템 (0~4) | `autonomy_level` 필드, `AutonomyLevel` enum |
| **AIGC** | AI Generated Content | Reporting Agent 역할 |
| **Anomaly** | AI 베이스라인 대비 이상 감지된 메트릭 | `incidents` 테이블 (source=`ai_baseline`) |
| **ASH** | Active Session History | `active_sessions` 테이블, `/api/v1/instances/{id}/ash` |
| **Auto-Baselining** | AI가 정상 패턴을 자동 학습 | `baselines` 테이블, `BaselineLearner` agent |

## B

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Baseline** | 학습된 정상 메트릭 범위 | `baselines` 테이블, `normal_min`/`normal_max` |
| **Blast Radius** | 자동 액션의 영향 범위 | `RemediationAction.blast_radius` 속성 |

## C

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Causal Chain** | RCA에서 도출된 인과 관계 경로 | `rca_results.causal_chain` JSONB |
| **Cluster** | DB 인스턴스들의 논리적 그룹 | `db_instances.cluster_id` |
| **Cold Metric** | 1분 간격 수집 메트릭 (백업, 인증서 등) | `metric_samples` (category=`cold`) |
| **Confidence** | AI RCA 결과의 신뢰도 (0.0~1.0) | `rca_results.confidence` |

## D

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **DDL Event** | CREATE/ALTER/DROP 등 스키마 변경 이벤트 | `schema_changes` 테이블 |
| **Diagnosis** | AI 근본 원인 분석 과정 | `agent-diagnosis`, `DiagnosisAgent` |
| **Downsample** | 고해상도 → 저해상도 메트릭 집계 | Materialized View (`mv_metrics_10s` 등) |

## H

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Harness** | AI 코드 생성 도구 (Claude Code) | CLAUDE.md, Skills |
| **Hot Metric** | 1초 간격 수집 메트릭 (CPU, 커넥션 등) | `metric_samples` (category=`hot`) |

## I

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Incident** | 탐지된 이상/장애 이벤트 | `incidents` 테이블, `Incident` model |
| **Instance** | 모니터링 대상 DB 인스턴스 | `db_instances` 테이블, `DBInstance` model |
| **Isolation Forest** | 이상 탐지 ML 알고리즘 | `sklearn.ensemble.IsolationForest` |

## M

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **MCP** | Model Context Protocol | `app.mcp.server`, MCP SDK |
| **Metric Sample** | 특정 시점의 메트릭 스냅샷 | `metric_samples` 테이블 |

## N

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **NL2SQL** | Natural Language to SQL | `agent-reporting`, `/api/v1/nl2sql/query` |
| **Node** | 토폴로지 맵의 구성 요소 | `topology_nodes` 테이블 |

## P

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Playbook** | YAML로 정의된 장애 대응 절차 | `playbooks` 테이블, `backend/playbooks/*.yaml` |
| **pg_partman** | PostgreSQL 파티션 관리 확장 | TimescaleDB 대체, 시계열 테이블에 사용 |

## R

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **RAG** | Retrieval-Augmented Generation | `app.rag.*`, `rag_documents` 테이블 (pgvector) |
| **RCA** | Root Cause Analysis | `rca_results` 테이블, `DiagnosisAgent.llm_rca()` |
| **Remediation** | 자동/수동 장애 대응 실행 | `remediation_logs` 테이블, `agent-remediation` |

## S

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Self-Healing** | 감지→진단→대응→검증→롤백 자동 파이프라인 | 4개 Agent 협업 체인 |
| **SLO Check** | 대응 후 서비스 수준 목표 달성 여부 검증 | `remediation_logs.slo_check` JSONB |
| **Spec** | Specification 문서 | `docs/specs/` 디렉토리 |
| **STL** | Seasonal-Trend Decomposition (시계열 분해) | `statsmodels.tsa.seasonal.STL` |

## T

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Topology** | App→DB→Infra 의존성 그래프 | `topology_nodes` + `topology_edges` 테이블 |

## W

| 용어 | 정의 | 코드 매핑 |
|------|------|----------|
| **Wait Event** | 세션이 대기 중인 이벤트 유형 | `active_sessions.wait_event_type` / `.wait_event` |
| **Warm Metric** | 10초 간격 수집 메트릭 (디스크, WAL 등) | `metric_samples` (category=`warm`) |
