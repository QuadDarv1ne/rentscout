import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import sys
import os

# Add the scripts directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.benchmark_search import SearchBenchmark
from app.models.schemas import PropertyCreate


@pytest.fixture
def sample_properties():
    """Sample properties for testing."""
    return [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="Квартира 1",
            price=3000.0,
            rooms=1,
            area=30.0,
            location=None,
            photos=[],
            description="Описание 1",
            link=None
        ),
        PropertyCreate(
            source="cian",
            external_id="2",
            title="Квартира 2",
            price=3500.0,
            rooms=2,
            area=50.0,
            location=None,
            photos=[],
            description="Описание 2",
            link=None
        ),
    ]


@pytest.mark.asyncio
async def test_benchmark_basic_search(sample_properties):
    """Test basic search benchmark functionality."""
    benchmark = SearchBenchmark()
    
    # Mock the search services
    with patch('scripts.benchmark_search.SearchService') as mock_search_service, \
         patch('scripts.benchmark_search.OptimizedSearchService') as mock_optimized_service:
        
        # Mock basic search service
        mock_basic_instance = AsyncMock()
        mock_basic_instance.search.return_value = sample_properties
        mock_search_service.return_value = mock_basic_instance
        
        # Mock optimized search service
        mock_optimized_instance = AsyncMock()
        mock_optimized_instance.search_cached.return_value = (sample_properties, True, {})
        mock_optimized_service.return_value = mock_optimized_instance
        
        # Run the benchmark
        results = await benchmark.benchmark_basic_search(iterations=2)
        
        # Verify results structure
        assert isinstance(results, dict)
        assert len(results) > 0
        
        # Check that we have results for both basic and optimized searches
        moscow_basic_key = "Москва_basic"
        moscow_optimized_key = "Москва_optimized"
        
        assert moscow_basic_key in results
        assert moscow_optimized_key in results
        
        # Check metrics structure
        basic_metrics = results[moscow_basic_key]
        optimized_metrics = results[moscow_optimized_key]
        
        assert "mean_time" in basic_metrics
        assert "median_time" in basic_metrics
        assert "min_time" in basic_metrics
        assert "max_time" in basic_metrics
        assert "iterations" in basic_metrics
        
        assert "mean_time" in optimized_metrics
        assert "median_time" in optimized_metrics
        assert "min_time" in optimized_metrics
        assert "max_time" in optimized_metrics
        assert "iterations" in optimized_metrics


@pytest.mark.asyncio
async def test_benchmark_concurrent_searches(sample_properties):
    """Test concurrent search benchmark functionality."""
    benchmark = SearchBenchmark()
    
    # Mock the optimized search service
    with patch('scripts.benchmark_search.OptimizedSearchService') as mock_optimized_service:
        mock_optimized_instance = AsyncMock()
        mock_optimized_instance.search_cached.return_value = (sample_properties, True, {})
        mock_optimized_service.return_value = mock_optimized_instance
        
        # Run the benchmark
        results = await benchmark.benchmark_concurrent_searches(concurrency=3)
        
        # Verify results structure
        assert isinstance(results, dict)
        assert "concurrent_requests" in results
        assert "successful_operations" in results
        assert "total_time" in results
        assert "operations_per_second" in results
        
        # Check values
        assert results["concurrent_requests"] == 3
        assert results["successful_operations"] == 3
        assert results["total_time"] >= 0
        assert results["operations_per_second"] >= 0


def test_print_results(capsys):
    """Test that results are printed correctly."""
    benchmark = SearchBenchmark()
    
    basic_results = {
        "Москва_basic": {
            "mean_time": 0.5,
            "median_time": 0.4,
            "min_time": 0.3,
            "max_time": 0.7,
            "iterations": 3
        },
        "Москва_optimized": {
            "mean_time": 0.1,
            "median_time": 0.1,
            "min_time": 0.05,
            "max_time": 0.15,
            "iterations": 3
        }
    }
    
    concurrent_results = {
        "concurrent_requests": 5,
        "successful_operations": 5,
        "total_time": 0.8,
        "operations_per_second": 6.25
    }
    
    # Call the print method
    benchmark.print_results(basic_results, concurrent_results)
    
    # Capture the output
    captured = capsys.readouterr()
    
    # Check that output contains expected elements
    assert "SEARCH PERFORMANCE BENCHMARK RESULTS" in captured.out
    assert "Basic Search Performance" in captured.out
    assert "Concurrent Search Performance" in captured.out
    assert "Performance Improvements" in captured.out
    assert "Москва: 80.0% faster with caching" in captured.out