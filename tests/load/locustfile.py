"""
Locust load tests for RentScout API.

Usage:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

    # Run headless (no web UI):
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 60s

    # With HTML report:
    locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 60s --html=report.html

Options:
    -u: Number of users to simulate
    -r: Spawn rate (users per second)
    -t: Test duration
"""

import random
import json
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner


# =============================================================================
# Test Data
# =============================================================================

CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург"]
PROPERTY_TYPES = ["Квартира", "Комната", "Дом"]
SOURCES = ["avito", "cian", "domclick", "domofond", "yandex_realty"]


# =============================================================================
# User Behaviors
# =============================================================================

class PropertySearchUser(HttpUser):
    """
    Simulates a user searching for properties.

    Behavior:
    - Search properties with various filters
    - View property details
    - Check health endpoints
    - Export data
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Called when user starts."""
        self.property_ids = []

    @task(10)
    def search_properties(self):
        """Search properties with random filters."""
        params = {
            "city": random.choice(CITIES),
            "property_type": random.choice(PROPERTY_TYPES),
            "limit": random.randint(10, 50),
            "skip": random.randint(0, 100),
        }

        # Add optional filters
        if random.random() > 0.5:
            params["min_price"] = random.randint(10000, 50000)
        if random.random() > 0.5:
            params["max_price"] = random.randint(50000, 200000)
        if random.random() > 0.5:
            params["min_rooms"] = random.randint(1, 2)
        if random.random() > 0.5:
            params["max_rooms"] = random.randint(2, 4)
        if random.random() > 0.5:
            params["min_area"] = random.randint(20, 40)
        if random.random() > 0.5:
            params["max_area"] = random.randint(40, 100)
        if random.random() > 0.5:
            params["source"] = random.choice(SOURCES)
        if random.random() > 0.5:
            params["sort_by"] = random.choice(["price", "area", "created_at"])
        if random.random() > 0.5:
            params["sort_order"] = random.choice(["asc", "desc"])

        with self.client.get("/api/properties", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "items" in data and len(data["items"]) > 0:
                    # Store property IDs for detail views
                    self.property_ids = [p["id"] for p in data["items"][:10]]
                    response.success()
                else:
                    response.success()  # No results is also valid
            else:
                response.failure(f"Search failed with status {response.status_code}")

    @task(5)
    def view_property_detail(self):
        """View property details."""
        if not self.property_ids:
            return

        property_id = random.choice(self.property_ids)
        self.client.get(f"/api/properties/{property_id}")

    @task(3)
    def check_health(self):
        """Check API health."""
        self.client.get("/api/health")

    @task(2)
    def check_parsers_health(self):
        """Check parsers health."""
        self.client.get("/api/health/parsers")

    @task(1)
    def export_data(self):
        """Export search results."""
        params = {
            "city": random.choice(CITIES),
            "format": random.choice(["json", "csv"]),
            "limit": random.randint(10, 100),
        }
        self.client.get("/api/properties/export", params=params)


class APIOnlyUser(HttpUser):
    """
    Simulates API-only usage (no browser).

    Lighter weight user for stress testing.
    """

    wait_time = between(0.5, 1)

    @task(20)
    def quick_search(self):
        """Quick search with minimal filters."""
        self.client.get(
            "/api/properties",
            params={
                "city": "Москва",
                "limit": 20,
            }
        )

    @task(5)
    def health_check(self):
        """Quick health check."""
        self.client.get("/api/health")


class HeavyUser(HttpUser):
    """
    Simulates power user with complex queries.
    """

    wait_time = between(2, 5)

    @task(10)
    def complex_search(self):
        """Search with many filters."""
        params = {
            "city": random.choice(CITIES),
            "property_type": random.choice(PROPERTY_TYPES),
            "min_price": random.randint(20000, 50000),
            "max_price": random.randint(100000, 200000),
            "min_rooms": 2,
            "max_rooms": 3,
            "min_area": 40,
            "max_area": 80,
            "min_floor": 3,
            "max_floor": 10,
            "has_photos": True,
            "source": random.choice(SOURCES),
            "sort_by": "price",
            "sort_order": "asc",
            "limit": 50,
        }
        self.client.get("/api/properties", params=params)

    @task(5)
    def statistics(self):
        """Get property statistics."""
        self.client.get(
            "/api/properties/statistics",
            params={"city": random.choice(CITIES)}
        )

    @task(3)
    def price_trends(self):
        """Get price trends."""
        self.client.get(
            "/api/properties/trends",
            params={
                "city": random.choice(CITIES),
                "days": 30,
            }
        )


# =============================================================================
# Event Handlers
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("=" * 60)
    print("🚀 RentScout Load Test Starting")
    print("=" * 60)
    print(f"Target: {environment.host}")
    print(f"Users: {environment.parsed_options.num_users if environment.parsed_options else 'N/A'}")
    print(f"Spawn rate: {environment.parsed_options.spawn_rate if environment.parsed_options else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("=" * 60)
    print("✅ Load Test Completed")
    print("=" * 60)

    if environment.stats:
        print(f"Total requests: {environment.stats.total.num_requests}")
        print(f"Failed requests: {environment.stats.total.num_failures}")
        print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
        print(f"Requests/sec: {environment.stats.total.current_rps:.2f}")
    print("=" * 60)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Called on each request."""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")


# =============================================================================
# Configuration for distributed mode
# =============================================================================

def worker_init(worker):
    """Initialize worker in distributed mode."""
    print(f"Worker {worker.client_id} connected")


def master_init(master):
    """Initialize master in distributed mode."""
    print(f"Master ready, waiting for workers")


if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8000")
