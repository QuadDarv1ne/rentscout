"""
Тесты для проверки безопасности конфигурации.
"""

import os
import pytest
import warnings
from pathlib import Path

from app.core.config import Settings


class TestPasswordValidation:
    """Тесты валидации паролей."""

    def test_weak_database_password_raises_error(self):
        """Слабый пароль БД должен вызывать ошибку."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                DATABASE_URL="postgresql://user:password@localhost:5432/db",
                SECRET_KEY="a" * 64,
                JWT_SECRET="b" * 64,
            )
        assert "является дефолтным или слишком слабым" in str(exc_info.value)

    def test_weak_redis_password_raises_error(self):
        """Слабый пароль Redis должен вызывать ошибку."""
        with pytest.raises(ValueError) as exc_info:
            Settings(
                DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                REDIS_URL="redis://:redis_password@localhost:6379/0",
                SECRET_KEY="a" * 64,
                JWT_SECRET="b" * 64,
            )
        assert "является дефолтным или слишком слабым" in str(exc_info.value)

    def test_short_password_warns(self):
        """Короткий пароль (менее 16 символов) должен вызывать предупреждение."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                DATABASE_URL="postgresql://user:Short1!@localhost:5432/db",
                SECRET_KEY="a" * 64,
                JWT_SECRET="b" * 64,
            )
            # Должно быть предупреждение о коротком пароле
            assert len(w) > 0
            assert any("слишком короткий" in str(warning.message) for warning in w)

    def test_strong_password_no_warning(self):
        """Надёжный пароль не должен вызывать предупреждений."""
        strong_password = "Xk9#mP2$vL5nQ8wR!tY7"  # 20 символов, все категории
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = Settings(
                DATABASE_URL=f"postgresql://user:{strong_password}@localhost:5432/db",
                SECRET_KEY="a" * 64,
                JWT_SECRET="b" * 64,
            )
            # Не должно быть предупреждений о слабых паролях
            password_warnings = [
                warning for warning in w 
                if "слишком короткий" in str(warning.message) or 
                   "является дефолтным" in str(warning.message)
            ]
            assert len(password_warnings) == 0


class TestSecretKeyValidation:
    """Тесты валидации секретных ключей."""

    def test_missing_secret_key_warns(self):
        """Отсутствующий SECRET_KEY должен вызывать предупреждение."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                SECRET_KEY="",
                JWT_SECRET="b" * 64,
                DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                REDIS_URL="redis://:SecurePass123!@localhost:6379/0",
            )
            assert len(w) > 0
            assert any("SECRET_KEY слишком короткий" in str(warning.message) for warning in w)

    def test_weak_secret_key_raises_error(self):
        """Слабый SECRET_KEY должен вызывать ошибку."""
        weak_keys = [
            "your_very_long_random_secret_key_change_this",
            "change_this",
            "secret",
            "secret_key",
        ]
        
        for weak_key in weak_keys:
            with pytest.raises(ValueError) as exc_info:
                Settings(
                    SECRET_KEY=weak_key,
                    JWT_SECRET="b" * 64,
                    DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                    REDIS_URL="redis://:SecurePass123!@localhost:6379/0",
                )
            assert "не должен быть дефолтным значением" in str(exc_info.value)

    def test_strong_secret_key_no_warning(self):
        """Надёжный SECRET_KEY не должен вызывать предупреждений."""
        strong_key = "a" * 64  # 64 символа
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                SECRET_KEY=strong_key,
                JWT_SECRET="b" * 64,
                DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                REDIS_URL="redis://:SecurePass123!@localhost:6379/0",
            )
            key_warnings = [
                warning for warning in w 
                if "SECRET_KEY слишком короткий" in str(warning.message)
            ]
            assert len(key_warnings) == 0


class TestJwtSecretValidation:
    """Тесты валидации JWT секрета."""

    def test_missing_jwt_secret_warns(self):
        """Отсутствующий JWT_SECRET должен вызывать предупреждение."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Settings(
                SECRET_KEY="a" * 64,
                JWT_SECRET="",
                DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                REDIS_URL="redis://:SecurePass123!@localhost:6379/0",
            )
            assert len(w) > 0
            assert any("JWT_SECRET слишком короткий" in str(warning.message) for warning in w)

    def test_weak_jwt_secret_raises_error(self):
        """Слабый JWT_SECRET должен вызывать ошибку."""
        weak_secrets = [
            "another_secret_key_for_jwt",
            "jwt_secret",
            "jwt",
            "changeme",
        ]
        
        for weak_secret in weak_secrets:
            with pytest.raises(ValueError) as exc_info:
                Settings(
                    SECRET_KEY="a" * 64,
                    JWT_SECRET=weak_secret,
                    DATABASE_URL="postgresql://user:SecurePass123!@localhost:5432/db",
                    REDIS_URL="redis://:SecurePass123!@localhost:6379/0",
                )
            assert "не должен быть дефолтным значением" in str(exc_info.value)


