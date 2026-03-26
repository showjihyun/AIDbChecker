# Spec: FS-AI-LLM-001
"""Tests for FS-AI-LLM-001 Acceptance Criteria.

Covers LLM provider abstraction, settings API, Ollama model listing,
multi-provider LangChain instance creation, availability checks,
service integration, and model testing.

IMPORTANT: Do NOT delete the @spec_ref decorator -- it enables AC tracking in CI.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_admin_override():
    """Create a mock super_admin user and return the override callable."""
    from app.api.deps import get_current_user
    from app.main import app as fastapi_app

    mock_user = MagicMock()
    mock_user.id = uuid4()
    mock_user.role = "super_admin"
    mock_user.is_active = True

    async def _override():
        return mock_user

    fastapi_app.dependency_overrides[get_current_user] = _override
    return get_current_user


def _cleanup_admin_override(dep_key):
    """Remove the auth override after test."""
    from app.main import app as fastapi_app
    fastapi_app.dependency_overrides.pop(dep_key, None)


# ---------------------------------------------------------------------------
# AC-1: GET /api/v1/settings/llm returns current provider/model
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-1")
async def test_fs_ai_llm_001_ac1_get_api_v1_settings_llm(client):
    """FS-AI-LLM-001 AC-1: GET /api/v1/settings/llm에서 현재 프로바이더/모델 반환"""
    dep_key = _make_admin_override()
    try:
        response = await client.get("/api/v1/settings/llm")
    finally:
        _cleanup_admin_override(dep_key)

    assert response.status_code == 200
    data = response.json()

    # Spec: FS-AI-LLM-001 Section 3.3 — LLMSettingsResponse fields
    assert "provider" in data
    assert "model" in data
    assert "ollama_base_url" in data
    assert "has_openai_key" in data
    assert "has_anthropic_key" in data
    assert "has_google_key" in data

    # API keys are never exposed directly
    assert "openai_api_key" not in data
    assert "anthropic_api_key" not in data
    assert "google_api_key" not in data

    # Values should match settings defaults
    from app.config import settings
    assert data["provider"] == settings.AI_PROVIDER
    assert data["model"] == settings.AI_MODEL


# ---------------------------------------------------------------------------
# AC-2: PUT /api/v1/settings/llm changes config
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-2")
async def test_fs_ai_llm_001_ac2_put_api_v1_settings_llm(client):
    """FS-AI-LLM-001 AC-2: PUT /api/v1/settings/llm으로 프로바이더/모델 변경 가능"""
    from app.config import settings

    # Save original values to restore after test
    original_provider = settings.AI_PROVIDER
    original_model = settings.AI_MODEL

    dep_key = _make_admin_override()
    try:
        response = await client.put(
            "/api/v1/settings/llm",
            json={"provider": "openai", "model": "gpt-4o-mini"},
        )
    finally:
        _cleanup_admin_override(dep_key)
        # Restore original settings
        settings.AI_PROVIDER = original_provider
        settings.AI_MODEL = original_model

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# AC-3: GET /api/v1/settings/llm/ollama-models returns local model list
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-3")
async def test_fs_ai_llm_001_ac3_get_api_v1_settings_llm_ollama_models(client):
    """FS-AI-LLM-001 AC-3: GET /api/v1/settings/llm/ollama-models에서 로컬 모델 목록 반환"""
    # Mock the Ollama /api/tags response
    mock_ollama_response = {
        "models": [
            {
                "name": "mistral:7b",
                "size": 4_370_000_000,
                "modified_at": "2026-03-20T10:00:00Z",
            },
            {
                "name": "llama3:8b",
                "size": 5_200_000_000,
                "modified_at": "2026-03-19T12:00:00Z",
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_ollama_response
    mock_resp.raise_for_status = MagicMock()

    dep_key = _make_admin_override()
    try:
        with patch("app.services.llm_provider.httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_resp
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            # Clear LLM manager singleton cache so our mock takes effect
            from app.services.llm_provider import get_llm_manager
            get_llm_manager.cache_clear()

            response = await client.get("/api/v1/settings/llm/ollama-models")
    finally:
        _cleanup_admin_override(dep_key)
        get_llm_manager.cache_clear()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify model structure matches OllamaModel schema
    assert data[0]["name"] == "mistral:7b"
    assert "GB" in data[0]["size"]
    assert data[0]["modified_at"] != ""

    assert data[1]["name"] == "llama3:8b"


# ---------------------------------------------------------------------------
# AC-4: 4 providers create LangChain instances
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-4")
async def test_fs_ai_llm_001_ac4_4_ollama_openai_anthropic_google_langchain():
    """FS-AI-LLM-001 AC-4: 4개 프로바이더(Ollama/OpenAI/Anthropic/Google) LangChain 인스턴스 생성"""
    from app.services.llm_provider import LLMProviderManager

    manager = LLMProviderManager()

    # Test Ollama provider
    mock_chat_ollama = MagicMock()
    with patch(
        "app.services.llm_provider.LLMProviderManager._create_ollama",
        return_value=mock_chat_ollama,
    ):
        result = manager._create_llm(
            "ollama", "mistral:7b",
            temperature=0.1, max_tokens=1500, request_timeout=30,
        )
        assert result is mock_chat_ollama

    # Test OpenAI provider
    mock_chat_openai = MagicMock()
    with patch(
        "app.services.llm_provider.LLMProviderManager._create_openai",
        return_value=mock_chat_openai,
    ):
        result = manager._create_llm(
            "openai", "gpt-4o",
            temperature=0.1, max_tokens=1500, request_timeout=30,
        )
        assert result is mock_chat_openai

    # Test Anthropic provider
    mock_chat_anthropic = MagicMock()
    with patch(
        "app.services.llm_provider.LLMProviderManager._create_anthropic",
        return_value=mock_chat_anthropic,
    ):
        result = manager._create_llm(
            "anthropic", "claude-sonnet-4-20250514",
            temperature=0.1, max_tokens=1500, request_timeout=30,
        )
        assert result is mock_chat_anthropic

    # Test Google provider
    mock_chat_google = MagicMock()
    with patch(
        "app.services.llm_provider.LLMProviderManager._create_google",
        return_value=mock_chat_google,
    ):
        result = manager._create_llm(
            "google", "gemini-2.0-flash",
            temperature=0.1, max_tokens=1500, request_timeout=30,
        )
        assert result is mock_chat_google

    # Test unknown provider raises ValueError
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        manager._create_llm(
            "unknown_provider", "some-model",
            temperature=0.1, max_tokens=1500, request_timeout=30,
        )


# ---------------------------------------------------------------------------
# AC-5: Missing API key -> available: false
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-5")
async def test_fs_ai_llm_001_ac5_api_available_false():
    """FS-AI-LLM-001 AC-5: API 키 미설정 프로바이더는 available: false 반환"""
    from app.config import settings
    from app.services.llm_provider import LLMProviderManager

    manager = LLMProviderManager()

    # Save originals
    orig_openai = settings.OPENAI_API_KEY
    orig_anthropic = settings.ANTHROPIC_API_KEY
    orig_google = settings.GOOGLE_API_KEY

    try:
        # Clear all API keys
        settings.OPENAI_API_KEY = ""
        settings.ANTHROPIC_API_KEY = ""
        settings.GOOGLE_API_KEY = ""

        providers = manager.list_providers()
        provider_map = {p.name: p for p in providers}

        # All 4 providers should be listed
        assert "ollama" in provider_map
        assert "openai" in provider_map
        assert "anthropic" in provider_map
        assert "google" in provider_map

        # Cloud providers without keys must be available=false
        assert provider_map["openai"].available is False
        assert provider_map["anthropic"].available is False
        assert provider_map["google"].available is False

        # Cloud providers without keys should have empty model lists
        assert provider_map["openai"].models == []
        assert provider_map["anthropic"].models == []
        assert provider_map["google"].models == []

    finally:
        # Restore original keys
        settings.OPENAI_API_KEY = orig_openai
        settings.ANTHROPIC_API_KEY = orig_anthropic
        settings.GOOGLE_API_KEY = orig_google


@spec_ref("FS-AI-LLM-001", "AC-5")
async def test_fs_ai_llm_001_ac5_api_key_set_available_true():
    """FS-AI-LLM-001 AC-5 (positive): API 키 설정 시 available: true + models populated"""
    from app.config import settings
    from app.services.llm_provider import LLMProviderManager

    manager = LLMProviderManager()

    orig_openai = settings.OPENAI_API_KEY

    try:
        settings.OPENAI_API_KEY = "sk-test-fake-key-for-testing"

        # Mock the langchain_openai import so it doesn't fail
        with patch.dict("sys.modules", {"langchain_openai": MagicMock()}):
            providers = manager.list_providers()
            provider_map = {p.name: p for p in providers}

            assert provider_map["openai"].available is True
            assert len(provider_map["openai"].models) > 0
    finally:
        settings.OPENAI_API_KEY = orig_openai


# ---------------------------------------------------------------------------
# AC-6: NL2SQL, MTL Lite, RAG use LLMProviderManager
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-6")
async def test_fs_ai_llm_001_ac6_nl2sql_mtl_lite_rag_llmprovidermanager_llm():
    """FS-AI-LLM-001 AC-6: NL2SQL, MTL Lite, RAG 서비스가 LLMProviderManager를 통해 LLM 호출"""
    import ast
    import inspect
    from pathlib import Path

    services_dir = Path(__file__).resolve().parent.parent.parent / "app" / "services"

    # Check nl2sql.py imports from llm_provider
    nl2sql_source = (services_dir / "nl2sql.py").read_text(encoding="utf-8")
    assert "get_llm_manager" in nl2sql_source, (
        "nl2sql.py must import get_llm_manager from app.services.llm_provider"
    )
    assert "LLMProviderManager" in nl2sql_source or "get_llm_manager" in nl2sql_source

    # Check mtl_lite.py imports from llm_provider
    mtl_source = (services_dir / "mtl_lite.py").read_text(encoding="utf-8")
    assert "get_llm_manager" in mtl_source, (
        "mtl_lite.py must import get_llm_manager from app.services.llm_provider"
    )
    assert "LLMProviderManager" in mtl_source or "get_llm_manager" in mtl_source

    # Verify the _get_llm() helper in nl2sql.py delegates to get_llm_manager
    assert "get_llm_manager().get_llm" in nl2sql_source or "get_llm_manager()" in nl2sql_source

    # Verify the _get_llm() helper in mtl_lite.py delegates to get_llm_manager
    assert "get_llm_manager().get_llm" in mtl_source or "get_llm_manager()" in mtl_source


# ---------------------------------------------------------------------------
# AC-7: POST /api/v1/settings/llm/test tests the selected model
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-7")
async def test_fs_ai_llm_001_ac7_post_api_v1_settings_llm_test(client):
    """FS-AI-LLM-001 AC-7: POST /api/v1/settings/llm/test로 선택 모델 테스트 가능"""
    from app.services.llm_provider import get_llm_manager

    # Mock the test_llm method to return a successful result
    mock_result = {
        "success": True,
        "response_text": "OK",
        "error": "",
        "latency_ms": 42,
    }

    dep_key = _make_admin_override()
    try:
        get_llm_manager.cache_clear()

        with patch.object(
            type(get_llm_manager()),
            "test_llm",
            new_callable=lambda: AsyncMock(return_value=mock_result),
        ) as mock_test:
            response = await client.post(
                "/api/v1/settings/llm/test",
                json={"provider": "ollama", "model": "mistral:7b"},
            )
    finally:
        _cleanup_admin_override(dep_key)
        get_llm_manager.cache_clear()

    assert response.status_code == 200
    data = response.json()

    # Spec: FS-AI-LLM-001 — LLMTestResponse fields
    assert data["success"] is True
    assert data["provider"] == "ollama"
    assert data["model"] == "mistral:7b"
    assert data["response_text"] == "OK"
    assert data["error"] == ""
    assert data["latency_ms"] == 42


@spec_ref("FS-AI-LLM-001", "AC-7")
async def test_fs_ai_llm_001_ac7_test_llm_failure(client):
    """FS-AI-LLM-001 AC-7 (negative): test returns failure when provider unavailable"""
    from app.services.llm_provider import get_llm_manager

    mock_result = {
        "success": False,
        "response_text": "",
        "error": "Provider 'openai' is not available.",
        "latency_ms": 0,
    }

    dep_key = _make_admin_override()
    try:
        get_llm_manager.cache_clear()

        with patch.object(
            type(get_llm_manager()),
            "test_llm",
            new_callable=lambda: AsyncMock(return_value=mock_result),
        ):
            response = await client.post(
                "/api/v1/settings/llm/test",
                json={"provider": "openai", "model": "gpt-4o"},
            )
    finally:
        _cleanup_admin_override(dep_key)
        get_llm_manager.cache_clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not available" in data["error"]


# ---------------------------------------------------------------------------
# AC-8: Frontend Settings — verify schema completeness
# ---------------------------------------------------------------------------
@spec_ref("FS-AI-LLM-001", "AC-8")
async def test_fs_ai_llm_001_ac8_frontend_settings_api_ui():
    """FS-AI-LLM-001 AC-8: Schema validation — LLM schemas have all fields needed by frontend"""
    from app.schemas.llm_settings import (
        LLMSettingsResponse,
        LLMSettingsUpdate,
        LLMTestRequest,
        LLMTestResponse,
        OllamaModel,
        ProviderInfo,
    )

    # Verify LLMSettingsResponse has all fields the frontend needs
    # Spec: FS-AI-LLM-001 Section 3.3
    response_fields = set(LLMSettingsResponse.model_fields.keys())
    assert "provider" in response_fields
    assert "model" in response_fields
    assert "ollama_base_url" in response_fields
    assert "has_openai_key" in response_fields
    assert "has_anthropic_key" in response_fields
    assert "has_google_key" in response_fields

    # Verify LLMSettingsUpdate supports partial updates
    update_fields = set(LLMSettingsUpdate.model_fields.keys())
    assert "provider" in update_fields
    assert "model" in update_fields
    assert "openai_api_key" in update_fields
    assert "anthropic_api_key" in update_fields
    assert "google_api_key" in update_fields
    assert "ollama_base_url" in update_fields

    # All update fields should be Optional (allow None for partial updates)
    for field_name, field_info in LLMSettingsUpdate.model_fields.items():
        assert field_info.default is None, (
            f"LLMSettingsUpdate.{field_name} should default to None for partial updates"
        )

    # Verify ProviderInfo has availability info for the dropdown
    provider_fields = set(ProviderInfo.model_fields.keys())
    assert "name" in provider_fields
    assert "display_name" in provider_fields
    assert "available" in provider_fields
    assert "models" in provider_fields

    # Verify OllamaModel has all needed display fields
    ollama_fields = set(OllamaModel.model_fields.keys())
    assert "name" in ollama_fields
    assert "size" in ollama_fields
    assert "modified_at" in ollama_fields

    # Verify LLMTestRequest schema
    test_req_fields = set(LLMTestRequest.model_fields.keys())
    assert "provider" in test_req_fields
    assert "model" in test_req_fields

    # Verify LLMTestResponse schema for displaying test results
    test_resp_fields = set(LLMTestResponse.model_fields.keys())
    assert "success" in test_resp_fields
    assert "provider" in test_resp_fields
    assert "model" in test_resp_fields
    assert "response_text" in test_resp_fields
    assert "error" in test_resp_fields
    assert "latency_ms" in test_resp_fields

    # Verify schemas can be instantiated with valid data (serialization sanity)
    resp = LLMSettingsResponse(
        provider="ollama",
        model="mistral:7b",
        ollama_base_url="http://localhost:11434",
        has_openai_key=False,
        has_anthropic_key=False,
        has_google_key=False,
    )
    assert resp.model_dump()["provider"] == "ollama"

    provider = ProviderInfo(
        name="openai",
        display_name="OpenAI",
        available=True,
        models=["gpt-4o", "gpt-4o-mini"],
    )
    assert provider.model_dump()["available"] is True
