# RentScout Metrics Documentation

## Overview

RentScout includes a built-in monitoring system based on Prometheus that provides detailed metrics about application performance, usage patterns, and system health.

## Accessing Metrics

Metrics are exposed at the `/metrics` endpoint:

```
http://localhost:8000/metrics
```

## Metric Categories

### 1. HTTP Request Metrics

These metrics track incoming HTTP requests to the API:

- `http_requests_total` - Total number of HTTP requests
- `http_request_duration_seconds` - HTTP request duration in seconds
- `http_requests_in_progress` - Number of HTTP requests currently in progress

Labels:
- `method` - HTTP method (GET, POST, etc.)
- `endpoint` - API endpoint path
- `status_code` - HTTP status code

### 2. Parser Performance Metrics

These metrics track the performance of property parsers:

- `parser_calls_total` - Total number of parser calls
- `parser_duration_seconds` - Parser execution time in seconds
- `parser_errors_total` - Total number of parser errors

Labels:
- `parser_name` - Name of the parser (AvitoParser, CianParser, etc.)
- `status` - Result status (success, error)
- `error_type` - Type of error (if applicable)

### 3. Cache Metrics

These metrics track cache performance:

- `cache_hits_total` - Total number of cache hits
- `cache_misses_total` - Total number of cache misses
- `cache_errors_total` - Total number of cache errors
- `cache_hit_rate` - Cache hit rate (calculated)

Labels:
- `cache_type` - Type of cache (Redis, in-memory, etc.)

### 4. Database Metrics

These metrics track database performance:

- `db_queries_total` - Total number of database queries
- `db_query_duration_seconds` - Database query duration in seconds
- `db_connections_active` - Number of active database connections

Labels:
- `query_type` - Type of query (SELECT, INSERT, UPDATE, DELETE)
- `table` - Database table name

### 5. Task Metrics

These metrics track background task processing:

- `tasks_processed_total` - Total number of processed tasks
- `tasks_failed_total` - Total number of failed tasks
- `tasks_queued` - Number of tasks currently queued

Labels:
- `task_type` - Type of task (parse_city, batch_parse, etc.)
- `status` - Task status (success, failure)

### 6. Rate Limiting Metrics

These metrics track API rate limiting:

- `rate_limit_exceeded_total` - Total number of rate limit violations
- `rate_limit_current` - Current rate limit counter

Labels:
- `client_ip` - Client IP address

### 7. Application Metrics

These metrics track general application health:

- `application_uptime_seconds` - Application uptime in seconds
- `active_requests` - Number of currently active requests
- `memory_usage_bytes` - Application memory usage in bytes

## Example Queries

### API Performance

```
# 95th percentile of request latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Requests per second by endpoint
sum(rate(http_requests_total[5m])) by (endpoint)

# Error rate by endpoint
sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (endpoint) / sum(rate(http_requests_total[5m])) by (endpoint)
```

### Parser Performance

```
# Parser success rate
sum(rate(parser_calls_total{status="success"}[5m])) / sum(rate(parser_calls_total[5m]))

# Average parser execution time
rate(parser_duration_seconds_sum[5m]) / rate(parser_duration_seconds_count[5m])

# Parser errors by type
sum(rate(parser_errors_total[5m])) by (parser_name, error_type)
```

### Cache Performance

```
# Cache hit rate
sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Cache error rate
sum(rate(cache_errors_total[5m])) / sum(rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

### Database Performance

```
# Database query latency
histogram_quantile(0.95, sum(rate(db_query_duration_seconds_bucket[5m])) by (le, query_type))

# Database queries per second by type
sum(rate(db_queries_total[5m])) by (query_type)

# Active database connections
db_connections_active
```

## Alerting Rules

Recommended alerting rules for monitoring:

### High Error Rates

```
# API error rate > 5%
rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05

# Parser error rate > 10%
rate(parser_calls_total{status="error"}[5m]) / rate(parser_calls_total[5m]) > 0.1
```

### Performance Degradation

```
# 95th percentile latency > 1 second
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) > 1

# Cache hit rate < 80%
sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m]))) < 0.8
```

### Resource Exhaustion

```
# Active requests > 100
active_requests > 100

# Rate limit violations in last 5 minutes
increase(rate_limit_exceeded_total[5m]) > 0
```

## Dashboard Recommendations

### Main Dashboard

1. **API Throughput** - Requests per second
2. **Error Rates** - HTTP error percentage
3. **Latency** - 50th, 95th, 99th percentile response times
4. **Active Requests** - Currently processing requests
5. **Uptime** - Application uptime counter

### Parser Dashboard

1. **Parser Success Rate** - Percentage of successful parses
2. **Parser Latency** - Average and 95th percentile parse times
3. **Parser Errors** - Error counts by parser and type
4. **Parser Volume** - Number of parses per minute

### Cache Dashboard

1. **Cache Hit Rate** - Percentage of cache hits
2. **Cache Latency** - Cache operation times
3. **Cache Size** - Memory usage (if available)
4. **Cache Errors** - Cache operation failures

### Database Dashboard

1. **Query Performance** - Query latencies by type
2. **Connection Pool** - Active and idle connections
3. **Query Volume** - Queries per second by type
4. **Database Errors** - Database operation failures

## Integration with Grafana

To visualize these metrics in Grafana:

1. Add Prometheus as a data source
2. Import the provided dashboard templates (if available)
3. Create custom dashboards using the example queries above

## Troubleshooting

### Common Issues

1. **Metrics not appearing** - Ensure the application is running and the `/metrics` endpoint is accessible
2. **High cardinality** - Too many label combinations can impact Prometheus performance
3. **Missing metrics** - Check application logs for metric collection errors

### Debugging Steps

1. Verify the `/metrics` endpoint returns data
2. Check application logs for metric-related errors
3. Ensure Prometheus is configured to scrape the correct endpoint
4. Validate that metric names follow Prometheus naming conventions

## Custom Metrics

To add custom metrics to the application:

1. Import the metrics collector in your module:
   ```python
   from app.utils.metrics import metrics_collector
   ```

2. Register your custom metric:
   ```python
   CUSTOM_METRIC = metrics_collector.register_counter(
       "custom_metric_total",
       "Description of custom metric",
       ["label1", "label2"]
   )
   ```

3. Increment the metric in your code:
   ```python
   CUSTOM_METRIC.labels(label1="value1", label2="value2").inc()
   ```

## Performance Considerations

1. **Metric Collection Overhead** - Minimal impact on application performance
2. **Label Cardinality** - Keep label values bounded to prevent memory issues
3. **Metric Retention** - Configure Prometheus retention policies appropriately
4. **Scraping Interval** - Balance between freshness and resource usage

## Best Practices

1. Use appropriate metric types (counter, gauge, histogram, summary)
2. Follow Prometheus naming conventions (suffixes like `_total`, `_seconds`)
3. Limit label cardinality to prevent memory issues
4. Document custom metrics in this file
5. Regularly review and clean up unused metrics