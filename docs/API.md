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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 404 | One or both properties not found |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Invalid parameters |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Invalid parameters |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 201 | Alert created successfully |
| 400 | Invalid parameters |
| 500 | Internal server error |

### List Alerts

`GET /api/properties/alerts`

List all active alerts for a specific email.

#### Parameters

| Name | Type | In | Required | Description |
|------|------|----|----------|-------------|
| email | string | query | Yes | Email to filter alerts |

#### Response

Array of property alert objects.

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Invalid parameters |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Alert updated successfully |
| 404 | Alert not found |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Alert deactivated successfully |
| 404 | Alert not found |
| 500 | Internal server error |

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

#### Response Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Alert deleted successfully |
| 404 | Alert not found |
| 500 | Internal server error |

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

### v1.1.0 (2023-06-16)
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