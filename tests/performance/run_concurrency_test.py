#!/usr/bin/env python3
"""
Run LLM concurrency performance tests to find optimal parallel request limit.

Usage:
    python run_concurrency_test.py [options]

Options:
    --min-concurrency   Minimum concurrency level to test (default: 1)
    --max-concurrency   Maximum concurrency level to test (default: 50)
    --total-requests    Total requests per test (default: 100)
    --custom-levels     Comma-separated list of concurrency levels to test
    --quick             Quick test mode (fewer levels, fewer requests)
    --update-config     Automatically update config.yaml with optimal values
    --help              Show this help message
"""

import asyncio
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from test_llm_concurrency_performance import LLMConcurrencyTester
from src.llm.client import LLMClient


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run LLM concurrency performance tests",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--min-concurrency',
        type=int,
        default=1,
        help='Minimum concurrency level to test (default: 1)'
    )
    
    parser.add_argument(
        '--max-concurrency',
        type=int,
        default=50,
        help='Maximum concurrency level to test (default: 50)'
    )
    
    parser.add_argument(
        '--total-requests',
        type=int,
        default=100,
        help='Total requests per test (default: 100)'
    )
    
    parser.add_argument(
        '--custom-levels',
        type=str,
        help='Comma-separated list of concurrency levels to test (overrides min/max)'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test mode (fewer levels, fewer requests)'
    )
    
    parser.add_argument(
        '--update-config',
        action='store_true',
        help='Automatically update config.yaml with optimal values'
    )
    
    parser.add_argument(
        '--llm-endpoint',
        type=str,
        help='LLM API endpoint (uses config if not specified)'
    )
    
    parser.add_argument(
        '--llm-model',
        type=str,
        help='LLM model name (uses config if not specified)'
    )
    
    return parser.parse_args()


async def run_test(args):
    """Run the concurrency test with given arguments."""
    # Create LLM client if custom endpoint/model specified
    llm_client = None
    if args.llm_endpoint or args.llm_model:
        llm_client = LLMClient(
            endpoint=args.llm_endpoint,
            model=args.llm_model
        )
    
    # Create tester
    tester = LLMConcurrencyTester(llm_client=llm_client)
    
    # Configure test parameters
    if args.quick:
        print("🚀 Running in quick test mode...")
        tester.CONCURRENCY_LEVELS = [1, 5, 10, 15, 20, 25]
        tester.TOTAL_REQUESTS = 20
        tester.RUNS_PER_LEVEL = 1
        tester.WARMUP_REQUESTS = 2
    elif args.custom_levels:
        levels = [int(x.strip()) for x in args.custom_levels.split(',')]
        tester.CONCURRENCY_LEVELS = sorted(levels)
    else:
        # Generate levels based on min/max
        levels = []
        current = args.min_concurrency
        while current <= args.max_concurrency:
            levels.append(current)
            if current < 10:
                current += 1
            elif current < 20:
                current += 2
            else:
                current += 5
        tester.CONCURRENCY_LEVELS = levels
    
    if args.total_requests:
        tester.TOTAL_REQUESTS = args.total_requests
    
    # Run the test
    try:
        await tester.run_performance_test()
        tester.print_summary()
        
        if args.update_config:
            await update_config_with_optimal_values(tester)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        tester.print_summary()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise
    finally:
        if llm_client:
            await llm_client.close()


async def update_config_with_optimal_values(tester: LLMConcurrencyTester):
    """Update config.yaml with optimal concurrency values."""
    if not tester.optimal_concurrency:
        print("\n⚠️  Cannot update config - no optimal concurrency found")
        return
    
    import yaml
    
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    
    # Read current config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Get recommendations
    recommendations = tester._generate_recommendations()
    optimal_value = recommendations['recommended_production_concurrency']
    
    # Update LLM section
    if 'llm' not in config:
        config['llm'] = {}
    
    config['llm']['max_concurrent_requests'] = optimal_value
    config['llm']['request_timeout'] = 30.0
    config['llm']['retry_attempts'] = 3
    
    # Write back
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ Updated config.yaml with max_concurrent_requests: {optimal_value}")


def main():
    """Main entry point."""
    args = parse_arguments()
    
    print("🔬 LLM Concurrency Performance Test Runner")
    print("=" * 50)
    
    # Print configuration
    print("\nTest Configuration:")
    if args.custom_levels:
        print(f"  • Custom concurrency levels: {args.custom_levels}")
    else:
        print(f"  • Concurrency range: {args.min_concurrency} to {args.max_concurrency}")
    print(f"  • Requests per test: {args.total_requests}")
    
    if args.llm_endpoint:
        print(f"  • LLM endpoint: {args.llm_endpoint}")
    if args.llm_model:
        print(f"  • LLM model: {args.llm_model}")
    
    if args.quick:
        print("\n  ⚡ Quick test mode enabled")
    
    if args.update_config:
        print("\n  📝 Will update config.yaml with optimal values")
    
    print("\nStarting concurrency test...\n")
    
    # Run the async test
    asyncio.run(run_test(args))


if __name__ == "__main__":
    main()