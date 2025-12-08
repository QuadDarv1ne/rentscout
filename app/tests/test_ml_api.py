"""
Тесты для ML API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestPredictPriceEndpoint:
    """Тесты endpoint предсказания цен."""
    
    def test_predict_price_basic(self):
        """Базовое предсказание цены."""
        response = client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "predicted_price" in data
        assert "confidence" in data
        assert "price_range" in data
        assert "factors" in data
        assert "trend" in data
        assert "recommendation" in data
        
        assert data["predicted_price"] > 0
        assert 0 <= data["confidence"] <= 1
        assert len(data["price_range"]) == 2
    
    @pytest.mark.asyncio
    async def test_predict_price_with_district(self, client):
        """Предсказание с указанием района."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
                "district": "Центральный",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["factors"]["district"] > 1.0  # Элитный район
    
    @pytest.mark.asyncio
    async def test_predict_price_with_floor(self, client):
        """Предсказание с этажом."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
                "floor": 5,
                "total_floors": 10,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "floor" in data["factors"]
    
    @pytest.mark.asyncio
    async def test_predict_price_verified(self, client):
        """Предсказание для верифицированного объявления."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
                "is_verified": True,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["factors"]["verified"] > 1.0
    
    @pytest.mark.asyncio
    async def test_predict_price_validation_negative_rooms(self, client):
        """Валидация: отрицательное количество комнат."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": -1,
                "area": 60.0,
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_predict_price_validation_small_area(self, client):
        """Валидация: слишком маленькая площадь."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 5.0,  # Меньше минимума
            }
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_predict_price_validation_large_area(self, client):
        """Валидация: слишком большая площадь."""
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 1000.0,  # Больше максимума
            }
        )
        
        assert response.status_code == 422


class TestPriceStatisticsEndpoint:
    """Тесты endpoint статистики цен."""
    
    @pytest.mark.asyncio
    async def test_get_statistics_basic(self, client):
        """Базовая статистика."""
        response = await client.get("/api/ml/price-statistics/Москва")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert "avg_price" in data
        assert "min_price" in data
        assert "max_price" in data
        assert "median_price" in data
        assert "std_dev" in data
    
    @pytest.mark.asyncio
    async def test_get_statistics_with_rooms(self, client):
        """Статистика с фильтром по комнатам."""
        response = await client.get("/api/ml/price-statistics/Москва?rooms=2")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_statistics_with_custom_period(self, client):
        """Статистика за кастомный период."""
        response = await client.get("/api/ml/price-statistics/Москва?days=7")
        
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_get_statistics_validation_days(self, client):
        """Валидация: слишком большой период."""
        response = await client.get("/api/ml/price-statistics/Москва?days=500")
        
        assert response.status_code == 422


class TestComparePriceEndpoint:
    """Тесты endpoint сравнения цен."""
    
    @pytest.mark.asyncio
    async def test_compare_price_basic(self, client):
        """Базовое сравнение."""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": 50000.0,
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "actual_price" in data
        assert "predicted_price" in data
        assert "difference" in data
        assert "difference_percent" in data
        assert "rating" in data
        assert "comment" in data
    
    @pytest.mark.asyncio
    async def test_compare_price_overpriced(self, client):
        """Сравнение завышенной цены."""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": 100000.0,  # Очень дорого
                "city": "Москва",
                "rooms": 1,
                "area": 30.0,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == "overpriced"
        assert data["difference_percent"] > 0
    
    @pytest.mark.asyncio
    async def test_compare_price_with_district(self, client):
        """Сравнение с учётом района."""
        response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": 50000.0,
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
                "district": "Центральный",
            }
        )
        
        assert response.status_code == 200


