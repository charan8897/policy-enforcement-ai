#!/usr/bin/env python3
"""
Comprehensive Test Suite for Policy Enforcement Engine
Tests both policies: Overseas Travel + Business Travel Policy
"""

import json
import subprocess
import sys

# Test scenarios
test_cases = [
    {
        "name": "Overseas Travel - MD & CEO APPROVE",
        "file": "test_ov_md.json",
        "data": {
            "request_id": "OV_MD_001",
            "grade": "MD & CEO",
            "destination_country": "Switzerland",
            "purpose": "Board meeting",
            "travel_duration_days": 14
        },
        "expected": "APPROVE"
    },
    {
        "name": "Overseas Travel - E8 APPROVE",
        "file": "test_ov_e8.json",
        "data": {
            "request_id": "OV_E8_001",
            "grade": "E8",
            "destination_country": "USA",
            "purpose": "Conference",
            "travel_duration_days": 10
        },
        "expected": "APPROVE"
    },
    {
        "name": "Overseas Travel - E7 APPROVE",
        "file": "test_ov_e7.json",
        "data": {
            "request_id": "OV_E7_001",
            "grade": "E7",
            "destination_country": "Canada",
            "purpose": "Training",
            "travel_duration_days": 5
        },
        "expected": "APPROVE"
    },
    {
        "name": "Overseas Travel - Directors APPROVE",
        "file": "test_ov_dir.json",
        "data": {
            "request_id": "OV_DIR_001",
            "grade": "Directors",
            "destination_country": "UK",
            "purpose": "Client meeting",
            "travel_duration_days": 7
        },
        "expected": "APPROVE"
    },
    {
        "name": "Business Travel - AstraZeneca Employee REJECT",
        "file": "test_bt_reject.json",
        "data": {
            "request_id": "BT_REJECT_001",
            "employee_status": "AstraZeneca employee",
            "destination_country": "Germany",
            "trip_duration_days": 3
        },
        "expected": "REJECT"
    },
    {
        "name": "Business Travel - Non-Employee REJECT",
        "file": "test_bt_non_emp.json",
        "data": {
            "request_id": "BT_NON_EMP_001",
            "employee_status": "Contractor",
            "destination_country": "France"
        },
        "expected": "REJECT"
    },
]

def run_test(test_case):
    """Run a single test case"""
    name = test_case["name"]
    filename = test_case["file"]
    data = test_case["data"]
    expected = test_case["expected"]
    
    # Write test data to file
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Run evaluation
    result = subprocess.run(
        ['python3', 'extract_policy.py', 'evaluate', filename],
        capture_output=True,
        text=True
    )
    
    # Parse result
    result_file = filename.replace('.json', '_result.json')
    try:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        actual = result_data.get('decision', 'UNKNOWN')
    except:
        actual = 'ERROR'
    
    # Check result
    status = "✓ PASS" if actual == expected else "✗ FAIL"
    
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "status": status,
        "result_data": result_data if actual != 'ERROR' else None
    }

def main():
    print(f"\n{'='*70}")
    print(f"Policy Enforcement Engine - Comprehensive Test Suite")
    print(f"{'='*70}\n")
    
    results = []
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"[{i}/{len(test_cases)}] Running: {test_case['name']}")
        
        result = run_test(test_case)
        results.append(result)
        
        status_color = "\033[92m" if result['status'].startswith("✓") else "\033[91m"
        reset_color = "\033[0m"
        
        print(f"  Expected: {result['expected']}")
        print(f"  Actual: {result['actual']}")
        print(f"  {status_color}{result['status']}{reset_color}\n")
        
        if result['status'].startswith("✓"):
            passed += 1
        else:
            failed += 1
    
    # Summary
    print(f"{'='*70}")
    print(f"Test Summary")
    print(f"{'='*70}")
    print(f"Total: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%\n")
    
    # Detailed results
    print(f"{'='*70}")
    print(f"Detailed Results")
    print(f"{'='*70}\n")
    
    for result in results:
        status_color = "\033[92m" if result['status'].startswith("✓") else "\033[91m"
        reset_color = "\033[0m"
        
        print(f"{status_color}{result['status']}{reset_color} - {result['name']}")
        if result['result_data']:
            reason = result['result_data'].get('primary_reason', 'N/A')
            print(f"    Reason: {reason}")
            if result['result_data'].get('violations'):
                print(f"    Violations: {len(result['result_data']['violations'])}")
            if result['result_data'].get('approvals'):
                print(f"    Approvals: {len(result['result_data']['approvals'])}")
        print()
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
