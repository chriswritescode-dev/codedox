# LLM Concurrency Performance Testing Suite

This performance testing suite helps determine the optimal concurrency level for parallel LLM API requests to maximize throughput while maintaining acceptable latency and error rates.

## Installation

### Install Required Dependencies

```bash
# From the project root
pip install matplotlib seaborn numpy

# Or install all visualization dependencies
pip install -r tests/performance/requirements.txt
```

### Verify Installation

```bash
python -c "import matplotlib, seaborn, numpy; print('✓ All dependencies installed')"
```

## Overview

The suite progressively tests different concurrency levels, measuring:
- **Throughput** (requests processed per second)
- **Response time** (average time per request)
- **Error rate** (failed requests percentage)
- **Latency percentiles** (P95, P99 response times)
- **Timeout rate** (requests exceeding timeout threshold)

It automatically identifies the optimal concurrency level by analyzing throughput improvements and error rates.

## Quick Start

### 1. Run a Quick Test

```bash
python run_concurrency_test.py --quick
```

This runs a fast test with smaller ranges to quickly validate your setup.

### 2. Run a Full Test

```bash
python run_concurrency_test.py
```

This runs a comprehensive test with default parameters:
- Concurrency levels: 1, 2, 5, 10, 15, 20, 25, 30, 40, 50
- 100 total requests per test
- Measures various performance metrics

### 3. Update Configuration Automatically

```bash
python run_concurrency_test.py --update-config
```

This runs the test and automatically updates `config.yaml` with the optimal `max_concurrent_requests` value.

## Advanced Usage

### Custom Test Parameters

```bash
python run_concurrency_test.py \
    --min-concurrency 5 \
    --max-concurrency 30 \
    --total-requests 200 \
    --custom-levels 5,10,15,20,25
```

### Test with Different LLM Endpoints

```bash
# Test local LLM
python run_concurrency_test.py \
    --llm-endpoint http://localhost:8080 \
    --llm-model llama2

# Test OpenAI-compatible endpoint
python run_concurrency_test.py \
    --llm-endpoint https://api.openai.com/v1 \
    --llm-model gpt-4
```

## Individual Scripts

### 1. Generate Test Data

```bash
python generate_test_data.py
```

Generates realistic code snippets in multiple languages:
- JavaScript/TypeScript (60%)
- Python (20%)
- React components (20%)

### 2. Run Concurrency Performance Test

```bash
python test_llm_concurrency_performance.py
```

Runs the core performance test and saves results to `concurrency_results_[timestamp].json`.

### 3. Visualize Results

```bash
python visualize_concurrency_results.py concurrency_results_[timestamp].json
```

Generates visualizations from test results (currently needs updating for concurrency metrics).

## Understanding Results

### Key Metrics

1. **Throughput**: Total requests processed per second
   - Higher is better
   - Primary optimization target

2. **Average Response Time**: Mean time for each request
   - Lower is better
   - Should stay within acceptable bounds

3. **P95/P99 Response Times**: 95th/99th percentile latencies
   - Important for SLA considerations
   - Shows worst-case performance

4. **Error Rate**: Percentage of failed requests
   - Should stay below 5%
   - High error rates indicate overload

5. **Timeout Rate**: Percentage of requests exceeding timeout
   - Should be minimal
   - Indicates server capacity limits

### Optimal Concurrency Level

The optimal concurrency level is determined by:
1. Maximum throughput achieved
2. Error rate below 5%
3. Acceptable P95/P99 latencies
4. Diminishing returns on throughput increase

### Example Results

```
📊 Optimal concurrency level: 10
   - Throughput: 8.5 requests/s
   - Avg response time: 1.18s
   - P95 response time: 1.45s
   - Error rate: 0.0%

📈 Performance improvement:
   - Sequential (concurrency=1): 0.85 requests/s
   - Optimal (concurrency=10): 8.5 requests/s
   - Improvement: 10x
```

## Configuration

### Test Parameters

Edit constants in `test_llm_concurrency_performance.py`:

```python
MIN_CONCURRENCY = 1              # Starting concurrency level
MAX_CONCURRENCY = 50             # Maximum concurrency to test
CONCURRENCY_LEVELS = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]
TOTAL_REQUESTS = 100             # Total requests per test
WARMUP_REQUESTS = 5              # Warmup before testing
ERROR_RATE_THRESHOLD = 0.05      # 5% error rate threshold
```

### LLM Configuration

The test uses your project's LLM configuration from `config.yaml`:

```yaml
llm:
  endpoint: http://YOUR_LLM_HOST:8000/v1
  model: Q3-30B
  max_concurrent_requests: 10  # This is what we're optimizing
  request_timeout: 30.0
  retry_attempts: 3
```

## Concurrency vs Batch Processing

This testing suite focuses on **concurrent requests** rather than batch processing:

- **Concurrent Processing**: Send multiple individual requests in parallel
  - Each request is independent
  - Limited by semaphore (`max_concurrent_requests`)
  - Better for varied request sizes and types

- **Batch Processing** (deprecated): Send multiple items in a single request
  - All items processed together
  - Limited by API payload size
  - Used in older versions of this system

## Troubleshooting

### "Test data file not found"

Run the test data generator:
```bash
python generate_test_data.py
```

### "LLM connection error"

1. Check your LLM endpoint is running
2. Verify endpoint URL in `.env` or `config.yaml`
3. Test with curl: `curl -X POST http://your-endpoint/v1/chat/completions`

### "Too many timeouts"

1. Reduce max concurrency level
2. Increase timeout threshold in config
3. Check LLM server resources
4. Monitor server logs for bottlenecks

### High Error Rates

1. Start with lower concurrency levels
2. Check server capacity and resource limits
3. Monitor memory usage on LLM server
4. Consider implementing rate limiting

## Integration with Main Project

The optimal concurrency level is automatically used through the configuration:

```python
# The LLM client automatically respects max_concurrent_requests
from src.llm.client import LLMClient

client = LLMClient()  # Uses config.yaml settings
# Semaphore limits concurrent requests automatically
```

Or update `config.yaml` directly:

```yaml
llm:
  max_concurrent_requests: 10  # Use optimal value from test
  request_timeout: 30.0
  retry_attempts: 3
```

## Performance Tips

1. **Start Conservative**: Begin with lower concurrency in production
2. **Monitor Continuously**: Track error rates and response times
3. **Scale Gradually**: Increase concurrency slowly while monitoring
4. **Consider Load Patterns**: LLM performance may vary with server load
5. **Test Regularly**: Re-run tests when changing LLM providers or models
6. **Network Latency**: Factor in network delays for remote endpoints
7. **Resource Limits**: Ensure LLM server has sufficient CPU/memory

## Output Files

- `test_snippets.json` - Generated test data
- `concurrency_results_[timestamp].json` - Raw test results
- Visualization outputs from visualize_concurrency_results.py

## Future Improvements

1. Add real-time monitoring during tests
2. Support for different request types/sizes
3. Automatic performance regression detection
4. Integration with monitoring systems (Prometheus, Grafana)