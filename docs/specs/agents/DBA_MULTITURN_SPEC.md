# Feature Spec: DBA Agent Multi-Turn 대화 (Valkey Memory)

## 메타데이터
- **Spec ID**: FS-DBA-004
- **PRD 참조**: FR-AI-012, FS-DBA-002
- **우선순위**: P0 (MVP)
- **상태**: Approved
- **선행 Spec**: FS-DBA-002 (DBA Orchestrator), AC-17/18 (세션 컨텍스트)

---

## 1. 개요

DBA Agent가 Multi-Turn 대화를 통해 사용자의 의도를 점진적으로 파악하고, 이전 턴의 **분석 결과, SQL 결과, 식별된 테이블/인덱스** 등을 기억하여 연속적인 DBA 작업을 수행합니다.

### 현재 한계 → 개선

| 항목 | 현재 (AC-17/18) | 개선 (FS-DBA-004) |
|------|----------------|-------------------|
| 답변 저장 | 200자 truncate | **전문 저장** (최대 2000자) |
| 데이터 저장 | 미저장 | **도구 결과 캐싱** (SQL결과, 메트릭, ASH 등) |
| 턴 수 | 5턴 고정 | **10턴** + 중요도 기반 압축 |
| TTL | 30분 고정 | **1시간** (활동 시 자동 갱신) |
| 컨텍스트 활용 | 단순 텍스트 연결 | **구조화된 Memory** (entities + facts) |
| intent 분류 | 이전 턴 미참조 | **이전 intent 흐름으로 모호성 해소** |

---

## 2. Valkey Memory 구조

### 2.1 세션 데이터 (Key: `dba:session:{session_id}`)

```json
{
  "instance_id": "uuid",
  "instance_name": "pg-prod-01",
  "created_at": "2026-04-01T10:00:00Z",
  "last_active_at": "2026-04-01T10:15:00Z",
  "turns": [
    {
      "role": "user",
      "content": "orders 테이블이 느려",
      "timestamp": "2026-04-01T10:00:00Z"
    },
    {
      "role": "agent",
      "content": "orders 테이블 분석 결과...(전문)",
      "intent": "analyze",
      "timestamp": "2026-04-01T10:00:05Z",
      "data_keys": ["dba:data:{session_id}:turn_1"]
    },
    {
      "role": "user",
      "content": "인덱스 만들어줘",
      "timestamp": "2026-04-01T10:01:00Z"
    },
    {
      "role": "agent",
      "content": "CREATE INDEX idx_orders_user_id...",
      "intent": "execute",
      "timestamp": "2026-04-01T10:01:03Z"
    }
  ],
  "entities": {
    "tables": ["orders", "users"],
    "indexes": ["idx_orders_user_id"],
    "metrics": ["cpu_usage", "active_connections"],
    "last_sql": "SELECT * FROM orders WHERE..."
  }
}
```

**TTL**: 1시간 (매 턴마다 갱신)

### 2.2 턴별 데이터 캐시 (Key: `dba:data:{session_id}:turn_{n}`)

큰 데이터(SQL 결과셋, 메트릭 스냅샷)는 별도 키에 저장:

```json
{
  "type": "query_result",
  "sql": "SELECT * FROM orders WHERE...",
  "columns": ["id", "user_id", "total"],
  "rows": [[1, 100, 5000], ...],
  "row_count": 125
}
```

**TTL**: 30분 (세션보다 짧음 — 큰 데이터는 빨리 만료)

### 2.3 Entity 추출

각 턴에서 자동 추출하는 엔티티:
- **테이블명**: SQL/답변에서 정규식으로 추출
- **인덱스명**: CREATE INDEX 결과에서 추출
- **메트릭 키워드**: cpu, connection, tps, buffer 등
- **최근 SQL**: 마지막 실행/생성된 SQL

---

## 3. Multi-Turn 흐름

### 3.1 대화 예시

```
Turn 1: "DB 느려"
  → intent: analyze (context: 없음)
  → Agent: orders 테이블 풀스캔 감지, CPU 85%
  → Memory: entities.tables=["orders"], entities.metrics=["cpu_usage"]

Turn 2: "그 테이블 인덱스 뭐가 있어?"
  → intent: query (context: "그 테이블" → entities.tables[-1] → "orders")
  → Agent: orders 테이블 인덱스 3개 (pk_orders, idx_orders_created_at, ...)
  → Memory: entities.indexes 업데이트

Turn 3: "user_id로 인덱스 만들어줘"
  → intent: execute (context: orders 테이블, user_id 컬럼)
  → Agent: CREATE INDEX idx_orders_user_id ON orders(user_id)
  → Memory: entities.indexes += ["idx_orders_user_id"]

Turn 4: "효과 있어?"
  → intent: analyze (context: 방금 생성한 인덱스 효과 확인)
  → Agent: 인덱스 생성 후 Seq Scan → Index Scan 전환, 응답시간 2340ms → 45ms
```

