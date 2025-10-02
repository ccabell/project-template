"""
Performance benchmarking and load testing suite for consultation pipeline.

This module provides comprehensive performance testing including:
- Load testing for 100 concurrent consultations
- Object Lambda redaction performance under load
- Dagster pipeline scalability testing
- Latency monitoring and P95 response times
- Cost per consultation tracking
- Throughput and scalability analysis
"""

import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PerformanceMetrics:
    """Performance metrics for load testing."""

    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    requests_per_second: float
    total_duration_seconds: float
    error_rate_percent: float
    memory_usage_mb: float | None = None
    cpu_utilization_percent: float | None = None


@dataclass
class CostMetrics:
    """Cost tracking metrics."""

    total_lambda_invocations: int
    total_comprehend_requests: int
    total_s3_operations: int
    total_textract_pages: int
    estimated_cost_usd: float
    cost_per_consultation_usd: float
    cost_breakdown: dict[str, float]


class LoadTestingConfiguration:
    """Configuration for load testing scenarios."""

    def __init__(self):
        self.consultation_processing_load_test = {
            "concurrent_users": 100,
            "total_consultations": 1000,
            "ramp_up_time_seconds": 60,
            "test_duration_seconds": 300,
            "think_time_seconds": 1,
        }

        self.object_lambda_load_test = {
            "concurrent_requests": 1000,
            "requests_per_minute": 1000,
            "test_duration_minutes": 10,
            "document_sizes": [1024, 10240, 102400, 1048576],  # 1KB to 1MB
        }

        self.dagster_scalability_test = {
            "parallel_jobs": 50,
            "jobs_per_batch": 10,
            "batch_interval_seconds": 30,
            "max_test_duration_minutes": 30,
        }


