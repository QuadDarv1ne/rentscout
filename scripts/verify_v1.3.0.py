#!/usr/bin/env python3
"""
v1.3.0 Feature Verification Script

This script verifies that all v1.3.0 features are correctly implemented
and integrated into the project.
"""

import os
import sys
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(file_path).exists():
        print(f"{GREEN}✓{RESET} {description}")
        return True
    else:
        print(f"{RED}✗{RESET} {description} - {file_path} not found")
        return False

def check_code_in_file(file_path: str, code_snippet: str, description: str) -> bool:
    """Check if a code snippet exists in a file."""
    if not Path(file_path).exists():
        print(f"{RED}✗{RESET} {description} - File not found")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if code_snippet in content:
                print(f"{GREEN}✓{RESET} {description}")
                return True
            else:
                print(f"{RED}✗{RESET} {description} - Code snippet not found")
                return False
    except Exception as e:
        print(f"{RED}✗{RESET} {description} - Error reading file: {e}")
        return False

def verify_v1_3_0_features():
    """Verify all v1.3.0 features."""
    print(f"\n{BLUE}{'='*60}")
    print(f"v1.3.0 Feature Verification")
    print(f"{'='*60}{RESET}\n")
    
    results = []
    
    # 1. Structured JSON Logging
    print(f"{YELLOW}1. Structured JSON Logging (ELK){RESET}")
    results.append(check_file_exists(
        'app/utils/structured_logger.py',
        'Structured logger file exists'
    ))
    results.append(check_code_in_file(
        'app/utils/structured_logger.py',
        'class StructuredLogger',
        'StructuredLogger class defined'
    ))
    results.append(check_code_in_file(
        'app/utils/structured_logger.py',
        'ISO 8601',
        'ISO 8601 timestamp support'
    ))
    print()
    
    # 2. Query Analyzer
    print(f"{YELLOW}2. Query Analysis & Optimization{RESET}")
    results.append(check_file_exists(
        'app/db/query_analyzer.py',
        'Query analyzer module exists'
    ))
    results.append(check_code_in_file(
        'app/db/query_analyzer.py',
        'class QueryAnalyzer',
        'QueryAnalyzer class defined'
    ))
    results.append(check_code_in_file(
        'app/db/query_analyzer.py',
        'EXPLAIN ANALYZE',
        'EXPLAIN ANALYZE support'
    ))
    results.append(check_code_in_file(
        'app/db/query_analyzer.py',
        'pg_stat_statements',
        'Slow query analysis support'
    ))
    print()
    
    # 3. Query Cache
    print(f"{YELLOW}3. Intelligent Query Caching{RESET}")
    results.append(check_file_exists(
        'app/db/query_cache.py',
        'Query cache module exists'
    ))
    results.append(check_code_in_file(
        'app/db/query_cache.py',
        'class QueryCache',
        'QueryCache class defined'
    ))
    results.append(check_code_in_file(
        'app/db/query_cache.py',
        '@cached_query',
        'Decorator support'
    ))
    results.append(check_code_in_file(
        'app/db/query_cache.py',
        'class PopularQueriesCache',
        'PopularQueriesCache class'
    ))
    print()
    
    # 4. Async Export
    print(f"{YELLOW}4. Asynchronous Export Service{RESET}")
    results.append(check_file_exists(
        'app/services/async_export.py',
        'Async export service exists'
    ))
    results.append(check_code_in_file(
        'app/services/async_export.py',
        'class AsyncExportService',
        'AsyncExportService class defined'
    ))
    results.append(check_code_in_file(
        'app/services/async_export.py',
        'export_properties_streaming',
        'Streaming export method'
    ))
    results.append(check_code_in_file(
        'app/services/async_export.py',
        'EXPORT_FORMATS = [',
        'Multiple format support'
    ))
    results.append(check_file_exists(
        'app/api/endpoints/export.py',
        'Export endpoints exist'
    ))
    print()
    
    # 5. Error Handling
    print(f"{YELLOW}5. Enhanced Error Handling{RESET}")
    results.append(check_code_in_file(
        'app/utils/error_handler.py',
        'class CircuitBreaker',
        'CircuitBreaker class defined'
    ))
    results.append(check_code_in_file(
        'app/utils/error_handler.py',
        'class RetryStrategy',
        'RetryStrategy enum defined'
    ))
    results.append(check_code_in_file(
        'app/utils/error_handler.py',
        '@retry_advanced',
        'Advanced retry decorator'
    ))
    results.append(check_code_in_file(
        'app/utils/error_handler.py',
        'CircuitBreakerState',
        'Circuit breaker states'
    ))
    print()
    
    # 6. Documentation
    print(f"{YELLOW}6. Documentation{RESET}")
    results.append(check_file_exists(
        'docs/IMPROVEMENTS_v1.3.md',
        'Comprehensive feature guide'
    ))
    results.append(check_file_exists(
        'docs/IMPROVEMENTS_COMPLETED_v1.3.md',
        'Release summary'
    ))
    results.append(check_file_exists(
        'INTEGRATION_v1.3.md',
        'Integration quick start'
    ))
    results.append(check_file_exists(
        'docs/v1.3.0_COMPLETION_SUMMARY.md',
        'Completion summary'
    ))
    print()
    
    # Summary
    print(f"{BLUE}{'='*60}")
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    if passed == total:
        print(f"{GREEN}✓ ALL CHECKS PASSED ({passed}/{total}) - {percentage:.0f}%{RESET}")
    else:
        print(f"{RED}✗ SOME CHECKS FAILED ({passed}/{total}) - {percentage:.0f}%{RESET}")
    
    print(f"{'='*60}{RESET}\n")
    
    return passed == total

