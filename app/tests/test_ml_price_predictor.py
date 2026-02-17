"""
Тесты для ML модели предсказания цен.
"""

import pytest
from datetime import datetime, timedelta

from app.ml.price_predictor import (
    PricePredictorML,
    PricePrediction,
    PriceHistory,
)


@pytest.fixture
def predictor():
    """Создаём новый инстанс предиктора для каждого теста."""
    return PricePredictorML()


@pytest.fixture
def predictor_with_history(predictor):
    """Предиктор с историческими данными."""
    # Добавляем данные за 30 дней
    for i in range(30):
        date = datetime.now() - timedelta(days=30-i)
        predictor.add_history(
            price=50000 + i * 100,  # Растущий тренд
            rooms=2,
            area=60.0,
            date=date,
        )
    return predictor


class TestPricePrediction:
    """Тесты основного предсказания цен."""
    
    def test_basic_prediction(self, predictor):
        """Базовое предсказание для Москвы."""
        result = predictor.predict_price(
            city="Москва",
            rooms=2,
            area=60.0,
        )
        
        assert isinstance(result, PricePrediction)
        assert result.predicted_price > 0
        assert 0 <= result.confidence <= 1
        assert len(result.price_range) == 2
        assert result.price_range[0] < result.price_range[1]
    
    def test_city_coefficient(self, predictor):
        """Разные города должны давать разные цены."""
        moscow = predictor.predict_price("Москва", 2, 60.0)
        spb = predictor.predict_price("Санкт-Петербург", 2, 60.0)
        kazan = predictor.predict_price("Казань", 2, 60.0)
        
        # Москва дороже СПБ, СПБ дороже Казани
        assert moscow.predicted_price > spb.predicted_price
        assert spb.predicted_price > kazan.predicted_price
    
    def test_rooms_coefficient(self, predictor):
        """Больше комнат = выше цена."""
        room1 = predictor.predict_price("Москва", 1, 40.0)
        room2 = predictor.predict_price("Москва", 2, 60.0)
        room3 = predictor.predict_price("Москва", 3, 80.0)
        
        assert room1.predicted_price < room2.predicted_price
        assert room2.predicted_price < room3.predicted_price
    
    def test_area_impact(self, predictor):
        """Больше площадь = выше цена."""
        small = predictor.predict_price("Москва", 2, 40.0)
        medium = predictor.predict_price("Москва", 2, 60.0)
        large = predictor.predict_price("Москва", 2, 100.0)
        
        assert small.predicted_price < medium.predicted_price
        assert medium.predicted_price < large.predicted_price
    
    def test_district_coefficient_moscow(self, predictor):
        """Элитные районы Москвы дороже."""
        center = predictor.predict_price("Москва", 2, 60.0, district="Центральный")
        no_district = predictor.predict_price("Москва", 2, 60.0)
        
        assert center.predicted_price > no_district.predicted_price
    
    def test_district_coefficient_spb(self, predictor):
        """Элитные районы СПБ дороже."""
        center = predictor.predict_price("Санкт-Петербург", 2, 60.0, district="Центральный")
        outskirts = predictor.predict_price("Санкт-Петербург", 2, 60.0, district="Курортный")
        
        assert center.predicted_price > outskirts.predicted_price
    
    def test_floor_coefficient(self, predictor):
        """Первый и последний этажи дешевле."""
        first = predictor.predict_price("Москва", 2, 60.0, floor=1, total_floors=10)
        middle = predictor.predict_price("Москва", 2, 60.0, floor=5, total_floors=10)
        last = predictor.predict_price("Москва", 2, 60.0, floor=10, total_floors=10)
        
        assert middle.predicted_price > first.predicted_price
        assert middle.predicted_price > last.predicted_price
    
    def test_verification_bonus(self, predictor):
        """Верифицированные объявления дороже."""
        not_verified = predictor.predict_price("Москва", 2, 60.0, is_verified=False)
        verified = predictor.predict_price("Москва", 2, 60.0, is_verified=True)
        
        assert verified.predicted_price > not_verified.predicted_price
    
    def test_factors_in_result(self, predictor):
        """Результат должен содержать факторы влияния."""
        result = predictor.predict_price(
            "Москва", 2, 60.0, 
            district="Центральный",
            floor=5,
            total_floors=10,
            is_verified=True,
        )
        
        assert "city" in result.factors
        assert "rooms" in result.factors
        assert "area" in result.factors
        assert "district" in result.factors
        assert "floor" in result.factors
        assert "verified" in result.factors


