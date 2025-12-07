"""
Скрипт для запуска RentScout с проверкой зависимостей.
"""
import sys
import subprocess
import os
from pathlib import Path

def check_python_version():
    """Проверка версии Python."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python 3.9+ требуется. Текущая версия: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Проверка установленных зависимостей."""
    try:
        import fastapi
        import uvicorn
        import redis
        print("✅ Основные зависимости установлены")
        return True
    except ImportError as e:
        print(f"❌ Отсутствуют зависимости: {e}")
        print("\n💡 Установите зависимости:")
        print("   pip install -r requirements.txt")
        return False

def check_env_file():
    """Проверка наличия .env файла."""
    env_path = Path(".env")
    if not env_path.exists():
        print("⚠️  Файл .env не найден")
        print("💡 Создаю минимальный .env файл...")
        with open(".env", "w", encoding="utf-8") as f:
            f.write("APP_NAME=RentScout\n")
            f.write("DEBUG=true\n")
            f.write("LOG_LEVEL=INFO\n")
            f.write("REDIS_URL=redis://localhost:6379/0\n")
        print("✅ Создан файл .env с базовой конфигурацией")
    else:
        print("✅ Файл .env существует")
    return True

def check_redis():
    """Проверка доступности Redis."""
    try:
        import redis as redis_module
        r = redis_module.Redis(host='localhost', port=6379, socket_connect_timeout=1)
        r.ping()
        print("✅ Redis доступен")
        return True
    except Exception:
        print("⚠️  Redis недоступен (не критично)")
        print("💡 Запустите Redis или используйте Docker:")
        print("   docker run -d -p 6379:6379 redis:7-alpine")
        return False

def check_postgres():
    """Проверка доступности PostgreSQL."""
    try:
        import asyncpg
        print("✅ asyncpg установлен")
        # Простая проверка - не подключаемся, т.к. это async
        return True
    except ImportError:
        print("⚠️  asyncpg не установлен (опционально)")
        return False

def start_server(reload=True):
    """Запуск сервера."""
    print("\n" + "="*60)
    print("🚀 Запуск RentScout API...")
    print("="*60)
    print("\n📍 Сервер будет доступен по адресу:")
    print("   • API: http://127.0.0.1:8000")
    print("   • Документация: http://127.0.0.1:8000/docs")
    print("   • Метрики: http://127.0.0.1:8000/metrics")
    print("\n⏹️  Для остановки нажмите Ctrl+C")
    print("="*60 + "\n")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ]
    
    if reload:
        cmd.append("--reload")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n✅ Сервер остановлен")

def main():
    """Основная функция."""
    print("🔍 Проверка окружения RentScout...\n")
    
    checks = [
        ("Python версия", check_python_version),
        ("Зависимости", check_dependencies),
        (".env файл", check_env_file),
        ("Redis", check_redis),
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        results.append(result)
    
    # Критичны только первые 3 проверки
    if not all(results[:3]):
        print("\n❌ Критичные проверки не пройдены. Исправьте ошибки.")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✅ Все критичные проверки пройдены!")
    print("="*60)
    
    # Запуск сервера
    start_server(reload="--no-reload" not in sys.argv)

if __name__ == "__main__":
    main()
