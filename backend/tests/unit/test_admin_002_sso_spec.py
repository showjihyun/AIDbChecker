# Spec: FS-ADMIN-002
"""Spec-Driven tests for SSO/LDAP/API Key authentication.

Feature Spec: docs/specs/services/SSO_LDAP_SPEC.md
Test Strategy: docs/specs/tests/TEST_STRATEGY.md

AC Coverage:
  AC-1: config에 SSO 설정 추가 → test_ac1_*
  AC-2: OIDC callback → JWT → test_ac2_*
  AC-3: LDAP login → JWT → test_ac3_*
  AC-4: API Key 인증 → test_ac4_*
  AC-5: SSO 사용자 auto-provision → test_ac5_*
  AC-6: SSO_ENABLED=false → 404 → test_ac6_*
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# AC-1: Config에 SSO 설정 추가
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-1")
def test_fs_admin_002_ac1_config_has_sso_fields():
    """FS-ADMIN-002 AC-1: Settings에 SSO 관련 필드 존재."""
    from app.config import Settings

    fields = Settings.model_fields
    assert "SSO_ENABLED" in fields
    assert "OIDC_ISSUER_URL" in fields
    assert "OIDC_CLIENT_ID" in fields
    assert "OIDC_CLIENT_SECRET" in fields
    assert "LDAP_SERVER_URL" in fields
    assert "LDAP_BIND_DN" in fields
    assert "LDAP_BIND_PASSWORD" in fields
    assert "API_KEY_HEADER" in fields


@spec_ref("FS-ADMIN-002", "AC-1")
def test_fs_admin_002_ac1_sso_disabled_by_default():
    """FS-ADMIN-002 AC-1: SSO_ENABLED 기본값 false."""
    from app.config import settings

    assert settings.SSO_ENABLED is False


# ---------------------------------------------------------------------------
# AC-2: OIDC callback → JWT
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-2")
def test_fs_admin_002_ac2_oidc_endpoint_registered():
    """FS-ADMIN-002 AC-2: /auth/oidc/callback POST 엔드포인트 등록."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/auth/oidc/callback" in routes


@spec_ref("FS-ADMIN-002", "AC-2")
@pytest.mark.asyncio
async def test_fs_admin_002_ac2_oidc_disabled_returns_error():
    """FS-ADMIN-002 AC-2: SSO_ENABLED=false → ValueError."""
    from app.services.sso import authenticate_oidc

    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="SSO is not enabled"):
        await authenticate_oidc(mock_session, "fake-token")


# ---------------------------------------------------------------------------
# AC-3: LDAP login → JWT
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-3")
def test_fs_admin_002_ac3_ldap_endpoint_registered():
    """FS-ADMIN-002 AC-3: /auth/ldap POST 엔드포인트 등록."""
    from app.main import app as fastapi_app

    routes = [r.path for r in fastapi_app.routes]
    assert "/api/v1/auth/ldap" in routes


@spec_ref("FS-ADMIN-002", "AC-3")
@pytest.mark.asyncio
async def test_fs_admin_002_ac3_ldap_disabled_returns_error():
    """FS-ADMIN-002 AC-3: SSO_ENABLED=false → ValueError."""
    from app.services.sso import authenticate_ldap

    mock_session = AsyncMock()
    with pytest.raises(ValueError, match="SSO is not enabled"):
        await authenticate_ldap(mock_session, "admin", "password")


# ---------------------------------------------------------------------------
# AC-4: API Key 인증
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-4")
def test_fs_admin_002_ac4_api_key_header_configurable():
    """FS-ADMIN-002 AC-4: API_KEY_HEADER 설정 존재."""
    from app.config import settings

    assert settings.API_KEY_HEADER == "X-API-Key"


@spec_ref("FS-ADMIN-002", "AC-4")
@pytest.mark.asyncio
async def test_fs_admin_002_ac4_api_key_no_match_returns_none():
    """FS-ADMIN-002 AC-4: 매칭되는 API Key 없으면 None."""
    from app.services.sso import authenticate_api_key

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value = MagicMock(all=MagicMock(return_value=[]))
    mock_session.execute.return_value = mock_result

    user = await authenticate_api_key(mock_session, "invalid-key")
    assert user is None


# ---------------------------------------------------------------------------
# AC-5: SSO 사용자 auto-provision
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-5")
@pytest.mark.asyncio
async def test_fs_admin_002_ac5_auto_provision_new_user(async_session):
    """FS-ADMIN-002 AC-5: 새 SSO 사용자 자동 생성."""
    from app.services.sso import _get_or_create_user

    user = await _get_or_create_user(
        async_session,
        email=f"sso-{uuid4().hex[:8]}@test.com",
        name="SSO Test User",
        auth_provider="oidc",
    )
    assert user is not None
    assert user.auth_provider == "oidc"
    assert user.hashed_password is None  # SSO users have no password
    assert user.role == "viewer"  # default role
    assert user.is_active is True


@spec_ref("FS-ADMIN-002", "AC-5")
@pytest.mark.asyncio
async def test_fs_admin_002_ac5_existing_user_updated(async_session):
    """FS-ADMIN-002 AC-5: 기존 사용자 로그인 시 auth_provider 갱신."""
    from app.services.sso import _get_or_create_user

    email = f"existing-{uuid4().hex[:8]}@test.com"

    # First login (creates user)
    user1 = await _get_or_create_user(
        async_session,
        email=email,
        name="Test",
        auth_provider="local",
    )

    # Second login via OIDC (updates provider)
    user2 = await _get_or_create_user(
        async_session,
        email=email,
        name="Test",
        auth_provider="oidc",
    )

    assert user1.id == user2.id
    assert user2.auth_provider == "oidc"
    assert user2.last_login_at is not None


# ---------------------------------------------------------------------------
# AC-6: SSO_ENABLED=false → 404
# ---------------------------------------------------------------------------


@spec_ref("FS-ADMIN-002", "AC-6")
@pytest.mark.asyncio
async def test_fs_admin_002_ac6_oidc_404_when_disabled(client):
    """FS-ADMIN-002 AC-6: SSO_ENABLED=false → OIDC callback returns 404."""
    resp = await client.post(
        "/api/v1/auth/oidc/callback",
        json={"id_token": "test"},
    )
    assert resp.status_code == 404


@spec_ref("FS-ADMIN-002", "AC-6")
@pytest.mark.asyncio
async def test_fs_admin_002_ac6_ldap_404_when_disabled(client):
    """FS-ADMIN-002 AC-6: SSO_ENABLED=false → LDAP returns 404."""
    resp = await client.post(
        "/api/v1/auth/ldap",
        json={"username": "admin", "password": "pass"},
    )
    assert resp.status_code == 404