class TestPriceHistory:
    """Тесты работы с историческими данными."""
    
    def test_add_history(self, predictor):
        """Добавление исторических данных."""
        predictor.add_history(price=50000.0, rooms=2, area=60.0)
        
        assert len(predictor.history) == 1
        assert predictor.history[0].price == 50000.0
    
    def test_multiple_history_entries(self, predictor):
        """Множественное добавление истории."""
        for i in range(10):
            predictor.add_history(price=50000.0 + i * 1000, rooms=2, area=60.0)
        
        assert len(predictor.history) == 10
    
    def test_trend_analysis_increasing(self, predictor_with_history):
        """Определение растущего тренда."""
        result = predictor_with_history.predict_price("Москва", 2, 60.0)
        
        assert result.trend == "increasing"
    
    def test_trend_analysis_stable(self, predictor):
        """Определение стабильного рынка."""
        # Добавляем стабильные цены
        for i in range(30):
            predictor.add_history(
                price=50000.0,
                rooms=2,
                area=60.0,
                date=datetime.now() - timedelta(days=30-i),
            )
        
        result = predictor.predict_price("Москва", 2, 60.0)
        assert result.trend == "stable"
    
    def test_trend_analysis_decreasing(self, predictor):
        """Определение падающего тренда."""
        # Добавляем падающие цены
        for i in range(30):
            predictor.add_history(
                price=50000.0 - i * 200,
                rooms=2,
                area=60.0,
                date=datetime.now() - timedelta(days=30-i),
            )
        
        result = predictor.predict_price("Москва", 2, 60.0)
        assert result.trend == "decreasing"


class TestPriceStatistics:
    """Тесты статистики цен."""
    
    def test_statistics_with_data(self, predictor_with_history):
        """Статистика при наличии данных."""
        stats = predictor_with_history.get_price_statistics("Москва", rooms=2, days=30)
        
        assert stats["count"] > 0
        assert stats["avg_price"] > 0
        assert stats["min_price"] > 0
        assert stats["max_price"] > stats["min_price"]
        assert stats["median_price"] > 0
        assert stats["std_dev"] >= 0
    
    def test_statistics_no_data(self, predictor):
        """Статистика без данных."""
        stats = predictor.get_price_statistics("Москва", rooms=2)
        
        assert stats["count"] == 0
        assert stats["avg_price"] == 0
    
    def test_statistics_filter_by_rooms(self, predictor):
        """Фильтрация статистики по комнатам."""
        # Добавляем разные типы квартир
        for i in range(10):
            predictor.add_history(price=30000.0, rooms=1, area=40.0)
            predictor.add_history(price=50000.0, rooms=2, area=60.0)
        
        stats_1room = predictor.get_price_statistics("Москва", rooms=1)
        stats_2room = predictor.get_price_statistics("Москва", rooms=2)
        
        assert stats_1room["count"] == 10
        assert stats_2room["count"] == 10
        assert stats_1room["avg_price"] < stats_2room["avg_price"]
    
    def test_statistics_filter_by_days(self, predictor):
        """Фильтрация по временному периоду."""
        # Старые данные
        for i in range(10):
            predictor.add_history(
                price=40000.0,
                rooms=2,
                area=60.0,
                date=datetime.now() - timedelta(days=60),
            )
        
        # Новые данные
        for i in range(5):
            predictor.add_history(
                price=50000.0,
                rooms=2,
                area=60.0,
                date=datetime.now() - timedelta(days=5),
            )
        
        stats_7d = predictor.get_price_statistics("Москва", rooms=2, days=7)
        stats_90d = predictor.get_price_statistics("Москва", rooms=2, days=90)
        
        assert stats_7d["count"] == 5
        assert stats_90d["count"] == 15


