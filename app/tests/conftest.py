import sys
import os
import pytest

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Add a simple pytest configuration
def pytest_configure():
    pytest.test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')