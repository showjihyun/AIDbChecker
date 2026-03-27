# ADR-009: LangChain + LangGraph AI 프레임워크 선택

- **Status**: Accepted
- **Date**: 2026-03-27
- **Deciders**: Project Lead
- **관련 Spec**: AG-001 (Agent Architecture), FS-AI-010 (MTL RCA), FS-AI-012 (DB Copilot)

## Context

NeuralDB의 AI 기능(RCA, NL2SQL, DB Copilot, Auto-Tuning)을 구현하기 위한 LLM 프레임워크 선택이 필요했다. 후보:

| 프레임워크 | 라이선스 | 장점 | 단점 |
|-----------|---------|------|------|
| **LangChain** | MIT | 가장 큰 생태계, 150+ 통합, 모든 LLM 지원 | 추상화 과다, 버전 변경 잦음 |
| **LangGraph** | MIT | 상태 그래프 기반 에이전트, LangChain 호환 | LangChain 의존 |
| **CrewAI** | MIT | 멀티 에이전트 오케스트레이션, 역할 기반 | 단독 사용 시 LLM 추상화 부족 |
| **LlamaIndex** | MIT | RAG 특화, 문서 인덱싱 우수 | 모니터링 도메인 부적합 |
| **직접 구현** | - | 완전한 제어 | 유지보수 비용 극대, LLM 통합 수동 |

## Decision

**LangChain(기반) + LangGraph(에이전트 상태 그래프)를 메인으로, CrewAI를 Phase 3 멀티 에이전트 오케스트레이션에 사용한다.**

### Phase별 활용

| Phase | 프레임워크 | 용도 |
|-------|-----------|------|
| MVP | LangChain | LLM 추상화 (MTL Lite, NL2SQL, RAG), 멀티 프로바이더 전환 |
| Phase 2 | + LangGraph | DB Copilot ToT 상태 그래프, Auto-Tuning 에이전트 |
| Phase 3 | + CrewAI | 4-Agent 오케스트레이션 (Monitoring→Diagnosis→Remediation→Reporting) |

### LLMProviderManager 패턴

```python
# LangChain BaseChatModel을 통일 인터페이스로 감싸 4개 프로바이더 지원
LLMProviderManager.get_llm(provider, model, temperature, max_tokens)
# → Ollama / OpenAI / Anthropic / Google → BaseChatModel 반환
```

## Consequences

### Positive
- 4개 LLM 프로바이더(Ollama/OpenAI/Anthropic/Google)를 단일 인터페이스로 전환
- LangChain의 150+ 도구/통합 재사용 (SQL Agent, RAG 파이프라인)
- LangGraph로 ToT 분기 추론을 상태 그래프로 자연스럽게 모델링
- 모든 컴포넌트 MIT 라이선스 → 라이선스 정책 준수

### Negative
- LangChain 버전 업데이트 시 breaking change 리스크 (langchain-core 분리 등)
- LangChain 추상화 레이어로 디버깅 복잡성 증가
- LangGraph 학습 곡선 (상태 머신 패러다임)

### Mitigation
- `LLMProviderManager`로 LangChain 의존을 단일 지점에 격리
- LangChain 버전 고정 (`uv.lock`)으로 예기치 않은 업데이트 방지
