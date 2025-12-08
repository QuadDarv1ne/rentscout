"""
ML модель для прогнозирования цен на аренду недвижимости.

Использует простую линейную регрессию и исторические данные для предсказания цен.
В production можно заменить на более сложные модели (Random Forest, XGBoost).
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics
import math

from app.utils.logger import logger


@dataclass
class PricePrediction:
    """Результат предсказания цены."""
    predicted_price: float
    confidence: float  # 0-1
    price_range: Tuple[float, float]  # (min, max)
    factors: Dict[str, float]  # Факторы, влияющие на цену
    trend: str  # "increasing", "stable", "decreasing"
    recommendation: str


@dataclass
class PriceHistory:
    """Исторические данные по ценам."""
    date: str  # ISO format datetime string
    price: float
    source: str
    rooms: Optional[int] = None
    area: Optional[float] = None


class PricePredictorML:
    """ML модель для прогнозирования цен."""
    
    def __init__(self):
        self.history: List[PriceHistory] = []
        self.city_coefficients: Dict[str, float] = {
            "Москва": 1.5,
            "Санкт-Петербург": 1.2,
            "Казань": 0.8,
            "Новосибирск": 0.7,
            "Екатеринбург": 0.75,
        }
        self.district_coefficients: Dict[str, Dict[str, float]] = {
            "Москва": {
                "Центральный": 1.8,
                "Тверской": 1.7,
                "Арбат": 1.9,
                "Таганский": 1.3,
                "Измайлово": 0.9,
            },
            "Санкт-Петербург": {
                "Центральный": 1.6,
                "Петроградский": 1.5,
                "Василеостровский": 1.4,
                "Невский": 1.2,
            }
        }
    
    def add_history(
        self,
        date: datetime,
        price: float,
        source: str,
        rooms: Optional[int] = None,
        area: Optional[float] = None,
    ):
        """Добавить историческую запись о цене."""
        self.history.append(
            PriceHistory(
                date=date,
                price=price,
                source=source,
                rooms=rooms,
                area=area,
            )
        )
    
    def predict_price(
        self,
        city: str,
        rooms: int,
        area: float,
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        is_verified: bool = False,
    ) -> PricePrediction:
        """
        Предсказать цену аренды на основе характеристик.
        
        Использует:
        - Базовая цена за м² для города
        - Коэффициенты района
        - Количество комнат
        - Этаж и состояние
        - Исторические данные
        """
        # Базовая цена за м² по городам
        base_price_per_sqm = {
            "Москва": 1500,
            "Санкт-Петербург": 1200,
            "Казань": 800,
            "Новосибирск": 700,
            "Екатеринбург": 750,
        }
        
        base_price = base_price_per_sqm.get(city, 600)
        
        # Фактор 1: Площадь
        area_price = base_price * area
        area_factor = 1.0
        
        # Фактор 2: Количество комнат
        rooms_factor = 1.0 + (rooms - 1) * 0.15  # +15% за каждую комнату
        
        # Фактор 3: Город
        city_factor = self.city_coefficients.get(city, 1.0)
        
        # Фактор 4: Район
        district_factor = 1.0
        if district and city in self.district_coefficients:
            district_factor = self.district_coefficients[city].get(district, 1.0)
        
        # Фактор 5: Этаж
        floor_factor = 1.0
        if floor and total_floors:
            if floor == 1:
                floor_factor = 0.95  # Первый этаж обычно дешевле
            elif floor == total_floors:
                floor_factor = 0.97  # Последний этаж тоже дешевле
            else:
                floor_factor = 1.0
        
        # Фактор 6: Верификация
        verified_factor = 1.1 if is_verified else 1.0
        
        # Итоговая цена
        predicted_price = (
            area_price
            * rooms_factor
            * city_factor
            * district_factor
            * floor_factor
            * verified_factor
        )
        
        # Анализ исторических данных для корректировки
        if self.history:
            cutoff = datetime.now() - timedelta(days=30)
            recent_prices = [
                h.price for h in self.history
                if datetime.fromisoformat(h.date) >= cutoff
            ]
            
            if recent_prices:
                avg_historical = statistics.mean(recent_prices)
                # Корректируем предсказание на основе исторических данных
                predicted_price = (predicted_price * 0.7) + (avg_historical * 0.3)
        
        # Диапазон цен (±15%)
        price_range = (
            predicted_price * 0.85,
            predicted_price * 1.15,
        )
        
        # Уверенность модели
        confidence = 0.75
        if is_verified:
            confidence += 0.1
        if district:
            confidence += 0.05
        if self.history:
            confidence += 0.1
        confidence = min(confidence, 0.95)
        
        # Определение тренда
        trend = self._analyze_trend(city, rooms)
        
        # Рекомендация
        recommendation = self._generate_recommendation(
            predicted_price,
            trend,
            confidence,
        )
        
        # Факторы влияния
        factors = {
            "area": area_factor,
            "rooms": rooms_factor,
            "city": city_factor,
            "district": district_factor,
            "floor": floor_factor,
            "verified": verified_factor,
        }
        
        logger.info(
            f"Price prediction: {predicted_price:.0f} RUB "
            f"for {rooms}-room, {area}m² in {city}"
        )
        
        return PricePrediction(
            predicted_price=round(predicted_price, 2),
            confidence=round(confidence, 2),
            price_range=(round(price_range[0], 2), round(price_range[1], 2)),
            factors=factors,
            trend=trend,
            recommendation=recommendation,
        )
    
    def add_history(
        self,
        price: float,
        source: str = "manual",
        rooms: Optional[int] = None,
        area: Optional[float] = None,
        date: Optional[datetime] = None,
    ):
        """Добавить исторические данные о цене."""
        if date is None:
            date = datetime.now()
        
        self.history.append(PriceHistory(
            date=date.isoformat(),
            price=price,
            source=source,
            rooms=rooms,
            area=area,
        ))
    
    def _analyze_trend(self, city: str, rooms: Optional[int] = None) -> str:
        """Анализ тренда цен на основе истории."""
        if not self.history:
            return "stable"
        
        # Фильтруем релевантные данные (за последние 30 дней)
        cutoff = datetime.now() - timedelta(days=30)
        recent = [h for h in self.history if datetime.fromisoformat(h.date) >= cutoff]
        
        if rooms:
            recent = [h for h in recent if h.rooms == rooms]
        
        if len(recent) < 3:
            return "stable"
        
        # Сортируем по дате
        recent.sort(key=lambda x: x.date)
        
        # Сравниваем первую и вторую половины
        mid = len(recent) // 2
        first_half_avg = statistics.mean([h.price for h in recent[:mid]])
        second_half_avg = statistics.mean([h.price for h in recent[mid:]])
        
        change = (second_half_avg - first_half_avg) / first_half_avg
        
        if change > 0.02:  # 2% порог вместо 5%
            return "increasing"
        elif change < -0.02:
            return "decreasing"
        else:
            return "stable"
    
    def _generate_recommendation(
        self,
        predicted_price: float,
        trend: str,
        confidence: float,
    ) -> str:
        """Генерация рекомендации на основе предсказания."""
        if trend == "increasing":
            return (
                f"Цены растут. Рекомендуется арендовать сейчас. "
                f"Ожидаемая цена: {predicted_price:.0f} ₽"
            )
        elif trend == "decreasing":
            return (
                f"Цены снижаются. Можно подождать лучших предложений. "
                f"Ожидаемая цена: {predicted_price:.0f} ₽"
            )
        else:
            return (
                f"Рынок стабилен. Хорошее время для аренды. "
                f"Ожидаемая цена: {predicted_price:.0f} ₽"
            )
    
    def get_price_statistics(
        self,
        city: str,
        rooms: Optional[int] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Получить статистику цен за период."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        relevant = [
            h for h in self.history
            if datetime.fromisoformat(h.date) >= cutoff_date
        ]
        
        if rooms:
            relevant = [h for h in relevant if h.rooms == rooms]
        
        if not relevant:
            return {
                "count": 0,
                "avg_price": 0,
                "min_price": 0,
                "max_price": 0,
                "median_price": 0,
                "std_dev": 0,
            }
        
        prices = [h.price for h in relevant]
        
        return {
            "count": len(prices),
            "avg_price": round(statistics.mean(prices), 2),
            "min_price": round(min(prices), 2),
            "max_price": round(max(prices), 2),
            "median_price": round(statistics.median(prices), 2),
            "std_dev": round(statistics.stdev(prices), 2) if len(prices) > 1 else 0,
        }
    
    def compare_price(
        self,
        actual_price: float,
        predicted_price: float,
    ) -> Dict[str, Any]:
        """Сравнить реальную и предсказанную цены."""
        difference = actual_price - predicted_price
        percentage = (difference / predicted_price) * 100
        
        if abs(percentage) <= 10:
            rating = "excellent"
            comment = "Цена соответствует рыночной"
        elif abs(percentage) <= 20:
            rating = "good"
            comment = "Цена близка к рыночной"
        elif percentage > 20:
            rating = "overpriced"
            comment = "Цена выше рыночной"
        else:
            rating = "underpriced"
            comment = "Цена ниже рыночной (возможно выгодное предложение)"
        
        return {
            "actual_price": actual_price,
            "predicted_price": predicted_price,
            "difference": round(difference, 2),
            "difference_percent": round(percentage, 2),
            "rating": rating,
            "comment": comment,
        }
    
    def get_optimal_price_range(
        self,
        city: str,
        rooms: int,
        area: float,
    ) -> Dict[str, Any]:
        """Получить оптимальный диапазон цен для быстрой аренды."""
        prediction = self.predict_price(city, rooms, area)
        
        # Оптимальная цена - немного ниже предсказанной
        optimal_price = prediction.predicted_price * 0.95
        
        return {
            "optimal_price": round(optimal_price, 2),
            "min_competitive": round(prediction.price_range[0], 2),
            "max_competitive": round(prediction.price_range[1], 2),
            "market_average": round(prediction.predicted_price, 2),
            "recommendation": f"Рекомендуем цену {optimal_price:.0f} ₽ для быстрой аренды",
        }


# Глобальный экземпляр
price_predictor = PricePredictorML()
