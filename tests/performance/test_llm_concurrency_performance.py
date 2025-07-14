"""Performance testing for optimal LLM request concurrency."""

import asyncio
import time
import statistics
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
import sys
import json

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.llm.client import LLMClient, LLMError
from src.config import get_settings


@dataclass
class ConcurrencyMetrics:
    """Metrics for a single concurrency level test."""
    concurrency_level: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    avg_response_time: float
    median_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput: float  # requests per second
    error_rate: float
    timeout_rate: float
    response_times: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding raw response times."""
        data = asdict(self)
        data.pop('response_times')  # Remove large array from output
        return data


class LLMConcurrencyTester:
    """Test LLM API performance with different concurrency levels."""
    
    # Test configuration
    MIN_CONCURRENCY = 1
    MAX_CONCURRENCY = 50
    CONCURRENCY_LEVELS = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]
    TOTAL_REQUESTS = 100  # Total requests to make per test
    WARMUP_REQUESTS = 5
    TIMEOUT_THRESHOLD = 30.0
    PERFORMANCE_DEGRADATION_THRESHOLD = 1.2  # 20% slower
    ERROR_RATE_THRESHOLD = 0.05  # 5% error rate
    RUNS_PER_LEVEL = 3  # Multiple runs for averaging
    
    # Test prompt (simple, consistent workload)
    TEST_PROMPT = """Analyze this code snippet and provide a brief summary:

```python
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)
```