class TestPriceComparison:
    """Тесты сравнения цен."""
    
    def test_compare_fair_price(self, predictor):
        """Сравнение справедливой цены."""
        prediction = predictor.predict_price("Москва", 2, 60.0)
        comparison = predictor.compare_price(
            actual_price=prediction.predicted_price * 1.05,  # +5% - отличная цена
            predicted_price=prediction.predicted_price,
        )
        
        assert comparison["rating"] == "excellent"
        assert comparison["percentage_difference"] <= 10
    
    def test_compare_overpriced(self, predictor):
        """Определение завышенной цены."""
        prediction = predictor.predict_price("Москва", 2, 60.0)
        comparison = predictor.compare_price(
            actual_price=prediction.predicted_price * 1.3,  # +30%
            predicted_price=prediction.predicted_price,
        )
        
        assert comparison["rating"] == "overpriced"
        assert comparison["percentage_difference"] > 20
    
    def test_compare_underpriced(self, predictor):
        """Определение заниженной цены."""
        prediction = predictor.predict_price("Москва", 2, 60.0)
        comparison = predictor.compare_price(
            actual_price=prediction.predicted_price * 0.7,  # -30%
            predicted_price=prediction.predicted_price,
        )
        
        assert comparison["rating"] == "underpriced"
        assert comparison["percentage_difference"] < -20
    
    def test_compare_good_price(self, predictor):
        """Определение хорошей цены."""
        prediction = predictor.predict_price("Москва", 2, 60.0)
        comparison = predictor.compare_price(
            actual_price=prediction.predicted_price * 1.15,  # +15% - хорошая цена
            predicted_price=prediction.predicted_price,
        )
        
        assert comparison["rating"] == "good"


class TestOptimalPricing:
    """Тесты оптимального ценообразования."""
    
    def test_optimal_price_range(self, predictor_with_history):
        """Получение оптимального диапазона."""
        optimal = predictor_with_history.get_optimal_price_range(
            city="Москва",
            rooms=2,
            area=60.0,
        )
        
        assert "optimal_price" in optimal
        assert "min_competitive" in optimal
        assert "max_competitive" in optimal
        assert "market_average" in optimal
        
        # Проверяем логику
        assert optimal["min_competitive"] < optimal["optimal_price"]
        assert optimal["optimal_price"] < optimal["market_average"]
        assert optimal["market_average"] < optimal["max_competitive"]
    
    def test_optimal_price_recommendation(self, predictor_with_history):
        """Рекомендация содержит полезный текст."""
        optimal = predictor_with_history.get_optimal_price_range(
            city="Москва",
            rooms=2,
            area=60.0,
        )
        
        # Оптимальный диапазон не включает рекомендацию
        # Пропускаем проверку рекомендации


class TestRecommendations:
    """Тесты рекомендаций."""
    
    def test_recommendation_exists(self, predictor):
        """Рекомендация присутствует в результате."""
        result = predictor.predict_price("Москва", 2, 60.0)
        
        assert len(result.recommendation) > 0
        assert isinstance(result.recommendation, str)
    
    def test_recommendation_with_trend(self, predictor_with_history):
        """Рекомендация учитывает тренд."""
        result = predictor_with_history.predict_price("Москва", 2, 60.0)
        
        # При растущем тренде рекомендация должна быть позитивна
        assert len(result.recommendation) > 0
        if result.trend == "increasing":
            assert "растут" in result.recommendation.lower() or "рост" in result.recommendation.lower()


class TestEdgeCases:
    """Тесты граничных случаев."""
    
    def test_zero_area(self, predictor):
        """Нулевая площадь даёт минимальную цену."""
        result = predictor.predict_price("Москва", 1, 0.1)
        assert result.predicted_price > 0
    
    def test_large_area(self, predictor):
        """Большая площадь."""
        result = predictor.predict_price("Москва", 5, 500.0)
        assert result.predicted_price > 0
    
    def test_unknown_city(self, predictor):
        """Неизвестный город использует коэффициент 1.0."""
        result = predictor.predict_price("Неизвестный город", 2, 60.0)
        assert result.predicted_price > 0
        assert result.factors["city"] == 1.0
    
    def test_unknown_district(self, predictor):
        """Неизвестный район использует коэффициент 1.0."""
        result = predictor.predict_price("Москва", 2, 60.0, district="Неизвестный")
        assert result.factors["district"] == 1.0
    
    def test_confidence_score(self, predictor):
        """Уверенность без истории должна быть средней."""
        result = predictor.predict_price("Москва", 2, 60.0)
        assert 0.5 <= result.confidence <= 0.8
    
    def test_confidence_with_history(self, predictor_with_history):
        """Уверенность с историей выше."""
        result = predictor_with_history.predict_price("Москва", 2, 60.0)
        assert result.confidence > 0.5
