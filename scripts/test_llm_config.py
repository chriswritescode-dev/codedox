#!/usr/bin/env python3
"""
Quick LLM Configuration Test Script

This script helps you find the optimal LLM configuration for your local setup.
It runs a simplified version of the performance test to determine the best
concurrency level for your LLM server.

Usage:
    python scripts/test_llm_config.py

The script will:
1. Test your current LLM connection
2. Run quick performance tests at different concurrency levels
3. Provide configuration recommendations for your .env file
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.llm.client import LLMClient, LLMError
from src.config import get_settings


class QuickLLMConfigTester:
    """Quick LLM configuration tester for optimal concurrency settings."""
    
    # Quick test configuration
    QUICK_CONCURRENCY_LEVELS = [1, 3, 5, 10, 15, 20]
    REQUESTS_PER_TEST = 20
    TIMEOUT_THRESHOLD = 10.0
    MAX_ERROR_RATE = 0.1  # 10%
    
    # Simple test prompt
    TEST_PROMPT = "What is 2 + 2? Answer with just the number."
    
    def __init__(self):
        """Initialize the tester."""
        self.settings = get_settings()
        self.llm_client = None
        self.results = {}
        
    async def test_connection(self) -> bool:
        """Test basic LLM connection."""
        print("🔍 Testing LLM connection...")
        
        try:
            self.llm_client = LLMClient(debug=True)
            connection_test = await self.llm_client.test_connection()
            
            if connection_test.get('connected'):
                print(f"✅ Connected to {connection_test.get('provider', 'unknown')} LLM")
                print(f"   Endpoint: {self.llm_client.endpoint}")
                print(f"   Model: {self.llm_client.model}")
                return True
            else:
                print(f"❌ Connection failed: {connection_test.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def quick_test_concurrency(self, concurrency: int) -> dict:
        """Run a quick test at specific concurrency level."""
        print(f"  Testing concurrency {concurrency}...", end='', flush=True)
        
        semaphore = asyncio.Semaphore(concurrency)
        start_time = time.time()
        successful = 0
        failed = 0
        response_times = []
        
        async def single_request():
            async with semaphore:
                request_start = time.time()
                try:
                    await self.llm_client.generate(
                        prompt=self.TEST_PROMPT,
                        temperature=0.1,
                        max_tokens=10
                    )
                    response_time = time.time() - request_start
                    response_times.append(response_time)
                    return True
                except Exception:
                    return False
        
        # Create and run tasks
        tasks = [single_request() for _ in range(self.REQUESTS_PER_TEST)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # Count results
        for result in results:
            if result is True:
                successful += 1
            else:
                failed += 1
        
        if successful == 0:
            print(" ❌ All requests failed")
            return {
                'concurrency': concurrency,
                'throughput': 0,
                'avg_response_time': 0,
                'error_rate': 1.0,
                'viable': False
            }
        
        avg_response_time = sum(response_times) / len(response_times)
        throughput = successful / total_time
        error_rate = failed / self.REQUESTS_PER_TEST
        viable = error_rate <= self.MAX_ERROR_RATE
        
        status = "✅" if viable else "⚠️"
        print(f" {status} {throughput:.1f} req/s, {avg_response_time:.2f}s avg, {error_rate:.1%} errors")
        
        return {
            'concurrency': concurrency,
            'throughput': throughput,
            'avg_response_time': avg_response_time,
            'error_rate': error_rate,
            'viable': viable
        }
    
    async def find_optimal_config(self):
        """Find optimal configuration through quick testing."""
        print("\n🚀 Running quick concurrency tests...")
        print("=" * 50)
        
        best_throughput = 0
        optimal_concurrency = 1
        viable_results = []
        
        for concurrency in self.QUICK_CONCURRENCY_LEVELS:
            result = await self.quick_test_concurrency(concurrency)
            self.results[concurrency] = result
            
            if result['viable']:
                viable_results.append(result)
                if result['throughput'] > best_throughput:
                    best_throughput = result['throughput']
                    optimal_concurrency = concurrency
        
        print("\n" + "=" * 50)
        return optimal_concurrency, viable_results
    
    def generate_recommendations(self, optimal_concurrency: int, viable_results: list):
        """Generate configuration recommendations."""
        print("📋 CONFIGURATION RECOMMENDATIONS")
        print("=" * 50)
        
        if not viable_results:
            print("❌ No viable concurrency levels found!")
            print("   Your LLM server may be overloaded or misconfigured.")
            print("   Try:")
            print("   - Reducing LLM_MAX_CONCURRENT_REQUESTS to 1-2")
            print("   - Increasing LLM_REQUEST_TIMEOUT")
            print("   - Checking LLM server resources")
            return
        
        # Find conservative and aggressive options
        conservative = min(r['concurrency'] for r in viable_results)
        aggressive = optimal_concurrency
        
        print(f"✅ Optimal concurrency found: {optimal_concurrency}")
        print(f"   Throughput: {self.results[optimal_concurrency]['throughput']:.2f} requests/second")
        print(f"   Average response time: {self.results[optimal_concurrency]['avg_response_time']:.2f} seconds")
        
        print(f"\n🔧 Recommended .env configuration:")
        print(f"   # Conservative (stable, lower throughput)")
        print(f"   LLM_MAX_CONCURRENT_REQUESTS={conservative}")
        print(f"   LLM_REQUEST_TIMEOUT=30.0")
        print(f"   LLM_RETRY_ATTEMPTS=3")
        
        print(f"\n   # Optimal (balanced performance)")
        print(f"   LLM_MAX_CONCURRENT_REQUESTS={optimal_concurrency}")
        print(f"   LLM_REQUEST_TIMEOUT=30.0")
        print(f"   LLM_RETRY_ATTEMPTS=3")
        
        if aggressive != conservative:
            print(f"\n   # Aggressive (maximum throughput, may be less stable)")
            print(f"   LLM_MAX_CONCURRENT_REQUESTS={aggressive}")
            print(f"   LLM_REQUEST_TIMEOUT=30.0")
            print(f"   LLM_RETRY_ATTEMPTS=3")
        
        print(f"\n💡 Tips:")
        print(f"   - Start with the conservative setting and increase if stable")
        print(f"   - Monitor your LLM server's CPU/GPU usage")
        print(f"   - Higher concurrency = faster crawling but more resource usage")
        print(f"   - For production, prefer stability over maximum throughput")
        
        # Generate system-specific advice
        if self.llm_client.endpoint.startswith('http://localhost') or '127.0.0.1' in self.llm_client.endpoint:
            print(f"\n🖥️  Local LLM detected:")
            if optimal_concurrency <= 5:
                print(f"   - Your system handles low concurrency well")
                print(f"   - Consider upgrading hardware for better performance")
            elif optimal_concurrency <= 15:
                print(f"   - Good local LLM performance")
                print(f"   - Your system can handle moderate parallel requests")
            else:
                print(f"   - Excellent local LLM performance!")
                print(f"   - Your system handles high concurrency very well")
        
        print(f"\n📊 For detailed analysis, run:")
        print(f"   python tests/performance/test_llm_concurrency_performance.py")
        print(f"   python tests/performance/visualize_concurrency_results.py")

    async def run(self):
        """Run the complete test."""
        print("🔧 CodeDox LLM Configuration Test")
        print("=" * 50)
        print("This script will help you find optimal LLM settings for your setup.")
        print()
        
        # Test connection
        if not await self.test_connection():
            print("\n❌ Cannot proceed without LLM connection.")
            print("   Check your .env file and ensure your LLM server is running.")
            return
        
        # Find optimal config
        try:
            optimal_concurrency, viable_results = await self.find_optimal_config()
            self.generate_recommendations(optimal_concurrency, viable_results)
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            print("   Try running with debug mode or check LLM server logs")
        finally:
            if self.llm_client:
                await self.llm_client.close()


async def main():
    """Main entry point."""
    tester = QuickLLMConfigTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())