# Spec: MVP-ADMIN-001
"""Unit tests for JWT token creation/validation and password hashing."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt

from app.api.v1.auth import pwd_context, _create_token, _create_access_token, _create_refresh_token
from app.config import settings


class TestPasswordHashing:
    """Tests for bcrypt password hashing via passlib CryptContext."""

    def test_hash_and_verify_correct_password(self) -> None:
        """Hashed password should verify against the original plain text."""
        plain = "NeuralDB@2026!"
        hashed = pwd_context.hash(plain)

        assert hashed != plain, "Hash must differ from plain text"
        assert pwd_context.verify(plain, hashed) is True

    def test_verify_wrong_password_fails(self) -> None:
        """Verification should fail for an incorrect password."""
        hashed = pwd_context.hash("correct-password")

        assert pwd_context.verify("wrong-password", hashed) is False

    def test_hash_produces_unique_values(self) -> None:
        """Two hashes of the same password should differ (bcrypt uses random salt)."""
        plain = "same-password-123"
        hash1 = pwd_context.hash(plain)
        hash2 = pwd_context.hash(plain)

        assert hash1 != hash2, "Bcrypt should produce unique hashes due to random salt"
        assert pwd_context.verify(plain, hash1) is True
        assert pwd_context.verify(plain, hash2) is True


class TestJWTTokenCreation:
    """Tests for JWT access and refresh token creation."""

    def test_create_access_token_has_valid_claims(self) -> None:
        """Access token should contain sub, exp, and iat claims."""
        user_id = str(uuid4())
        token = _create_access_token(user_id)

        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        assert payload["sub"] == user_id
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token_expires_later_than_access(self) -> None:
        """Refresh token should have a later expiration than the access token."""
        user_id = str(uuid4())
        access = _create_access_token(user_id)
        refresh = _create_refresh_token(user_id)

        access_payload = jwt.decode(
            access, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        refresh_payload = jwt.decode(
            refresh, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        assert refresh_payload["exp"] > access_payload["exp"]

    def test_expired_token_raises_on_decode(self) -> None:
        """Decoding an expired token should raise an error."""
        user_id = str(uuid4())
        token = _create_token(
            sub=user_id,
            expires_delta=timedelta(seconds=-10),  # already expired
        )

        with pytest.raises(Exception):
            jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )

    def test_token_with_wrong_secret_fails(self) -> None:
        """Decoding a token with a different secret should fail."""
        user_id = str(uuid4())
        token = _create_access_token(user_id)

        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret-key", algorithms=[settings.JWT_ALGORITHM])
