#!/usr/bin/env python3
"""
LLM-Based Rule Extraction from Policy Documents
Uses Gemini to intelligently extract structured rules from policy.txt
Generates complete rules.json with all leave policies
"""

import json
import google.generativeai as genai
from datetime import datetime

class PolicyRuleExtractor:
    def __init__(self, api_key, policy_file="policy.txt", output_file="rules.json"):
        """Initialize with Gemini API key"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemma-3-27b-it')
        self.policy_file = policy_file
        self.output_file = output_file
        
        # Read policy file
        with open(policy_file, 'r') as f:
            self.policy_text = f.read()
    
    def extract_all_rules(self):
        """Extract all leave policy rules"""
        print(f"\n{'='*70}")
        print(f"Policy Rule Extraction")
        print(f"{'='*70}")
        print(f"[FILE] {self.policy_file}")
        print(f"[SIZE] {len(self.policy_text)} characters")
        
        # Dynamically extract leave types from policy using LLM
        leave_types = self._extract_leave_types_from_policy()
        
        if not leave_types:
            print("[WARNING] No leave types found. Using fallback list.")
            leave_types = ['Casual Leave', 'Earned Leave', 'Sick Leave']
        
        print(f"[DETECTED] {len(leave_types)} leave types: {', '.join(leave_types)}")
        
        all_rules = []
        rule_counter = 1
        
        for leave_type in leave_types:
            print(f"\n[EXTRACTING] {leave_type}...")
            
            # Extract rules for this leave type
            rules = self._extract_leave_type_rules(leave_type, rule_counter)
            
            if rules:
                all_rules.extend(rules)
                rule_counter += len(rules)
                print(f"  ✓ Found {len(rules)} rules")
            else:
                print(f"  ⚠ No rules found")
        
        print(f"\n[TOTAL] {len(all_rules)} rules extracted")
        
        return all_rules
    
    def _extract_policy_categories(self):
        """Use LLM to dynamically extract all policy categories/types from ANY policy document"""
        print(f"[LLM] Extracting policy categories dynamically...")
        
        # Search for common section patterns first
        policy_context = self._find_policy_section()
        
        if not policy_context:
            policy_context = self.policy_text[:10000]
            print(f"[LLM] Using first 10000 characters as fallback")
        
        # Single LLM call to extract categories generically
        categories = self._extract_categories_from_context(policy_context)
        
        return categories
    
    def _find_policy_section(self):
        """Dynamically find the section in policy that defines categories"""
        # Try multiple search patterns (works for most policy types)
        search_patterns = [
            # Explicit listings
            ("kinds of", "kinds of"),
            ("types of", "types of"),
            ("categories", "categories"),
            ("list of", "list of"),
            
            # Policy structure headers
            ("type ", "type "),
            ("mode of", "mode of"),
            ("classification of", "classification of"),
            ("grade", "grade"),
            ("designation", "designation"),
            ("entitlement", "entitlement"),
            
            # Section markers
            ("eligibility", "eligibility"),
            ("benefit", "benefit"),
        ]
        
        # Search for any matching pattern
        for pattern, label in search_patterns:
            pos = self.policy_text.lower().find(pattern)
            if pos > 0:
                section = self.policy_text[pos:pos + 15000]
                print(f"[LLM] Found section with '{label}' at position {pos}")
                return section
        
        return None
    
    def _extract_categories_from_context(self, policy_context):
        """Extract all policy categories/types dynamically without hardcoded examples"""
        prompt = f"""
You are a policy analysis expert. Extract ALL distinct categories/types/kinds mentioned in this policy section.

Policy text excerpt:
{policy_context}

Task: Identify EVERY category or type mentioned. Look for patterns like:
- "Type X: [Name]"
- "Kind of [Name]"
- "[Name] [Category]"
- Section headers with multiple items listed

Extract the category names exactly as they appear. Do NOT include numbers, labels, or bullets.

Return ONLY a valid JSON array with category names.

Rules:
- One category name per array element
- Use exact wording from policy
- Skip generic terms like "Type", "Kind", just extract the actual names
- Return ONLY the JSON array, nothing else

Example output formats (for different policies):
Leave: ["Casual Leave", "Earned Leave", "Sick Leave"]
Procurement: ["Equipment", "Software", "Services"]
Travel: ["Domestic", "International", "Emergency"]

If no categories found, return: []

JSON Array:"""
        
        try:
            print(f"[LLM] Calling API for category extraction...")
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            print(f"[LLM] Response: {response_text[:150]}...")
            
            # Extract JSON array
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                print(f"[LLM] No JSON found")
                return []
            
            json_str = response_text[start:end]
            categories = json.loads(json_str)
            
            if isinstance(categories, list) and categories:
                print(f"[LLM] ✓ Extracted {len(categories)} categories: {categories}")
                return categories
            else:
                return []
        
        except json.JSONDecodeError as e:
            print(f"[LLM] JSON error: {e}")
            return []
        except Exception as e:
            print(f"[LLM] Error: {type(e).__name__}: {e}")
            return []
    
    def _extract_leave_types_from_policy(self):
        """Wrapper for backward compatibility - now uses generic extraction"""
        return self._extract_policy_categories()
    
    def _extract_leave_type_rules(self, leave_type, rule_start_id):
        """Extract rules for a specific leave type using LLM"""
        
        prompt = f"""
