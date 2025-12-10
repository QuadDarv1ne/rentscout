"""Tests for quality metrics API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_quality_endpoint_exists():
    """Test that quality metrics endpoint exists."""
    response = client.get("/api/quality/parser-stats")
    assert response.status_code == 200


def test_parser_stats_structure():
    """Test parser statistics response structure."""
    response = client.get("/api/quality/parser-stats")
    data = response.json()
    
    assert "period" in data
    assert "parsers" in data
    assert "summary" in data
    
    # Check period structure
    assert "start" in data["period"]
    assert "end" in data["period"]
    
    # Check summary structure
    assert "total_requests" in data["summary"]
    assert "total_successful" in data["summary"]
    assert "overall_success_rate" in data["summary"]


def test_data_quality_endpoint():
    """Test data quality assessment endpoint."""
    response = client.get("/api/quality/data-quality")
    assert response.status_code == 200
    
    data = response.json()
    assert "completeness" in data
    assert "validity" in data
    assert "duplicates" in data
    assert "outliers" in data


def test_health_report_endpoint():
    """Test system health report endpoint."""
    response = client.get("/api/quality/health-report")
    assert response.status_code == 200
    
    data = response.json()
    assert "overall_status" in data
    assert "services" in data
    assert "performance" in data
    assert "recommendations" in data


def test_source_quality_valid_source():
    """Test source quality for valid source."""
    response = client.get("/api/quality/source-quality/avito")
    assert response.status_code == 200
    
    data = response.json()
    assert data["source"] == "avito"
    assert "metrics" in data
    assert "recent_errors" in data


def test_source_quality_invalid_source():
    """Test source quality for invalid source."""
    response = client.get("/api/quality/source-quality/invalid_source")
    assert response.status_code == 400


def test_parser_stats_with_dates():
    """Test parser stats with custom date range."""
    response = client.get(
        "/api/quality/parser-stats?"
        "start_date=2025-12-01&"
        "end_date=2025-12-10"
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["period"]["start"] == "2025-12-01T00:00:00"


def test_parser_stats_invalid_date():
    """Test parser stats with invalid date format."""
    response = client.get(
        "/api/quality/parser-stats?start_date=invalid"
    )
    assert response.status_code == 400


def test_health_report_services():
    """Test that health report includes all critical services."""
    response = client.get("/api/quality/health-report")
    data = response.json()
    
    services = data["services"]
    critical_services = ["api", "database", "cache", "celery"]
    
    for service in critical_services:
        assert service in services
        assert "status" in services[service]


def test_completeness_metrics():
    """Test data completeness metrics."""
    response = client.get("/api/quality/data-quality")
    data = response.json()
    
    completeness = data["completeness"]
    assert "score" in completeness
    assert "properties_complete" in completeness
    assert "missing_by_field" in completeness
    
    # Score should be between 0 and 100
    assert 0 <= completeness["score"] <= 100


def test_validity_metrics():
    """Test data validity metrics."""
    response = client.get("/api/quality/data-quality")
    data = response.json()
    
    validity = data["validity"]
    assert "score" in validity
    assert "valid_prices" in validity
    assert "invalid_prices" in validity
    assert "issues" in validity


def test_duplicate_detection():
    """Test duplicate detection metrics."""
    response = client.get("/api/quality/data-quality")
    data = response.json()
    
    duplicates = data["duplicates"]
    assert "potential_duplicates" in duplicates
    assert "duplicate_rate_percent" in duplicates


def test_outlier_detection():
    """Test outlier detection metrics."""
    response = client.get("/api/quality/data-quality")
    data = response.json()
    
    outliers = data["outliers"]
    assert "suspicious_records" in outliers
    assert "outlier_rate_percent" in outliers
    assert "types" in outliers


def test_source_quality_metrics():
    """Test source quality metrics structure."""
    response = client.get("/api/quality/source-quality/cian")
    data = response.json()
    
    assert "total_properties" in data
    assert "metrics" in data
    assert "success_rate" in data["metrics"]
    assert "data_completeness" in data["metrics"]


def test_health_report_recommendations():
    """Test that health report includes recommendations."""
    response = client.get("/api/quality/health-report")
    data = response.json()
    
    recommendations = data["recommendations"]
    assert isinstance(recommendations, list)
    
    # If recommendations exist, check structure
    if recommendations:
        rec = recommendations[0]
        assert "severity" in rec
        assert "component" in rec
        assert "message" in rec