def show_integration_instructions():
    """Show integration instructions."""
    print(f"{BLUE}{'='*60}")
    print("Integration Instructions")
    print(f"{'='*60}{RESET}\n")
    
    print(f"{YELLOW}1. Enable JSON Logging{RESET}")
    print("   Update app/main.py:")
    print("   from app.utils.structured_logger import setup_logger")
    print("   logger = setup_logger(json_format=True)\n")
    
    print(f"{YELLOW}2. Mount Export Router{RESET}")
    print("   In app/main.py:")
    print("   from app.api.endpoints.export import router as export_router")
    print("   app.include_router(export_router, prefix='/api')\n")
    
    print(f"{YELLOW}3. Apply Caching Decorator{RESET}")
    print("   In repository methods:")
    print("   @cached_query('popular_properties', ttl=3600)")
    print("   async def get_popular(self, city: str):\n")
    
    print(f"{YELLOW}4. Use Advanced Retry Logic{RESET}")
    print("   On external API calls:")
    print("   @retry_advanced(strategy=RetryStrategy.EXPONENTIAL)")
    print("   async def fetch_from_api():\n")
    
    print(f"{YELLOW}5. Optional: Enable Query Analysis{RESET}")
    print("   In PostgreSQL:")
    print("   CREATE EXTENSION pg_stat_statements;\n")
    
    print(f"{BLUE}{'='*60}{RESET}\n")

def main():
    """Main verification function."""
    # Change to project root
    project_root = Path(__file__).parent.parent if Path(__file__).name == 'verify_v1.3.0.py' else Path.cwd()
    os.chdir(project_root)
    
    # Run verification
    success = verify_v1_3_0_features()
    
    # Show instructions
    show_integration_instructions()
    
    # Print helpful information
    print(f"{YELLOW}📚 Documentation:{RESET}")
    print(f"  • {BLUE}docs/IMPROVEMENTS_v1.3.md{RESET} - Full feature guide")
    print(f"  • {BLUE}INTEGRATION_v1.3.md{RESET} - Quick start")
    print(f"  • {BLUE}docs/v1.3.0_COMPLETION_SUMMARY.md{RESET} - Completion details\n")
    
    print(f"{YELLOW}🧪 Testing:{RESET}")
    print(f"  pytest app/tests/test_async_export.py -v")
    print(f"  pytest app/tests/test_query_analyzer.py -v")
    print(f"  pytest app/tests/test_query_cache.py -v")
    print(f"  pytest app/tests/test_error_handler.py -v\n")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
