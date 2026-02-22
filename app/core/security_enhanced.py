"""
Security enhancements for RentScout.

Features:
- Two-Factor Authentication (TOTP)
- API Key management
- Session management
- Security audit logging

Usage:
    from app.core.security import SecurityManager
    
    security = SecurityManager()
    
    # Generate 2FA secret
    secret = security.generate_2fa_secret(user_id=123)
    
    # Verify 2FA code
    is_valid = security.verify_2fa_code(user_id=123, code="123456")
    
    # Create API key
    api_key = security.create_api_key(user_id=123, name="My App")
"""

import secrets
import hashlib
import hmac
import base64
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import struct
import hmac as hmac_lib

from app.utils.logger import logger

# Try to import pyotp for TOTP
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
    logger.warning("pyotp not installed. Install with: pip install pyotp")

# Try to import cryptography for encryption
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography not installed. Install with: pip install cryptography")


@dataclass
class APIKey:
    """API Key representation."""
    id: str
    user_id: int
    name: str
    key_hash: str
    prefix: str  # First 8 chars for identification
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    permissions: List[str] = field(default_factory=list)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (without sensitive data)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "prefix": self.prefix,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "permissions": self.permissions,
            "is_active": self.is_active,
        }


@dataclass
class TOTPConfig:
    """TOTP configuration for a user."""
    user_id: int
    secret: str
    enabled: bool
    backup_codes: List[str]
    created_at: datetime
    last_verified_at: Optional[datetime] = None


