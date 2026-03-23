# GraphQL Schema Spec: Strawberry Code-First

> **Spec ID**: API-GQL-001
> **PRD 참조**: FR-DASH-001~005
> **상태**: Approved
> **적용 Phase**: Phase 2
> **Framework**: Strawberry (MIT, Python Code-First)

---

## 1. Overview

GraphQL은 대시보드의 **복합 조회**(여러 엔티티 동시 fetch)에 사용합니다.
MVP(Phase 1)는 REST API만 사용하고, Phase 2에서 GraphQL을 추가합니다.

**Endpoint**: `POST /graphql`
**Auth**: `Authorization: Bearer <JWT>` (REST과 동일)

---

## 2. Enums

```graphql
enum DBType {
  POSTGRESQL
  MYSQL
  MSSQL
}

enum Environment {
  PRODUCTION
  STAGING
  DEVELOPMENT
}

enum Severity {
  CRITICAL
  WARNING
  NOTICE
  INFO
}

enum IncidentStatus {
  OPEN
  ACKNOWLEDGED
  IN_PROGRESS
  RESOLVED
  CLOSED
}

enum IncidentSource {
  AI_BASELINE
  THRESHOLD
  MANUAL
  SCHEMA_CHANGE
}

enum AutonomyLevel {
  L0_ALERT_ONLY
  L1_SUGGEST
  L2_APPROVED
  L3_AUTO
  L4_FULL_AUTONOMOUS
}

enum MetricCategory {
  HOT
  WARM
  COLD
}

enum RemediationStatus {
  PENDING
  RUNNING
  SUCCESS
  FAILED
  ROLLED_BACK
}

enum HealthStatus {
  HEALTHY
  DEGRADED
  DOWN
  UNKNOWN
}

enum WaitEventType {
  CPU
  LWLOCK
  LOCK
  BUFFER_PIN
  IO
  IPC
  NETWORK
  TIMEOUT
  EXTENSION
  CLIENT
  ACTIVITY
}
```

---

## 3. Types