class TestSecretsGeneratorScript:
    """Тесты скрипта генерации секретов."""

    def test_generate_secure_password(self):
        """Тест генерации безопасного пароля."""
        from scripts.generate_secrets import generate_secure_password
        
        password = generate_secure_password(32)
        
        assert len(password) >= 32
        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(c in "!@#$%^&*()-_=+" for c in password)

    def test_generate_secret_key(self):
        """Тест генерации секретного ключа."""
        from scripts.generate_secrets import generate_secret_key
        
        key = generate_secret_key(64)
        
        assert len(key) == 64
        assert all(c in '0123456789abcdef' for c in key)

    def test_validate_password_strength(self):
        """Тест проверки сложности пароля."""
        from scripts.generate_secrets import validate_password_strength
        
        # Слабый пароль
        is_valid, problems = validate_password_strength("weak")
        assert is_valid is False
        assert len(problems) > 0
        
        # Надёжный пароль
        strong_password = "Xk9#mP2$vL5nQ8wR!tY7"
        is_valid, problems = validate_password_strength(strong_password)
        assert is_valid is True
        assert len(problems) == 0


class TestEnvExampleFile:
    """Тесты файла .env.example."""

    def test_env_example_exists(self):
        """Файл .env.example должен существовать."""
        env_example_path = Path(__file__).parent.parent.parent / ".env.example"
        assert env_example_path.exists()

    def test_env_example_has_security_warnings(self):
        """Файл .env.example должен содержать предупреждения о безопасности."""
        env_example_path = Path(__file__).parent.parent.parent / ".env.example"
        
        with open(env_example_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверка наличия инструкций по генерации
        assert "generate_secrets.py" in content
        assert "GENERATE_SECURE_PASSWORD" in content
        assert "GENERATE_WITH_SCRIPT" in content
        
        # Проверка отсутствия реальных паролей
        assert "your_password" not in content
        assert "redis_password" not in content
        assert "your_secure_password" not in content
        assert "your_very_long_random_secret_key_change_this" not in content
        assert "another_secret_key_for_jwt" not in content


class TestSecurityDocumentation:
    """Тесты документации по безопасности."""

    def test_security_guide_exists(self):
        """Руководство по безопасности должно существовать."""
        security_doc_path = Path(__file__).parent.parent.parent / "docs" / "SECURITY.md"
        assert security_doc_path.exists()

    def test_security_guide_has_content(self):
        """Руководство должно содержать необходимые разделы."""
        security_doc_path = Path(__file__).parent.parent.parent / "docs" / "SECURITY.md"
        
        with open(security_doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_sections = [
            "Генерация безопасных секретов",
            "Требования к паролям",
            "Production чеклист",
            "JWT Tokens",
            "Rate Limiting",
        ]
        
        for section in required_sections:
            assert section in content, f"Отсутствует раздел: {section}"
