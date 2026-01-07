"""
Tests for configuration management and SECRET_KEY security
"""
import os
import warnings
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestSecretKeyConfig:
    """Test SECRET_KEY configuration and security"""

    def test_secret_key_loads_from_env(self):
        """Test that SECRET_KEY is loaded from environment variable"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "test-secret-key-12345",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "testpass",
            "ENVIRONMENT": "local"
        }):
            settings = Settings()
            assert settings.SECRET_KEY == "test-secret-key-12345"

    def test_secret_key_required_when_not_in_env(self):
        """Test that SECRET_KEY is required and cannot be empty"""
        # Remove SECRET_KEY from environment
        with patch.dict(os.environ, {
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "testpass"
        }, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            # Check that the error is about SECRET_KEY
            errors = exc_info.value.errors()
            secret_key_error = next(
                (e for e in errors if 'SECRET_KEY' in str(e.get('loc'))),
                None
            )
            assert secret_key_error is not None, "Should have validation error for SECRET_KEY"

    def test_secret_key_rejects_default_value_in_production(self):
        """Test that 'changethis' is rejected in production environment"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "changethis",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "securepass",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "securepass",
            "ENVIRONMENT": "production"
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "SECRET_KEY" in str(exc_info.value)
            assert "changethis" in str(exc_info.value)

    def test_secret_key_allows_default_in_local_with_warning(self):
        """Test that 'changethis' is allowed in local environment but shows warning"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "changethis",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "changethis",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "changethis",
            "ENVIRONMENT": "local"
        }):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                settings = Settings()

                # Should have warning about SECRET_KEY
                secret_key_warning = any(
                    "SECRET_KEY" in str(warning.message) and "changethis" in str(warning.message)
                    for warning in w
                )
                assert secret_key_warning, "Should show warning about default SECRET_KEY in local environment"
                assert settings.SECRET_KEY == "changethis"

    def test_secret_key_accepts_secure_value(self):
        """Test that a secure SECRET_KEY is accepted"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "nQh8K_jZxM2vP9wB4tY7uR3eW6qN1oL5sA0fG8hD4cV2mX9zK",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "securepass",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "securepass",
            "ENVIRONMENT": "production"
        }):
            settings = Settings()
            assert settings.SECRET_KEY == "nQh8K_jZxM2vP9wB4tY7uR3eW6qN1oL5sA0fG8hD4cV2mX9zK"

    def test_staging_environment_rejects_default_secret(self):
        """Test that staging environment also rejects default SECRET_KEY"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "changethis",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "securepass",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "securepass",
            "ENVIRONMENT": "staging"
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "SECRET_KEY" in str(exc_info.value)


class TestConfigValidation:
    """Test other configuration validation"""

    def test_postgres_password_rejects_default_in_production(self):
        """Test that default PostgreSQL password is rejected in production"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "secure-secret-key",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "changethis",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "securepass",
            "ENVIRONMENT": "production"
        }):
            with pytest.raises(ValueError) as exc_info:
                Settings()

            assert "POSTGRES_PASSWORD" in str(exc_info.value)

    def test_all_config_loads_successfully_with_valid_values(self):
        """Test that configuration loads successfully with all valid values"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "secure-secret-key-12345",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "securepassword123",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "securepassword123",
            "ENVIRONMENT": "production",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_HOST": "https://example.com"
        }):
            settings = Settings()

            assert settings.SECRET_KEY == "secure-secret-key-12345"
            assert settings.ENVIRONMENT == "production"
            assert settings.POSTGRES_SERVER == "localhost"
            assert settings.REDIS_URL == "redis://localhost:6379/0"


class TestVerificationCodeConfig:
    """Test verification code configuration"""

    def test_verification_code_defaults(self):
        """Test that verification code configuration has proper defaults"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "test-secret",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "changethis",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "changethis",
            "ENVIRONMENT": "local"
        }):
            settings = Settings()

            assert settings.VERIFICATION_CODE_EXPIRE_MINUTES == 5
            assert settings.VERIFICATION_CODE_MAX_ATTEMPTS == 3
            assert settings.VERIFICATION_CODE_RATE_LIMIT_MINUTES == 1
            assert settings.VERIFICATION_CODE_RATE_LIMIT_COUNT == 5

    def test_verification_code_custom_values(self):
        """Test that verification code configuration can be customized"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "test-secret",
            "POSTGRES_SERVER": "localhost",
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": "changethis",
            "POSTGRES_DB": "testdb",
            "FIRST_SUPERUSER": "13800138000",
            "FIRST_SUPERUSER_PASSWORD": "changethis",
            "ENVIRONMENT": "local",
            "VERIFICATION_CODE_EXPIRE_MINUTES": "10",
            "VERIFICATION_CODE_MAX_ATTEMPTS": "5",
            "VERIFICATION_CODE_RATE_LIMIT_COUNT": "3"
        }):
            settings = Settings()

            assert settings.VERIFICATION_CODE_EXPIRE_MINUTES == 10
            assert settings.VERIFICATION_CODE_MAX_ATTEMPTS == 5
            assert settings.VERIFICATION_CODE_RATE_LIMIT_COUNT == 3