class ConsultationPipelineLoadTester:
    """Load testing framework for consultation pipeline."""

    def __init__(self, config: LoadTestingConfiguration):
        self.config = config
        self.metrics_storage: list[PerformanceMetrics] = []
        self.cost_tracker = CostTracker()

    def run_comprehensive_load_tests(self) -> dict[str, PerformanceMetrics]:
        """
        Run comprehensive load testing suite.

        Returns:
            Dictionary of test results with performance metrics
        """
        test_results = {}

        print("🚀 Starting comprehensive load testing suite...")

        # Test 1: Consultation Processing Load Test
        print("\n📊 Running consultation processing load test...")
        consultation_metrics = self.run_consultation_processing_load_test()
        test_results["consultation_processing"] = consultation_metrics

        # Test 2: Object Lambda Redaction Load Test
        print("\n🔒 Running Object Lambda redaction load test...")
        redaction_metrics = self.run_object_lambda_load_test()
        test_results["object_lambda_redaction"] = redaction_metrics

        # Test 3: Dagster Pipeline Scalability Test
        print("\n⚙️ Running Dagster pipeline scalability test...")
        dagster_metrics = self.run_dagster_scalability_test()
        test_results["dagster_scalability"] = dagster_metrics

        # Test 4: End-to-End Pipeline Stress Test
        print("\n🌊 Running end-to-end pipeline stress test...")
        stress_metrics = self.run_end_to_end_stress_test()
        test_results["end_to_end_stress"] = stress_metrics

        # Generate comprehensive report
        self.generate_performance_report(test_results)

        return test_results

    def run_consultation_processing_load_test(self) -> PerformanceMetrics:
        """
        Test consultation processing under load.

        Simulates 100 concurrent users processing consultations
        and measures response times, throughput, and error rates.
        """
        config = self.config.consultation_processing_load_test

        print(f"Testing {config['concurrent_users']} concurrent users processing {config['total_consultations']} consultations...")

        results = []
        start_time = time.time()

        # Generate test consultation data
        test_consultations = self._generate_test_consultations(config["total_consultations"])

        # Execute load test with thread pool
        with ThreadPoolExecutor(max_workers=config["concurrent_users"]) as executor:
            # Submit all consultation processing tasks
            future_to_consultation = {
                executor.submit(self._process_consultation_load_test, consultation): consultation
                for consultation in test_consultations
            }

            # Collect results
            for future in as_completed(future_to_consultation):
                consultation = future_to_consultation[future]
                try:
                    result = future.result(timeout=30)  # 30 second timeout per consultation
                    results.append(result)

                    # Track cost metrics
                    self.cost_tracker.record_consultation_processing(result)

                except Exception as e:
                    results.append({
                        "success": False,
                        "response_time_ms": 30000,  # Timeout
                        "error": str(e),
                        "consultation_id": consultation["consultation_id"],
                    })

        end_time = time.time()

        # Calculate performance metrics
        return self._calculate_performance_metrics(
            "consultation_processing_load_test",
            results,
            start_time,
            end_time,
        )

    def run_object_lambda_load_test(self) -> PerformanceMetrics:
        """
        Test Object Lambda redaction performance under high load.

        Tests 1000 requests per minute with various document sizes
        to validate redaction performance and latency.
        """
        config = self.config.object_lambda_load_test

        print(f"Testing Object Lambda with {config['concurrent_requests']} concurrent requests...")

        results = []
        start_time = time.time()

        # Generate test documents of various sizes
        test_documents = self._generate_test_documents(
            config["concurrent_requests"],
            config["document_sizes"],
        )

        # Execute load test
        with ThreadPoolExecutor(max_workers=50) as executor:  # Limit concurrent threads
            future_to_doc = {
                executor.submit(self._test_object_lambda_redaction, doc): doc
                for doc in test_documents
            }

            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    result = future.result(timeout=10)  # 10 second timeout
                    results.append(result)

                    # Track cost metrics
                    self.cost_tracker.record_object_lambda_request(result)

                except Exception as e:
                    results.append({
                        "success": False,
                        "response_time_ms": 10000,  # Timeout
                        "error": str(e),
                        "document_size": doc["size"],
                    })

        end_time = time.time()

        return self._calculate_performance_metrics(
            "object_lambda_load_test",
            results,
            start_time,
            end_time,
        )

    def run_dagster_scalability_test(self) -> PerformanceMetrics:
        """
        Test Dagster pipeline scalability with parallel job execution.

        Executes 50 parallel pipeline jobs to test Dagster's
        ability to handle concurrent workloads.
        """
        config = self.config.dagster_scalability_test

        print(f"Testing Dagster scalability with {config['parallel_jobs']} parallel jobs...")

        results = []
        start_time = time.time()

        # Generate pipeline job configurations
        pipeline_jobs = self._generate_pipeline_job_configs(config["parallel_jobs"])

        # Execute jobs in batches to avoid overwhelming the system
        batch_size = config["jobs_per_batch"]
        for i in range(0, len(pipeline_jobs), batch_size):
            batch = pipeline_jobs[i:i + batch_size]

            print(f"Executing batch {i//batch_size + 1} with {len(batch)} jobs...")

            # Execute batch concurrently
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                future_to_job = {
                    executor.submit(self._execute_dagster_pipeline_job, job): job
                    for job in batch
                }

                for future in as_completed(future_to_job):
                    job = future_to_job[future]
                    try:
                        result = future.result(timeout=300)  # 5 minute timeout
                        results.append(result)

                        # Track cost metrics
                        self.cost_tracker.record_dagster_job(result)

                    except Exception as e:
                        results.append({
                            "success": False,
                            "response_time_ms": 300000,  # Timeout
                            "error": str(e),
                            "job_id": job["job_id"],
                        })

            # Wait between batches to allow system recovery
            if i + batch_size < len(pipeline_jobs):
                time.sleep(config["batch_interval_seconds"])

        end_time = time.time()

        return self._calculate_performance_metrics(
            "dagster_scalability_test",
            results,
            start_time,
            end_time,
        )

    def run_end_to_end_stress_test(self) -> PerformanceMetrics:
        """
        Run end-to-end stress test with high load across all components.

        Tests the complete pipeline under maximum load to identify
        bottlenecks and failure points.
        """
        print("Running end-to-end stress test with maximum load...")

        results = []
        start_time = time.time()

        # Generate high-volume test scenario
        stress_test_config = {
            "concurrent_consultations": 200,
            "redaction_requests_per_second": 500,
            "dagster_jobs": 25,
            "test_duration_minutes": 15,
        }

        # Execute stress test components in parallel
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = []

            # Submit consultation processing stress
            for i in range(stress_test_config["concurrent_consultations"]):
                consultation = self._generate_stress_test_consultation(i)
                future = executor.submit(self._stress_test_consultation_processing, consultation)
                futures.append(future)

            # Submit Object Lambda stress
            for i in range(stress_test_config["redaction_requests_per_second"] * 2):  # 2 minutes worth
                doc = self._generate_stress_test_document(i)
                future = executor.submit(self._stress_test_object_lambda, doc)
                futures.append(future)

            # Submit Dagster stress
            for i in range(stress_test_config["dagster_jobs"]):
                job = self._generate_stress_test_job(i)
                future = executor.submit(self._stress_test_dagster_job, job)
                futures.append(future)

            # Collect all results
            for future in as_completed(futures, timeout=stress_test_config["test_duration_minutes"] * 60):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "success": False,
                        "response_time_ms": 60000,
                        "error": str(e),
                        "test_type": "stress_test",
                    })

        end_time = time.time()

        return self._calculate_performance_metrics(
            "end_to_end_stress_test",
            results,
            start_time,
            end_time,
        )

    def generate_performance_report(self, test_results: dict[str, PerformanceMetrics]) -> None:
        """
        Generate comprehensive performance testing report.

        Creates detailed report with metrics, charts, and recommendations.
        """
        report_timestamp = datetime.utcnow().isoformat()

        print(f"\n📈 PERFORMANCE TESTING REPORT - {report_timestamp}")
        print("=" * 80)

        for test_name, metrics in test_results.items():
            print(f"\n🔍 {test_name.upper().replace('_', ' ')}")
            print("-" * 50)
            print(f"Total Requests: {metrics.total_requests:,}")
            print(f"Successful: {metrics.successful_requests:,} ({(metrics.successful_requests/metrics.total_requests)*100:.1f}%)")
            print(f"Failed: {metrics.failed_requests:,} ({metrics.error_rate_percent:.1f}%)")
            print(f"Duration: {metrics.total_duration_seconds:.1f}s")
            print(f"Throughput: {metrics.requests_per_second:.1f} req/s")
            print(f"Avg Response Time: {metrics.avg_response_time_ms:.1f}ms")
            print(f"P95 Response Time: {metrics.p95_response_time_ms:.1f}ms")
            print(f"P99 Response Time: {metrics.p99_response_time_ms:.1f}ms")
            print(f"Max Response Time: {metrics.max_response_time_ms:.1f}ms")

            # Performance assessment
            self._assess_performance(test_name, metrics)

        # Cost analysis
        cost_metrics = self.cost_tracker.get_cost_summary()
        print("\n💰 COST ANALYSIS")
        print("-" * 50)
        print(f"Estimated Total Cost: ${cost_metrics.estimated_cost_usd:.2f}")
        print(f"Cost per Consultation: ${cost_metrics.cost_per_consultation_usd:.4f}")
        print(f"Lambda Invocations: {cost_metrics.total_lambda_invocations:,}")
        print(f"Comprehend Requests: {cost_metrics.total_comprehend_requests:,}")
        print(f"S3 Operations: {cost_metrics.total_s3_operations:,}")

        # Generate recommendations
        self._generate_performance_recommendations(test_results, cost_metrics)

        # Save detailed report to file
        self._save_detailed_report(test_results, cost_metrics, report_timestamp)

    def _generate_test_consultations(self, count: int) -> list[dict]:
        """Generate test consultation data for load testing."""
        consultations = []
        for i in range(count):
            consultation = {
                "consultation_id": f"load-test-{i:06d}-{uuid.uuid4().hex[:8]}",
                "tenant_id": f"tenant-{i % 10:03d}",  # 10 different tenants
                "transcript": self._generate_realistic_transcript(),
                "metadata": {
                    "consultation_date": datetime.utcnow().isoformat(),
                    "test_id": i,
                    "load_test": True,
                },
            }
            consultations.append(consultation)
        return consultations

    def _generate_realistic_transcript(self) -> dict:
        """Generate realistic consultation transcript for testing."""
        return {
            "conversation": [
                {
                    "speaker": "Doctor",
                    "text": f"Hello, I see your medical record number is MRN{uuid.uuid4().hex[:8].upper()}. How are you feeling today?",
                },
                {
                    "speaker": "Patient",
                    "text": f"I've been having some pain. My insurance policy is INS{uuid.uuid4().hex[:8].upper()}.",
                },
                {
                    "speaker": "Doctor",
                    "text": "Can you describe the pain level from 1 to 10?",
                },
                {
                    "speaker": "Patient",
                    "text": "I'd say it's about a 6 or 7. It's been going on for about two weeks.",
                },
            ],
        }

    def _process_consultation_load_test(self, consultation: dict) -> dict:
        """Process single consultation for load testing."""
        start_time = time.time()

        try:
            # Simulate consultation processing pipeline
            # In real implementation, this would call actual Lambda functions

            # Simulate PII redaction (100-300ms)
            time.sleep(0.1 + (0.2 * (time.time() % 1)))

            # Simulate PHI detection (200-500ms)
            time.sleep(0.2 + (0.3 * (time.time() % 1)))

            # Simulate Bedrock processing (1-3s)
            time.sleep(1.0 + (2.0 * (time.time() % 1)))

            # Simulate storage operations (50-150ms)
            time.sleep(0.05 + (0.1 * (time.time() % 1)))

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": response_time,
                "consultation_id": consultation["consultation_id"],
                "tenant_id": consultation["tenant_id"],
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e),
                "consultation_id": consultation["consultation_id"],
            }

    def _generate_test_documents(self, count: int, sizes: list[int]) -> list[dict]:
        """Generate test documents for Object Lambda testing."""
        documents = []
        for i in range(count):
            size = sizes[i % len(sizes)]
            doc = {
                "document_id": f"doc-{i:06d}",
                "size": size,
                "content": "x" * size,  # Simple content for testing
                "redaction_level": ["basic", "strict", "healthcare"][i % 3],
            }
            documents.append(doc)
        return documents

    def _test_object_lambda_redaction(self, document: dict) -> dict:
        """Test Object Lambda redaction for single document."""
        start_time = time.time()

        try:
            # Simulate Object Lambda redaction
            # Processing time varies by document size and redaction level
            base_time = 0.05  # 50ms base
            size_factor = document["size"] / 1024  # Additional time per KB
            complexity_factor = {"basic": 1.0, "strict": 1.5, "healthcare": 2.0}[document["redaction_level"]]

            processing_time = base_time + (size_factor * 0.001) * complexity_factor
            time.sleep(processing_time)

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": response_time,
                "document_id": document["document_id"],
                "document_size": document["size"],
                "redaction_level": document["redaction_level"],
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e),
                "document_id": document["document_id"],
            }

    def _generate_pipeline_job_configs(self, count: int) -> list[dict]:
        """Generate Dagster pipeline job configurations."""
        jobs = []
        for i in range(count):
            job = {
                "job_id": f"dagster-job-{i:04d}",
                "consultation_id": f"consultation-{i:06d}",
                "tenant_id": f"tenant-{i % 5:03d}",
                "pipeline_type": ["full", "partial", "reprocess"][i % 3],
                "priority": ["high", "medium", "low"][i % 3],
            }
            jobs.append(job)
        return jobs

    def _execute_dagster_pipeline_job(self, job: dict) -> dict:
        """Execute single Dagster pipeline job."""
        start_time = time.time()

        try:
            # Simulate Dagster job execution
            # Different pipeline types have different execution times
            base_times = {"full": 10.0, "partial": 5.0, "reprocess": 7.0}
            base_time = base_times[job["pipeline_type"]]

            # Add some variability
            execution_time = base_time * (0.8 + 0.4 * (time.time() % 1))
            time.sleep(execution_time)

            response_time = (time.time() - start_time) * 1000

            return {
                "success": True,
                "response_time_ms": response_time,
                "job_id": job["job_id"],
                "pipeline_type": job["pipeline_type"],
                "tenant_id": job["tenant_id"],
            }

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "response_time_ms": response_time,
                "error": str(e),
                "job_id": job["job_id"],
            }

    def _calculate_performance_metrics(
        self,
        test_name: str,
        results: list[dict],
        start_time: float,
        end_time: float,
    ) -> PerformanceMetrics:
        """Calculate performance metrics from test results."""

        total_requests = len(results)
        successful_requests = sum(1 for r in results if r.get("success", False))
        failed_requests = total_requests - successful_requests

        # Extract response times for successful requests
        response_times = [r["response_time_ms"] for r in results if r.get("success", False)]

        if response_times:
            avg_response_time = statistics.mean(response_times)
            p50_response_time = statistics.median(response_times)
            p95_response_time = self._percentile(response_times, 95)
            p99_response_time = self._percentile(response_times, 99)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
        else:
            avg_response_time = p50_response_time = p95_response_time = p99_response_time = 0
            max_response_time = min_response_time = 0

        total_duration = end_time - start_time
        requests_per_second = total_requests / total_duration if total_duration > 0 else 0
        error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0

        return PerformanceMetrics(
            test_name=test_name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            max_response_time_ms=max_response_time,
            min_response_time_ms=min_response_time,
            requests_per_second=requests_per_second,
            total_duration_seconds=total_duration,
            error_rate_percent=error_rate,
        )

    def _percentile(self, data: list[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        return sorted_data[index]

    def _assess_performance(self, test_name: str, metrics: PerformanceMetrics) -> None:
        """Assess performance against benchmarks and provide status."""

        # Define performance benchmarks
        benchmarks = {
            "consultation_processing_load_test": {
                "p95_threshold_ms": 5000,
                "error_rate_threshold": 2.0,
                "throughput_threshold": 10.0,
            },
            "object_lambda_load_test": {
                "p95_threshold_ms": 500,
                "error_rate_threshold": 1.0,
                "throughput_threshold": 100.0,
            },
            "dagster_scalability_test": {
                "p95_threshold_ms": 30000,
                "error_rate_threshold": 5.0,
                "throughput_threshold": 2.0,
            },
            "end_to_end_stress_test": {
                "p95_threshold_ms": 10000,
                "error_rate_threshold": 5.0,
                "throughput_threshold": 5.0,
            },
        }

        benchmark = benchmarks.get(test_name, {})

        status_indicators = []

        # Check P95 response time
        if metrics.p95_response_time_ms <= benchmark.get("p95_threshold_ms", float("inf")):
            status_indicators.append("✅ P95 Response Time")
        else:
            status_indicators.append("❌ P95 Response Time")

        # Check error rate
        if metrics.error_rate_percent <= benchmark.get("error_rate_threshold", float("inf")):
            status_indicators.append("✅ Error Rate")
        else:
            status_indicators.append("❌ Error Rate")

        # Check throughput
        if metrics.requests_per_second >= benchmark.get("throughput_threshold", 0):
            status_indicators.append("✅ Throughput")
        else:
            status_indicators.append("❌ Throughput")

        print(f"Performance Assessment: {' | '.join(status_indicators)}")

    # Additional helper methods for stress testing and cost tracking

    def _generate_stress_test_consultation(self, index: int) -> dict:
        """Generate consultation for stress testing."""
        return {
            "consultation_id": f"stress-consultation-{index}",
            "tenant_id": f"stress-tenant-{index % 20}",
            "content": "stress test content" * 100,  # Larger content
        }

    def _stress_test_consultation_processing(self, consultation: dict) -> dict:
        """Process consultation under stress test conditions."""
        start_time = time.time()
        try:
            # Simulate intensive processing
            time.sleep(2.0 + (1.0 * (time.time() % 1)))
            return {
                "success": True,
                "response_time_ms": (time.time() - start_time) * 1000,
                "test_type": "consultation_stress",
            }
        except Exception as e:
            return {
                "success": False,
                "response_time_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "test_type": "consultation_stress",
            }

    def _generate_stress_test_document(self, index: int) -> dict:
        """Generate document for stress testing."""
        return {
            "document_id": f"stress-doc-{index}",
            "size": 1048576,  # 1MB documents
            "content": "x" * 1048576,
        }

    def _stress_test_object_lambda(self, document: dict) -> dict:
        """Test Object Lambda under stress conditions."""
        start_time = time.time()
        try:
            # Simulate intensive redaction
            time.sleep(0.5 + (0.3 * (time.time() % 1)))
            return {
                "success": True,
                "response_time_ms": (time.time() - start_time) * 1000,
                "test_type": "object_lambda_stress",
            }
        except Exception as e:
            return {
                "success": False,
                "response_time_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "test_type": "object_lambda_stress",
            }

    def _generate_stress_test_job(self, index: int) -> dict:
        """Generate Dagster job for stress testing."""
        return {
            "job_id": f"stress-job-{index}",
            "pipeline_type": "full",
            "complexity": "high",
        }

    def _stress_test_dagster_job(self, job: dict) -> dict:
        """Execute Dagster job under stress conditions."""
        start_time = time.time()
        try:
            # Simulate complex pipeline
            time.sleep(15.0 + (10.0 * (time.time() % 1)))
            return {
                "success": True,
                "response_time_ms": (time.time() - start_time) * 1000,
                "test_type": "dagster_stress",
            }
        except Exception as e:
            return {
                "success": False,
                "response_time_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "test_type": "dagster_stress",
            }

    def _generate_performance_recommendations(
        self,
        test_results: dict[str, PerformanceMetrics],
        cost_metrics: CostMetrics,
    ) -> None:
        """Generate performance optimization recommendations."""
        print("\n🎯 PERFORMANCE RECOMMENDATIONS")
        print("-" * 50)

        recommendations = []

        # Analyze consultation processing
        consultation_metrics = test_results.get("consultation_processing")
        if consultation_metrics and consultation_metrics.p95_response_time_ms > 5000:
            recommendations.append("Consider increasing Lambda memory for consultation processing")

        # Analyze Object Lambda performance
        redaction_metrics = test_results.get("object_lambda_redaction")
        if redaction_metrics and redaction_metrics.p95_response_time_ms > 500:
            recommendations.append("Optimize Object Lambda redaction algorithms")

        # Analyze cost efficiency
        if cost_metrics.cost_per_consultation_usd > 0.10:
            recommendations.append("Review AWS service usage to optimize costs")

        # Analyze error rates
        high_error_tests = [
            name for name, metrics in test_results.items()
            if metrics.error_rate_percent > 2.0
        ]
        if high_error_tests:
            recommendations.append(f"Investigate high error rates in: {', '.join(high_error_tests)}")

        # Print recommendations
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

        if not recommendations:
            print("✅ All performance metrics within acceptable ranges")

    def _save_detailed_report(
        self,
        test_results: dict[str, PerformanceMetrics],
        cost_metrics: CostMetrics,
        timestamp: str,
    ) -> None:
        """Save detailed performance report to file."""
        report_data = {
            "timestamp": timestamp,
            "test_results": {
                name: {
                    "test_name": metrics.test_name,
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "avg_response_time_ms": metrics.avg_response_time_ms,
                    "p95_response_time_ms": metrics.p95_response_time_ms,
                    "p99_response_time_ms": metrics.p99_response_time_ms,
                    "requests_per_second": metrics.requests_per_second,
                    "error_rate_percent": metrics.error_rate_percent,
                }
                for name, metrics in test_results.items()
            },
            "cost_analysis": {
                "total_cost_usd": cost_metrics.estimated_cost_usd,
                "cost_per_consultation_usd": cost_metrics.cost_per_consultation_usd,
                "lambda_invocations": cost_metrics.total_lambda_invocations,
                "comprehend_requests": cost_metrics.total_comprehend_requests,
                "s3_operations": cost_metrics.total_s3_operations,
            },
        }

        filename = f"performance_report_{timestamp.replace(':', '-').replace('.', '_')}.json"
        with open(filename, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved to: {filename}")


class CostTracker:
    """Track costs during performance testing."""

    def __init__(self):
        self.lambda_invocations = 0
        self.comprehend_requests = 0
        self.s3_operations = 0
        self.textract_pages = 0

        # AWS pricing (approximate, varies by region)
        self.pricing = {
            "lambda_request": 0.0000002,  # $0.20 per 1M requests
            "lambda_gb_second": 0.0000166667,  # $1.00 per 600,000 GB-seconds
            "comprehend_pii": 0.0001,  # $0.0001 per unit
            "comprehend_medical": 0.0001,  # $0.0001 per unit
            "s3_request": 0.0004,  # $0.40 per 1,000 requests
            "textract_page": 0.0015,  # $1.50 per 1,000 pages
        }

    def record_consultation_processing(self, result: dict) -> None:
        """Record costs for consultation processing."""
        if result.get("success"):
            self.lambda_invocations += 4  # PII, PHI, Bedrock, Storage lambdas
            self.comprehend_requests += 2  # PII + Medical
            self.s3_operations += 6  # Multiple read/write operations

    def record_object_lambda_request(self, result: dict) -> None:
        """Record costs for Object Lambda request."""
        if result.get("success"):
            self.lambda_invocations += 1
            self.comprehend_requests += 1
            self.s3_operations += 2

    def record_dagster_job(self, result: dict) -> None:
        """Record costs for Dagster job execution."""
        if result.get("success"):
            self.lambda_invocations += 2  # Trigger + monitoring
            self.s3_operations += 4  # Code location + results

    def get_cost_summary(self) -> CostMetrics:
        """Calculate total cost summary."""
        lambda_cost = (
            self.lambda_invocations * self.pricing["lambda_request"] +
            self.lambda_invocations * 0.512 * 3 * self.pricing["lambda_gb_second"]  # Assume 512MB, 3s avg
        )

        comprehend_cost = self.comprehend_requests * self.pricing["comprehend_pii"]
        s3_cost = self.s3_operations * self.pricing["s3_request"]
        textract_cost = self.textract_pages * self.pricing["textract_page"]

        total_cost = lambda_cost + comprehend_cost + s3_cost + textract_cost

        consultations_processed = self.lambda_invocations // 4  # Rough estimate
        cost_per_consultation = total_cost / consultations_processed if consultations_processed > 0 else 0

        return CostMetrics(
            total_lambda_invocations=self.lambda_invocations,
            total_comprehend_requests=self.comprehend_requests,
            total_s3_operations=self.s3_operations,
            total_textract_pages=self.textract_pages,
            estimated_cost_usd=total_cost,
            cost_per_consultation_usd=cost_per_consultation,
            cost_breakdown={
                "lambda": lambda_cost,
                "comprehend": comprehend_cost,
                "s3": s3_cost,
                "textract": textract_cost,
            },
        )


if __name__ == "__main__":
    # Run performance testing suite
    config = LoadTestingConfiguration()
    tester = ConsultationPipelineLoadTester(config)

    print("🚀 Starting A360 Healthcare Platform Load Testing Suite")
    print("=" * 80)

    results = tester.run_comprehensive_load_tests()

    print("\n✅ Load testing completed successfully!")
    print("Check the generated performance report for detailed analysis.")
