
import os
import sys
import pytest

# Добавить корень проекта в PYTHONPATH для корректного импорта app.*
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def pytest_configure():
    pytest.test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
