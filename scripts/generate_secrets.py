#!/usr/bin/env python3
"""
Генератор безопасных секретов для RentScout.

Использование:
    python scripts/generate_secrets.py
    
Скрипт создаст файл .env с безопасными паролями или обновит существующий.
"""

import secrets
import string
import os
from pathlib import Path


def generate_secure_password(length: int = 32) -> str:
    """
    Генерирует криптографически стойкий пароль.
    
    Args:
        length: Длина пароля (минимум 16 символов)
    
    Returns:
        Безопасный пароль
    """
    if length < 16:
        length = 16
    
    # Используем все категории символов
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    # Гарантием наличие хотя бы одного символа каждой категории
    password_chars = list(password)
    password_chars[0] = secrets.choice(string.ascii_uppercase)
    password_chars[1] = secrets.choice(string.ascii_lowercase)
    password_chars[2] = secrets.choice(string.digits)
    password_chars[3] = secrets.choice("!@#$%^&*()-_=+")
    
    return ''.join(password_chars)


def generate_secret_key(length: int = 64) -> str:
    """
    Генерирует криптографически стойкий секретный ключ.
    
    Args:
        length: Длина ключа
    
    Returns:
        Секретный ключ в hex формате
    """
    return secrets.token_hex(length // 2)


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Проверяет сложность пароля.
    
    Args:
        password: Пароль для проверки
    
    Returns:
        Кортеж (валиден, список проблем)
    """
    problems = []
    
    if len(password) < 16:
        problems.append("Пароль должен быть не менее 16 символов")
    
    if not any(c.isupper() for c in password):
        problems.append("Пароль должен содержать заглавные буквы")
    
    if not any(c.islower() for c in password):
        problems.append("Пароль должен содержать строчные буквы")
    
    if not any(c.isdigit() for c in password):
        problems.append("Пароль должен содержать цифры")
    
    if not any(c in "!@#$%^&*()-_=+" for c in password):
        problems.append("Пароль должен содержать специальные символы")
    
    return len(problems) == 0, problems


def generate_env_file(env_path: Path, template_path: Path) -> None:
    """
    Создает .env файл с безопасными паролями на основе шаблона.
    
    Args:
        env_path: Путь к целевому .env файлу
        template_path: Путь к шаблону .env.example
    """
    if not template_path.exists():
        print(f"❌ Шаблон {template_path} не найден")
        return
    
    # Читаем шаблон
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Генерируем секреты
    postgres_password = generate_secure_password(32)
    redis_password = generate_secure_password(32)
    secret_key = generate_secret_key(64)
    jwt_secret = generate_secret_key(64)
    
    # Заменяем значения в шаблоне
    replacements = {
        'your_password': postgres_password,
        'your_secure_password': postgres_password,
        'redis_password': redis_password,
        'your_very_long_random_secret_key_change_this': secret_key,
        'another_secret_key_for_jwt': jwt_secret,
    }
    
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    # Записываем .env файл
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Создан файл {env_path}")
    print("\n📊 Сгенерированные секреты:")
    print(f"   POSTGRES_PASSWORD: {postgres_password[:8]}... (длина: {len(postgres_password)})")
    print(f"   REDIS_PASSWORD: {redis_password[:8]}... (длина: {len(redis_password)})")
    print(f"   SECRET_KEY: {secret_key[:16]}... (длина: {len(secret_key)})")
    print(f"   JWT_SECRET: {jwt_secret[:16]}... (длина: {len(jwt_secret)})")
    
    # Проверяем сложность паролей
    print("\n🔒 Проверка сложности паролей:")
    for name, pwd in [("POSTGRES_PASSWORD", postgres_password), ("REDIS_PASSWORD", redis_password)]:
        is_valid, problems = validate_password_strength(pwd)
        if is_valid:
            print(f"   ✅ {name}: соответствует требованиям")
        else:
            print(f"   ❌ {name}: не соответствует")
            for problem in problems:
                print(f"      - {problem}")


def main():
    """Основная функция."""
    project_root = Path(__file__).parent.parent
    env_path = project_root / ".env"
    template_path = project_root / ".env.example"
    
    print("🔐 RentScout Secret Generator\n")
    
    if env_path.exists():
        response = input(f"⚠️  Файл {env_path} уже существует. Перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("❌ Отменено")
            return
    
    generate_env_file(env_path, template_path)
    
    print("\n💡 Не забудьте:")
    print("   1. Сохраните эти секреты в надежном месте (менеджер паролей)")
    print("   2. Не коммитьте .env в git (он в .gitignore)")
    print("   3. Для production используйте environment variables или secrets manager")


if __name__ == "__main__":
    main()
