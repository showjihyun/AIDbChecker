# Feature Spec: ReAct Trace — AI 추론 과정 실시간 표시

## 메타데이터
- **Spec ID**: FS-AI-TRACE-001
- **PRD 참조**: FR-AI-011 (Explainable AI)
- **우선순위**: P1 (Phase 2+)
- **상태**: Approved
- **선행 Spec**: FS-AI-011 (Confidence Score), FS-AI-010 (MTL RCA)

---

## 1. 개요

AI 에이전트(MTL RCA, DB Copilot, NL2SQL, AIGC Report)가 작업할 때
**ReAct(Reasoning + Acting) 스타일**로 추론 과정을 단계별로 기록하고,
프론트엔드에서 **접혀있는 패널**로 표시합니다.

```
[AI 분석 중...] ▶ 클릭하면 펼침

   💭 Thought: CPU 92% 급증, 베이스라인(40~60%) 대비 이탈
   🔍 Action: RAG 유사 인시던트 검색 (Top-3)
   📊 Observation: 유사 사례 3건 발견 (similarity: 0.89, 0.85, 0.72)
   💭 Thought: 과거 사례 모두 Missing Index가 원인
   🔍 Action: pg_stat_statements Top 5 Slow Query 분석
   📊 Observation: SELECT * FROM orders WHERE created_at > ... (Seq Scan, 12.8s)
   💭 Thought: orders.created_at 인덱스 없음 → 근본 원인 확정
   ✅ Result: anomaly_type=query_performance, confidence=0.87
```

---

## 2. 데이터 모델

```python
class TraceStep(BaseModel):
    step_type: str   # "thought" | "action" | "observation" | "result" | "error"
    content: str     # 표시할 텍스트
    timestamp_ms: int  # 시작 이후 경과 시간 (ms)
    metadata: dict | None = None  # 추가 데이터 (query, scores 등)

class ReActTrace(BaseModel):
    agent: str       # "mtl_rca" | "copilot" | "nl2sql" | "report"
    steps: list[TraceStep]
    total_duration_ms: int
    status: str      # "running" | "completed" | "failed"
```

---

## 3. 인수 기준

- [ ] **AC-1**: AI 응답에 `trace: ReActTrace` 필드 포함
- [ ] **AC-2**: trace.steps에 최소 3단계 (thought → action → result) 포함
- [ ] **AC-3**: FE에서 기본 접힌 상태, 클릭 시 펼침
- [ ] **AC-4**: 각 step_type별 아이콘/색상 구분
- [ ] **AC-5**: total_duration_ms로 전체 소요 시간 표시
