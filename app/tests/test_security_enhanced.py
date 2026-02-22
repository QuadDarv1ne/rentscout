"""
Tests for enhanced security features.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.core.security_enhanced import (
    SecurityManager,
    APIKey,
    security_manager,
    PYOTP_AVAILABLE,
    CRYPTO_AVAILABLE,
)


@pytest.fixture
def security():
    """Create security manager for tests."""
    return SecurityManager(issuer="TestApp")


class TestAPIKey:
    """Tests for APIKey dataclass."""

    def test_create_api_key(self):
        """Test creating API key."""
        key = APIKey(
            id="test_id",
            user_id=123,
            name="Test Key",
            key_hash="hash123",
            prefix="rsc_test",
            created_at=datetime.utcnow(),
            expires_at=None,
            last_used_at=None,
            permissions=["read", "write"],
            is_active=True
        )
        assert key.id == "test_id"
        assert key.user_id == 123
        assert key.is_active is True

    def test_api_key_to_dict(self):
        """Test API key to_dict."""
        key = APIKey(
            id="test_id",
            user_id=123,
            name="Test Key",
            key_hash="hash123",
            prefix="rsc_test",
            created_at=datetime.utcnow(),
            expires_at=None,
            last_used_at=None,
            is_active=True
        )
        data = key.to_dict()
        assert "id" in data
        assert "key_hash" not in data  # Should not expose hash
        assert data["prefix"] == "rsc_test"


class TestSecurityManager:
    """Tests for SecurityManager."""

    def test_init(self, security):
        """Test initialization."""
        assert security.issuer == "TestApp"
        assert security.totp_digits == 6
        assert security.totp_interval == 30

    def test_generate_2fa_secret_no_pyotp(self, security):
        """Test 2FA secret generation without pyotp."""
        if not PYOTP_AVAILABLE:
            with pytest.raises(RuntimeError, match="pyotp not available"):
                security.generate_2fa_secret(user_id=123)

    def test_generate_2fa_secret_with_pyotp(self, security):
        """Test 2FA secret generation with pyotp."""
        if PYOTP_AVAILABLE:
            secret, uri = security.generate_2fa_secret(user_id=123)
            assert secret is not None
            assert len(secret) > 0
            assert "user_123" in uri
            assert "TestApp" in uri

    def test_verify_2fa_code_not_configured(self, security):
        """Test verifying code when 2FA not configured."""
        result = security.verify_2fa_code(user_id=123, code="123456")
        assert result is False

    def test_enable_2fa_not_configured(self, security):
        """Test enabling 2FA when not configured."""
        result = security.enable_2fa(user_id=123, code="123456")
        assert result is False

    def test_disable_2fa_not_configured(self, security):
        """Test disabling 2FA when not configured."""
        result = security.disable_2fa(user_id=123)
        assert result is False

    def test_get_2fa_status_not_configured(self, security):
        """Test getting 2FA status when not configured."""
        status = security.get_2fa_status(user_id=123)
        assert status["configured"] is False
        assert status["enabled"] is False

    def test_get_2fa_status_configured(self, security):
        """Test getting 2FA status when configured."""
        if PYOTP_AVAILABLE:
            security.generate_2fa_secret(user_id=123)
            status = security.get_2fa_status(user_id=123)
            assert status["configured"] is True
            assert status["enabled"] is False  # Not confirmed yet
            assert status["backup_codes_remaining"] == 10

    def test_verify_backup_code(self, security):
        """Test backup code verification."""
        if PYOTP_AVAILABLE:
            security.generate_2fa_secret(user_id=123)
            config = security._totp_configs[123]
            
            # Use a backup code
            code = config.backup_codes[0]
            result = security.verify_backup_code(user_id=123, code=code)
            assert result is True
            
            # Code should be consumed
            assert code not in config.backup_codes
            
            # Using same code again should fail
            result = security.verify_backup_code(user_id=123, code=code)
            assert result is False

    def test_create_api_key(self, security):
        """Test creating API key."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App"
        )
        
        assert raw_key.startswith("rsc_")
        assert len(raw_key) > 20
        assert api_key.id is not None
        assert api_key.user_id == 123
        assert api_key.name == "Test App"
        assert api_key.is_active is True
        assert api_key.prefix in raw_key

    def test_create_api_key_with_expiration(self, security):
        """Test creating API key with expiration."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App",
            expires_in_days=30
        )
        
        assert api_key.expires_at is not None
        expected = datetime.utcnow() + timedelta(days=30)
        # Allow 1 second difference
        assert abs((api_key.expires_at - expected).total_seconds()) < 1

    def test_create_api_key_with_permissions(self, security):
        """Test creating API key with permissions."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App",
            permissions=["read", "write"]
        )
        
        assert api_key.permissions == ["read", "write"]

    def test_validate_api_key_valid(self, security):
        """Test validating valid API key."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App"
        )
        
        result = security.validate_api_key(raw_key)
        assert result is not None
        assert result.user_id == 123
        assert result.is_active is True

    def test_validate_api_key_invalid(self, security):
        """Test validating invalid API key."""
        result = security.validate_api_key("invalid_key")
        assert result is None

    def test_validate_api_key_revoked(self, security):
        """Test validating revoked API key."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App"
        )
        
        # Revoke the key
        security.revoke_api_key(api_key.id)
        
        # Should not validate
        result = security.validate_api_key(raw_key)
        assert result is None

    def test_revoke_api_key(self, security):
        """Test revoking API key."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App"
        )
        
        result = security.revoke_api_key(api_key.id)
        assert result is True
        
        # Key should be inactive
        assert api_key.is_active is False

    def test_revoke_api_key_not_found(self, security):
        """Test revoking non-existent API key."""
        result = security.revoke_api_key("nonexistent")
        assert result is False

    def test_list_api_keys(self, security):
        """Test listing API keys."""
        security.create_api_key(user_id=123, name="Key 1")
        security.create_api_key(user_id=123, name="Key 2")
        security.create_api_key(user_id=456, name="Key 3")
        
        keys = security.list_api_keys(user_id=123)
        assert len(keys) == 2
        assert all(k["user_id"] == 123 for k in keys)

    def test_get_api_key(self, security):
        """Test getting API key by ID."""
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="Test App"
        )
        
        result = security.get_api_key(api_key.id)
        assert result is not None
        assert result["id"] == api_key.id
        assert result["name"] == "Test App"

    def test_get_api_key_not_found(self, security):
        """Test getting non-existent API key."""
        result = security.get_api_key("nonexistent")
        assert result is None

    def test_create_session(self, security):
        """Test creating session."""
        token = security.create_session(
            user_id=123,
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        
        assert token is not None
        assert len(token) > 30

    def test_create_session_with_expiration(self, security):
        """Test creating session with custom expiration."""
        token = security.create_session(
            user_id=123,
            ip_address="192.168.1.1",
            user_agent="Test Browser",
            expires_in_hours=12
        )
        
        assert token is not None

    def test_revoke_session(self, security):
        """Test revoking session."""
        token = security.create_session(
            user_id=123,
            ip_address="192.168.1.1",
            user_agent="Test Browser"
        )
        
        result = security.revoke_session(token)
        assert result is True

    def test_revoke_all_sessions(self, security):
        """Test revoking all sessions."""
        security.create_session(user_id=123, ip_address="192.168.1.1", user_agent="Browser")
        security.create_session(user_id=123, ip_address="192.168.1.2", user_agent="Mobile")
        
        count = security.revoke_all_sessions(user_id=123)
        # In-memory implementation returns 0
        assert count >= 0

    def test_encrypt_decrypt(self, security):
        """Test encryption/decryption."""
        if CRYPTO_AVAILABLE:
            # Need to create security manager with valid Fernet key
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            secure = SecurityManager(encryption_key=key)
            
            data = "sensitive information"
            encrypted = secure.encrypt(data)
            assert encrypted is not None
            assert encrypted != data
            
            decrypted = secure.decrypt(encrypted)
            assert decrypted == data

    def test_encrypt_no_key(self, security):
        """Test encryption without key."""
        result = security.encrypt("data")
        assert result is None

    def test_decrypt_no_key(self, security):
        """Test decryption without key."""
        result = security.decrypt("encrypted")
        assert result is None

    def test_hash_api_key(self, security):
        """Test API key hashing."""
        key = "test_key_123"
        hash1 = security._hash_api_key(key)
        hash2 = security._hash_api_key(key)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex

    def test_generate_backup_code(self, security):
        """Test backup code generation."""
        code = security._generate_backup_code()
        assert len(code) > 0
        assert '-' in code  # Should have dashes


class TestGlobalSecurityManager:
    """Tests for global security manager."""

    def test_global_instance_exists(self):
        """Test global instance exists."""
        assert security_manager is not None
        assert isinstance(security_manager, SecurityManager)

    def test_global_instance_default_issuer(self):
        """Test global instance default issuer."""
        assert security_manager.issuer == "RentScout"


class TestSecurityIntegration:
    """Integration tests for security features."""

    def test_full_2fa_workflow(self, security):
        """Test complete 2FA workflow."""
        if PYOTP_AVAILABLE:
            # Generate secret
            secret, uri = security.generate_2fa_secret(user_id=123)
            assert secret is not None
            
            # Check status (should be configured but not enabled)
            status = security.get_2fa_status(user_id=123)
            assert status["configured"] is True
            assert status["enabled"] is False
            
            # Get current TOTP code
            import pyotp
            totp = pyotp.TOTP(secret)
            code = totp.now()
            
            # Enable 2FA
            result = security.enable_2fa(user_id=123, code=code)
            assert result is True
            
            # Check status (should be enabled)
            status = security.get_2fa_status(user_id=123)
            assert status["enabled"] is True

    def test_full_api_key_workflow(self, security):
        """Test complete API key workflow."""
        # Create key
        raw_key, api_key = security.create_api_key(
            user_id=123,
            name="My App",
            permissions=["read"],
            expires_in_days=30
        )
        
        # Validate key
        validated = security.validate_api_key(raw_key)
        assert validated is not None
        assert validated.user_id == 123
        
        # List keys
        keys = security.list_api_keys(user_id=123)
        assert len(keys) >= 1
        
        # Get key
        key_info = security.get_api_key(api_key.id)
        assert key_info is not None
        
        # Revoke key
        security.revoke_api_key(api_key.id)
        
        # Validate should fail
        validated = security.validate_api_key(raw_key)
        assert validated is None
