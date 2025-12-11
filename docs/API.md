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
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error - Something went wrong |

## Core Endpoints

### Property Search

Search for rental properties across multiple platforms with advanced filtering.

#### Search Properties

`GET /api/properties/search`

Search properties with basic filtering.

##### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| city | string | query | Yes | City to search in |
| property_type | string | query | No | Type of property (default: Квартира) |
| min_price | number | query | No | Minimum price |
| max_price | number | query | No | Maximum price |
| min_rooms | integer | query | No | Minimum number of rooms |
| max_rooms | integer | query | No | Maximum number of rooms |
| min_area | number | query | No | Minimum area in square meters |
| max_area | number | query | No | Maximum area in square meters |
| min_floor | integer | query | No | Minimum floor |
| max_floor | integer | query | No | Maximum floor |
| min_total_floors | integer | query | No | Minimum total floors |
| max_total_floors | integer | query | No | Maximum total floors |
| district | string | query | No | District filter |
| has_photos | boolean | query | No | Filter by presence of photos |
| source | string | query | No | Filter by source (avito, cian, etc.) |
| features | array | query | No | List of required features |
| max_price_per_sqm | number | query | No | Maximum price per square meter |
| has_contact | boolean | query | No | Filter by presence of contact info |
| min_first_seen | string | query | No | Minimum first seen date (ISO format) |
| max_first_seen | string | query | No | Maximum first seen date (ISO format) |
| min_last_seen | string | query | No | Minimum last seen date (ISO format) |
| max_last_seen | string | query | No | Maximum last seen date (ISO format) |
| sort_by | string | query | No | Sort by field (price, area, rooms, floor, first_seen, last_seen) |
| sort_order | string | query | No | Sort order (asc or desc) |
| skip | integer | query | No | Number of records to skip (pagination) |
| limit | integer | query | No | Max records in response (1-100) |

##### Response

Array of property objects.

#### Advanced Search

`POST /api/properties/advanced-search`

Advanced search with comprehensive filtering and ranking.

##### Request Body

```json
{
  "city": "Москва",
  "property_type": "Квартира",
  "min_price": 30000,
  "max_price": 100000,
  "min_rooms": 1,
  "max_rooms": 3,
  "min_area": 30,
  "max_area": 100,
  "sort_by": "price",
  "sort_order": "asc",
  "limit": 50
}
```

##### Response

Array of property objects sorted by the specified criteria.

### Property Management

Manage properties stored in the PostgreSQL database.

#### Get Property by ID

`GET /api/db/properties/{property_id}`

Retrieve a specific property by its ID.

##### Response

Property object.

#### Create Property

`POST /api/db/properties/`

Create a new property in the database.

##### Request Body

Property object.

##### Response

Created property object.

#### Update Property

`PUT /api/db/properties/{property_id}`

Update an existing property.

##### Request Body

Property object with updated fields.

##### Response

Updated property object.

#### Delete Property

`DELETE /api/db/properties/{property_id}`

Delete a property from the database.

##### Response

```json
{
  "success": true,
  "message": "Property deleted successfully"
}
```

### Property Analytics

Analyze property data and market trends.

#### Get Property Statistics

`GET /api/db/properties/statistics`

Get comprehensive statistics about properties in the database.

##### Response

```json
{
  "total_properties": 1250,
  "sources": ["avito", "cian"],
  "avg_price": 65000,
  "min_price": 30000,
  "max_price": 150000,
  "avg_area": 65.5,
  "price_per_sqm": 950
}
```

#### Search Properties by Price per Square Meter

`GET /api/db/properties/by-price-per-sqm`

Find properties within a specific price per square meter range.

##### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| min_price_per_sqm | number | query | No | Minimum price per square meter |
| max_price_per_sqm | number | query | No | Maximum price per square meter |
| limit | integer | query | No | Maximum number of results |

##### Response

Array of property objects.

## Machine Learning Endpoints

