#!/usr/bin/env python3
"""
Test runner script for RentScout project.
"""
import os
import sys
import subprocess

def run_tests():
    """Run all tests for the RentScout project."""
    # Change to the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Run pytest with coverage
    cmd = [
        sys.executable, "-m", "pytest",
        "app/tests",
        "-v",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov"
    ]
    
    print("Running tests...")
    print(" ".join(cmd))
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\nTests completed successfully!")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\nTests failed with return code {e.returncode}")
        return e.returncode

if __name__ == "__main__":
    sys.exit(run_tests())