#!/usr/bin/env python3
"""
Генератор безопасных секретов для RentScout.

Использование:
    python scripts/generate_secrets.py

Выводит готовые значения для .env файла.
"""

import secrets
import string


def generate_secret(length: int = 64) -> str:
    """
    Генерирует криптографически стойкую случайную строку.

    Args:
        length: Длина строки (минимум 32 для секретов)

    Returns:
        Случайная строка из букв и цифр
    """
    if length < 32:
        raise ValueError("Длина секрета должна быть минимум 32 символа")

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_password(length: int = 32) -> str:
    """
    Генерирует безопасный пароль для БД/Redis.

    Args:
        length: Длина пароля

    Returns:
        Случайный пароль
    """
    if length < 16:
        raise ValueError("Длина пароля должна быть минимум 16 символов")

    # Используем все символы для максимальной энтропии
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*_-+=[]"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def main():
    """Генерирует и выводит все необходимые секреты."""
    print("=" * 60)
    print("🔐 RentScout — Генератор безопасных секретов")
    print("=" * 60)
    print()
    print("📋 Добавьте эти значения в ваш .env файл:\n")

    secret_key = generate_secret(64)
    jwt_secret = generate_secret(64)
    postgres_password = generate_password(32)
    redis_password = generate_password(32)

    print(f"SECRET_KEY={secret_key}")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print(f"REDIS_PASSWORD={redis_password}")
    print()
    print("=" * 60)
    print("✅ Секреты сгенерированы!")
    print()
    print("⚠️  ВАЖНО:")
    print("   - Сохраните эти значения в надёжном месте")
    print("   - Никогда не коммитьте .env с реальными секретами в git")
    print("   - Для production используйте разные секреты на каждом окружении")
    print("=" * 60)


if __name__ == "__main__":
    main()