class TestOptimalPriceEndpoint:
    """Тесты endpoint оптимальной цены."""
    
    @pytest.mark.asyncio
    async def test_get_optimal_price(self, client):
        """Получение оптимальной цены."""
        response = await client.get(
            "/api/ml/optimal-price/Москва?rooms=2&area=60.0"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "optimal_price" in data
        assert "min_competitive" in data
        assert "max_competitive" in data
        assert "market_average" in data
        assert "recommendation" in data
    
    @pytest.mark.asyncio
    async def test_optimal_price_validation(self, client):
        """Валидация параметров."""
        response = await client.get(
            "/api/ml/optimal-price/Москва?rooms=-1&area=60.0"
        )
        
        assert response.status_code == 422


class TestMarketTrendsEndpoint:
    """Тесты endpoint трендов рынка."""
    
    @pytest.mark.asyncio
    async def test_get_market_trends(self, client):
        """Получение трендов рынка."""
        response = await client.get("/api/ml/market-trends/Москва")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "city" in data
        assert "trend" in data
        assert "comment" in data
        assert "stats_7_days" in data
        assert "stats_30_days" in data
        assert "change_percentage" in data
    
    @pytest.mark.asyncio
    async def test_get_market_trends_with_rooms(self, client):
        """Тренды с фильтром по комнатам."""
        response = await client.get("/api/ml/market-trends/Москва?rooms=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["rooms"] == 2
    
    @pytest.mark.asyncio
    async def test_market_trends_structure(self, client):
        """Структура данных о трендах."""
        response = await client.get("/api/ml/market-trends/Москва")
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем структуру статистики
        for period in ["stats_7_days", "stats_30_days"]:
            assert "count" in data[period]
            assert "avg_price" in data[period]
            assert "min_price" in data[period]
            assert "max_price" in data[period]


class TestMLHealthEndpoint:
    """Тесты health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_ml_health(self, client):
        """Проверка здоровья ML сервиса."""
        response = await client.get("/api/ml/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "ml-predictions"
        assert "features" in data
        assert "model" in data
        assert "history_size" in data
        
        # Проверяем список фич
        features = data["features"]
        assert "price_prediction" in features
        assert "price_comparison" in features
        assert "market_trends" in features


class TestMLIntegration:
    """Интеграционные тесты ML API."""
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, client):
        """Полный рабочий процесс: предсказание -> сравнение -> оптимизация."""
        # 1. Предсказываем цену
        predict_response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
            }
        )
        assert predict_response.status_code == 200
        predicted = predict_response.json()
        
        # 2. Сравниваем с рыночной ценой
        compare_response = await client.post(
            "/api/ml/compare-price",
            json={
                "actual_price": predicted["predicted_price"] * 1.1,
                "city": "Москва",
                "rooms": 2,
                "area": 60.0,
            }
        )
        assert compare_response.status_code == 200
        
        # 3. Получаем оптимальную цену
        optimal_response = await client.get(
            "/api/ml/optimal-price/Москва?rooms=2&area=60.0"
        )
        assert optimal_response.status_code == 200
        optimal = optimal_response.json()
        
        # Проверяем, что оптимальная цена в разумных пределах
        assert optimal["min_competitive"] < optimal["optimal_price"]
        assert optimal["optimal_price"] < optimal["max_competitive"]
    
    @pytest.mark.asyncio
    async def test_different_cities_comparison(self, client):
        """Сравнение цен в разных городах."""
        cities = ["Москва", "Санкт-Петербург", "Казань"]
        results = []
        
        for city in cities:
            response = await client.post(
                "/api/ml/predict-price",
                json={
                    "city": city,
                    "rooms": 2,
                    "area": 60.0,
                }
            )
            assert response.status_code == 200
            results.append(response.json())
        
        # Москва дороже других
        assert results[0]["predicted_price"] > results[1]["predicted_price"]
        assert results[0]["predicted_price"] > results[2]["predicted_price"]
    
    @pytest.mark.asyncio
    async def test_market_analysis_workflow(self, client):
        """Анализ рынка: статистика + тренды."""
        # Получаем статистику
        stats_response = await client.get("/api/ml/price-statistics/Москва?rooms=2")
        assert stats_response.status_code == 200
        
        # Получаем тренды
        trends_response = await client.get("/api/ml/market-trends/Москва?rooms=2")
        assert trends_response.status_code == 200
        
        trends = trends_response.json()
        assert trends["trend"] in ["increasing", "decreasing", "stable", "unknown"]
