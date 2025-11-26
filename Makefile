# Makefile для проекта RentScout

# Переменные
PYTHON := python3
PIP := pip
PROJECT := rentscout
TEST_DIR := app/tests
SRC_DIR := app

# Цвета для вывода
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

# Функция для вывода цветного текста
define colorecho
	@echo "$(1)$(2)$(NC)"
endef

.PHONY: help install install-dev test test-cov run run-dev lint format clean docs

help:
	@echo "Доступные команды:"
	@echo "  install     - Установка зависимостей"
	@echo "  install-dev - Установка зависимостей для разработки"
	@echo "  test        - Запуск тестов"
	@echo "  test-cov    - Запуск тестов с покрытием"
	@echo "  run         - Запуск сервера"
	@echo "  run-dev     - Запуск сервера разработки с перезагрузкой"
	@echo "  lint        - Проверка кода"
	@echo "  format      - Форматирование кода"
	@echo "  clean       - Очистка временных файлов"
	@echo "  docs        - Генерация документации"

install:
	$(call colorecho,$(GREEN),"Установка зависимостей...")
	$(PIP) install -r requirements.txt

install-dev:
	$(call colorecho,$(GREEN),"Установка зависимостей для разработки...")
	$(PIP) install -r requirements-dev.txt

test:
	$(call colorecho,$(GREEN),"Запуск тестов...")
	$(PYTHON) -m pytest $(TEST_DIR) -v

test-cov:
	$(call colorecho,$(GREEN),"Запуск тестов с покрытием...")
	$(PYTHON) -m pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term

run:
	$(call colorecho,$(GREEN),"Запуск сервера...")
	$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

run-dev:
	$(call colorecho,$(GREEN),"Запуск сервера разработки с перезагрузкой...")
	$(PYTHON) scripts/dev_server.py --reload

lint:
	$(call colorecho,$(YELLOW),"Проверка кода...")
	$(PYTHON) -m flake8 $(SRC_DIR) $(TEST_DIR)

format:
	$(call colorecho,$(GREEN),"Форматирование кода...")
	$(PYTHON) -m black $(SRC_DIR) $(TEST_DIR)
	$(PYTHON) -m isort $(SRC_DIR) $(TEST_DIR)

clean:
	$(call colorecho,$(YELLOW),"Очистка временных файлов...")
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf site/

docs:
	$(call colorecho,$(GREEN),"Генерация документации...")
	$(PYTHON) -m mkdocs build

docs-serve:
	$(call colorecho,$(GREEN),"Запуск сервера документации...")
	$(PYTHON) -m mkdocs serve