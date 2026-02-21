"""
Тесты для ML endpoints (предсказание цен, аналитика, тренды).

Проверяют:
- Предсказание цены
- Сравнение цен
- Статистику цен по городам
- Оптимальное ценообразование
- Тренды рынка
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Тесты предсказания цены
# =============================================================================

class TestPricePrediction:
    """Тесты эндпоинта /api/ml/predict-price"""

    @pytest.mark.asyncio
    async def test_predict_price_success(self, client: AsyncClient):
        """Успешное предсказание цены"""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 54.5,
                "district": "ЦАО",
                "floor": 5,
                "total_floors": 12,
                "is_verified": True,
            }
        )
        # Эндпоинт должен вернуть предсказание даже без данных (дефолтное)
        assert response.status_code == 200
        data = response.json()
        assert "predicted_price" in data
        assert "confidence" in data
        assert "price_range" in data
        assert "trend" in data
        assert "recommendation" in data

    @pytest.mark.asyncio
    async def test_predict_price_minimal(self, client: AsyncClient):
        """Предсказание с минимальными параметрами"""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Санкт-Петербург",
                "rooms": 1,
                "area": 35.0,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "predicted_price" in data

    @pytest.mark.asyncio
    async def test_predict_price_invalid_rooms(self, client: AsyncClient):
        """Предсказание с некорректным количеством комнат"""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 15,  # Больше максимума (10)
                "area": 50.0,
            }
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_predict_price_invalid_area(self, client: AsyncClient):
        """Предсказание с некорректной площадью"""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 5,  # Меньше минимума (10)
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_predict_price_empty_city(self, client: AsyncClient):
        """Предсказание с пустым городом"""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "",
                "rooms": 2,
                "area": 50.0,
            }
        )
        assert response.status_code == 422


# =============================================================================
# Тесты статистики цен
# =============================================================================

class TestPriceStatistics:
    """Тесты эндпоинта /api/ml/price-statistics/{city}"""

    @pytest.mark.asyncio
    async def test_price_statistics_success(self, client: AsyncClient):
        """Получение статистики цен по городу"""
        response = await client.get(
            "/api/ml/price-statistics/Москва"
        )
        # Должен вернуть статистику даже без данных
        assert response.status_code == 200
        data = response.json()
        assert "city" in data or "count" in data or "average_price" in data

    @pytest.mark.asyncio
    async def test_price_statistics_with_rooms_filter(self, client: AsyncClient):
        """Статистика с фильтром по комнатам"""
        response = await client.get(
            "/api/ml/price-statistics/Санкт-Петербург",
            params={"rooms": 2}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_price_statistics_with_period(self, client: AsyncClient):
        """Статистика с указанием периода"""
        response = await client.get(
            "/api/ml/price-statistics/Екатеринбург",
            params={"days": 30}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_price_statistics_invalid_days(self, client: AsyncClient):
        """Статистика с некорректным периодом"""
        response = await client.get(
            "/api/ml/price-statistics/Москва",
            params={"days": 1000}  # Больше максимума (365)
        )
        assert response.status_code == 422


# =============================================================================
# Тесты сравнения цен
# =============================================================================

class TestPriceComparison:
    """Тесты эндпоинта /api/ml/compare-price"""

    @pytest.mark.asyncio
    async def test_compare_price_success(self, client: AsyncClient):
        """Успешное сравнение цены"""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": 50000,
                "city": "Москва",
                "rooms": 2,
                "area": 54.0,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "actual_price" in data
        assert "predicted_price" in data
        assert "difference" in data
        assert "percentage_difference" in data
        assert "rating" in data

    @pytest.mark.asyncio
    async def test_compare_price_with_district(self, client: AsyncClient):
        """Сравнение цены с указанием района"""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": 75000,
                "city": "Москва",
                "rooms": 3,
                "area": 80.0,
                "district": "ЗАО",
            }
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_compare_price_invalid_actual_price(self, client: AsyncClient):
        """Сравнение с некорректной ценой"""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": -1000,  # Отрицательная цена
                "city": "Москва",
                "rooms": 2,
                "area": 50.0,
            }
        )
        assert response.status_code == 422


# =============================================================================
# Тесты оптимального ценообразования
# =============================================================================

class TestOptimalPrice:
    """Тесты эндпоинта /api/ml/optimal-price"""

    @pytest.mark.asyncio
    async def test_optimal_price_success(self, client: AsyncClient):
        """Получение оптимальной цены"""
        response = await client.post(
            "/api/ml/optimal-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 54.0,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "optimal_price" in data
        assert "min_competitive" in data
        assert "max_competitive" in data
        assert "confidence" in data

    @pytest.mark.asyncio
    async def test_optimal_price_with_district(self, client: AsyncClient):
        """Оптимальная цена с районом"""
        response = await client.post(
            "/api/ml/optimal-price",
            json={
                "city": "Санкт-Петербург",
                "rooms": 1,
                "area": 40.0,
                "district": "Центральный",
            }
        )
        assert response.status_code == 200


# =============================================================================
# Тесты трендов рынка
# =============================================================================

class TestMarketTrend:
    """Тесты эндпоинта /api/ml/market-trend"""

    @pytest.mark.asyncio
    async def test_market_trend_success(self, client: AsyncClient):
        """Получение тренда рынка"""
        response = await client.get(
            "/api/ml/market-trend/Москва"
        )
        assert response.status_code == 200
        data = response.json()
        assert "city" in data
        assert "trend" in data
        assert "comment" in data

    @pytest.mark.asyncio
    async def test_market_trend_with_rooms(self, client: AsyncClient):
        """Тренд с фильтром по комнатам"""
        response = await client.get(
            "/api/ml/market-trend/Москва",
            params={"rooms": 2}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("rooms") == 2 or "city" in data

    @pytest.mark.asyncio
    async def test_market_trend_multiple_cities(self, client: AsyncClient):
        """Тренд для нескольких городов"""
        response = await client.get(
            "/api/ml/market-trend/multiple",
            params={"cities": "Москва,Санкт-Петербург,Екатеринбург"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "trends" in data


# =============================================================================
# Тесты рекомендаций
# =============================================================================

class TestPriceRecommendations:
    """Тесты эндпоинта /api/ml/recommendations"""

    @pytest.mark.asyncio
    async def test_recommendations_success(self, client: AsyncClient):
        """Получение рекомендаций"""
        response = await client.get(
            "/api/ml/recommendations",
            params={
                "city": "Москва",
                "budget": 50000,
                "rooms": 2,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_recommendations_with_district(self, client: AsyncClient):
        """Рекомендации с районом"""
        response = await client.get(
            "/api/ml/recommendations",
            params={
                "city": "Москва",
                "budget": 70000,
                "rooms": 3,
                "district": "ЗАО",
            }
        )
        assert response.status_code == 200
