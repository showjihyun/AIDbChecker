# AI Diagnosis & RCA: User Flow & Use Case Specification

**문서 번호:** UC-DIAG-001
**상태:** Draft v1.0
**관련 화면:** {{DATA:SCREEN:SCREEN_13}} (AI Diagnosis & RCA Panel)

---

## 1. Use Case 개요 (Overview)

본 Use Case는 데이터베이스 성능 저하나 장애가 발생했을 때, AI 에이전트가 어떻게 근본 원인을 분석(RCA)하고 운영자에게 대응 방안을 제시하는지에 대한 지능형 진단 프로세스를 정의합니다.

### 1.1 기본 정보
- **Actor:** DB 운영자(DBA), SRE 엔지니어, AI Diagnosis Agent
- **Pre-condition:** DB 모니터링 에이전트가 활성화되어 있으며, AI 자동 베이스라인 학습이 완료된 상태.
- **Goal:** 장애의 근본 원인을 정확히 파악하고, 최적의 복구 절차(Playbook)를 실행하여 MTTR(평균 복구 시간)을 최소화함.

---

## 2. User Flow (작업 흐름)

AI와 운영자가 협업하는 **Closed-Loop 진단 흐름**입니다.

### [Step 1] 이상 징후 감지 (Anomaly Detection)
- **AI Monitoring Agent**가 실시간 메트릭(1s ASH)과 동적 베이스라인을 비교.
- 평소 패턴을 벗어나는 'Response Time Spike' 또는 'Lock Contention' 감지.
- **Action:** 대시보드 및 Slack에 'Critical Alert' 발송 및 진단 에이전트 호출.

### [Step 2] 근본 원인 분석 (RCA Execution)
- **AI Diagnosis Agent**가 활성화된 세션, 실행 중인 쿼리, 최근의 스키마 변경 이력을 전수 조사.
- **Causal Inference(인과 추론):** "15분 전 `dev_ops_bot`에 의해 추가된 컬럼이 특정 쿼리의 Full Table Scan을 유발함"과 같은 인과관계를 식별.
- **Action:** RCA 패널에 진단 결과 및 신뢰도(Confidence Score) 표시.

### [Step 3] 지식 베이스 참조 (RAG Reference)
- **RAG Engine**이 과거 유사 장애 이력(`pgvector` 저장소) 및 내부 운영 가이드를 검색.
- **Action:** "유사 장애 #421 사례와 92% 일치"와 같은 참조 데이터를 제시하여 진단 근거 강화.

### [Step 4] 대응 방안 제안 (Remediation Strategy)
- 진단 결과를 바탕으로 최적의 **Playbook-as-Code** 추천.
- **Action:** 인덱스 생성, 쿼리 리라이트, 혹은 파라미터 튜닝 등의 구체적인 SQL 및 액션 제시.

### [Step 5] 검증 및 실행 (Validation & Execution)
- 운영자가 **NL2SQL Assistant**를 통해 추가 질문 (예: "이 락에 걸려 있는 다른 쿼리는 뭐야?")을 던져 상세 분석 수행.
- 최종적으로 'Generate Playbook' 또는 'Auto-Remediation' 실행.

---

## 3. 핵심 시나리오 (Key Scenarios)

### Scenario A: 스키마 변경으로 인한 성능 저하
1. **사건:** 운영자가 인덱스 없이 대량의 데이터가 있는 테이블에 컬럼을 추가함.
2. **진단:** AI가 DDL 로그와 쿼리 지연 시간의 상관관계를 분석.
3. **해결:** 해당 컬럼을 사용하는 쿼리에 최적화된 인덱스 생성을 Playbook으로 제안.

### Scenario B: 특정 쿼리의 급격한 유입 (Micro-burst)
1. **사건:** 이벤트 오픈으로 인해 특정 API 호출이 급증하며 CPU Spike 발생.
2. **진단:** ASH 분석을 통해 특정 SQL Hash가 CPU의 80%를 점유함을 식별.
3. **해결:** 해당 세션의 강제 종료(Kill) 또는 어플리케이션 레이어의 Rate Limit 조정 가이드 제시.

---

## 4. 진단 정책 (Diagnosis Policy)

- **신뢰도 임계치:** RCA 신뢰도가 90% 이상일 때만 자동 실행 옵션(L3 Autonomy) 활성화.
- **보안 가이드:** 모든 진단 로그는 마스킹 처리되어 보관되며, 실행 권한은 RBAC 정책에 따름.
