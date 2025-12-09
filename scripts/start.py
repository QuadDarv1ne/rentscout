"""
Скрипт для запуска RentScout с проверкой зависимостей.
"""
import sys
import subprocess
import os
from pathlib import Path

def check_python_version():
    """Проверка версии Python.
    
    Убедитесь, что версия Python не ниже 3.9.
    """
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Требуется Python 3.9+. У вас: {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_dependencies():
    """Проверка установленных зависимостей.
    
    Проверяет, установлены ли основные библиотеки:
    fastapi, uvicorn и redis.
    Если какая-либо библиотека отсутствует, выводит инструкцию по установке.
    """
    required_libs = ["fastapi", "uvicorn", "redis"]
    missing_libs = []
    for lib in required_libs:
        try:
            __import__(lib)
        except ImportError:
            missing_libs.append(lib)
    
    if missing_libs:
        print(f"❌ Отсутствуют зависимости: {', '.join(missing_libs)}")
        print("💡 Установите их с помощью:")
        print("   pip install -r requirements.txt")
        return False
    
    print("✅ Все основные зависимости установлены")
    return True

def check_env_file():
    """Проверка наличия файла .env.
    
    Если файл .env отсутствует, создаёт его с минимальной конфигурацией.
    """
    env_path = Path(".env")
    if not env_path.exists():
        print("⚠️  Файл .env не найден, создаю новый...")
        with open(".env", "w", encoding="utf-8") as f:
            f.write("APP_NAME=RentScout\nDEBUG=true\nLOG_LEVEL=INFO\nREDIS_URL=redis://localhost:6379/0\n")
        print("✅ Создан .env с базовой конфигурацией")
    else:
        print("✅ Файл .env существует")
    return True

def check_redis():
    """Проверка доступности Redis.
    
    Проверяет, запущен ли сервер Redis и доступен ли он для соединения.
    """
    try:
        import redis as redis_module
        r = redis_module.Redis(host='localhost', port=6379, socket_connect_timeout=1)
        r.ping()
        print("✅ Redis доступен")
        return True
    except Exception:
        print("⚠️  Redis недоступен (не критично)")
        print("💡 Запустите Redis или используйте Docker: docker run -d -p 6379:6379 redis:7-alpine")
        return False

def check_postgres():
    """Проверка доступности PostgreSQL.
    
    Проверяет наличие библиотеки asyncpg.
    Опциональная проверка соединения с PostgreSQL может быть добавлена.
    """
    try:
        import asyncpg
        print("✅ asyncpg установлен")
        # Можно добавить проверку соединения с БД
        return True
    except ImportError:
        print("⚠️  asyncpg не установлен (опционально)")
        return False

def start_server(reload=True):
    """Запуск сервера RentScout API.
    
    Осуществляет запуск API с помощью uvicorn.
    """
    print("\n" + "="*60)
    print("🚀 Запуск RentScout API...")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
    ]
    if reload:
        cmd.append("--reload")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n✅ Сервер остановлен")
    except FileNotFoundError:
        print("❌ uvicorn не установлен. Установите его с помощью pip.")

def main():
    """Основная функция программы.
    
    Выполняет последовательную проверку окружения и запускает сервер RentScout 
    при успешной верификации критичных зависимостей.
    """
    print("🔍 Проверка окружения RentScout...\n")
    
    checks = [
        ("Проверка версии Python", check_python_version),
        ("Проверка зависимостей", check_dependencies),
        (".env файл", check_env_file),
        ("Проверка Redis", check_redis),
        ("Проверка PostgreSQL", check_postgres),
    ]
    
    results = [check_func() for _, check_func in checks]
    
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
