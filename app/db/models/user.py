"""
SQLAlchemy модель пользователя для аутентификации.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.models.property import Base
from app.core.security import UserRole


class User(Base):
    """Модель пользователя для PostgreSQL."""

    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Basic information
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Role and status
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # 2FA fields
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String(32), nullable=True)  # Encrypted TOTP secret
    backup_codes = Column(String(1000), nullable=True)  # JSON array of hashed backup codes
    backup_codes_used = Column(String(500), nullable=True)  # JSON array of used backup code indices

    # Indexes
    __table_args__ = (
        Index('ix_users_username_active', 'username', 'is_active'),
        Index('ix_users_email_active', 'email', 'is_active'),
        Index('ix_users_role', 'role'),
    )

    # Relationships
    properties = relationship("Property", back_populates="owner", lazy="selectin")
    bookmarks = relationship("Bookmark", back_populates="user", lazy="selectin", cascade="all, delete-orphan")
    alerts = relationship("PropertyAlert", back_populates="user", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