```graphql
type DBInstance {
  id: UUID!
  name: String!
  dbType: DBType!
  host: String!
  port: Int!
  databaseName: String!
  clusterId: String
  environment: Environment!
  isActive: Boolean!
  autonomyLevel: Int!
  healthStatus: HealthStatus!
  metadata: JSON
  createdAt: DateTime!
  updatedAt: DateTime!

  # Nested resolvers
  latestMetrics: MetricSnapshot
  activeIncidents(limit: Int = 5): [Incident!]!
  baselines: [Baseline!]!
}

type MetricSnapshot {
  instanceId: UUID!
  sampledAt: DateTime!
  category: MetricCategory!
  cpuUsage: Float
  memoryUsage: Float
  activeConnections: Int
  tps: Float
  bufferHitRatio: Float
  replicationLagMs: Float
}

type MetricSample {
  instanceId: UUID!
  sampledAt: DateTime!
  category: MetricCategory!
  metrics: JSON!
}

type ActiveSession {
  instanceId: UUID!
  sampledAt: DateTime!
  pid: Int!
  query: String
  state: String!
  waitEventType: WaitEventType
  waitEvent: String
  clientAddr: String
  applicationName: String
  durationMs: Float
}

type Incident {
  id: UUID!
  instance: DBInstance!
  severity: Severity!
  status: IncidentStatus!
  title: String!
  description: String
  source: IncidentSource!
  metricType: String
  metricValue: Float
  baselineValue: Float
  detectedAt: DateTime!
  resolvedAt: DateTime
  createdAt: DateTime!

  # Nested
  rca: RCAResult
  remediationLogs: [RemediationLog!]!
}

type RCAResult {
  id: UUID!
  incidentId: UUID!
  rootCause: String!
  confidence: Float!
  causalChain: [CausalNode!]!
  recommendations: [String!]!
  aiModel: String!
  similarIncidents: [IncidentSummary!]!
  createdAt: DateTime!
}

type CausalNode {
  node: String!
  type: String!
  description: String!
}

type IncidentSummary {
  id: UUID!
  title: String!
  severity: Severity!
  detectedAt: DateTime!
  similarity: Float!
}

type TopologyGraph {
  nodes: [TopologyNode!]!
  edges: [TopologyEdge!]!
}

type TopologyNode {
  id: UUID!
  name: String!
  nodeType: String!
  healthStatus: HealthStatus!
  metadata: JSON
  instance: DBInstance
}

type TopologyEdge {
  id: UUID!
  sourceId: UUID!
  targetId: UUID!
  edgeType: String!
  avgLatencyMs: Float
  status: String!
}

type Baseline {
  id: UUID!
  instanceId: UUID!
  metricType: String!
  timeBucket: String!
  normalMin: Float!
  normalMax: Float!
  mean: Float!
  stddev: Float!
  modelType: String!
  lastTrainedAt: DateTime!
}

type Playbook {
  id: UUID!
  name: String!
  version: String!
  description: String
  triggerType: String!
  minAutonomyLevel: Int!
  riskLevel: String!
  successRate: Float!
  executionCount: Int!
  yamlContent: String!
  tags: [String!]!
}

type RemediationLog {
  id: UUID!
  playbook: Playbook!
  incident: Incident
  instance: DBInstance!
  autonomyLevel: Int!
  status: RemediationStatus!
  actions: JSON!
  startedAt: DateTime!
  completedAt: DateTime
  executedBy: String!
}

type SchemaChange {
  id: UUID!
  instanceId: UUID!
  changeType: String!
  objectType: String!
  objectName: String!
  ddlCommand: String
  executedBy: String
  detectedAt: DateTime!
  impactAnalysis: JSON
}

type AuditLog {
  id: UUID!
  userId: UUID
  action: String!
  resourceType: String!
  resourceId: UUID
  details: JSON!
  ipAddress: String
  createdAt: DateTime!
}

type SystemHealth {
  status: HealthStatus!
  uptimeSeconds: Int!
  version: String!
  components: SystemComponents!
}

type SystemComponents {
  database: ComponentHealth!
  valkey: ComponentHealth!
  kafka: ComponentHealth!
  celery: ComponentHealth!
}

type ComponentHealth {
  status: HealthStatus!
  latencyMs: Float
  details: JSON
}
```

---

## 4. Queries

```graphql
type Query {
  # Instances
  instances(
    filter: InstanceFilter
    limit: Int = 20
    cursor: String
  ): InstanceConnection!
  instance(id: UUID!): DBInstance

  # Metrics
  metrics(
    instanceId: UUID!
    from: DateTime!
    to: DateTime!
    category: MetricCategory
    resolution: String = "auto"
  ): [MetricSample!]!

  # ASH
  ashSessions(
    instanceId: UUID!
    from: DateTime!
    to: DateTime!
    state: String
  ): [ActiveSession!]!
  ashHeatmap(
    instanceId: UUID!
    from: DateTime!
    to: DateTime!
  ): JSON!

  # Incidents
  incidents(
    status: IncidentStatus
    severity: Severity
    limit: Int = 20
    cursor: String
  ): IncidentConnection!
  incident(id: UUID!): Incident

  # Topology
  topology(clusterId: String): TopologyGraph!

  # Playbooks
  playbooks(triggerType: String, isActive: Boolean = true): [Playbook!]!
  playbook(id: UUID!): Playbook

  # System
  systemHealth: SystemHealth!

  # Audit
  auditLogs(
    resourceType: String
    resourceId: UUID
    limit: Int = 50
    cursor: String
  ): AuditLogConnection!
}

input InstanceFilter {
  dbType: DBType
  environment: Environment
  isActive: Boolean
  clusterId: String
  search: String
}
```

---

## 5. Mutations