class SecurityManager:
    """
    Security manager for 2FA and API keys.
    """
    
    def __init__(
        self,
        issuer: str = "RentScout",
        totp_digits: int = 6,
        totp_interval: int = 30,
        encryption_key: Optional[str] = None
    ):
        self.issuer = issuer
        self.totp_digits = totp_digits
        self.totp_interval = totp_interval
        
        # Initialize encryption
        if encryption_key and CRYPTO_AVAILABLE:
            self.fernet = Fernet(encryption_key.encode())
        else:
            self.fernet = None
        
        # In-memory storage (replace with database in production)
        self._totp_configs: Dict[int, TOTPConfig] = {}
        self._api_keys: Dict[str, APIKey] = {}
        
        logger.info(f"✅ Security manager initialized (2FA: {PYOTP_AVAILABLE}, Encryption: {CRYPTO_AVAILABLE})")
    
    # =========================================================================
    # TOTP (2FA) Methods
    # =========================================================================
    
    def generate_2fa_secret(self, user_id: int) -> Tuple[str, str]:
        """
        Generate 2FA secret for user.
        
        Returns:
            Tuple of (secret, provisioning_uri)
        """
        if not PYOTP_AVAILABLE:
            raise RuntimeError("pyotp not available")
        
        # Generate random secret
        secret = base64.b32encode(secrets.token_bytes(32)).decode('utf-8')
        
        # Create TOTP object
        totp = pyotp.TOTP(secret)
        
        # Create provisioning URI
        provisioning_uri = totp.provisioning_uri(
            name=f"user_{user_id}",
            issuer_name=self.issuer
        )
        
        # Generate backup codes
        backup_codes = [self._generate_backup_code() for _ in range(10)]
        
        # Store config
        self._totp_configs[user_id] = TOTPConfig(
            user_id=user_id,
            secret=secret,
            enabled=False,  # Disabled until user confirms
            backup_codes=backup_codes,
            created_at=datetime.utcnow()
        )
        
        logger.info(f"Generated 2FA secret for user {user_id}")
        return secret, provisioning_uri
    
    def verify_2fa_code(self, user_id: int, code: str) -> bool:
        """
        Verify 2FA code.
        
        Args:
            user_id: User ID
            code: 6-digit TOTP code
        
        Returns:
            True if valid
        """
        if not PYOTP_AVAILABLE:
            return False
        
        config = self._totp_configs.get(user_id)
        if not config or not config.enabled:
            return False
        
        try:
            totp = pyotp.TOTP(config.secret)
            is_valid = totp.verify(code, valid_window=1)  # Allow 1 interval drift
            
            if is_valid:
                config.last_verified_at = datetime.utcnow()
                logger.info(f"2FA verified for user {user_id}")
            
            return is_valid
        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            return False
    
    def enable_2fa(self, user_id: int, code: str) -> bool:
        """
        Enable 2FA after user confirms with code.
        
        Args:
            user_id: User ID
            code: Current TOTP code
        
        Returns:
            True if enabled successfully
        """
        config = self._totp_configs.get(user_id)
        if not config:
            return False
        
        # Verify the code
        if not self.verify_2fa_code_with_secret(config.secret, code):
            return False
        
        # Enable 2FA
        config.enabled = True
        logger.info(f"2FA enabled for user {user_id}")
        return True
    
    def disable_2fa(self, user_id: int) -> bool:
        """Disable 2FA for user."""
        config = self._totp_configs.get(user_id)
        if not config:
            return False
        
        config.enabled = False
        logger.info(f"2FA disabled for user {user_id}")
        return True
    
    def verify_backup_code(self, user_id: int, code: str) -> bool:
        """Verify and consume backup code."""
        config = self._totp_configs.get(user_id)
        if not config:
            return False
        
        if code in config.backup_codes:
            config.backup_codes.remove(code)
            logger.info(f"Backup code used for user {user_id}")
            return True
        
        return False
    
    def get_2fa_status(self, user_id: int) -> Dict[str, Any]:
        """Get 2FA status for user."""
        config = self._totp_configs.get(user_id)
        if not config:
            return {"enabled": False, "configured": False}
        
        return {
            "enabled": config.enabled,
            "configured": True,
            "backup_codes_remaining": len(config.backup_codes),
            "last_verified": config.last_verified_at.isoformat() if config.last_verified_at else None,
        }
    
    def verify_2fa_code_with_secret(self, secret: str, code: str) -> bool:
        """Verify code with secret (internal use)."""
        if not PYOTP_AVAILABLE:
            return False
        
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False
    
    def _generate_backup_code(self) -> str:
        """Generate a backup code."""
        return '-'.join(secrets.token_hex(2).upper() for _ in range(4))
    
    # =========================================================================
    # API Key Methods
    # =========================================================================
    
    def create_api_key(
        self,
        user_id: int,
        name: str,
        permissions: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[str, APIKey]:
        """
        Create new API key.
        
        Args:
            user_id: User ID
            name: Key name/description
            permissions: List of permissions
            expires_in_days: Days until expiration
        
        Returns:
            Tuple of (raw_key, api_key_info)
        """
        # Generate raw API key
        raw_key = f"rsc_{secrets.token_urlsafe(32)}"
        
        # Hash the key for storage
        key_hash = self._hash_api_key(raw_key)
        
        # Get prefix for identification
        prefix = raw_key[:12]
        
        # Generate ID
        key_id = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Create API key record
        api_key = APIKey(
            id=key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            last_used_at=None,
            permissions=permissions or [],
            is_active=True
        )
        
        # Store
        self._api_keys[key_id] = api_key
        
        logger.info(f"Created API key {prefix}... for user {user_id}")
        return raw_key, api_key
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKey]:
        """
        Validate API key and return key info if valid.
        
        Args:
            raw_key: Raw API key from request
        
        Returns:
            APIKey if valid, None otherwise
        """
        # Hash the provided key
        key_hash = self._hash_api_key(raw_key)
        
        # Find matching key
        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash:
                # Check if active
                if not api_key.is_active:
                    logger.warning(f"API key {api_key.prefix}... is inactive")
                    return None
                
                # Check expiration
                if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
                    logger.warning(f"API key {api_key.prefix}... is expired")
                    return None
                
                # Update last used
                api_key.last_used_at = datetime.utcnow()
                
                return api_key
        
        return None
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke API key."""
        api_key = self._api_keys.get(key_id)
        if not api_key:
            return False
        
        api_key.is_active = False
        logger.info(f"Revoked API key {key_id}")
        return True
    
    def list_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """List all API keys for user."""
        keys = []
        for api_key in self._api_keys.values():
            if api_key.user_id == user_id:
                keys.append(api_key.to_dict())
        return keys
    
    def get_api_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get API key info by ID."""
        api_key = self._api_keys.get(key_id)
        if not api_key:
            return None
        return api_key.to_dict()
    
    def _hash_api_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    # =========================================================================
    # Session Management
    # =========================================================================
    
    def create_session(
        self,
        user_id: int,
        ip_address: str,
        user_agent: str,
        expires_in_hours: int = 24
    ) -> str:
        """
        Create new session.
        
        Returns:
            Session token
        """
        # Generate session token
        token = secrets.token_urlsafe(32)
        
        # Store session info (in production, use Redis/database)
        session_data = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=expires_in_hours)
        }
        
        # In production, encrypt and store in database
        logger.info(f"Created session for user {user_id} from {ip_address}")
        return token
    
    def validate_session(self, token: str) -> Optional[int]:
        """
        Validate session token.
        
        Returns:
            User ID if valid, None otherwise
        """
        # In production, retrieve from database and validate
        # This is a placeholder
        return None
    
    def revoke_session(self, token: str) -> bool:
        """Revoke session."""
        # In production, delete from database
        return True
    
    def revoke_all_sessions(self, user_id: int) -> int:
        """
        Revoke all sessions for user.
        
        Returns:
            Number of sessions revoked
        """
        # In production, delete all from database
        logger.info(f"Revoked all sessions for user {user_id}")
        return 0
    
    # =========================================================================
    # Encryption Utilities
    # =========================================================================
    
    def encrypt(self, data: str) -> Optional[str]:
        """Encrypt data."""
        if not self.fernet:
            return None
        
        encrypted = self.fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> Optional[str]:
        """Decrypt data."""
        if not self.fernet:
            return None
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None


# Global security manager instance
security_manager = SecurityManager()


__all__ = [
    "SecurityManager",
    "APIKey",
    "TOTPConfig",
    "security_manager",
]
