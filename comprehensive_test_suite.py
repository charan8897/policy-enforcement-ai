#!/usr/bin/env python3
"""
Comprehensive Test Suite with Accept/Reject Scenarios
Tests policy enforcement with multiple scenarios
"""

import json
import subprocess
import sys
from datetime import datetime

test_cases = [
    # ===== OVERSEAS TRAVEL POLICY TESTS =====
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "MD & CEO travels to First Class",
        "file": "test_ov_md_approve.json",
        "data": {
            "request_id": "OV_APPROVE_001",
            "grade": "MD & CEO",
            "destination_country": "Switzerland",
            "purpose": "Executive Board Meeting",
            "travel_duration_days": 14,
            "mode_of_transport": "Air",
            "class_of_travel": "First Class"
        },
        "expected": "APPROVE"
    },
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "Directors travel to Business/Club Class",
        "file": "test_ov_dir_approve.json",
        "data": {
            "request_id": "OV_APPROVE_002",
            "grade": "Directors",
            "destination_country": "Germany",
            "purpose": "Business Conference",
            "travel_duration_days": 10,
            "mode_of_transport": "Air",
            "class_of_travel": "Business Class"
        },
        "expected": "APPROVE"
    },
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "E8-E10 range travels to Business Class",
        "file": "test_ov_e9_approve.json",
        "data": {
            "request_id": "OV_APPROVE_003",
            "grade": "E9",
            "destination_country": "USA",
            "purpose": "Technical Conference",
            "travel_duration_days": 7,
            "mode_of_transport": "Air",
            "class_of_travel": "Business Class"
        },
        "expected": "APPROVE"
    },
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "E7 and below travel to Economy Class",
        "file": "test_ov_e7_approve.json",
        "data": {
            "request_id": "OV_APPROVE_004",
            "grade": "E7",
            "destination_country": "Canada",
            "purpose": "Training Programme",
            "travel_duration_days": 5,
            "mode_of_transport": "Air",
            "class_of_travel": "Economy Class"
        },
        "expected": "APPROVE"
    },
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "E8 within eligible range",
        "file": "test_ov_e8_approve.json",
        "data": {
            "request_id": "OV_APPROVE_005",
            "grade": "E8",
            "destination_country": "France",
            "purpose": "Client Meeting",
            "travel_duration_days": 4,
            "mode_of_transport": "Air"
        },
        "expected": "APPROVE"
    },
    {
        "category": "Overseas Travel - Grade-based APPROVAL",
        "name": "E10 upper boundary test",
        "file": "test_ov_e10_approve.json",
        "data": {
            "request_id": "OV_APPROVE_006",
            "grade": "E10",
            "destination_country": "Japan",
            "purpose": "Strategic Partnership",
            "travel_duration_days": 12,
            "mode_of_transport": "Air",
            "class_of_travel": "Business Class"
        },
        "expected": "APPROVE"
    },
    
    # ===== REJECTION TESTS =====
    {
        "category": "Invalid Grade - REJECTION",
        "name": "Non-existent grade E5 rejected",
        "file": "test_ov_invalid_grade.json",
        "data": {
            "request_id": "OV_REJECT_001",
            "grade": "E5",
            "destination_country": "India",
            "purpose": "Site Visit",
            "travel_duration_days": 3
        },
        "expected": "REJECT"
    },
    {
        "category": "Invalid Grade - REJECTION",
        "name": "Unknown grade category rejected",
        "file": "test_ov_unknown_grade.json",
        "data": {
            "request_id": "OV_REJECT_002",
            "grade": "Intern",
            "destination_country": "UK",
            "purpose": "Training",
            "travel_duration_days": 2
        },
        "expected": "REJECT"
    },
    
    # ===== EDGE CASES =====
    {
        "category": "Edge Cases",
        "name": "Boundary test: E7 (minimum eligible)",
        "file": "test_ov_boundary_e7.json",
        "data": {
            "request_id": "OV_EDGE_001",
            "grade": "E7",
            "destination_country": "Australia",
            "purpose": "Long-haul meeting",
            "travel_duration_days": 20
        },
        "expected": "APPROVE"
    },
    {
        "category": "Edge Cases",
        "name": "Missing required field - rejection",
        "file": "test_ov_missing_field.json",
        "data": {
            "request_id": "OV_EDGE_002",
            "destination_country": "Singapore"
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
        text=True,
        timeout=10
    )
    
    # Parse result
    result_file = filename.replace('.json', '_result.json')
    try:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        actual = result_data.get('decision', 'UNKNOWN')
    except Exception as e:
        actual = 'ERROR'
        result_data = {'error': str(e)}
    
    # Check result
    status = "✓ PASS" if actual == expected else "✗ FAIL"
    
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "status": status,
        "result_data": result_data
    }

def print_test_details(result):
    """Print detailed test result"""
    print(f"\n  Decision: {result['actual']}")
    
    if result['result_data']:
        if result['actual'] in ['APPROVE', 'REJECT']:
            reason = result['result_data'].get('primary_reason', 'N/A')
            print(f"  Reason: {reason}")
            
            approvals = result['result_data'].get('approvals', [])
            violations = result['result_data'].get('violations', [])
            
            if approvals:
                print(f"  ✓ Approvals: {len(approvals)}")
                for approval in approvals:
                    print(f"    - {approval['rule_id']}")
            
            if violations:
                print(f"  ✗ Violations: {len(violations)}")
                for violation in violations:
                    print(f"    - {violation['rule_id']}: {violation['message'][:50]}...")

def main():
    print(f"\n{'='*80}")
    print(f"Policy Enforcement Engine - Comprehensive Test Suite")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # Group tests by category
    categories = {}
    for test in test_cases:
        cat = test['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(test)
    
    total_passed = 0
    total_failed = 0
    results_by_category = {}
    
    # Run tests by category
    for category, tests in categories.items():
        print(f"\n{category}")
        print("-" * 80)
        
        category_results = []
        for test in tests:
            result = run_test(test)
            category_results.append(result)
            
            status_symbol = "✓" if result['status'].startswith("✓") else "✗"
            print(f"{status_symbol} {result['name']}")
            print_test_details(result)
            
            if result['status'].startswith("✓"):
                total_passed += 1
            else:
                total_failed += 1
        
        results_by_category[category] = category_results
    
    # Overall summary
    print(f"\n{'='*80}")
    print(f"Test Summary")
    print(f"{'='*80}")
    print(f"Total Tests: {len(test_cases)}")
    print(f"✓ Passed: {total_passed}")
    print(f"✗ Failed: {total_failed}")
    print(f"Success Rate: {(total_passed/len(test_cases)*100):.1f}%")
    
    # Category summary
    print(f"\nResults by Category:")
    for category in categories.keys():
        results = results_by_category[category]
        passed = sum(1 for r in results if r['status'].startswith("✓"))
        total = len(results)
        print(f"  {category}: {passed}/{total}")
    
    print(f"\n{'='*80}\n")
    
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
