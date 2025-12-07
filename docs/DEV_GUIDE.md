# RentScout Developer Guide

## Project Overview

RentScout is a high-performance rental property aggregator that collects data from multiple real estate platforms, filters duplicates, and provides a unified API for accessing rental listings.

## Architecture

The application follows a layered architecture:

1. **API Layer** - FastAPI endpoints for external access
2. **Service Layer** - Business logic implementation
3. **Parser Layer** - Data extraction from various sources
4. **Data Layer** - Database interactions and caching
5. **Utility Layer** - Common utilities and helpers

## Technology Stack

- **Framework**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL with SQLAlchemy 2.0
- **Caching**: Redis
- **Task Queue**: Celery with Redis backend
- **Monitoring**: Prometheus
- **Containerization**: Docker
- **Testing**: pytest

## Project Structure

```
app/
├── api/                 # API endpoints
│   └── endpoints/       # Individual endpoint modules
├── core/                # Core application configuration
├── db/                  # Database models and repositories
├── models/              # Data transfer objects (Pydantic models)
├── parsers/             # Data parsers for different sources
├── services/            # Business logic services
├── tasks/               # Background task definitions
├── utils/               # Utility functions and helpers
└── main.py             # Application entry point
```

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (recommended)
- PostgreSQL (if running locally)
- Redis (if running locally)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/QuadDarv1ne/rentscout.git
   cd rentscout
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the Application

#### Using Docker (Recommended)

```bash
docker-compose -f docker-compose.dev.yml up --build
```

#### Local Development

```bash
python -m uvicorn app.main:app --reload
```

## Adding a New Parser

To add support for a new real estate platform:

1. Create a new directory in `app/parsers/` with the platform name
2. Implement a parser class that inherits from `BaseParser`
3. Add the parser to the search service in `app/services/search.py`
4. Add the parser to the dependencies in `app/dependencies/parsers.py`
5. Create tests in `app/tests/`

### Parser Implementation Requirements

Your parser must implement the following methods:

```python
from app.parsers.base_parser import BaseParser

class NewPlatformParser(BaseParser):
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        """Parse properties from the platform"""
        pass
    
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate parser-specific parameters"""
        pass
```

### Example Parser Implementation

```python
import asyncio
import httpx
from typing import Any, Dict, List

from app.core.config import settings
from app.models.schemas import PropertyCreate
from app.parsers.base_parser import BaseParser, metrics_collector_decorator
from app.services.advanced_cache import cached_parser
from app.utils.parser_errors import ParserErrorHandler, NetworkError
from app.utils.retry import retry

class ExampleParser(BaseParser):
    BASE_URL = "https://example-platform.com"
    
    @cached_parser(expire=600, source="example")
    @retry(max_attempts=3, initial_delay=1.0)
    @metrics_collector_decorator
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Process parameters
        processed_params = await self.preprocess_params(params)
        
        # Build request
        url = f"{self.BASE_URL}/search"
        query_params = self._build_query_params(location, processed_params)
        
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=query_params)
                response.raise_for_status()
                results = self._parse_html(response.text)
                return await self.postprocess_results(results)
        except httpx.RequestError as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="ExampleParser.parse")
            raise parser_error
        except Exception as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="ExampleParser.parse")
            raise parser_error
    
    def _build_query_params(self, location: str, params: Dict[str, Any]) -> Dict[str, str]:
        """Build query parameters for the platform's API"""
        return {
            "location": location,
            "type": params.get("type", "apartment"),
        }
    
    def _parse_html(self, html: str) -> List[PropertyCreate]:
        """Parse HTML response and extract property data"""
        # Implementation depends on the platform's HTML structure
        pass
```

## Extending the API

To add new API endpoints:

1. Create a new module in `app/api/endpoints/`
2. Define your routes using FastAPI decorators
3. Register the router in `app/main.py`

### Example API Endpoint

```python
from fastapi import APIRouter, HTTPException
from typing import List

from app.models.schemas import Property
from app.services.example_service import ExampleService

router = APIRouter(prefix="/example", tags=["example"])

@router.get("/properties", response_model=List[Property])
async def get_example_properties(limit: int = 10):
    """Get example properties"""
    try:
        service = ExampleService()
        properties = await service.get_properties(limit)
        return properties
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Database Schema

The application uses PostgreSQL with the following main tables:

### Properties Table

Stores property listings with the following fields:
- `id` - Internal identifier
- `source` - Source platform (avito, cian, etc.)
- `external_id` - Identifier on the source platform
- `title` - Property title
- `description` - Property description
- `link` - Link to the property listing
- `price` - Rental price
- `currency` - Currency code
- `rooms` - Number of rooms
- `area` - Area in square meters
- `location` - JSON field with location data
- `photos` - Array of photo URLs
- `is_active` - Whether the listing is still active
- `created_at` - When the record was created
- `last_updated` - When the record was last updated

### Price History Table

Tracks price changes for properties:
- `id` - Internal identifier
- `property_id` - Reference to the property
- `old_price` - Previous price
- `new_price` - New price
- `changed_at` - When the change occurred

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest app/tests/test_example.py

# Run with coverage
python -m pytest --cov=app
```

