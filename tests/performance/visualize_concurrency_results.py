"""Visualize concurrency performance test results with graphs and charts."""

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def load_results(file_path: str) -> dict[str, Any]:
    """Load performance test results from JSON file."""
    path = Path(file_path)

    if not path.exists():
        path = Path(__file__).parent / file_path
        if not path.exists():
            raise FileNotFoundError(f"Results file not found: {file_path}")

    with open(path) as f:
        return json.load(f)


def create_performance_dashboard(results: dict[str, Any]) -> None:
    """Create a comprehensive performance dashboard for concurrency metrics."""
    # Extract data
    concurrency_levels = []
    throughputs = []
    avg_response_times = []
    p95_response_times = []
    p99_response_times = []
    error_rates = []
    timeout_rates = []

    for level_str, metrics in sorted(results['results'].items(), key=lambda x: int(x[0])):
        level = int(level_str)
        concurrency_levels.append(level)
        throughputs.append(metrics['throughput'])
        avg_response_times.append(metrics['avg_response_time'])
        p95_response_times.append(metrics['p95_response_time'])
        p99_response_times.append(metrics['p99_response_time'])
        error_rates.append(metrics['error_rate'] * 100)  # Convert to percentage
        timeout_rates.append(metrics['timeout_rate'] * 100)

    # Create figure with subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('LLM Concurrency Performance Dashboard', fontsize=16, fontweight='bold')

    # Plot 1: Throughput vs Concurrency
    ax1.plot(concurrency_levels, throughputs, 'o-', linewidth=2, markersize=8)
    ax1.set_xlabel('Concurrency Level')
    ax1.set_ylabel('Throughput (requests/s)')
    ax1.set_title('Throughput vs Concurrency Level')
    ax1.grid(True, alpha=0.3)

    # Highlight optimal point
    optimal = results.get('optimal_concurrency')
    if optimal and optimal in results['results']:
        optimal_idx = concurrency_levels.index(optimal)
        ax1.plot(optimal, throughputs[optimal_idx], 'ro', markersize=12,
                label=f'Optimal: {optimal}')
        ax1.legend()

    # Plot 2: Response Times vs Concurrency
    ax2.plot(concurrency_levels, avg_response_times, 'o-', label='Average', linewidth=2)
    ax2.plot(concurrency_levels, p95_response_times, 's--', label='P95', linewidth=1.5)
    ax2.plot(concurrency_levels, p99_response_times, '^:', label='P99', linewidth=1.5)
    ax2.set_xlabel('Concurrency Level')
    ax2.set_ylabel('Response Time (s)')
    ax2.set_title('Response Times vs Concurrency Level')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Plot 3: Error Rates vs Concurrency
    ax3.plot(concurrency_levels, error_rates, 'o-', color='red', linewidth=2, markersize=8)
    ax3.fill_between(concurrency_levels, error_rates, alpha=0.3, color='red')
    ax3.set_xlabel('Concurrency Level')
    ax3.set_ylabel('Error Rate (%)')
    ax3.set_title('Error Rate vs Concurrency Level')
    ax3.grid(True, alpha=0.3)

    # Add 5% threshold line
    ax3.axhline(y=5, color='darkred', linestyle='--', alpha=0.7, label='5% threshold')
    ax3.legend()

    # Plot 4: Efficiency (Throughput per Concurrency Unit)
    efficiency = [t/c for t, c in zip(throughputs, concurrency_levels)]
    ax4.plot(concurrency_levels, efficiency, 'o-', color='green', linewidth=2, markersize=8)
    ax4.set_xlabel('Concurrency Level')
    ax4.set_ylabel('Efficiency (throughput/concurrency)')
    ax4.set_title('Resource Efficiency vs Concurrency Level')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('concurrency_performance_dashboard.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: concurrency_performance_dashboard.png")


def create_comparison_chart(results: dict[str, Any]) -> None:
    """Create a before/after comparison chart."""
    optimal = results.get('optimal_concurrency')
    if not optimal or optimal not in results['results']:
        print("⚠️  No optimal concurrency found, skipping comparison chart")
        return

    baseline_metrics = results['results']['1']  # Sequential performance
    optimal_metrics = results['results'][str(optimal)]

    # Create comparison data
    categories = ['Throughput\n(req/s)', 'Avg Response\nTime (s)', 'Error Rate\n(%)']
    baseline_values = [
        baseline_metrics['throughput'],
        baseline_metrics['avg_response_time'],
        baseline_metrics['error_rate'] * 100
    ]
    optimal_values = [
        optimal_metrics['throughput'],
        optimal_metrics['avg_response_time'],
        optimal_metrics['error_rate'] * 100
    ]

    # Create bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width/2, baseline_values, width, label='Sequential (1)', alpha=0.8)
    bars2 = ax.bar(x + width/2, optimal_values, width, label=f'Optimal ({optimal})', alpha=0.8)

    # Add value labels on bars
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.2f}',
                       xy=(rect.get_x() + rect.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom')

    autolabel(bars1)
    autolabel(bars2)

    ax.set_xlabel('Metrics')
    ax.set_title('Performance Comparison: Sequential vs Optimal Concurrency')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # Add improvement percentage
    throughput_improvement = (optimal_metrics['throughput'] / baseline_metrics['throughput'] - 1) * 100
    ax.text(0.02, 0.98, f'Throughput Improvement: {throughput_improvement:.1f}%',
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig('concurrency_performance_comparison.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: concurrency_performance_comparison.png")


def create_heatmap(results: dict[str, Any]) -> None:
    """Create a heatmap of normalized metrics across concurrency levels."""
    # Prepare data
    metrics_names = ['Throughput', 'Avg Response', 'P95 Response', 'Error Rate', 'Timeout Rate']
    concurrency_levels = sorted([int(k) for k in results['results'].keys()])

    # Create matrix
    data_matrix = []
    for level in concurrency_levels:
        metrics = results['results'][str(level)]
        row = [
            metrics['throughput'],
            metrics['avg_response_time'],
            metrics['p95_response_time'],
            metrics['error_rate'] * 100,
            metrics['timeout_rate'] * 100
        ]
        data_matrix.append(row)

    data_matrix = np.array(data_matrix).T

    # Normalize each metric (0-1 scale)
    # For response times and error rates, lower is better, so we invert
    normalized_matrix = np.zeros_like(data_matrix)

    # Throughput: higher is better
    normalized_matrix[0] = (data_matrix[0] - data_matrix[0].min()) / (data_matrix[0].max() - data_matrix[0].min())

    # Response times and error rates: lower is better
    for i in range(1, 5):
        if data_matrix[i].max() > 0:
            normalized_matrix[i] = 1 - (data_matrix[i] - data_matrix[i].min()) / (data_matrix[i].max() - data_matrix[i].min())
        else:
            normalized_matrix[i] = 1  # All zeros means perfect score

    # Create heatmap
    plt.figure(figsize=(12, 8))
    sns.heatmap(normalized_matrix,
                xticklabels=concurrency_levels,
                yticklabels=metrics_names,
                annot=True,
                fmt='.2f',
                cmap='RdYlGn',
                center=0.5,
                cbar_kws={'label': 'Normalized Score (1=best, 0=worst)'})

    plt.title('Performance Metrics Heatmap (Normalized)', fontsize=14, fontweight='bold')
    plt.xlabel('Concurrency Level')
    plt.ylabel('Metrics')

    # Highlight optimal column
    optimal = results.get('optimal_concurrency')
    if optimal and optimal in concurrency_levels:
        optimal_idx = concurrency_levels.index(optimal)
        plt.axvline(x=optimal_idx + 0.5, color='blue', linestyle='--', linewidth=2, alpha=0.7)
        plt.axvline(x=optimal_idx - 0.5, color='blue', linestyle='--', linewidth=2, alpha=0.7)

    plt.tight_layout()
    plt.savefig('concurrency_performance_heatmap.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: concurrency_performance_heatmap.png")


def generate_markdown_report(results: dict[str, Any]) -> None:
    """Generate a markdown report of the performance test results."""
    report = []
    report.append("# LLM Concurrency Performance Test Report\n")
    report.append(f"**Test Date**: {results['test_configuration']['timestamp']}\n")
    report.append(f"**Total Requests per Test**: {results['test_configuration']['total_requests_per_test']}\n")
    report.append(f"**Runs per Level**: {results['test_configuration']['runs_per_level']}\n")

    # Summary
    optimal = results.get('optimal_concurrency')
    if optimal and 'recommendations' in results:
        rec = results['recommendations']
        report.append("\n## Summary\n")
        report.append(f"**Optimal Concurrency Level**: {optimal}\n")
        report.append(f"**Optimal Throughput**: {rec.get('optimal_throughput', 'N/A')} requests/s\n")

        if 'improvement_factor' in rec:
            report.append(f"**Performance Improvement**: {rec['improvement_factor']}x over sequential\n")

    # Detailed Results Table
    report.append("\n## Detailed Results\n")
    report.append("| Concurrency | Throughput (req/s) | Avg Response (s) | P95 (s) | P99 (s) | Error Rate | Timeout Rate |")
    report.append("|------------|-------------------|------------------|---------|---------|------------|--------------|")

    for level_str, metrics in sorted(results['results'].items(), key=lambda x: int(x[0])):
        level = int(level_str)
        is_optimal = level == optimal
        prefix = "**" if is_optimal else ""
        suffix = "** ⭐" if is_optimal else ""

        report.append(f"| {prefix}{level}{suffix} | "
                     f"{metrics['throughput']:.2f} | "
                     f"{metrics['avg_response_time']:.2f} | "
                     f"{metrics['p95_response_time']:.2f} | "
                     f"{metrics['p99_response_time']:.2f} | "
                     f"{metrics['error_rate']:.1%} | "
                     f"{metrics['timeout_rate']:.1%} |")

    # Recommendations
    if 'recommendations' in results:
        report.append("\n## Recommendations\n")
        rec = results['recommendations']

        if 'production_concurrency' in rec:
            report.append(f"1. **Production Setting**: Start with concurrency level of {rec['production_concurrency']} "
                         f"(conservative approach)\n")

        if 'max_safe_concurrency' in rec:
            report.append(f"2. **Maximum Safe Level**: Can scale up to {rec['max_safe_concurrency']} "
                         f"under optimal conditions\n")

        report.append("3. **Monitor Closely**: Track error rates and P95 latencies when scaling\n")
        report.append("4. **Regular Testing**: Re-test when changing LLM models or infrastructure\n")

    # Write report
    with open('concurrency_performance_report.md', 'w') as f:
        f.write('\n'.join(report))

    print("✅ Saved: concurrency_performance_report.md")


def main():
    """Main function to generate all visualizations."""
    if len(sys.argv) < 2:
        # Try to find the most recent results file
        results_files = list(Path(__file__).parent.glob('concurrency_results_*.json'))
        if not results_files:
            print("❌ No results file specified and no concurrency_results_*.json files found")
            print("Usage: python visualize_concurrency_results.py <results_file.json>")
            return

        # Use the most recent file
        results_file = max(results_files, key=lambda p: p.stat().st_mtime)
        print(f"📊 Using most recent results file: {results_file.name}")
    else:
        results_file = sys.argv[1]

    try:
        # Load results
        results = load_results(str(results_file))

        print("🎨 Generating visualizations...")

        # Generate all visualizations
        create_performance_dashboard(results)
        create_comparison_chart(results)
        create_heatmap(results)
        generate_markdown_report(results)

        print("\n✨ All visualizations generated successfully!")

        # Print summary
        if 'optimal_concurrency' in results and results['optimal_concurrency']:
            optimal = results['optimal_concurrency']
            optimal_metrics = results['results'][str(optimal)]
            print(f"\n📊 Optimal concurrency level: {optimal}")
            print(f"   - Throughput: {optimal_metrics['throughput']:.2f} requests/s")
            print(f"   - Avg response time: {optimal_metrics['avg_response_time']:.2f}s")
            print(f"   - Error rate: {optimal_metrics['error_rate']:.1%}")

            if '1' in results['results']:
                baseline = results['results']['1']
                improvement = optimal_metrics['throughput'] / baseline['throughput']
                print(f"\n📈 Performance improvement over sequential: {improvement:.1f}x")

    except Exception as e:
        print(f"❌ Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
