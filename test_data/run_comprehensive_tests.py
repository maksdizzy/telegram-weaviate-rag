#!/usr/bin/env python3
"""
Comprehensive API Testing Script for RAG Knowledge Base
Tests all endpoints with various scenarios and measures performance
"""

import requests
import json
import time
import os
from datetime import datetime
from pathlib import Path

class APITester:
    def __init__(self, base_url="http://localhost:8000", api_key="1fd700a4634a291e28fbe69023cd4f761f2ea6da5b8a653183d37c5f125370cb"):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.test_results = []
        self.start_time = time.time()

    def log_test(self, test_name, status, duration, details=None, error=None):
        """Log test results"""
        result = {
            "test_name": test_name,
            "status": status,
            "duration_ms": round(duration * 1000, 2),
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
            "error": error
        }
        self.test_results.append(result)

        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name}: {status} ({result['duration_ms']}ms)")
        if error:
            print(f"   Error: {error}")
        if details:
            print(f"   Details: {details}")

    def test_health_check(self):
        """Test health endpoint"""
        start = time.time()
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                self.log_test("Health Check", "PASS", duration, {
                    "status_code": response.status_code,
                    "response": data
                })
                return True
            else:
                self.log_test("Health Check", "FAIL", duration, {
                    "status_code": response.status_code
                })
                return False
        except Exception as e:
            duration = time.time() - start
            self.log_test("Health Check", "FAIL", duration, error=str(e))
            return False

    def test_root_endpoint(self):
        """Test root endpoint"""
        start = time.time()
        try:
            response = requests.get(f"{self.base_url}/", timeout=10)
            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                self.log_test("Root Endpoint", "PASS", duration, {
                    "status_code": response.status_code,
                    "endpoints_listed": len(data.get("endpoints", {}))
                })
                return True
            else:
                self.log_test("Root Endpoint", "FAIL", duration, {
                    "status_code": response.status_code
                })
                return False
        except Exception as e:
            duration = time.time() - start
            self.log_test("Root Endpoint", "FAIL", duration, error=str(e))
            return False

    def test_upload_file(self, file_path, merge=False, chat_name=None, expected_status=200):
        """Test file upload endpoint"""
        test_name = f"Upload File ({Path(file_path).name})"
        if merge:
            test_name += " - Merge Mode"
        if chat_name:
            test_name += f" - Chat: {chat_name}"

        start = time.time()
        try:
            params = {}
            if merge:
                params["merge"] = "true"
            if chat_name:
                params["chat_name"] = chat_name

            with open(file_path, 'rb') as f:
                files = {"file": (Path(file_path).name, f, "application/json")}
                headers = {"Authorization": self.headers["Authorization"]}

                response = requests.post(
                    f"{self.base_url}/upload",
                    files=files,
                    headers=headers,
                    params=params,
                    timeout=30
                )

            duration = time.time() - start

            if response.status_code == expected_status:
                if response.status_code == 200:
                    data = response.json()
                    self.log_test(test_name, "PASS", duration, {
                        "status_code": response.status_code,
                        "mode": data.get("mode"),
                        "total_messages": data.get("total_messages"),
                        "filename": data.get("filename"),
                        "size": data.get("size")
                    })
                else:
                    self.log_test(test_name, "PASS", duration, {
                        "status_code": response.status_code,
                        "expected_error": True
                    })
                return True
            else:
                error_data = response.json() if response.content else {}
                self.log_test(test_name, "FAIL", duration, {
                    "status_code": response.status_code,
                    "expected": expected_status,
                    "response": error_data
                })
                return False

        except Exception as e:
            duration = time.time() - start
            self.log_test(test_name, "FAIL", duration, error=str(e))
            return False

    def test_process_endpoint(self, file_path, knowledge_id="telegram-rag", merge=False, chat_name=None, incremental=True, expected_status=200):
        """Test process endpoint (upload + ingestion)"""
        test_name = f"Process File ({Path(file_path).name})"
        if merge:
            test_name += " - Merge"
        if incremental:
            test_name += " - Incremental"

        start = time.time()
        try:
            params = {
                "knowledge_id": knowledge_id,
                "merge": str(merge).lower(),
                "incremental": str(incremental).lower()
            }
            if chat_name:
                params["chat_name"] = chat_name

            with open(file_path, 'rb') as f:
                files = {"file": (Path(file_path).name, f, "application/json")}
                headers = {"Authorization": self.headers["Authorization"]}

                response = requests.post(
                    f"{self.base_url}/process",
                    files=files,
                    headers=headers,
                    params=params,
                    timeout=60  # Longer timeout for processing
                )

            duration = time.time() - start

            if response.status_code == expected_status:
                if response.status_code == 200:
                    data = response.json()
                    self.log_test(test_name, "PASS", duration, {
                        "status_code": response.status_code,
                        "knowledge_id": data.get("knowledge_id"),
                        "uploaded_messages": data.get("uploaded", {}).get("total_messages"),
                        "process_status": data.get("processed", {}).get("status")
                    })
                else:
                    self.log_test(test_name, "PASS", duration, {
                        "status_code": response.status_code,
                        "expected_error": True
                    })
                return True
            else:
                error_data = response.json() if response.content else {}
                self.log_test(test_name, "FAIL", duration, {
                    "status_code": response.status_code,
                    "expected": expected_status,
                    "response": error_data
                })
                return False

        except Exception as e:
            duration = time.time() - start
            self.log_test(test_name, "FAIL", duration, error=str(e))
            return False

    def test_retrieval(self, query, knowledge_id="telegram-rag", top_k=3, score_threshold=0.5):
        """Test retrieval endpoint"""
        test_name = f"Retrieval: '{query[:30]}...'"
        start = time.time()
        try:
            data = {
                "knowledge_id": knowledge_id,
                "query": query,
                "retrieval_setting": {
                    "top_k": top_k,
                    "score_threshold": score_threshold
                }
            }

            response = requests.post(
                f"{self.base_url}/retrieval",
                headers=self.headers,
                json=data,
                timeout=30
            )

            duration = time.time() - start

            if response.status_code == 200:
                result = response.json()
                records = result.get("records", [])
                self.log_test(test_name, "PASS", duration, {
                    "status_code": response.status_code,
                    "results_count": len(records),
                    "avg_score": round(sum(r.get("score", 0) for r in records) / len(records), 3) if records else 0,
                    "query_length": len(query)
                })
                return True
            else:
                error_data = response.json() if response.content else {}
                self.log_test(test_name, "FAIL", duration, {
                    "status_code": response.status_code,
                    "response": error_data
                })
                return False

        except Exception as e:
            duration = time.time() - start
            self.log_test(test_name, "FAIL", duration, error=str(e))
            return False

    def test_knowledge_base_stats(self, knowledge_id="telegram-rag"):
        """Test knowledge base stats endpoint"""
        test_name = f"KB Stats: {knowledge_id}"
        start = time.time()
        try:
            response = requests.get(
                f"{self.base_url}/knowledge-bases/{knowledge_id}/stats",
                headers=self.headers,
                timeout=30
            )

            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                self.log_test(test_name, "PASS", duration, {
                    "status_code": response.status_code,
                    "total_documents": data.get("total_documents"),
                    "total_messages": data.get("total_messages"),
                    "participants_count": len(data.get("participants", [])),
                    "collection_exists": data.get("collection_exists")
                })
                return True
            else:
                error_data = response.json() if response.content else {}
                self.log_test(test_name, "FAIL", duration, {
                    "status_code": response.status_code,
                    "response": error_data
                })
                return False

        except Exception as e:
            duration = time.time() - start
            self.log_test(test_name, "FAIL", duration, error=str(e))
            return False

    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 Starting Comprehensive API Tests")
        print("=" * 50)

        # Test 1: Basic Health Checks
        print("\n📋 Phase 1: Health Checks")
        self.test_health_check()
        self.test_root_endpoint()

        # Test 2: File Validation Tests
        print("\n📋 Phase 2: File Validation Tests")
        test_dir = Path(__file__).parent

        # Test invalid JSON
        self.test_upload_file(test_dir / "invalid_json.json", expected_status=400)

        # Test non-Telegram format
        self.test_upload_file(test_dir / "non_telegram_format.json", expected_status=400)

        # Test 3: Valid File Processing
        print("\n📋 Phase 3: Valid File Processing")

        # Test valid file upload (replace mode)
        self.test_upload_file(test_dir / "valid_telegram_export.json")

        # Test process endpoint with valid file
        self.test_process_endpoint(test_dir / "valid_telegram_export.json")

        # Test 4: Merge Mode Testing
        print("\n📋 Phase 4: Merge Mode Testing")

        # Upload family chat with merge
        self.test_upload_file(test_dir / "family_chat.json", merge=True, chat_name="family")

        # Upload work chat with merge
        self.test_upload_file(test_dir / "work_chat.json", merge=True, chat_name="work")

        # Process merged data
        self.test_process_endpoint(test_dir / "family_chat.json", merge=True, chat_name="family_new")

        # Test 5: Large File Performance
        print("\n📋 Phase 5: Performance Testing")

        # Test large file processing
        large_file = test_dir / "large_telegram_export.json"
        if large_file.exists():
            self.test_process_endpoint(large_file)

        # Test 6: Search Functionality
        print("\n📋 Phase 6: Search & Retrieval Testing")

        # Wait a moment for indexing
        time.sleep(2)

        # Test various search queries
        queries = [
            "coffee morning",
            "family dinner",
            "work project meeting",
            "weekend plans",
            "technology programming"
        ]

        for query in queries:
            self.test_retrieval(query)

        # Test 7: Knowledge Base Management
        print("\n📋 Phase 7: Knowledge Base Management")

        # Test stats endpoint
        self.test_knowledge_base_stats()

        # Generate report
        self.generate_report()

    def generate_report(self):
        """Generate comprehensive test report"""
        total_duration = time.time() - self.start_time
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = len([r for r in self.test_results if r["status"] == "FAIL"])

        print("\n" + "=" * 50)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Total Duration: {total_duration:.2f}s")

        # Performance metrics
        durations = [r["duration_ms"] for r in self.test_results]
        print(f"\nPerformance Metrics:")
        print(f"  Average Response Time: {sum(durations)/len(durations):.2f}ms")
        print(f"  Fastest Test: {min(durations):.2f}ms")
        print(f"  Slowest Test: {max(durations):.2f}ms")

        # Failed tests details
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"  - {result['test_name']}: {result.get('error', 'Unknown error')}")

        # Save detailed report
        report_file = test_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "success_rate": (passed_tests/total_tests)*100,
                    "total_duration": total_duration,
                    "timestamp": datetime.now().isoformat()
                },
                "detailed_results": self.test_results
            }, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    # Get the test directory
    test_dir = Path(__file__).parent

    # Initialize tester
    tester = APITester()

    # Run all tests
    tester.run_all_tests()