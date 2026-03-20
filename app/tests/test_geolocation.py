"""
Unit-тесты для геолокации API.
"""
import pytest
from math import radians, sin, cos, sqrt, atan2

from app.api.endpoints.geolocation import (
    haversine_distance,
    estimate_walking_time,
    estimate_cycling_time,
    get_density_label,
    LocationPoint,
    NearbyPropertiesRequest,
    DistanceRequest,
)


class TestHaversineDistance:
    """Тесты для функции расчёта расстояния."""

    def test_moscow_center_to_kremlin(self):
        """Расстояние внутри Москвы (малое)."""
        # Красная площадь
        lat1, lon1 = 55.7539, 37.6208
        # Кремль (рядом)
        lat2, lon2 = 55.7520, 37.6175
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        assert distance > 0
        assert distance < 1  # Меньше 1 км

    def test_moscow_to_spb(self):
        """Расстояние Москва - Санкт-Петербург."""
        # Москва
        lat1, lon1 = 55.7558, 37.6173
        # Санкт-Петербург
        lat2, lon2 = 59.9343, 30.3351
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        # Реальное расстояние ~635 км
        assert 600 < distance < 700

    def test_same_point(self):
        """Расстояние до той же точки."""
        distance = haversine_distance(55.75, 37.61, 55.75, 37.61)
        assert distance == 0

    def test_equator_distance(self):
        """Расстояние вдоль экватора."""
        # Точки на экваторе с разницей 1 градус долготы
        lat1, lon1 = 0, 0
        lat2, lon2 = 0, 1
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        # 1 градус долготы на экваторе ≈ 111 км
        assert 110 < distance < 112

    def test_pole_to_pole(self):
        """Расстояние от полюса до полюса."""
        # Северный полюс
        lat1, lon1 = 90, 0
        # Южный полюс
        lat2, lon2 = -90, 0
        
        distance = haversine_distance(lat1, lon1, lat2, lon2)
        
        # Диаметр Земли ≈ 12742 км
        assert 12700 < distance < 12800


class TestTimeEstimation:
    """Тесты для оценки времени."""

    def test_walking_time_1km(self):
        """Время пешком 1 км."""
        time_min = estimate_walking_time(1.0)
        assert time_min == 12  # 1 км / 5 км/ч * 60 = 12 мин

    def test_walking_time_5km(self):
        """Время пешком 5 км."""
        time_min = estimate_walking_time(5.0)
        assert time_min == 60  # 1 час

    def test_cycling_time_1km(self):
        """Время на велосипеде 1 км."""
        time_min = estimate_cycling_time(1.0)
        assert time_min == 4  # 1 км / 15 км/ч * 60 = 4 мин

    def test_cycling_time_15km(self):
        """Время на велосипеде 15 км."""
        time_min = estimate_cycling_time(15.0)
        assert time_min == 60  # 1 час

    def test_zero_distance(self):
        """Время для нулевого расстояния."""
        assert estimate_walking_time(0) == 0
        assert estimate_cycling_time(0) == 0


class TestDensityLabel:
    """Тесты для определения плотности."""

    def test_low_density(self):
        """Низкая плотность."""
        assert get_density_label(0) == "low"
        assert get_density_label(5) == "low"
        assert get_density_label(9) == "low"

    def test_medium_density(self):
        """Средняя плотность."""
        assert get_density_label(10) == "medium"
        assert get_density_label(25) == "medium"
        assert get_density_label(49) == "medium"

    def test_high_density(self):
        """Высокая плотность."""
        assert get_density_label(50) == "high"
        assert get_density_label(100) == "high"
        assert get_density_label(1000) == "high"


