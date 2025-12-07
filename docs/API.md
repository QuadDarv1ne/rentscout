# RentScout API Documentation

## Overview

RentScout is a high-performance API for aggregating rental property data from leading platforms. It collects up-to-date information, filters duplicates, and provides a convenient interface for integration.

## Base URL

```
http://localhost:8000/api
```

## Authentication

Most endpoints are publicly accessible. Some administrative endpoints may require authentication (to be implemented).

## Rate Limiting

The API implements rate limiting to prevent abuse:
- 100 requests per minute per IP address
- Exceeding the limit returns a 429 status code

## Error Responses

The API uses standard HTTP status codes:

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Authentication required |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Something went wrong |
| 503 | Service Unavailable - Temporary issue |

## Endpoints

### Properties (Real-time Search)

#### GET /properties

Search for properties in real-time from multiple sources with filtering.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| city* | string | City name for search | Москва |
| property_type | string | Property type | Квартира |
| min_price | number | Minimum price | 3000 |
| max_price | number | Maximum price | 10000 |
| min_rooms | integer | Minimum rooms | 1 |
| max_rooms | integer | Maximum rooms | 3 |
| min_area | number | Minimum area (sq.m) | 30 |
| max_area | number | Maximum area (sq.m) | 100 |
| min_floor | integer | Minimum floor | 1 |
| max_floor | integer | Maximum floor | 10 |
| min_total_floors | integer | Minimum total floors in building | 5 |
| max_total_floors | integer | Maximum total floors in building | 20 |
| district | string | District filter | Центральный |
| has_photos | boolean | Filter by photo availability | true |
| source | string | Filter by source (avito, cian, etc.) | avito |
| features | array[string] | Required features | wifi,parking |
| max_price_per_sqm | number | Max price per sq.m | 100 |
| has_contact | boolean | Filter by contact info availability | true |
| min_first_seen | string | Min first seen date (ISO) | 2023-01-01 |
| max_first_seen | string | Max first seen date (ISO) | 2023-12-31 |
| min_last_seen | string | Min last seen date (ISO) | 2023-01-01 |
| max_last_seen | string | Max last seen date (ISO) | 2023-12-31 |
| sort_by | string | Sort field (price, area, rooms, floor, first_seen, last_seen) | price |
| sort_order | string | Sort order (asc, desc) | asc |

**Example Request:**

```http
GET /api/properties?city=Москва&property_type=Квартира&min_price=3000&max_price=8000&min_rooms=1&max_rooms=3&min_area=30&max_area=80
```

**Response:**

```json
[
  {
    "id": 12345678,
    "source": "avito",
    "external_id": "987654321",
    "title": "2-комн. квартира, 45 м², ЦАО",
    "description": "Сдается 2-комнатная квартира в центре Москвы",
    "link": "https://www.avito.ru/moskva/sdam/na_sutki/...",
    "price": 5000,
    "currency": "RUB",
    "price_per_sqm": 111.11,
    "rooms": 2,
    "area": 45,
    "floor": 3,
    "total_floors": 9,
    "city": "Москва",
    "district": "Центральный",
    "address": "ул. Тверская, 10",
    "latitude": 55.7558,
    "longitude": 37.6176,
    "location": {
      "city": "Москва",
      "district": "Центральный",
      "address": "ул. Тверская, 10"
    },
    "photos": [
      "https://img.avito.ru/...",
      "https://img.avito.ru/..."
    ],
    "features": {
      "wifi": true,
      "parking": false,
      "furniture": true
    },
    "contact_name": "Иван Петров",
    "contact_phone": "+7 (999) 123-45-67",
    "is_active": true,
    "is_verified": false,
    "first_seen": "2023-06-15T10:30:00",
    "last_seen": "2023-06-15T10:30:00",
    "created_at": "2023-06-15T10:30:00",
    "last_updated": "2023-06-15T10:30:00"
  }
]
```

#### GET /properties/search

Alias for `/properties` endpoint.

### Properties (Database Storage)

#### POST /properties

Create a new property in the database.

**Request Body:**

```json
{
  "source": "avito",
  "external_id": "987654321",
  "title": "2-комн. квартира, 45 м², ЦАО",
  "description": "Сдается 2-комнатная квартира в центре Москвы",
  "link": "https://www.avito.ru/moskva/sdam/na_sutki/...",
  "price": 5000,
  "currency": "RUB",
  "rooms": 2,
  "area": 45,
  "photos": ["https://img.avito.ru/..."]
}
```

#### GET /properties/{property_id}

Get a property by its internal ID.

#### GET /properties/

