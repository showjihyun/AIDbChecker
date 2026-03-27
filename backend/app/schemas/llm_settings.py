# Spec: FS-AI-LLM-001
"""Pydantic schemas for LLM Settings API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LLMSettingsResponse(BaseModel):
    """Current LLM configuration (API keys are NEVER exposed)."""

    provider: str  # ollama | openai | anthropic | google
    model: str  # Current active model name
    ollama_base_url: str
    has_openai_key: bool
    has_anthropic_key: bool
    has_google_key: bool


class LLMSettingsUpdate(BaseModel):
    """Partial update for LLM settings. Only provided fields are changed."""

    provider: Literal["ollama", "openai", "anthropic", "google"] | None = None
    model: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    ollama_base_url: str | None = None


class ProviderInfo(BaseModel):
    """Information about a single LLM provider."""

    name: str
    display_name: str
    available: bool  # API key set or Ollama reachable
    models: list[str]  # Known / available models


class OllamaModel(BaseModel):
    """A locally available Ollama model."""

    name: str  # e.g., "mistral:7b"
    size: str  # e.g., "4.1 GB"
    modified_at: str


class LLMTestRequest(BaseModel):
    """Request body for POST /settings/llm/test."""

    provider: Literal["ollama", "openai", "anthropic", "google"]
    model: str


class LLMTestResponse(BaseModel):
    """Result of an LLM connectivity/inference test."""

    success: bool
    provider: str
    model: str
    response_text: str = ""
    error: str = ""
    latency_ms: int = 0