Advanced predictive analytics and market intelligence powered by machine learning.

### Price Prediction

`POST /api/ml/predict-price`

Predict rental price based on property characteristics using machine learning.

#### Request Body

```json
{
  "city": "Москва",
  "rooms": 2,
  "area": 60,
  "district": "Центральный",
  "floor": 5,
  "total_floors": 9,
  "is_verified": true
}
```

#### Response

```json
{
  "predicted_price": 75000,
  "confidence": 0.85,
  "price_range": [65000, 85000],
  "factors": {
    "area": 1.0,
    "rooms": 1.15,
    "city": 1.5,
    "district": 1.8,
    "floor": 1.0,
    "verified": 1.1
  },
  "trend": "stable",
  "recommendation": "Рынок стабилен. Хорошее время для аренды. Ожидаемая цена: 75000 ₽"
}
```

### Price Comparison

`POST /api/ml/compare-price`

Compare actual price with predicted market price.

#### Request Body

```json
{
  "actual_price": 70000,
  "city": "Москва",
  "rooms": 2,
  "area": 60,
  "district": "Центральный"
}
```

#### Response

```json
{
  "actual_price": 70000,
  "predicted_price": 75000,
  "difference": -5000,
  "percentage_difference": -6.67,
  "rating": "good",
  "comment": "Хорошая цена"
}
```

### Market Trends

`GET /api/ml/market-trends/{city}`

Analyze market trends for a specific city.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| rooms | integer | query | No | Number of rooms to filter by |

#### Response

```json
{
  "city": "Москва",
  "rooms": 2,
  "trend": "stable",
  "comment": "Рынок стабилен",
  "stats_7_days": {
    "count": 250,
    "avg_price": 72000,
    "min_price": 45000,
    "max_price": 120000
  },
  "stats_30_days": {
    "count": 1100,
    "avg_price": 71000,
    "min_price": 40000,
    "max_price": 130000
  },
  "change_percentage": 1.41
}
```

### Optimal Pricing

`GET /api/ml/optimal-price/{city}`

Get optimal price range for quick rental.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| rooms | integer | query | Yes | Number of rooms |
| area | number | query | Yes | Area in square meters |
| district | string | query | No | District |
| floor | integer | query | No | Floor |
| total_floors | integer | query | No | Total floors |
| is_verified | boolean | query | No | Verified property |

#### Response

```json
{
  "optimal_price": 71250,
  "min_competitive": 63750,
  "max_competitive": 86250,
  "market_average": 75000,
  "confidence": 0.85
}
```

### Price Statistics

`GET /api/ml/price-statistics/{city}`

Get price statistics for a city over a period.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| rooms | integer | query | No | Number of rooms |
| days | integer | query | No | Period in days (default: 30) |

#### Response

```json
{
  "count": 1250,
  "avg_price": 72000,
  "min_price": 30000,
  "max_price": 150000,
  "median_price": 68000,
  "std_dev": 15000
}
```

## Advanced Search Endpoints

Enhanced search capabilities with detailed analytics and property ranking.

### Price Distribution

`GET /api/properties/{city}/price-distribution`

Analyze price distribution in a city.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| property_type | string | query | No | Property type |
| bucket_count | integer | query | No | Number of distribution buckets |

#### Response

```json
{
  "count": 1250,
  "min": 30000,
  "max": 150000,
  "avg": 72000,
  "median": 68000,
  "distribution": [50, 120, 200, 300, 250, 180, 100, 30, 20]
}
```

### City Statistics

`GET /api/properties/{city}/statistics`

Get comprehensive statistics for a city.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| property_type | string | query | No | Property type |

#### Response

```json
{
  "city": "Москва",
  "property_type": "Квартира",
  "total_count": 1250,
  "sources": ["avito", "cian", "domofond", "yandex_realty", "domclick"],
  "price": {
    "min": 30000,
    "max": 150000,
    "avg": 72000
  },
  "area": {
    "min": 20,
    "max": 200,
    "avg": 65.5
  },
  "rooms": {
    "min": 1,
    "max": 5,
    "avg": 2.3
  },
  "price_per_sqm": {
    "min": 500,
    "max": 2000,
    "avg": 1100
  }
}
```