Provide a one-sentence description of what this function does."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize concurrency tester."""
        self.llm_client = llm_client or LLMClient()
        self.results: Dict[int, ConcurrencyMetrics] = {}
        self.optimal_concurrency: Optional[int] = None
        
    async def _send_request(self, semaphore: asyncio.Semaphore, request_id: int) -> tuple[Optional[float], Optional[str]]:
        """Send a single LLM request with concurrency control."""
        async with semaphore:
            start_time = time.time()
            try:
                response = await self.llm_client.generate(
                    prompt=self.TEST_PROMPT,
                    system_prompt="You are a helpful code analysis assistant.",
                    temperature=0.1,
                    max_tokens=100
                )
                response_time = time.time() - start_time
                return response_time, None
            except asyncio.TimeoutError:
                return None, "timeout"
            except LLMError as e:
                return None, f"error: {str(e)}"
            except Exception as e:
                return None, f"unexpected: {str(e)}"
    
    async def warmup(self):
        """Warm up the LLM API connection."""
        print("🔥 Warming up LLM connection...")
        warmup_tasks = []
        semaphore = asyncio.Semaphore(5)  # Moderate concurrency for warmup
        
        for i in range(self.WARMUP_REQUESTS):
            warmup_tasks.append(self._send_request(semaphore, i))
        
        await asyncio.gather(*warmup_tasks)
        print("✅ Warmup complete\n")
    
    async def test_concurrency_level(self, concurrency_level: int) -> ConcurrencyMetrics:
        """Test performance at a specific concurrency level."""
        print(f"\n📊 Testing concurrency level: {concurrency_level}")
        
        all_response_times = []
        failed_requests = 0
        timeout_count = 0
        run_results = []
        
        # Run multiple times for averaging
        for run in range(self.RUNS_PER_LEVEL):
            print(f"  Run {run + 1}/{self.RUNS_PER_LEVEL}...", end='', flush=True)
            
            response_times = []
            run_failed = 0
            run_timeout = 0
            
            # Create semaphore for this concurrency level
            semaphore = asyncio.Semaphore(concurrency_level)
            
            # Create all tasks
            tasks = []
            for i in range(self.TOTAL_REQUESTS):
                tasks.append(self._send_request(semaphore, i))
            
            # Execute with controlled concurrency
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time
            
            # Process results
            for response_time, error in results:
                if response_time is not None:
                    response_times.append(response_time)
                else:
                    run_failed += 1
                    if error == "timeout":
                        run_timeout += 1
            
            if response_times:
                run_results.append({
                    'response_times': response_times,
                    'failed': run_failed,
                    'timeouts': run_timeout,
                    'total_time': total_time
                })
                all_response_times.extend(response_times)
                failed_requests += run_failed
                timeout_count += run_timeout
                
            print(f" ✓ ({len(response_times)}/{self.TOTAL_REQUESTS} successful, {total_time:.2f}s)")
        
        # Calculate aggregate metrics
        if not all_response_times:
            # All requests failed
            return ConcurrencyMetrics(
                concurrency_level=concurrency_level,
                total_requests=self.TOTAL_REQUESTS * self.RUNS_PER_LEVEL,
                successful_requests=0,
                failed_requests=self.TOTAL_REQUESTS * self.RUNS_PER_LEVEL,
                total_time=0,
                avg_response_time=0,
                median_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
                throughput=0,
                error_rate=1.0,
                timeout_rate=1.0,
                response_times=[]
            )
        
        # Calculate statistics
        total_requests = self.TOTAL_REQUESTS * self.RUNS_PER_LEVEL
        successful_requests = len(all_response_times)
        
        # Average total time across runs
        avg_total_time = sum(r['total_time'] for r in run_results) / len(run_results)
        
        # Sort response times for percentile calculations
        sorted_times = sorted(all_response_times)
        
        metrics = ConcurrencyMetrics(
            concurrency_level=concurrency_level,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_time=avg_total_time,
            avg_response_time=statistics.mean(all_response_times),
            median_response_time=statistics.median(all_response_times),
            p95_response_time=sorted_times[int(len(sorted_times) * 0.95)],
            p99_response_time=sorted_times[int(len(sorted_times) * 0.99)],
            throughput=successful_requests / avg_total_time,
            error_rate=failed_requests / total_requests,
            timeout_rate=timeout_count / total_requests,
            response_times=all_response_times
        )
        
        # Print summary
        print(f"  📈 Summary: {metrics.throughput:.2f} req/s, "
              f"avg latency: {metrics.avg_response_time:.2f}s, "
              f"error rate: {metrics.error_rate:.1%}")
        
        return metrics
    
    async def run_performance_test(self):
        """Run the complete performance test suite."""
        print("🚀 Starting LLM Concurrency Performance Test")
        print("=" * 60)
        print(f"Configuration:")
        print(f"  - Total requests per test: {self.TOTAL_REQUESTS}")
        print(f"  - Runs per concurrency level: {self.RUNS_PER_LEVEL}")
        print(f"  - Concurrency levels to test: {self.CONCURRENCY_LEVELS}")
        print(f"  - LLM endpoint: {self.llm_client.endpoint}")
        print(f"  - LLM model: {self.llm_client.model}")
        print("=" * 60)
        
        # Warm up
        await self.warmup()
        
        # Test each concurrency level
        for concurrency_level in self.CONCURRENCY_LEVELS:
            metrics = await self.test_concurrency_level(concurrency_level)
            self.results[concurrency_level] = metrics
            
            # Save intermediate results
            self._save_results()
        
        # Find optimal concurrency
        self._find_optimal_concurrency()
        
        # Generate and save report
        report = self._generate_report()
        self._save_report(report)
    
    def _find_optimal_concurrency(self):
        """Find the optimal concurrency level based on throughput and error rate."""
        valid_results = [
            (level, metrics) for level, metrics in self.results.items()
            if metrics.error_rate < self.ERROR_RATE_THRESHOLD
        ]
        
        if not valid_results:
            print("\n⚠️  No concurrency level achieved acceptable error rate!")
            self.optimal_concurrency = 1
            return
        
        # Sort by throughput
        valid_results.sort(key=lambda x: x[1].throughput, reverse=True)
        
        # Find the point where throughput stops improving significantly
        best_throughput = valid_results[0][1].throughput
        
        for level, metrics in valid_results:
            # If throughput is within 95% of best, prefer lower concurrency for stability
            if metrics.throughput >= best_throughput * 0.95:
                self.optimal_concurrency = level
                break
        
        if self.optimal_concurrency is None:
            self.optimal_concurrency = valid_results[0][0]
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive performance report."""
        sorted_results = sorted(self.results.items())
        
        report = {
            "test_configuration": {
                "total_requests_per_test": self.TOTAL_REQUESTS,
                "runs_per_level": self.RUNS_PER_LEVEL,
                "concurrency_levels": self.CONCURRENCY_LEVELS,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "results": {
                level: metrics.to_dict() 
                for level, metrics in sorted_results
            },
            "optimal_concurrency": self.optimal_concurrency,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> Dict[str, Any]:
        """Generate recommendations based on test results."""
        if not self.optimal_concurrency or self.optimal_concurrency not in self.results:
            return {
                "error": "Could not determine optimal concurrency",
                "fallback_concurrency": 5
            }
        
        optimal_metrics = self.results[self.optimal_concurrency]
        
        # Find the highest stable concurrency (low error rate, good performance)
        stable_levels = [
            (level, metrics) for level, metrics in self.results.items()
            if metrics.error_rate < 0.01  # Less than 1% errors
        ]
        
        highest_stable = max(stable_levels, key=lambda x: x[0])[0] if stable_levels else self.optimal_concurrency
        
        return {
            "optimal_concurrency": self.optimal_concurrency,
            "optimal_throughput": round(optimal_metrics.throughput, 2),
            "optimal_avg_latency": round(optimal_metrics.avg_response_time, 2),
            "highest_stable_concurrency": highest_stable,
            "recommended_production_concurrency": min(self.optimal_concurrency, 20),  # Conservative for production
            "config_yaml_snippet": {
                "llm": {
                    "max_concurrent_requests": min(self.optimal_concurrency, 20),
                    "request_timeout": 30.0,
                    "retry_attempts": 3
                }
            }
        }
    
    def _save_results(self):
        """Save intermediate results to file."""
        output_file = Path(__file__).parent / "concurrency_test_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                level: metrics.to_dict() 
                for level, metrics in self.results.items()
            }, f, indent=2)
    
    def _save_report(self, report: Dict[str, Any]):
        """Save the final report."""
        output_file = Path(__file__).parent / "concurrency_performance_report.json"
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Report saved to: {output_file}")
    
    def print_summary(self):
        """Print a summary of the test results."""
        if not self.results:
            print("\n❌ No test results available")
            return
        
        print("\n" + "=" * 60)
        print("📊 CONCURRENCY TEST SUMMARY")
        print("=" * 60)
        
        # Table header
        print(f"{'Concurrency':<12} {'Throughput':<12} {'Avg Latency':<12} {'P95 Latency':<12} {'Error Rate':<12}")
        print("-" * 60)
        
        # Results table
        for level in sorted(self.results.keys()):
            metrics = self.results[level]
            print(f"{level:<12} "
                  f"{metrics.throughput:>9.2f}/s  "
                  f"{metrics.avg_response_time:>9.2f}s  "
                  f"{metrics.p95_response_time:>9.2f}s  "
                  f"{metrics.error_rate:>10.1%}  ")
        
        print("=" * 60)
        
        if self.optimal_concurrency:
            optimal = self.results[self.optimal_concurrency]
            print(f"\n🎯 Optimal Concurrency: {self.optimal_concurrency}")
            print(f"   - Throughput: {optimal.throughput:.2f} requests/second")
            print(f"   - Average latency: {optimal.avg_response_time:.2f} seconds")
            print(f"   - Error rate: {optimal.error_rate:.1%}")
            
            recommendations = self._generate_recommendations()
            print(f"\n📝 Recommendations:")
            print(f"   - Production concurrency: {recommendations['recommended_production_concurrency']}")
            print(f"   - Highest stable concurrency: {recommendations['highest_stable_concurrency']}")
            print(f"\n🔧 Add to config.yaml:")
            print("   ```yaml")
            print("   llm:")
            print(f"     max_concurrent_requests: {recommendations['config_yaml_snippet']['llm']['max_concurrent_requests']}")
            print(f"     request_timeout: {recommendations['config_yaml_snippet']['llm']['request_timeout']}")
            print(f"     retry_attempts: {recommendations['config_yaml_snippet']['llm']['retry_attempts']}")
            print("   ```")


async def main():
    """Run the concurrency test."""
    tester = LLMConcurrencyTester()
    try:
        await tester.run_performance_test()
        tester.print_summary()
    finally:
        await tester.llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())