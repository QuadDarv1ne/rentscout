#!/usr/bin/env python3
"""
Performance benchmarking script for RentScout search operations.

This script measures the performance of various search operations
and compares cached vs non-cached performance.
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.search import SearchService
from app.services.optimized_search import OptimizedSearchService


class SearchBenchmark:
    """Benchmark suite for search operations."""
    
    def __init__(self):
        self.results: Dict[str, List[float]] = {}
    
    async def benchmark_basic_search(self, iterations: int = 10) -> Dict[str, Any]:
        """Benchmark basic search operations."""
        print("Running basic search benchmark...")
        
        # Test cities
        test_cities = ["Москва", "Санкт-Петербург", "Новосибирск"]
        results = {}
        
        for city in test_cities:
            print(f"Benchmarking search for {city}...")
            
            # Benchmark original search service
            search_service = SearchService()
            times = []
            
            for i in range(iterations):
                start_time = time.time()
                try:
                    properties = await search_service.search(city, "Квартира")
                    end_time = time.time()
                    times.append(end_time - start_time)
                except Exception as e:
                    print(f"Error in iteration {i}: {e}")
                    continue
            
            if times:
                results[f"{city}_basic"] = {
                    "mean_time": statistics.mean(times),
                    "median_time": statistics.median(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "iterations": len(times)
                }
            
            # Benchmark optimized search service (cached)
            optimized_service = OptimizedSearchService()
            cached_times = []
            
            for i in range(iterations):
                start_time = time.time()
                try:
                    properties, is_cached, stats = await optimized_service.search_cached(
                        city, "Квартира"
                    )
                    end_time = time.time()
                    cached_times.append(end_time - start_time)
                except Exception as e:
                    print(f"Error in iteration {i}: {e}")
                    continue
            
            if cached_times:
                results[f"{city}_optimized"] = {
                    "mean_time": statistics.mean(cached_times),
                    "median_time": statistics.median(cached_times),
                    "min_time": min(cached_times),
                    "max_time": max(cached_times),
                    "iterations": len(cached_times)
                }
        
        return results
    
    async def benchmark_concurrent_searches(self, concurrency: int = 5) -> Dict[str, Any]:
        """Benchmark concurrent search operations."""
        print(f"Running concurrent search benchmark with {concurrency} concurrent requests...")
        
        search_service = OptimizedSearchService()
        city = "Москва"
        
        # Measure concurrent performance
        start_time = time.time()
        
        # Create concurrent tasks
        tasks = []
        for i in range(concurrency):
            task = search_service.search_cached(city, "Квартира")
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Count successful operations
        successful_ops = sum(1 for r in results if not isinstance(r, Exception))
        
        return {
            "concurrent_requests": concurrency,
            "successful_operations": successful_ops,
            "total_time": total_time,
            "operations_per_second": successful_ops / total_time if total_time > 0 else 0
        }
    
    def print_results(self, basic_results: Dict[str, Any], concurrent_results: Dict[str, Any]):
        """Print formatted benchmark results."""
        print("\n" + "="*80)
        print("SEARCH PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        print("\nBasic Search Performance:")
        print("-" * 50)
        for key, metrics in basic_results.items():
            print(f"\n{key}:")
            print(f"  Mean Time:     {metrics['mean_time']:.3f}s")
            print(f"  Median Time:   {metrics['median_time']:.3f}s")
            print(f"  Min Time:      {metrics['min_time']:.3f}s")
            print(f"  Max Time:      {metrics['max_time']:.3f}s")
            print(f"  Iterations:    {metrics['iterations']}")
        
        print("\nConcurrent Search Performance:")
        print("-" * 50)
        print(f"  Concurrent Requests:     {concurrent_results['concurrent_requests']}")
        print(f"  Successful Operations:   {concurrent_results['successful_operations']}")
        print(f"  Total Time:              {concurrent_results['total_time']:.3f}s")
        print(f"  Operations Per Second:   {concurrent_results['operations_per_second']:.2f}")
        
        # Compare performance improvements
        print("\nPerformance Improvements:")
        print("-" * 50)
        for city in ["Москва", "Санкт-Петербург", "Новосибирск"]:
            basic_key = f"{city}_basic"
            optimized_key = f"{city}_optimized"
            
            if basic_key in basic_results and optimized_key in basic_results:
                basic_mean = basic_results[basic_key]['mean_time']
                optimized_mean = basic_results[optimized_key]['mean_time']
                
                if optimized_mean > 0:
                    improvement = ((basic_mean - optimized_mean) / basic_mean) * 100
                    print(f"  {city}: {improvement:.1f}% faster with caching")


async def main():
    """Run the benchmark suite."""
    print("RentScout Search Performance Benchmark")
    print("=" * 50)
    
    benchmark = SearchBenchmark()
    
    # Run basic search benchmark
    basic_results = await benchmark.benchmark_basic_search(iterations=3)
    
    # Run concurrent search benchmark
    concurrent_results = await benchmark.benchmark_concurrent_searches(concurrency=5)
    
    # Print results
    benchmark.print_results(basic_results, concurrent_results)
    
    print("\nBenchmark completed!")


if __name__ == "__main__":
    asyncio.run(main())