### Compare Cities

`GET /api/properties/compare-cities`

Compare property markets across multiple cities.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| cities | array | query | Yes | List of cities to compare |
| property_type | string | query | No | Property type |

#### Response

```json
{
  "Москва": {
    "total_count": 1250,
    "avg_price": 72000,
    "min_price": 30000,
    "max_price": 150000,
    "avg_area": 65.5,
    "price_per_sqm": 1100
  },
  "Санкт-Петербург": {
    "total_count": 890,
    "avg_price": 58000,
    "min_price": 25000,
    "max_price": 120000,
    "avg_area": 58.2,
    "price_per_sqm": 950
  },
  "best_value": "Санкт-Петербург"
}
```

### Top Rated Properties

`GET /api/properties/{city}/top-rated`

Get properties ranked by comprehensive scoring system.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| property_type | string | query | No | Property type |
| limit | integer | query | No | Maximum number of results |

#### Response

```json
[
  {
    "property": {
      "id": 12345,
      "source": "avito",
      "external_id": "avito_12345",
      "title": "2-комнатная квартира в центре",
      "price": 70000,
      "rooms": 2,
      "area": 60,
      "city": "Москва",
      "district": "Центральный",
      "is_verified": true
    },
    "score": {
      "total": 92.5,
      "price_score": 85.0,
      "area_score": 90.0,
      "location_score": 95.0,
      "amenities_score": 88.0,
      "verification_score": 100.0,
      "freshness_score": 95.0,
      "photos_score": 80.0,
      "price_per_sqm_score": 87.5,
      "market_position_score": 90.0
    },
    "rating": "Отличное"
  }
]
```

## Property Alerts

Create and manage property alerts to get notified about new listings.

### Create Alert

`POST /api/properties/alerts`

Create a new property alert.

#### Request Body

```json
{
  "city": "Москва",
  "max_price": 60000,
  "min_price": 40000,
  "rooms": 2,
  "min_area": 50,
  "max_area": 70,
  "email": "user@example.com"
}
```

#### Response

Property alert object.

### List Alerts

`GET /api/properties/alerts`

List all active alerts for a specific email.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| email | string | query | Yes | Email to filter alerts |

#### Response

Array of property alert objects.

### Update Alert

`PUT /api/properties/alerts/{alert_id}`

Update an existing property alert.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| alert_id | integer | path | Yes | Alert ID to update |

#### Request Body

Same as create alert.

#### Response

Updated property alert object.

### Deactivate Alert

`POST /api/properties/alerts/{alert_id}/deactivate`

Deactivate an existing property alert (does not delete it).

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| alert_id | integer | path | Yes | Alert ID to deactivate |

#### Response

```json
{
  "success": true,
  "message": "Alert deactivated successfully"
}
```

### Delete Alert

`DELETE /api/properties/alerts/{alert_id}`

Delete an existing property alert.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| alert_id | integer | path | Yes | Alert ID to delete |

#### Response

```json
{
  "success": true,
  "message": "Alert deleted successfully"
}
```

## Property Comparison

Compare two properties to help users make informed decisions.

### Compare Properties

`GET /api/properties/compare/{property_id1}/{property_id2}`

Compare two properties by their IDs.

#### Parameters

| Name | Type | In | Description |
|------|------|----|-------------|
| property_id1 | integer | path | First property ID |
| property_id2 | integer | path | Second property ID |

#### Response

