"""Тесты для функционала экспорта данных."""
import csv
import json
from io import StringIO

import pytest

from app.models.schemas import PropertyCreate
from app.services.export import ExportService


@pytest.fixture
def sample_properties():
    """Создает список тестовых объектов для экспорта."""
    return [
        PropertyCreate(
            title="1-комнатная квартира, 40 м²",
            price=30000,
            url="https://example.com/1",
            source="test",
            external_id="test_1",
            city="Moscow",
            property_type="flat",
            rooms=1,
            area=40.0,
            floor=5,
            total_floors=10,
            address="ул. Тестовая, 1",
            description="Уютная квартира",
            photos=["photo1.jpg"],
            contact_name="Иван",
            contact_phone="+79991234567",
        ),
        PropertyCreate(
            title="2-комнатная квартира, 60 м²",
            price=50000,
            url="https://example.com/2",
            source="test",
            external_id="test_2",
            city="Moscow",
            property_type="flat",
            rooms=2,
            area=60.0,
            floor=3,
            total_floors=9,
            address="ул. Пробная, 2",
            description="Просторная квартира",
            photos=["photo2.jpg", "photo3.jpg"],
            contact_name="Петр",
            contact_phone="+79991234568",
        ),
    ]


class TestExportService:
    """Тесты для ExportService."""

    def test_to_csv_basic(self, sample_properties):
        """Тест экспорта в CSV формат."""
        service = ExportService()
        csv_content = service.to_csv(sample_properties)
        
        # Проверяем, что это строка
        assert isinstance(csv_content, str)
        assert len(csv_content) > 0
        
        # Парсим CSV
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        # Проверяем количество строк
        assert len(rows) == 2
        
        # Проверяем заголовки
        assert "title" in rows[0]
        assert "price" in rows[0]
        assert "url" in rows[0]
        
        # Проверяем значения первой строки
        assert rows[0]["title"] == "1-комнатная квартира, 40 м²"
        assert rows[0]["price"] == "30000"
        assert rows[0]["rooms"] == "1"
        assert rows[0]["area"] == "40.0"

    def test_to_csv_empty_list(self):
        """Тест экспорта пустого списка в CSV."""
        service = ExportService()
        csv_content = service.to_csv([])
        
        # Должен быть только заголовок
        lines = csv_content.strip().split("\n")
        assert len(lines) == 1  # Только строка с заголовками
        assert "title" in lines[0]

    def test_to_json_basic(self, sample_properties):
        """Тест экспорта в JSON формат."""
        service = ExportService()
        json_content = service.to_json(sample_properties, pretty=False)
        
        # Проверяем, что это валидный JSON
        data = json.loads(json_content)
        
        # Проверяем количество элементов
        assert len(data) == 2
        
        # Проверяем структуру первого элемента
        assert data[0]["title"] == "1-комнатная квартира, 40 м²"
        assert data[0]["price"] == 30000
        assert data[0]["rooms"] == 1
        assert data[0]["area"] == 40.0

    def test_to_json_pretty(self, sample_properties):
        """Тест экспорта в форматированный JSON."""
        service = ExportService()
        json_content = service.to_json(sample_properties, pretty=True)
        
        # Проверяем, что это валидный JSON
        data = json.loads(json_content)
        assert len(data) == 2
        
        # Проверяем наличие отступов
        assert "\n" in json_content
        assert "  " in json_content  # Отступы

    def test_to_json_empty_list(self):
        """Тест экспорта пустого списка в JSON."""
        service = ExportService()
        json_content = service.to_json([])
        
        # Проверяем, что это пустой массив
        data = json.loads(json_content)
        assert data == []

    def test_to_jsonl_basic(self, sample_properties):
        """Тест экспорта в JSONL формат."""
        service = ExportService()
        jsonl_content = service.to_jsonl(sample_properties)
        
        # Разбиваем на строки
        lines = jsonl_content.strip().split("\n")
        
        # Проверяем количество строк
        assert len(lines) == 2
        
        # Проверяем, что каждая строка - валидный JSON
        for line in lines:
            data = json.loads(line)
            assert "title" in data
            assert "price" in data
            assert "url" in data
        
        # Проверяем первую строку
        first_item = json.loads(lines[0])
        assert first_item["title"] == "1-комнатная квартира, 40 м²"
        assert first_item["price"] == 30000

    def test_to_jsonl_empty_list(self):
        """Тест экспорта пустого списка в JSONL."""
        service = ExportService()
        jsonl_content = service.to_jsonl([])
        
        # Пустая строка или только перенос строки
        assert jsonl_content.strip() == ""

    def test_csv_field_order(self, sample_properties):
        """Тест правильного порядка полей в CSV."""
        service = ExportService()
        csv_content = service.to_csv(sample_properties)
        
        # Читаем заголовок
        reader = csv.DictReader(StringIO(csv_content))
        
        # Проверяем наличие всех ожидаемых полей
        expected_fields = [
            "title", "price", "url", "source", "external_id", "city",
            "property_type", "rooms", "area", "floor", "total_floors",
            "address", "description", "photos", "location", "features",
            "contact_name", "contact_phone"
        ]
        
        fieldnames = reader.fieldnames
        for field in expected_fields:
            assert field in fieldnames

    def test_export_with_none_values(self):
        """Тест экспорта объектов с None значениями."""
        property_with_nones = PropertyCreate(
            title="Тест",
            price=10000,
            url="https://test.com",
            source="test",
            external_id="test_none",
            city="Moscow",
            property_type="flat",
            rooms=None,  # None значение
            area=None,   # None значение
            floor=None,
            total_floors=None,
            address=None,
            description=None,
            photos=None,
            contact_name=None,
            contact_phone=None,
        )
        
        service = ExportService()
        
        # CSV
        csv_content = service.to_csv([property_with_nones])
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        assert rows[0]["rooms"] == ""  # None должны стать пустыми строками
        
        # JSON
        json_content = service.to_json([property_with_nones])
        data = json.loads(json_content)
        # В JSON None должны быть null
        assert data[0]["rooms"] is None

    def test_export_with_special_characters(self):
        """Тест экспорта с спецсимволами."""
        property_with_special = PropertyCreate(
            title='Квартира "люкс", 50 м²',
            price=40000,
            url="https://test.com",
            source="test",
            external_id="test_special",
            city="Moscow",
            property_type="flat",
            description="Описание с запятой, точкой. И кавычками \"тест\"",
        )
        
        service = ExportService()
        
        # CSV должен корректно экранировать кавычки
        csv_content = service.to_csv([property_with_special])
        assert "люкс" in csv_content
        
        # JSON должен корректно экранировать кавычки
        json_content = service.to_json([property_with_special])
        data = json.loads(json_content)
        assert "люкс" in data[0]["title"]
        assert "тест" in data[0]["description"]

    def test_export_large_dataset(self):
        """Тест экспорта большого количества записей."""
        # Создаем 1000 тестовых объектов
        large_dataset = [
            PropertyCreate(
                title=f"Квартира {i}",
                price=30000 + i * 1000,
                url=f"https://test.com/{i}",
                source="test",
                external_id=f"test_{i}",
                city="Moscow",
                property_type="flat",
                rooms=i % 5 + 1,
                area=40.0 + i * 0.5,
            )
            for i in range(1000)
        ]
        
        service = ExportService()
        
        # CSV
        csv_content = service.to_csv(large_dataset)
        csv_lines = csv_content.split("\n")
        # 1001 строка: 1 заголовок + 1000 данных + 1 пустая в конце
        assert len(csv_lines) >= 1000
        
        # JSON
        json_content = service.to_json(large_dataset)
        data = json.loads(json_content)
        assert len(data) == 1000
        
        # JSONL
        jsonl_content = service.to_jsonl(large_dataset)
        jsonl_lines = [line for line in jsonl_content.split("\n") if line.strip()]
        assert len(jsonl_lines) == 1000