### 3.2 컨텍스트 참조 해소

| 사용자 표현 | 해소 방법 | 참조 |
|-----------|----------|------|
| "그 테이블" / "아까 그거" | `entities.tables[-1]` | 마지막 언급 테이블 |
| "인덱스 만들어줘" (테이블 미명시) | `entities.tables[-1]` | 이전 턴 테이블 |
| "효과 있어?" | 이전 턴 intent=execute → before/after 비교 | 이전 액션 결과 |
| "다른 쿼리는?" | `entities.last_sql` 참조 | 이전 SQL 결과 |

---

## 4. 구현 변경사항

### 4.1 `_save_session` 개선

```python
async def _save_session(session_id, question, answer, intent, data=None, instance_id=None):
    session_data = await _load_raw_session(session_id)
    
    # Add turn with full answer (2000자)
    turn = {
        "role": "agent",
        "content": answer[:2000],
        "intent": intent,
        "timestamp": now_iso(),
    }
    
    # Cache large data separately
    if data and len(json.dumps(data)) > 500:
        data_key = f"dba:data:{session_id}:turn_{len(session_data['turns'])}"
        await valkey.setex(data_key, 1800, json.dumps(data))
        turn["data_keys"] = [data_key]
    
    session_data["turns"].append(turn)
    session_data["turns"] = session_data["turns"][-20:]  # max 10 turns (20 entries)
    
    # Extract entities
    _extract_entities(session_data, question, answer, data)
    
    # Update TTL to 1 hour
    await valkey.setex(key, 3600, json.dumps(session_data))
```

### 4.2 `_build_contextual_question` 개선

```python
def _build_contextual_question(self, question):
    if not self._session_data:
        return question
    
    entities = self._session_data.get("entities", {})
    recent_turns = self._session_data.get("turns", [])[-6:]  # last 3 turns
    
    context_parts = []
    
    # Entity context
    if entities.get("tables"):
        context_parts.append(f"관련 테이블: {', '.join(entities['tables'][-3:])}")
    if entities.get("last_sql"):
        context_parts.append(f"최근 SQL: {entities['last_sql'][:200]}")
    
    # Conversation history
    for turn in recent_turns:
        role = "사용자" if turn["role"] == "user" else "Agent"
        context_parts.append(f"{role}: {turn['content'][:300]}")
    
    return f"[대화 컨텍스트]\n" + "\n".join(context_parts) + f"\n\n[현재 질문]\n{question}"
```

### 4.3 Intent 분류 개선

이전 intent 흐름으로 모호한 질문 해소:
```python
# "만들어줘" → 이전 턴이 analyze(테이블 분석) → execute (인덱스 생성)
# "확인해봐" → 이전 턴이 execute → analyze (효과 확인)
prev_intent = session_data["turns"][-1]["intent"] if turns else None
if prev_intent == "analyze" and ambiguous:
    intent = "execute"  # 분석 후 → 실행 유도
elif prev_intent == "execute" and ambiguous:
    intent = "analyze"  # 실행 후 → 효과 확인
```

---

## 5. 인수 기준

- [ ] **AC-1**: 세션 데이터에 답변 전문 저장 (최대 2000자, 기존 200자 → 확대)
- [ ] **AC-2**: 도구 결과(SQL 결과, 메트릭)가 별도 Valkey 키에 캐싱 (TTL 30분)
- [ ] **AC-3**: Entity 자동 추출 — 테이블명, 인덱스명이 `entities` 필드에 저장
- [ ] **AC-4**: 이전 턴의 entities를 참조하여 "그 테이블" 등 대명사 해소
- [ ] **AC-5**: 이전 intent 흐름 기반 모호한 질문의 intent 자동 추론
- [ ] **AC-6**: 세션 TTL 1시간 + 매 턴마다 TTL 갱신 (활동 유지)
- [ ] **AC-7**: LLM 프롬프트에 구조화된 대화 히스토리 (entities + recent turns) 주입
- [ ] **AC-8**: 10턴(20 entries) 초과 시 오래된 턴 자동 제거 (FIFO)

---

## 6. 의존성

- **선행**: FS-DBA-002 (AC-17/18 세션 컨텍스트)
- **인프라**: Valkey (메모리 사용량 ~50KB/세션)
