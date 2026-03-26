# Feature Spec: LLM Provider 추상화 + 멀티 프로바이더

## 메타데이터
- **Spec ID**: FS-AI-LLM-001
- **PRD 참조**: FR-AI-008 (Online/Offline 전환), MVP-AI-005
- **우선순위**: P0 (Phase 2)
- **상태**: Approved
- **선행 Spec**: FS-AI-010 (MTL RCA), FR-AI-003 (NL2SQL)
- **구현 파일**:
  - Backend: `backend/app/services/llm_provider.py`, `backend/app/api/v1/llm_settings.py`
  - Frontend: `frontend/src/routes/pages/LLMSettingsPage.tsx`
  - Test: `backend/tests/unit/test_llm_provider_spec.py`

---

## 1. 개요

NeuralDB의 모든 LLM 호출을 **단일 추상화 레이어**로 통합합니다. 4개 프로바이더(Ollama, OpenAI, Anthropic Claude, Google Gemini)를 Settings에서 선택/전환할 수 있으며, Ollama는 로컬 모델 리스트를 동적으로 조회합니다.

---

## 2. 지원 프로바이더

| Provider | Mode | 모델 예시 | API Key 필요 | 비고 |
|----------|------|----------|-------------|------|
| **Ollama** | offline | mistral:7b, llama3:8b, gemma2:9b | ❌ | 로컬 실행, 모델 리스트 동적 조회 |
| **OpenAI** | online | gpt-4o, gpt-4o-mini, gpt-3.5-turbo | ✅ | `OPENAI_API_KEY` |
| **Anthropic** | online | claude-sonnet-4-20250514, claude-haiku-4-5-20251001 | ✅ | `ANTHROPIC_API_KEY` |
| **Google** | online | gemini-2.0-flash, gemini-1.5-pro | ✅ | `GOOGLE_API_KEY` |

---

## 3. 인터페이스 계약

### 3.1 LLM Provider 추상화

```python
# backend/app/services/llm_provider.py
# Spec: FS-AI-LLM-001

from langchain_core.language_models import BaseChatModel

class LLMProviderManager:
    """Unified LLM provider factory."""

    def get_llm(self, provider: str | None = None, model: str | None = None) -> BaseChatModel:
        """Get LLM instance by provider name.

        Falls back to settings.AI_PROVIDER / settings.AI_MODEL if not specified.
        """
        ...

    async def list_ollama_models(self) -> list[str]:
        """Query Ollama API for available local models."""
        # GET http://{OLLAMA_BASE_URL}/api/tags
        ...

    def list_providers(self) -> list[ProviderInfo]:
        """Return all configured providers with availability status."""
        ...
```

### 3.2 API 엔드포인트

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/settings/llm` | super_admin | 현재 LLM 설정 조회 |
| PUT | `/api/v1/settings/llm` | super_admin | LLM 프로바이더/모델 변경 |
| GET | `/api/v1/settings/llm/providers` | super_admin | 사용 가능한 프로바이더 목록 |
| GET | `/api/v1/settings/llm/ollama-models` | super_admin | Ollama 로컬 모델 리스트 |
| POST | `/api/v1/settings/llm/test` | super_admin | 선택한 프로바이더+모델로 테스트 호출 |

### 3.3 Request/Response 스키마

```python
class LLMSettingsResponse(BaseModel):
    provider: str           # ollama | openai | anthropic | google
    model: str              # 현재 사용 중인 모델
    ollama_base_url: str    # Ollama 서버 URL
    has_openai_key: bool    # API 키 설정 여부 (키 자체는 노출하지 않음)
    has_anthropic_key: bool
    has_google_key: bool

class LLMSettingsUpdate(BaseModel):
    provider: Literal["ollama", "openai", "anthropic", "google"]
    model: str
    openai_api_key: str | None = None    # 변경 시에만 전송
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

class ProviderInfo(BaseModel):
    name: str
    display_name: str
    available: bool         # 키 설정 또는 Ollama 접속 가능 여부
    models: list[str]       # 사용 가능한 모델 목록

class OllamaModel(BaseModel):
    name: str               # e.g., "mistral:7b"
    size: str               # e.g., "4.1 GB"
    modified_at: str
```

---

## 4. 환경 변수 매핑

```
AI_PROVIDER=ollama          # 기본 프로바이더
AI_MODEL=mistral:7b         # 기본 모델
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=             # 비어있으면 미설정
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=
```

---

## 5. 프론트엔드 Settings UI

### 5.1 LLM Settings 페이지

Settings → "AI Configuration" 섹션에 LLM 설정 UI 추가:

```
┌─ AI Model Configuration ─────────────────────────┐
│                                                    │
│  Provider: [Ollama ▼]                              │
│                                                    │
│  Model: [mistral:7b ▼]     [Refresh Models]       │
│                                                    │
│  ── API Keys ──────────────────────────────────── │
│  OpenAI:    [••••••••••] [Show] [Test]            │
│  Anthropic: [not set]           [Test]            │
│  Google:    [not set]           [Test]            │
│                                                    │
│  [Save Changes]  [Test Current Model]              │
└────────────────────────────────────────────────────┘
```

### 5.2 Model Dropdown

- **Ollama**: API에서 동적 조회 (`/api/v1/settings/llm/ollama-models`)
- **OpenAI**: 하드코딩 목록 (`gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`)
- **Anthropic**: 하드코딩 목록 (`claude-sonnet-4-20250514`, `claude-haiku-4-5-20251001`)
- **Google**: 하드코딩 목록 (`gemini-2.0-flash`, `gemini-1.5-pro`)

---

## 6. 인수 기준

- [ ] AC-1: GET /api/v1/settings/llm에서 현재 프로바이더/모델 반환
- [ ] AC-2: PUT /api/v1/settings/llm으로 프로바이더/모델 변경 가능
- [ ] AC-3: GET /api/v1/settings/llm/ollama-models에서 로컬 모델 목록 반환
- [ ] AC-4: 4개 프로바이더(Ollama/OpenAI/Anthropic/Google) LangChain 인스턴스 생성
- [ ] AC-5: API 키 미설정 프로바이더는 available: false 반환
- [ ] AC-6: NL2SQL, MTL Lite, RAG 서비스가 LLMProviderManager를 통해 LLM 호출
- [ ] AC-7: POST /api/v1/settings/llm/test로 선택 모델 테스트 가능
- [ ] AC-8: Frontend Settings에서 프로바이더/모델 선택 + API 키 입력 UI
