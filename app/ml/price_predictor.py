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
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.compose import TransformedTargetRegressor

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
    district: Optional[str] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    is_verified: bool = False


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
                "Замоскворечье": 1.6,
                "Басманный": 1.4,
                "Пресненский": 1.5,
                "Красносельский": 1.2,
            },
            "Санкт-Петербург": {
                "Центральный": 1.6,
                "Петроградский": 1.5,
                "Василеостровский": 1.4,
                "Невский": 1.2,
                "Московский": 1.1,
                "Фрунзенский": 1.0,
            }
        }
        # Initialize ML models
        self.linear_model = LinearRegression()
        self.rf_model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
        self.scaler = StandardScaler()
        self.model_trained = False
        self.model_performance = {
            "linear_mae": 0.0,
            "rf_mae": 0.0,
            "linear_r2": 0.0,
            "rf_r2": 0.0,
            "linear_rmse": 0.0,
            "rf_rmse": 0.0,
            "cross_val_score_linear": 0.0,
            "cross_val_score_rf": 0.0
        }
        self.feature_names = [
            "rooms", 
            "area", 
            "floor_ratio", 
            "is_verified",
            "city_coefficient",
            "district_coefficient",
            "area_per_room"
        ]
    
    def add_history(
        self,
        date: datetime,
        price: float,
        source: str,
        rooms: Optional[int] = None,
        area: Optional[float] = None,
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        is_verified: bool = False,
    ):
        """Добавить историческую запись о цене."""
        self.history.append(
            PriceHistory(
                date=date.isoformat(),
                price=price,
                source=source,
                rooms=rooms,
                area=area,
                district=district,
                floor=floor,
                total_floors=total_floors,
                is_verified=is_verified,
            )
        )
    
    def train_model(self):
        """Train the ML models with historical data."""
        if len(self.history) < 20:
            logger.warning("Not enough data to train model. Need at least 20 samples.")
            return False
        
        # Prepare training data with enhanced features
        X = []
        y = []
        cities = list(self.city_coefficients.keys())
        
        for record in self.history:
            if record.rooms is not None and record.area is not None and record.area > 0:
                # Enhanced features
                floor_ratio = 0.5
                if record.floor and record.total_floors and record.total_floors > 0:
                    floor_ratio = record.floor / record.total_floors
                
                # City coefficient
                city_coeff = self.city_coefficients.get(record.city, 1.0) if record.city else 1.0
                
                # District coefficient
                district_coeff = 1.0
                if record.district and record.city:
                    district_coeff = self.district_coefficients.get(record.city, {}).get(record.district, 1.0)
                
                # Area per room
                area_per_room = record.area / max(record.rooms, 1)
                
                features = [
                    record.rooms,
                    record.area,
                    floor_ratio,
                    1.0 if record.is_verified else 0.0,
                    city_coeff,
                    district_coeff,
                    area_per_room
                ]
                X.append(features)
                y.append(record.price)
        
        if len(X) < 15:
            logger.warning(f"Not enough complete data samples for training. Have {len(X)}, need at least 15.")
            return False
        
        # Convert to numpy arrays
        X = np.array(X)
        y = np.array(y)
        
        # Split data for training and testing
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train linear regression model
        self.linear_model.fit(X_train_scaled, y_train)
        
        # Train random forest model
        self.rf_model.fit(X_train, y_train)
        
        # Evaluate models
        linear_pred = self.linear_model.predict(X_test_scaled)
        rf_pred = self.rf_model.predict(X_test)
        
        # Calculate metrics
        linear_mae = mean_absolute_error(y_test, linear_pred)
        rf_mae = mean_absolute_error(y_test, rf_pred)
        linear_r2 = r2_score(y_test, linear_pred)
        rf_r2 = r2_score(y_test, rf_pred)
        linear_rmse = np.sqrt(mean_squared_error(y_test, linear_pred))
        rf_rmse = np.sqrt(mean_squared_error(y_test, rf_pred))
        
        # Cross-validation scores
        try:
            cv_scores_linear = cross_val_score(self.linear_model, X_train_scaled, y_train, cv=5, scoring='r2')
            cv_scores_rf = cross_val_score(self.rf_model, X_train, y_train, cv=5, scoring='r2')
            cv_score_linear_mean = cv_scores_linear.mean()
            cv_score_rf_mean = cv_scores_rf.mean()
        except Exception as e:
            logger.warning(f"Cross-validation failed: {e}")
            cv_score_linear_mean = 0.0
            cv_score_rf_mean = 0.0
        
        self.model_performance = {
            "linear_mae": linear_mae,
            "rf_mae": rf_mae,
            "linear_r2": linear_r2,
            "rf_r2": rf_r2,
            "linear_rmse": linear_rmse,
            "rf_rmse": rf_rmse,
            "cross_val_score_linear": cv_score_linear_mean,
            "cross_val_score_rf": cv_score_rf_mean
        }
        
        self.model_trained = True
        
        logger.info(f"ML models trained with {len(X)} samples")
        logger.info(f"Linear Regression MAE: {linear_mae:.2f}, R²: {linear_r2:.3f}, RMSE: {linear_rmse:.2f}")
        logger.info(f"Random Forest MAE: {rf_mae:.2f}, R²: {rf_r2:.3f}, RMSE: {rf_rmse:.2f}")
        logger.info(f"Cross-validation scores - Linear: {cv_score_linear_mean:.3f}, RF: {cv_score_rf_mean:.3f}")
        
        return True
    
    def _get_city_base_price(self, city: str) -> float:
        """Get base price per square meter for a city."""
        base_price_per_sqm = {
            "Москва": 1500,
            "Санкт-Петербург": 1200,
            "Казань": 800,
            "Новосибирск": 700,
            "Екатеринбург": 750,
            "Краснодар": 850,
            "Самара": 650,
            "Воронеж": 600,
            "Волгоград": 550,
            "Пермь": 600,
        }
        return base_price_per_sqm.get(city, 600)
    
    def _get_district_multiplier(self, city: str, district: Optional[str]) -> float:
        """Get district multiplier for pricing."""
        if not district or city not in self.district_coefficients:
            return 1.0
        return self.district_coefficients[city].get(district, 1.0)
    
    def _get_floor_factor(self, floor: Optional[int], total_floors: Optional[int]) -> float:
        """Calculate floor factor for pricing."""
        if not floor or not total_floors or total_floors <= 0:
            return 1.0
            
        floor_ratio = floor / total_floors
        
        # Preferred floors are typically middle floors (0.3-0.7 ratio)
        if 0.3 <= floor_ratio <= 0.7:
            return 1.05  # Premium for middle floors
        elif floor == 1:
            return 0.95  # Discount for first floor
        elif floor == total_floors:
            return 0.97  # Slight discount for top floor
        else:
            return 1.0  # Standard pricing
    
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
        base_price = self._get_city_base_price(city)
        
        # Фактор 1: Площадь
        area_price = base_price * area
        area_factor = 1.0
        
        # Фактор 2: Количество комнат
        rooms_factor = 1.0 + (rooms - 1) * 0.15  # +15% за каждую комнату
        
        # Фактор 3: Город
        city_factor = self.city_coefficients.get(city, 1.0)
        
        # Фактор 4: Район
        district_factor = self._get_district_multiplier(city, district)
        
        # Фактор 5: Этаж
        floor_factor = self._get_floor_factor(floor, total_floors)
        
        # Фактор 6: Верификация
        verified_factor = 1.1 if is_verified else 1.0
        
        # Итоговая цена по правилам
        rule_based_price = (
            area_price
            * rooms_factor
            * city_factor
            * district_factor
            * floor_factor
            * verified_factor
        )
        
        # Используем ML модель если она обучена
        ml_prediction = None
        if self.model_trained:
            try:
                # Prepare enhanced features for prediction
                floor_ratio = 0.5
                if floor and total_floors and total_floors > 0:
                    floor_ratio = floor / total_floors
                
                # City coefficient
                city_coeff = self.city_coefficients.get(city, 1.0)
                
                # District coefficient
                district_coeff = 1.0
                if district and city:
                    district_coeff = self.district_coefficients.get(city, {}).get(district, 1.0)
                
                # Area per room
                area_per_room = area / max(rooms, 1)
                
                features_linear = [[rooms, area, floor_ratio, 1.0 if is_verified else 0.0, city_coeff, district_coeff, area_per_room]]
                features_rf = [[rooms, area, floor_ratio, 1.0 if is_verified else 0.0, city_coeff, district_coeff, area_per_room]]
                
                # Scale features for linear model
                features_linear_scaled = self.scaler.transform(features_linear)
                
                # Get predictions
                linear_pred = self.linear_model.predict(features_linear_scaled)[0]
                rf_pred = self.rf_model.predict(features_rf)[0]
                
                # Dynamic weighting based on model performance
                linear_weight = max(0.1, self.model_performance["linear_r2"]) if self.model_performance["linear_r2"] > 0 else 0.1
                rf_weight = max(0.1, self.model_performance["rf_r2"]) if self.model_performance["rf_r2"] > 0 else 0.1
                
                # Normalize weights
                total_weight = linear_weight + rf_weight
                if total_weight > 0:
                    linear_weight /= total_weight
                    rf_weight /= total_weight
                else:
                    linear_weight = rf_weight = 0.45  # Equal split if no performance data
                
                # Weighted ensemble: dynamic weights based on performance + rule-based
                rule_weight = 0.1  # Reduced rule-based weight
                ml_prediction = (rule_based_price * rule_weight) + (linear_pred * linear_weight) + (rf_pred * rf_weight)
                
                logger.info(f"Rule-based: {rule_based_price:.0f}, Linear: {linear_pred:.0f}, RF: {rf_pred:.0f}, Ensemble: {ml_prediction:.0f}")
                logger.debug(f"Weights - Rule: {rule_weight:.2f}, Linear: {linear_weight:.2f}, RF: {rf_weight:.2f}")
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}")
                ml_prediction = rule_based_price
        
        # Если ML модель не обучена, используем только правило
        predicted_price = ml_prediction if ml_prediction is not None else rule_based_price
        
        # Анализ исторических данных для корректировки
        if self.history:
            cutoff = datetime.now() - timedelta(days=60)
            recent_prices = [
                h.price for h in self.history
                if datetime.fromisoformat(h.date) >= cutoff
            ]
            
            if recent_prices:
                avg_historical = statistics.mean(recent_prices)
                # Корректируем предсказание на основе исторических данных (20% weight)
                predicted_price = (predicted_price * 0.8) + (avg_historical * 0.2)
        
        # Диапазон цен (±15%)
        price_range = (
            predicted_price * 0.85,
            predicted_price * 1.15,
        )
        
        # Уверенность модели
        confidence = 0.7
        if is_verified:
            confidence += 0.1
        if district:
            confidence += 0.05
        if self.history and len(self.history) > 30:
            confidence += 0.1
        if self.model_trained:
            # Increase confidence based on model performance
            r2_score_avg = (self.model_performance["linear_r2"] + self.model_performance["rf_r2"]) / 2
            confidence += min(0.2, r2_score_avg * 0.2)
            
            # Also consider cross-validation scores
            cv_score_avg = (self.model_performance["cross_val_score_linear"] + self.model_performance["cross_val_score_rf"]) / 2
            confidence += min(0.1, cv_score_avg * 0.1)
        
        # Adjust based on data quantity
        if len(self.history) < 50:
            confidence *= 0.8  # Reduce confidence for small datasets
        
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
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        is_verified: bool = False,
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
            district=district,
            floor=floor,
            total_floors=total_floors,
            is_verified=is_verified,
        ))

    def load_from_database(
        self,
        db,
        city: str,
        days: int = 60,
        rooms: Optional[int] = None,
    ) -> int:
        """Загрузить исторические данные из базы."""
        try:
            from app.db.repositories.ml_price_history import MLPriceHistoryRepository
            
            db_records = MLPriceHistoryRepository.get_by_city(
                db,
                city=city,
                days=days,
                rooms=rooms,
            )
            
            self.history = []
            for record in db_records:
                self.history.append(PriceHistory(
                    date=record.recorded_at.isoformat(),
                    price=record.price,
                    source=record.source or "database",
                    rooms=record.rooms,
                    area=record.area,
                    district=record.district,
                    floor=record.floor,
                    total_floors=record.total_floors,
                    is_verified=bool(record.is_verified),
                ))
            
            # Train the model with loaded data
            self.train_model()
            
            logger.info(f"Loaded {len(self.history)} records from database for {city}")
            return len(self.history)
        except Exception as e:
            logger.error(f"Failed to load from database: {e}")
            return 0

    def save_to_database(
        self,
        db,
        city: str,
        price: float,
        rooms: Optional[int] = None,
        area: Optional[float] = None,
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        source: Optional[str] = None,
        is_verified: bool = False,
    ) -> bool:
        """Сохранить историческую цену в базу."""
        try:
            from app.db.repositories.ml_price_history import MLPriceHistoryRepository
            
            MLPriceHistoryRepository.add_price(
                db,
                city=city,
                price=price,
                rooms=rooms,
                area=area,
                district=district,
                floor=floor,
                total_floors=total_floors,
                source=source,
                is_verified=is_verified,
            )
            
            self.add_history(
                price=price,
                source=source or "database",
                rooms=rooms,
                area=area,
                district=district,
                floor=floor,
                total_floors=total_floors,
                is_verified=is_verified,
            )
            
            logger.info(f"Saved price to database: {city} - {price} RUB")
            return True
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
            return False
    
    def _analyze_trend(self, city: str, rooms: Optional[int] = None) -> str:
        """Анализ тренда цен на основе истории."""
        if not self.history:
            return "stable"
        
        # Фильтруем релевантные данные (за последние 60 дней)
        cutoff = datetime.now() - timedelta(days=60)
        recent = [h for h in self.history if datetime.fromisoformat(h.date) >= cutoff]
        
        if rooms:
            recent = [h for h in recent if h.rooms == rooms]
        
        if len(recent) < 5:
            return "stable"
        
        # Сортируем по дате
        recent.sort(key=lambda x: x.date)
        
        # Сравниваем первую и вторую половины
        mid = len(recent) // 2
        first_half_avg = statistics.mean([h.price for h in recent[:mid]])
        second_half_avg = statistics.mean([h.price for h in recent[mid:]])
        
        change = (second_half_avg - first_half_avg) / first_half_avg
        
        if change > 0.025:  # 2.5% порог
            return "increasing"
        elif change < -0.03:
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
        days: int = 60,
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
        """Сравнить реальную цену с предсказанной."""
        difference = actual_price - predicted_price
        percentage_diff = (difference / predicted_price * 100) if predicted_price > 0 else 0
        
        # Определяем рейтинг
        if abs(percentage_diff) <= 5:
            rating = "excellent"
            comment = "Отличная цена!"
        elif abs(percentage_diff) <= 15:
            rating = "good"
            comment = "Хорошая цена"
        elif percentage_diff > 15:
            rating = "overpriced"
            comment = "Цена завышена"
        else:
            rating = "underpriced"
            comment = "Цена занижена"
        
        return {
            "actual_price": actual_price,
            "predicted_price": predicted_price,
            "difference": round(difference, 2),
            "percentage_difference": round(percentage_diff, 2),
            "rating": rating,
            "comment": comment,
        }
    
    def get_optimal_price_range(
        self,
        city: str,
        rooms: int,
        area: float,
        district: Optional[str] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        is_verified: bool = False,
    ) -> Dict[str, Any]:
        """Получить оптимальный диапазон цен для быстрой аренды."""
        # Предсказываем рыночную цену
        prediction = self.predict_price(
            city=city,
            rooms=rooms,
            area=area,
            district=district,
            floor=floor,
            total_floors=total_floors,
            is_verified=is_verified,
        )
        
        # Оптимальная цена немного ниже рынка для быстрой сдачи
        optimal_price = prediction.predicted_price * 0.95
        min_competitive = prediction.predicted_price * 0.85
        max_competitive = prediction.predicted_price * 1.15
        market_average = prediction.predicted_price
        
        return {
            "optimal_price": round(optimal_price, 2),
            "min_competitive": round(min_competitive, 2),
            "max_competitive": round(max_competitive, 2),
            "market_average": round(market_average, 2),
            "confidence": prediction.confidence,
        }

# Global instance
price_predictor = PricePredictorML()