Extract all policy rules for "{leave_type}" from the policy text below.

For each rule, extract:
1. The condition (what must be true)
2. The action (what happens - APPROVE, REJECT, REQUIRE_DOCUMENTATION, ELIGIBLE, etc)
3. The allocation (days/weeks if applicable)
4. The message (human-readable rule description)
5. The severity (HIGH, MEDIUM, LOW)

Policy text section for {leave_type}:
{self._search_policy_section(leave_type)}

Return ONLY valid JSON array. Example format:
[
  {{
    "rule_id": "RULE_CL_001",
    "policy_id": "POL_CASUAL_LEAVE",
    "policy_name": "{leave_type} Policy",
    "conditions": [
      {{
        "field": "leave_type",
        "operator": "equals",
        "value": "casual"
      }}
    ],
    "action": "ELIGIBLE",
    "allocation": 8,
    "period": "per_annum",
    "message": "description",
    "severity": "MEDIUM"
  }}
]

Requirements:
- Return ONLY JSON array
- Each rule must have: rule_id, policy_id, policy_name, conditions, action, message
- Use valid operators: equals, greater_than, less_than, greater_than_or_equals, in, and, or
- Use valid actions: APPROVE, REJECT, ELIGIBLE, REQUIRE_DOCUMENTATION, WARN, ESCALATE
- Include all conditions mentioned in policy
- Return empty array [] if no rules found

JSON:"""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response
            if response_text.startswith('['):
                json_str = response_text
            else:
                # Try to extract JSON from text
                start = response_text.find('[')
                end = response_text.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
                else:
                    return []
            
            rules = json.loads(json_str)
            
            # Update rule IDs to be sequential
            for i, rule in enumerate(rules):
                leave_prefix = leave_type.split()[0][:2].upper()
                rule['rule_id'] = f"RULE_{leave_prefix}_{rule_start_id + i:03d}"
            
            return rules
            
        except json.JSONDecodeError as e:
            print(f"  [ERROR] Invalid JSON: {e}")
            return []
        except Exception as e:
            print(f"  [ERROR] {e}")
            return []
    
    def _search_policy_section(self, leave_type):
        """Search policy text for relevant section"""
        lines = self.policy_text.split('\n')
        section_lines = []
        capture = False
        line_count = 0
        max_lines = 100  # Limit lines to send to LLM
        
        for line in lines:
            # Start capturing when we find the leave type
            if leave_type.lower() in line.lower():
                capture = True
            
            if capture:
                section_lines.append(line)
                line_count += 1
                
                # Stop after collecting enough lines
                if line_count > max_lines:
                    break
        
        return '\n'.join(section_lines[:max_lines]) if section_lines else f"No section found for {leave_type}"
    
    def save_rules(self, rules):
        """Save rules to JSON file"""
        with open(self.output_file, 'w') as f:
            json.dump(rules, f, indent=2)
        print(f"\n[SAVED] {self.output_file}")
    
    def validate_rules(self, rules):
        """Validate extracted rules"""
        print(f"\n{'='*70}")
        print(f"Rule Validation")
        print(f"{'='*70}")
        
        required_fields = ['rule_id', 'policy_id', 'policy_name', 'conditions', 'action', 'message']
        valid_actions = ['APPROVE', 'REJECT', 'ELIGIBLE', 'REQUIRE_DOCUMENTATION', 'WARN', 'ESCALATE']
        valid_operators = ['equals', 'greater_than', 'less_than', 'greater_than_or_equals', 'less_than_or_equals', 'in', 'and', 'or', 'not']
        
        issues = []
        
        for rule in rules:
            # Check required fields
            missing = [f for f in required_fields if f not in rule]
            if missing:
                issues.append(f"Rule {rule.get('rule_id')}: Missing fields {missing}")
            
            # Check action validity
            if rule.get('action') not in valid_actions:
                issues.append(f"Rule {rule.get('rule_id')}: Invalid action '{rule.get('action')}'")
            
            # Check conditions
            for cond in rule.get('conditions', []):
                if cond.get('operator') not in valid_operators:
                    issues.append(f"Rule {rule.get('rule_id')}: Invalid operator '{cond.get('operator')}'")
        
        if issues:
            print(f"\n[ISSUES FOUND] {len(issues)}")
            for issue in issues:
                print(f"  ⚠ {issue}")
        else:
            print(f"\n[OK] All {len(rules)} rules are valid")
        
        # Summary
        policy_groups = {}
        for rule in rules:
            policy = rule.get('policy_name', 'Unknown')
            policy_groups[policy] = policy_groups.get(policy, 0) + 1
        
        print(f"\n[SUMMARY]")
        for policy, count in sorted(policy_groups.items()):
            print(f"  {policy}: {count} rules")
    
    def run(self):
        """Run complete extraction pipeline"""
        rules = self.extract_all_rules()
        self.validate_rules(rules)
        self.save_rules(rules)
        return rules


def main():
    api_key = "AIzaSyBNA3ulr_NxSCa8S3emQk_GH-jIwwydCdc"
    
    extractor = PolicyRuleExtractor(api_key)
    rules = extractor.run()


if __name__ == "__main__":
    main()
