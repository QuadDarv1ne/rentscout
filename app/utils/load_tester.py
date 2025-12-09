"""
Load testing и benchmarking для оценки производительности системы.

Инструменты:
- Асинхронные тесты нагрузки
- Benchmarking различных компонентов
- Анализ результатов и генерация отчётов
"""
import asyncio
import time
from typing import List, Callable, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import statistics
from concurrent.futures import ThreadPoolExecutor

import httpx
from tqdm import tqdm


@dataclass
class LoadTestConfig:
    """Конфигурация load testing."""
    base_url: str
    endpoints: List[str]  # Список эндпоинтов для тестирования
    concurrent_users: int = 10
    requests_per_user: int = 100
    timeout: int = 30
    test_duration_seconds: Optional[int] = None
    ramp_up_seconds: int = 0  # Время для постепенного увеличения нагрузки


@dataclass
class RequestMetrics:
    """Метрики одного запроса."""
    status_code: int
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class LoadTestResults:
    """Результаты load testing."""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    metrics: List[RequestMetrics]
    
    @property
    def success_rate(self) -> float:
        """Процент успешных запросов."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
        
    @property
    def average_response_time_ms(self) -> float:
        """Среднее время ответа."""
        if not self.metrics:
            return 0.0
        durations = [m.duration_ms for m in self.metrics]
        return statistics.mean(durations)
        
    @property
    def median_response_time_ms(self) -> float:
        """Медианное время ответа."""
        if not self.metrics:
            return 0.0
        durations = [m.duration_ms for m in self.metrics if m.status_code == 200]
        if not durations:
            return 0.0
        return statistics.median(durations)
        
    @property
    def p95_response_time_ms(self) -> float:
        """95-й перцентиль времени ответа."""
        if not self.metrics:
            return 0.0
        durations = sorted([m.duration_ms for m in self.metrics])
        idx = int(len(durations) * 0.95)
        return durations[idx] if idx < len(durations) else 0.0
        
    @property
    def p99_response_time_ms(self) -> float:
        """99-й перцентиль времени ответа."""
        if not self.metrics:
            return 0.0
        durations = sorted([m.duration_ms for m in self.metrics])
        idx = int(len(durations) * 0.99)
        return durations[idx] if idx < len(durations) else 0.0
        
    @property
    def requests_per_second(self) -> float:
        """Количество запросов в секунду."""
        if self.duration_seconds == 0:
            return 0.0
        return self.total_requests / self.duration_seconds
        
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            'endpoint': self.endpoint,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': f"{self.success_rate:.2f}%",
            'duration_seconds': self.duration_seconds,
            'requests_per_second': f"{self.requests_per_second:.2f}",
            'average_response_time_ms': f"{self.average_response_time_ms:.2f}",
            'median_response_time_ms': f"{self.median_response_time_ms:.2f}",
            'p95_response_time_ms': f"{self.p95_response_time_ms:.2f}",
            'p99_response_time_ms': f"{self.p99_response_time_ms:.2f}",
        }


class LoadTester:
    """Инструмент для load testing."""
    
    def __init__(self, config: LoadTestConfig):
        """
        Инициализация.
        
        Args:
            config: Конфигурация тестирования
        """
        self.config = config
        self.results: List[LoadTestResults] = []
        
    async def _make_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str
    ) -> RequestMetrics:
        """
        Выполнение одного запроса.
        
        Args:
            client: httpx AsyncClient
            endpoint: Эндпоинт для запроса
            
        Returns:
            Метрики запроса
        """
        start_time = time.time()
        
        try:
            response = await client.get(
                f"{self.config.base_url}{endpoint}",
                timeout=httpx.Timeout(self.config.timeout)
            )
            duration_ms = (time.time() - start_time) * 1000
            
            return RequestMetrics(
                status_code=response.status_code,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            return RequestMetrics(
                status_code=0,
                duration_ms=duration_ms,
                error=str(e)
            )
            
    async def _user_session(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        requests_count: int,
        progress_bar: Optional[tqdm] = None
    ) -> List[RequestMetrics]:
        """
        Симуляция сессии одного пользователя.
        
        Args:
            client: httpx AsyncClient
            endpoint: Эндпоинт для запроса
            requests_count: Количество запросов
            progress_bar: Progress bar для отслеживания
            
        Returns:
            Список метрик запросов
        """
        metrics = []
        
        for _ in range(requests_count):
            metric = await self._make_request(client, endpoint)
            metrics.append(metric)
            
            if progress_bar:
                progress_bar.update(1)
                
        return metrics
        
    async def run_test(self, endpoint: str) -> LoadTestResults:
        """
        Запуск теста нагрузки для одного эндпоинта.
        
        Args:
            endpoint: Эндпоинт для тестирования
            
        Returns:
            Результаты тестирования
        """
        print(f"\n🚀 Testing {endpoint}")
        print(f"   Users: {self.config.concurrent_users}")
        print(f"   Requests per user: {self.config.requests_per_user}")
        
        all_metrics: List[RequestMetrics] = []
        start_time = time.time()
        
        # Создание progress bar
        total_requests = self.config.concurrent_users * self.config.requests_per_user
        progress_bar = tqdm(total=total_requests, unit="req", desc="Requests")
        
        try:
            # Создание HTTP клиента
            limits = httpx.Limits(max_connections=self.config.concurrent_users)
            async with httpx.AsyncClient(limits=limits) as client:
                # Создание задач для всех пользователей
                tasks = [
                    self._user_session(
                        client,
                        endpoint,
                        self.config.requests_per_user,
                        progress_bar
                    )
                    for _ in range(self.config.concurrent_users)
                ]
                
                # Рamp-up: постепенное увеличение нагрузки
                if self.config.ramp_up_seconds > 0:
                    delay = self.config.ramp_up_seconds / self.config.concurrent_users
                    for task in tasks:
                        asyncio.create_task(task)
                        await asyncio.sleep(delay)
                    
                    results = await asyncio.gather(*tasks)
                else:
                    results = await asyncio.gather(*tasks)
                    
                # Объединение результатов
                for user_metrics in results:
                    all_metrics.extend(user_metrics)
                    
        finally:
            progress_bar.close()
            
        duration_seconds = time.time() - start_time
        
        # Подсчёт успешных/неуспешных
        successful = sum(1 for m in all_metrics if m.status_code == 200)
        failed = len(all_metrics) - successful
        
        return LoadTestResults(
            endpoint=endpoint,
            total_requests=len(all_metrics),
            successful_requests=successful,
            failed_requests=failed,
            duration_seconds=duration_seconds,
            metrics=all_metrics
        )
        
    async def run_all_tests(self) -> List[LoadTestResults]:
        """
        Запуск тестов для всех эндпоинтов.
        
        Returns:
            Список результатов для каждого эндпоинта
        """
        print(f"\n{'='*60}")
        print(f"🔥 Load Testing Report")
        print(f"URL: {self.config.base_url}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        for endpoint in self.config.endpoints:
            result = await self.run_test(endpoint)
            self.results.append(result)
            
        return self.results
        
    def print_results(self):
        """Вывод результатов тестирования."""
        print(f"\n{'='*60}")
        print(f"📊 Load Test Results")
        print(f"{'='*60}\n")
        
        for result in self.results:
            print(f"📍 Endpoint: {result.endpoint}")
            print(f"   Total Requests: {result.total_requests}")
            print(f"   Successful: {result.successful_requests} ({result.success_rate:.2f}%)")
            print(f"   Failed: {result.failed_requests}")
            print(f"   Duration: {result.duration_seconds:.2f}s")
            print(f"   Throughput: {result.requests_per_second:.2f} req/s")
            print(f"   Response Times:")
            print(f"      Average: {result.average_response_time_ms:.2f}ms")
            print(f"      Median: {result.median_response_time_ms:.2f}ms")
            print(f"      P95: {result.p95_response_time_ms:.2f}ms")
            print(f"      P99: {result.p99_response_time_ms:.2f}ms")
            print()
            
    def export_results(self, filepath: str = "load_test_results.json"):
        """
        Экспорт результатов в JSON.
        
        Args:
            filepath: Путь к файлу для сохранения
        """
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'base_url': self.config.base_url,
                'concurrent_users': self.config.concurrent_users,
                'requests_per_user': self.config.requests_per_user,
            },
            'results': [r.to_dict() for r in self.results]
        }
        
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        print(f"\n✅ Results exported to {filepath}")


async def example_load_test():
    """Пример использования load tester."""
    config = LoadTestConfig(
        base_url="http://localhost:8000",
        endpoints=[
            "/health",
            "/api/properties",
            "/api/search?location=Moscow"
        ],
        concurrent_users=10,
        requests_per_user=100,
        ramp_up_seconds=5
    )
    
    tester = LoadTester(config)
    await tester.run_all_tests()
    tester.print_results()
    tester.export_results("data/load_test_results.json")


if __name__ == "__main__":
    asyncio.run(example_load_test())