Search properties stored in the database.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| city | string | Filter by city | Москва |
| source | string | Filter by source | avito |
| district | string | Filter by district | Центральный |
| min_price | number | Minimum price | 3000 |
| max_price | number | Maximum price | 10000 |
| min_rooms | integer | Minimum rooms | 1 |
| max_rooms | integer | Maximum rooms | 3 |
| min_area | number | Minimum area | 30 |
| max_area | number | Maximum area | 100 |
| is_active | boolean | Filter by active status | true |
| sort_by | string | Sort field (created_at, price, area, rooms) | created_at |
| sort_order | string | Sort order (asc, desc) | desc |
| limit | integer | Max results (1-1000) | 100 |
| offset | integer | Results to skip | 0 |

#### GET /properties/stats/overview

Get property statistics.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| city | string | Filter by city | Москва |
| source | string | Filter by source | avito |
| district | string | Filter by district | Центральный |

#### GET /properties/{property_id}/price-history

Get price history for a property.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| limit | integer | Max entries (1-100) | 10 |

#### POST /properties/{property_id}/view

Track a property view.

#### GET /properties/stats/popular

Get popular properties.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| limit | integer | Max results (1-100) | 10 |
| days | integer | Period in days (1-365) | 7 |

#### GET /properties/stats/searches

Get popular search queries.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| limit | integer | Max results (1-100) | 10 |
| days | integer | Period in days (1-365) | 7 |

#### POST /properties/bulk

Bulk create/update properties.

#### POST /properties/deactivate-old

Deactivate old properties.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| source* | string | Source to deactivate from | avito |
| hours | integer | Hours since last seen (1-720) | 24 |

#### GET /properties/by-price-per-sqm

Search properties sorted by price per square meter.

### Tasks (Background Jobs)

#### POST /tasks/parse

Create a background parsing task for a city.

**Request Body:**

```json
{
  "city": "Москва",
  "property_type": "Квартира"
}
```

#### POST /tasks/parse/batch

Create batch parsing tasks for multiple cities.

**Request Body:**

```json
{
  "cities": ["Москва", "Санкт-Петербург"],
  "property_type": "Квартира"
}
```

#### POST /tasks/parse/schedule

Schedule a parsing task.

**Request Body:**

```json
{
  "city": "Москва",
  "property_type": "Квартира",
  "eta_seconds": 3600
}
```

#### GET /tasks/{task_id}

Get task information by ID.

#### DELETE /tasks/{task_id}

Cancel a task.

#### GET /tasks

List active and recent tasks.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| limit | integer | Number of tasks (1-100) | 10 |
| status | string | Filter by status | PENDING |

#### GET /tasks/workers/stats

Get Celery worker statistics.

### Health Checks

#### GET /health

Basic health check.

#### GET /health/detailed

Detailed health check.

#### GET /stats

Application statistics.

#### GET /cache/stats

Cache statistics.

#### GET /ratelimit/stats

Rate limit statistics.

#### GET /errors/diagnostic

Error diagnostics.

**Query Parameters:**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| error_type | string | Specific error type | TimeoutError |

## Supported Sources

The API currently supports parsing from the following sources:

1. **Avito** - https://www.avito.ru
2. **CIAN** - https://www.cian.ru
3. **Domofond** - https://domofond.ru
4. **Yandex Realty** - https://realty.yandex.ru

## Response Formats

All endpoints return JSON responses with UTF-8 encoding.

## Caching

Results are cached for 5 minutes to improve performance and reduce load on external sources.

## Examples

### Example 1: Find affordable apartments in Moscow

```http
GET /api/properties?city=Москва&property_type=Квартира&max_price=6000&min_rooms=1&max_rooms=2
```

### Example 2: Find properties with specific features

```http
GET /api/properties?city=Санкт-Петербург&features=wifi,parking&has_photos=true
```

### Example 3: Find properties sorted by price per square meter

```http
GET /api/properties?city=Москва&sort_by=price_per_sqm&sort_order=asc
```

### Example 4: Create a background parsing task

```http
POST /api/tasks/parse
Content-Type: application/json

{
  "city": "Новосибирск",
  "property_type": "Квартира"
}
```

## Monitoring and Metrics

The API exposes Prometheus metrics at `/metrics` endpoint, including:

- HTTP request counts and durations
- Parser performance metrics
- Active request counts
- Cache hit/miss ratios
- Error rates

## Changelog

### v1.0.0 (2023-06-15)
- Initial release
- Support for Avito and CIAN parsing
- Basic filtering and sorting
- PostgreSQL storage
- Background task processing with Celery