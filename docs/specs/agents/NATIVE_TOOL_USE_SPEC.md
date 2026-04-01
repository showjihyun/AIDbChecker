# Feature Spec: Claude Native Tool Use + 200K Context 활용

## 메타데이터
- **Spec ID**: FS-DBA-005
- **PRD 참조**: FR-AI-012, FS-DBA-002
- **우선순위**: P0
- **상태**: Approved
- **선행 Spec**: FS-DBA-004 (Multi-Turn), FS-AI-LLM-001

---

## 1. 개요

현재 ReAct 텍스트 파싱 방식 (`"Action: tool_name\nAction Input: {...}"`)을
**Anthropic Native Tool Use API** (`ToolUseBlock` / `ToolResultBlock`)로 전환합니다.

### 변경 효과

| 항목 | Before (ReAct) | After (Native Tool Use) |
|------|---------------|------------------------|
| Tool 호출 | 텍스트 파싱 (정규식) | SDK 구조화 (ToolUseBlock) |
| 입력 파싱 | JSON.parse 시도 + fallback | SDK가 자동 파싱 |
| 응답 형식 | "Final Answer: {json}" 텍스트 | TextBlock 직접 반환 |
| 에러 처리 | 텍스트 "Error: ..." | ToolResultBlock(is_error=True) |
| 컨텍스트 | 1500 토큰 제한 | **200K 토큰** (전체 스키마 + 대화) |
| 한국어 품질 | 모델 의존 | Claude 최적화 (네이티브 한국어) |
| Hallucination | ReAct 루프 이탈 가능 | Tool 결과 기반 강제 |

---

## 2. 기술 설계

### 2.1 Anthropic SDK 직접 사용

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

response = await client.messages.create(
    model=settings.AI_MODEL,  # claude-sonnet-4-6
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    tools=TOOL_DEFINITIONS,
    messages=conversation_messages,
)
```

### 2.2 Tool 정의 (7개 진단 도구)

```python
TOOL_DEFINITIONS = [
    {
        "name": "slow_queries",
        "description": "pg_stat_statements에서 Top-N 느린 쿼리 조회",
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {"type": "integer", "default": 10, "description": "상위 N개"}
            }
        }
    },
    # ... 6개 더
]
```

### 2.3 Tool Use Loop

```python
while response.stop_reason == "tool_use":
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = await invoke_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
    
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})
    
    response = await client.messages.create(...)

# stop_reason == "end_turn" → 최종 답변
final_text = response.content[0].text
```

### 2.4 Fallback 전략

Claude API 불가 시 기존 ReAct 방식으로 fallback:
```
Claude API 가능? → Native Tool Use
Claude API 불가? → LangChain ReAct (Ollama/OpenAI)
```

---

## 3. 인수 기준

- [ ] **AC-1**: Anthropic SDK 직접 호출로 tool_use 메시지 생성
- [ ] **AC-2**: 7개 진단 도구가 Native Tool 정의로 변환
- [ ] **AC-3**: ToolUseBlock → 도구 실행 → ToolResultBlock 루프 동작
- [ ] **AC-4**: max_tokens 4096 + 200K 컨텍스트 활용 (스키마 + 대화)
- [ ] **AC-5**: stop_reason="end_turn" 시 한국어 최종 답변 반환
- [ ] **AC-6**: Claude 불가 시 기존 ReAct fallback 유지
- [ ] **AC-7**: 응답 시간 P95 < 15초

---

## 4. 의존성

- **패키지**: `anthropic` (AsyncAnthropic)
- **선행**: FS-DBA-004 (Multi-Turn Memory)