class TestLocationPoint:
    """Тесты для модели LocationPoint."""

    def test_valid_coordinates(self):
        """Валидные координаты."""
        point = LocationPoint(latitude=55.75, longitude=37.61)
        assert point.latitude == 55.75
        assert point.longitude == 37.61

    def test_latitude_bounds(self):
        """Границы широты."""
        # Минимальная
        point = LocationPoint(latitude=-90, longitude=0)
        assert point.latitude == -90
        
        # Максимальная
        point = LocationPoint(latitude=90, longitude=0)
        assert point.latitude == 90

    def test_longitude_bounds(self):
        """Границы долготы."""
        # Минимальная
        point = LocationPoint(latitude=0, longitude=-180)
        assert point.longitude == -180
        
        # Максимальная
        point = LocationPoint(latitude=0, longitude=180)
        assert point.longitude == 180

    def test_invalid_latitude(self):
        """Невалидная широта."""
        with pytest.raises Exception:
            LocationPoint(latitude=91, longitude=0)
        
        with pytest.raises Exception:
            LocationPoint(latitude=-91, longitude=0)

    def test_invalid_longitude(self):
        """Невалидная долгота."""
        with pytest.raises Exception:
            LocationPoint(latitude=0, longitude=181)
        
        with pytest.raises Exception:
            LocationPoint(latitude=0, longitude=-181)


class TestNearbyPropertiesRequest:
    """Тесты для запроса ближайших объектов."""

    def test_default_values(self):
        """Значения по умолчанию."""
        location = LocationPoint(latitude=55.75, longitude=37.61)
        request = NearbyPropertiesRequest(location=location)
        
        assert request.radius_km == 1.0
        assert request.limit == 20

    def test_custom_values(self):
        """Пользовательские значения."""
        location = LocationPoint(latitude=55.75, longitude=37.61)
        request = NearbyPropertiesRequest(
            location=location,
            radius_km=5.0,
            limit=50
        )
        
        assert request.radius_km == 5.0
        assert request.limit == 50

    def test_radius_bounds(self):
        """Границы радиуса."""
        location = LocationPoint(latitude=55.75, longitude=37.61)
        
        # Минимальный
        request = NearbyPropertiesRequest(location=location, radius_km=0.1)
        assert request.radius_km == 0.1
        
        # Максимальный
        request = NearbyPropertiesRequest(location=location, radius_km=50.0)
        assert request.radius_km == 50.0

    def test_limit_bounds(self):
        """Границы лимита."""
        location = LocationPoint(latitude=55.75, longitude=37.61)
        
        # Минимальный
        request = NearbyPropertiesRequest(location=location, limit=1)
        assert request.limit == 1
        
        # Максимальный
        request = NearbyPropertiesRequest(location=location, limit=100)
        assert request.limit == 100


class TestDistanceRequest:
    """Тесты для запроса расстояния."""

    def test_valid_request(self):
        """Валидный запрос."""
        from_loc = LocationPoint(latitude=55.75, longitude=37.61)
        to_loc = LocationPoint(latitude=59.93, longitude=30.33)
        
        request = DistanceRequest(
            from_location=from_loc,
            to_location=to_loc
        )
        
        assert request.from_location.latitude == 55.75
        assert request.to_location.latitude == 59.93


class TestGeoIntegration:
    """Интеграционные тесты для гео API."""

    def test_moscow_landmarks_distances(self):
        """Расстояния между достопримечательностями Москвы."""
        # Красная площадь
        kremlin = (55.7520, 37.6175)
        # МГУ
        msu = (55.7034, 37.5340)
        # Останкинская башня
        ostankino = (55.8194, 37.6106)
        
        # Кремль - МГУ (~7 км)
        dist_kremlin_msu = haversine_distance(*kremlin, *msu)
        assert 6 < dist_kremlin_msu < 8
        
        # Кремль - Останкино (~7.5 км)
        dist_kremlin_ostankino = haversine_distance(*kremlin, *ostankino)
        assert 7 < dist_kremlin_ostankino < 8
        
        # МГУ - Останкино (~13 км)
        dist_msu_ostankino = haversine_distance(*msu, *ostankino)
        assert 12 < dist_msu_ostankino < 14

    def test_walking_vs_cycling(self):
        """Сравнение времени пешком и на велосипеде."""
        distance = 10.0  # 10 км
        
        walking = estimate_walking_time(distance)
        cycling = estimate_cycling_time(distance)
        
        # Велосипед должен быть быстрее в ~3 раза
        assert cycling < walking
        assert walking / cycling > 2.5


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