```graphql
type Mutation {
  # Instances
  createInstance(input: CreateInstanceInput!): DBInstance!
  updateInstance(id: UUID!, input: UpdateInstanceInput!): DBInstance!
  deleteInstance(id: UUID!): Boolean!
  updateAutonomyLevel(id: UUID!, level: Int!): DBInstance!

  # Incidents
  acknowledgeIncident(id: UUID!): Incident!
  resolveIncident(id: UUID!): Incident!
  triggerDiagnosis(incidentId: UUID!): RCAResult!

  # Playbooks
  createPlaybook(input: CreatePlaybookInput!): Playbook!
  executePlaybook(playbookId: UUID!, instanceId: UUID!, dryRun: Boolean = true): RemediationLog!

  # Baselines
  retrainBaseline(instanceId: UUID!, metricType: String): Baseline!

  # NL2SQL
  nl2sqlQuery(question: String!, instanceId: UUID!, execute: Boolean = true): NL2SQLResult!
}

input CreateInstanceInput {
  name: String!
  dbType: DBType!
  host: String!
  port: Int! = 5432
  databaseName: String!
  clusterId: String
  environment: Environment!
  connectionConfig: JSON!
}

input UpdateInstanceInput {
  name: String
  host: String
  port: Int
  environment: Environment
  isActive: Boolean
  connectionConfig: JSON
}

input CreatePlaybookInput {
  name: String!
  description: String
  yamlContent: String!
  targetDbTypes: [DBType!]!
  minAutonomyLevel: Int! = 2
}

type NL2SQLResult {
  naturalQuery: String!
  generatedSql: String!
  result: JSON
  aiModel: String!
}
```

---

## 6. Subscriptions (WebSocket)

```graphql
type Subscription {
  # 실시간 메트릭 (1초 간격)
  metricUpdated(instanceId: UUID!): MetricSnapshot!

  # 인시던트 실시간
  incidentCreated: Incident!
  incidentUpdated(id: UUID): Incident!

  # Remediation 진행
  remediationProgress(logId: UUID!): RemediationLog!

  # System Health 변경
  systemHealthChanged: SystemHealth!
}
```

---

## 7. Pagination (Connection Pattern)

```graphql
type InstanceConnection {
  items: [DBInstance!]!
  total: Int!
  hasNext: Boolean!
  nextCursor: String
}

type IncidentConnection {
  items: [Incident!]!
  total: Int!
  hasNext: Boolean!
  nextCursor: String
}

type AuditLogConnection {
  items: [AuditLog!]!
  total: Int!
  hasNext: Boolean!
  nextCursor: String
}
```

---

## 8. Scalar Types

```graphql
scalar UUID
scalar DateTime
scalar JSON
```

Strawberry 구현:
```python
import strawberry
from uuid import UUID
from datetime import datetime

# UUID, datetime은 Strawberry 내장 지원
# JSON은 strawberry.scalars.JSON 사용
```

---

## v3.3 신규 타입 (MTL / Confidence / Copilot)

```graphql
# Spec: FR-AI-010, FR-AI-011
type MTLPrediction {
  id: UUID!
  incidentId: UUID!
  anomalyType: AnomalyType!
  anomalyConfidence: Float!
  rootCause: String!
  rootCauseDetail: JSON
  severity: SeverityLevel!
  severityScore: Float!
  suggestedActions: [SuggestedAction!]!
  confidence: Float!
  reasoningChain: [String!]!
  evidenceLinks: [String!]!
  modelVersion: String!
  inferenceTimeMs: Int!
  feedbackCorrect: Boolean
  createdAt: DateTime!
}

enum AnomalyType {
  QUERY_PERFORMANCE_DEGRADATION
  RESOURCE_EXHAUSTION
  LOCK_CONTENTION
  REPLICATION_LAG
  CONNECTION_SATURATION
  VACUUM_BLOAT
  SCHEMA_REGRESSION
  SECURITY_ANOMALY
  UNKNOWN
}

type SuggestedAction {
  action: String!
  description: String!
  confidence: Float!
  risk: ActionRisk!
}

enum ActionRisk { LOW MEDIUM HIGH CRITICAL }

# Spec: FR-AI-013
type LLMObservabilitySummary {
  period: String!
  totalCalls: Int!
  totalTokens: Int!
  avgLatencyMs: Float!
  p95LatencyMs: Float!
  accuracyRate: Float
  hallucinationRate: Float!
  estimatedCostUsd: Float!
  modelBreakdown: [ModelUsage!]!
}

type ModelUsage {
  model: String!
  calls: Int!
  tokens: Int!
  avgLatencyMs: Float!
  costUsd: Float!
}
```