```json
{
  "property1": {
    "id": 123,
    "title": "2-комнатная квартира в центре",
    "source": "avito",
    "price": 50000,
    "rooms": 2,
    "area": 60,
    "price_per_sqm": 833.33,
    "city": "Москва",
    "address": "Тверская, 1"
  },
  "property2": {
    "id": 456,
    "title": "Студия в бизнес-центре",
    "source": "cian",
    "price": 45000,
    "rooms": 1,
    "area": 40,
    "price_per_sqm": 1125.0,
    "city": "Москва",
    "address": "Арбат, 10"
  },
  "differences": {
    "price_difference": 5000,
    "price_per_sqm_diff": 291.67,
    "area_difference": 20,
    "rooms_difference": 1
  },
  "better_value": "property1"
}
```

## Property Recommendations

Get personalized property recommendations based on user criteria.

### Get Recommendations

`GET /api/properties/recommendations`

Get property recommendations based on various criteria.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| city | string | query | Yes | City to search in |
| budget | number | query | No | Maximum budget |
| rooms | integer | query | No | Number of rooms |
| min_area | number | query | No | Minimum area in square meters |
| max_area | number | query | No | Maximum area in square meters |
| limit | integer | query | No | Number of recommendations (default: 10, max: 50) |

#### Response

Array of property objects sorted by value (price per square meter).

## Price Trends

Analyze price trends over time to understand market dynamics.

### Get Price Trends

`GET /api/properties/trends/{city}`

Get price trends for a specific city over a period of time.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| city | string | path | Yes | City to analyze |
| days | integer | query | No | Number of days to analyze (default: 30, max: 365) |

#### Response

```json
{
  "city": "Москва",
  "days": 30,
  "trends": [
    {
      "date": "2023-06-01",
      "average_price": 55000,
      "property_count": 1250,
      "min_price": 30000,
      "max_price": 120000
    }
  ],
  "average_change": -2.5
}
```

## Property Export

Export property data in various formats for offline analysis.

### Export Properties

`GET /api/properties/export/{format}`

Export search results in CSV, JSON, or JSONL format.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| format | string | path | Yes | Export format (csv, json, jsonl) |
| city | string | query | Yes | City to search in |
| property_type | string | query | No | Property type |
| min_price | number | query | No | Minimum price |
| max_price | number | query | No | Maximum price |
| min_rooms | integer | query | No | Minimum rooms |
| max_rooms | integer | query | No | Maximum rooms |
| min_area | number | query | No | Minimum area |
| max_area | number | query | No | Maximum area |
| district | string | query | No | District filter |
| has_photos | boolean | query | No | Filter by photos |
| source | string | query | No | Filter by source |
| sort_by | string | query | No | Sort by field |
| sort_order | string | query | No | Sort order |

#### Response

File download with exported data.

## Metrics and Monitoring

The API exposes Prometheus metrics at `/metrics` for monitoring:

- HTTP request counts and durations
- Parser performance metrics
- Active request counts
- Cache hit/miss ratios
- Error rates
- Property processing metrics
- Business metrics (comparisons, recommendations, trends, alerts)

## Changelog

### v2.0.0 (2025-12-11)
- Added support for DomClick real estate platform
- Enhanced property scoring system with additional metrics (price per sqm, market position)
- Improved ML model accuracy with ensemble methods (LinearRegression + RandomForest)
- Optimized database indexes for better query performance
- Enhanced API documentation with comprehensive examples
- Added property export functionality (CSV, JSON, JSONL)

### v1.7.0 (2023-06-17)
- Enhanced ML model with scikit-learn integration
- Improved property scoring system with freshness and photos metrics
- Added top-rated properties endpoint with detailed scoring breakdown
- Enhanced database integration for all ML endpoints
- Improved API documentation with better examples

### v1.6.0 (2023-06-16)
- Added property comparison endpoint
- Added property recommendations endpoint
- Added price trends analysis endpoint
- Added property alerts system
- Enhanced metrics collection with business metrics
- Improved database connection pooling
- Added bulk insert operations for better performance

### v1.0.0 (2023-06-15)
- Initial release
- Support for Avito and CIAN parsing
- Basic filtering and sorting
- PostgreSQL storage
- Background task processing with Celery