### Writing Tests

Tests should follow the AAA pattern (Arrange, Act, Assert):

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.parsers.example_parser import ExampleParser
from app.models.schemas import PropertyCreate

@pytest.fixture
def example_parser():
    return ExampleParser()

@pytest.mark.asyncio
async def test_example_parser_parse_success(example_parser):
    """Test successful parsing"""
    # Arrange
    mock_html = "<html>...</html>"
    
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.text = mock_html
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Act
        results = await example_parser.parse("Moscow")
        
        # Assert
        assert isinstance(results, list)
        assert len(results) > 0
```

## Error Handling

The application uses a comprehensive error handling system:

1. **Custom Exceptions** - Defined in `app/utils/parser_errors.py`
2. **Error Classification** - Errors are classified by severity and retryability
3. **Logging** - All errors are logged with appropriate context
4. **Retry Logic** - Automatic retries with exponential backoff

### Error Types

- `NetworkError` - Network connectivity issues
- `TimeoutError` - Request timeouts
- `RateLimitError` - API rate limiting
- `AuthenticationError` - Authentication failures
- `ParsingError` - Data parsing failures
- `ValidationError` - Data validation failures

## Caching Strategy

The application uses Redis for caching with the following strategies:

1. **Result Caching** - Cache parsed results for 5 minutes
2. **Adaptive Caching** - Adjust TTL based on usage patterns
3. **Compression** - Compress large cache values
4. **Cache Warming** - Pre-populate cache with popular queries

## Monitoring and Metrics

Metrics are collected using Prometheus:

1. **HTTP Metrics** - Request counts, durations, error rates
2. **Parser Metrics** - Parser performance and error rates
3. **Cache Metrics** - Hit/miss ratios, error rates
4. **Database Metrics** - Query performance, connection counts

See `docs/METRICS.md` for detailed metrics documentation.

## Deployment

### Docker Deployment

The application can be deployed using Docker Compose:

```bash
docker-compose up -d
```

### Environment Variables

Key environment variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `REQUEST_TIMEOUT` - HTTP request timeout in seconds
- `CACHE_TTL` - Default cache TTL in seconds

### Scaling

The application can be scaled horizontally:

1. **Multiple API instances** - Behind a load balancer
2. **Multiple Celery workers** - For background task processing
3. **Database connection pooling** - For database scalability

## Contributing

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write docstrings for all public functions and classes
- Keep functions small and focused
- Use descriptive variable names

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

### Code Review Guidelines

- Review for correctness and performance
- Check for security vulnerabilities
- Ensure proper error handling
- Verify test coverage
- Confirm documentation updates

## Troubleshooting

### Common Issues

1. **Database Connection Failed** - Check DATABASE_URL environment variable
2. **Redis Connection Failed** - Check REDIS_URL environment variable
3. **Parser Failures** - Platform HTML structure may have changed
4. **Rate Limiting** - Reduce request frequency or implement delays

### Debugging Tips

1. Enable debug logging by setting `LOG_LEVEL=DEBUG`
2. Check application logs for error messages
3. Use the health check endpoints to verify service status
4. Monitor metrics for performance degradation

## Performance Optimization

### Database Optimization

- Use database indexes for frequently queried fields
- Optimize complex queries with proper JOINs
- Use connection pooling to reduce overhead
- Implement pagination for large result sets

### Caching Optimization

- Use appropriate TTL values for different data types
- Implement cache warming for popular queries
- Use compression for large cache values
- Monitor cache hit rates and adjust strategies

### Parser Optimization

- Implement efficient HTML parsing algorithms
- Use connection pooling for HTTP requests
- Implement proper rate limiting
- Cache intermediate parsing results when appropriate

## Security Considerations

### Input Validation

- Validate all user inputs
- Sanitize HTML content
- Use parameterized queries for database access
- Implement proper authentication and authorization

### Rate Limiting

- Implement IP-based rate limiting
- Use appropriate limits for different endpoints
- Monitor for abuse patterns
- Implement automatic blocking for malicious activity

### Data Protection

- Encrypt sensitive data at rest
- Use HTTPS for all communications
- Implement proper access controls
- Regularly audit security permissions