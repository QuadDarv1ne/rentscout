#!/usr/bin/env python3
"""
API Endpoints Validation Script

Проверяет все новые эндпоинты и их доступность.
"""

import httpx
import asyncio
from typing import List, Dict, Any

# Базовый URL
BASE_URL = "http://localhost:8000"

# Группы эндпоинтов
ENDPOINTS = {
    "metrics": [
        ("/api/metrics/health", "GET"),
        ("/api/metrics/summary", "GET"),
        ("/api/metrics/parsers", "GET"),
        ("/api/metrics/cache", "GET"),
        ("/api/metrics/api-endpoints", "GET"),
        ("/api/metrics/system", "GET"),
        ("/api/metrics/quality-report", "GET"),
    ],
    "batch": [
        ("/api/batch/health", "GET"),
        ("/api/batch/info", "GET"),
        ("/api/batch/summary", "GET"),
        ("/api/batch/recommendations", "GET"),
        ("/api/batch/performance", "GET"),
    ],
    "errors": [
        ("/api/errors/health", "GET"),
        ("/api/errors/summary", "GET"),
        ("/api/errors/top-errors", "GET"),
        ("/api/errors/circuit-breaker/status", "GET"),
        ("/api/errors/stats", "GET"),
    ],
    "duplicates": [
        ("/api/duplicates/health", "GET"),
        ("/api/duplicates/statistics", "GET"),
        ("/api/duplicates/trends", "GET"),
        ("/api/duplicates/recommendations", "POST"),
    ],
    "cache-optimization": [
        ("/api/cache-optimization/health", "GET"),
        ("/api/cache-optimization/stats", "GET"),
        ("/api/cache-optimization/compression", "GET"),
        ("/api/cache-optimization/memory-usage", "GET"),
        ("/api/cache-optimization/hit-ratio", "GET"),
        ("/api/cache-optimization/recommendations", "GET"),
    ],
    "system": [
        ("/api/system/health", "GET"),
        ("/api/system/info", "GET"),
        ("/api/system/resources", "GET"),
        ("/api/system/diagnostics", "GET"),
        ("/api/system/status", "GET"),
    ],
}


async def check_endpoint(
    client: httpx.AsyncClient,
    endpoint: str,
    method: str = "GET"
) -> Dict[str, Any]:
    """Check single endpoint."""
    try:
        url = f"{BASE_URL}{endpoint}"
        
        if method == "GET":
            response = await client.get(url, timeout=5.0)
        elif method == "POST":
            response = await client.post(url, timeout=5.0)
        else:
            return {
                "endpoint": endpoint,
                "method": method,
                "status": "error",
                "error": "Unknown method"
            }
        
        return {
            "endpoint": endpoint,
            "method": method,
            "status": "ok" if response.status_code < 400 else "error",
            "status_code": response.status_code,
        }
    except Exception as e:
        return {
            "endpoint": endpoint,
            "method": method,
            "status": "error",
            "error": str(e)
        }


async def validate_all_endpoints():
    """Validate all endpoints."""
    async with httpx.AsyncClient() as client:
        print("🔍 Проверка всех новых эндпоинтов...\n")
        
        all_results = []
        
        for group, endpoints in ENDPOINTS.items():
            print(f"📍 Группа: {group}")
            print("-" * 50)
            
            group_results = []
            for endpoint, method in endpoints:
                result = await check_endpoint(client, endpoint, method)
                group_results.append(result)
                
                status_emoji = "✅" if result["status"] == "ok" else "❌"
                status_code = result.get("status_code", "N/A")
                print(f"{status_emoji} {method:4} {endpoint:40} [{status_code}]")
            
            all_results.extend(group_results)
            print()
        
        # Summary
        ok_count = sum(1 for r in all_results if r["status"] == "ok")
        error_count = len(all_results) - ok_count
        
        print("=" * 50)
        print(f"✅ OK: {ok_count}/{len(all_results)}")
        print(f"❌ Errors: {error_count}/{len(all_results)}")
        
        if error_count == 0:
            print("\n🎉 Все эндпоинты работают корректно!")
        else:
            print("\n⚠️ Найдены ошибки. Проверьте логи приложения.")
        
        return all_results


if __name__ == "__main__":
    results = asyncio.run(validate_all_endpoints())
