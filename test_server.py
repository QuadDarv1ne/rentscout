#!/usr/bin/env python3
"""
Тестирование запущенного сервера RentScout
Проверяет основные endpoints и функциональность
"""
import asyncio
import httpx
import sys
import json
from datetime import datetime

async def test_server():
    """Основная функция тестирования"""
    
    BASE_URL = "http://127.0.0.1:8000"
    
    print("=" * 60)
    print("🧪 Тестирование сервера RentScout")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Тест 1: Health check
        print("\n1️⃣  Проверка здоровья приложения...")
        try:
            resp = await client.get(f"{BASE_URL}/health")
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 200:
                print(f"   Response: {resp.json()}")
                print("   ✅ Health check passed")
            else:
                print(f"   ❌ Unexpected status: {resp.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Тест 2: OpenAPI schema
        print("\n2️⃣  Проверка OpenAPI schema...")
        try:
            resp = await client.get(f"{BASE_URL}/openapi.json")
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"   ✅ OpenAPI available")
                print(f"   Title: {data.get('info', {}).get('title', 'N/A')}")
                print(f"   Version: {data.get('info', {}).get('version', 'N/A')}")
                print(f"   Endpoints: {len(data.get('paths', {}))}")
            else:
                print(f"   ❌ Unexpected status: {resp.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Тест 3: Swagger UI
        print("\n3️⃣  Проверка Swagger UI...")
        try:
            resp = await client.get(f"{BASE_URL}/docs")
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 200:
                print("   ✅ Swagger UI available")
            else:
                print(f"   ⚠️  Status: {resp.status_code}")
        except Exception as e:
            print(f"   ⚠️  Note: {e}")
        
        # Тест 4: ReDoc
        print("\n4️⃣  Проверка ReDoc...")
        try:
            resp = await client.get(f"{BASE_URL}/redoc")
            print(f"   Status: {resp.status_code}")
            if resp.status_code == 200:
                print("   ✅ ReDoc available")
            else:
                print(f"   ⚠️  Status: {resp.status_code}")
        except Exception as e:
            print(f"   ⚠️  Note: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Тестирование завершено")
    print("=" * 60)
    
    # Вывод инструкций
    print("\n📋 Следующие шаги:")
    print("1. Запустить сервер: python -m uvicorn app.main:app --reload")
    print("2. Открыть документацию: http://127.0.0.1:8000/docs")
    print("3. Проверить основные эндпоинты")
    print("4. Запустить Docker для полного стека:")
    print("   docker-compose -f docker-compose.dev.yml up -d")
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(test_server())
    sys.exit(exit_code)
