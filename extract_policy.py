#!/usr/bin/env python3
"""
Policy Document Extraction & Rule Extraction Script
1. Extracts file type and converts to policy.txt
2. Uses LLM to extract structured rules to rules.json
"""

import os
import sys
import subprocess
import PyPDF2
import json
import google.generativeai as genai
from pathlib import Path
from PIL import Image
import io

class PolicyExtractor:
    def __init__(self, input_file):
        """Initialize with input file path"""
        self.input_file = input_file
        self.output_file = "policy.txt"
        
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")
    
    def detect_file_type(self):
        """Detect if file is PDF, DOCX, or image-based PDF"""
        file_ext = Path(self.input_file).suffix.lower()
        
        if file_ext == '.docx':
            return 'docx'
        elif file_ext == '.pdf':
            # Check if PDF is image-based or text-based
            return self._check_pdf_type()
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def _check_pdf_type(self):
        """Check if PDF contains extractable text or is image-based"""
        try:
            with open(self.input_file, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Check first 5 pages to detect text (skip cover pages)
                total_text = ""
                pages_to_check = min(5, len(pdf_reader.pages))
                
                for i in range(pages_to_check):
                    text = pdf_reader.pages[i].extract_text()
                    if text:
                        total_text += text
                
                # If any page has extractable text > 50 chars, it's text-based
                if len(total_text.strip()) > 50:
                    return 'pdf_text'
                else:
                    return 'pdf_image'
        except Exception as e:
            print(f"Warning: Could not read PDF metadata: {e}")
            return 'pdf_text'  # Default to pdftotext if uncertain
    
    def extract_from_docx(self):
        """Extract text from DOCX using Pandoc"""
        print(f"[INFO] Detected: DOCX file")
        print(f"[INFO] Using: Pandoc")
        
        try:
            result = subprocess.run(
                ['pandoc', self.input_file, '-t', 'plain'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"Pandoc extraction failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("Pandoc not installed. Install with: sudo apt-get install pandoc")
    
    def extract_from_pdf_text(self):
        """Extract text from text-based PDF using pdftotext"""
        print(f"[INFO] Detected: Text-based PDF")
        print(f"[INFO] Using: pdftotext")
        
        try:
            # Use pdftotext (faster than Tesseract)
            result = subprocess.run(
                ['pdftotext', self.input_file, '-'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"pdftotext extraction failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("pdftotext not installed. Install with: sudo apt-get install poppler-utils")
    
    def extract_from_pdf_image(self):
        """Extract text from image-based PDF using Tesseract OCR"""
        print(f"[INFO] Detected: Image-based PDF (scanned)")
        print(f"[INFO] Using: Tesseract OCR")
        
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError:
            raise Exception(
                "Required packages not installed.\n"
                "Install with: pip install pytesseract pdf2image pillow\n"
                "And install Tesseract: sudo apt-get install tesseract-ocr"
            )
        
        try:
            # Convert PDF pages to images
            print("[PROGRESS] Converting PDF to images...")
            images = convert_from_path(self.input_file)
            
            # Extract text from each image using OCR
            print(f"[PROGRESS] Processing {len(images)} pages with Tesseract OCR...")
            all_text = []
            
            for i, image in enumerate(images):
                print(f"[PROGRESS] Page {i+1}/{len(images)}...")
                text = pytesseract.image_to_string(image)
                all_text.append(text)
            
            return "\n\n---PAGE BREAK---\n\n".join(all_text)
        
        except subprocess.CalledProcessError as e:
            raise Exception(f"Tesseract OCR failed: {e}")
        except Exception as e:
            raise Exception(f"PDF to image conversion failed: {e}")
    
    def extract_text(self):
        """Main extraction method - detects type and extracts accordingly"""
        print(f"\n{'='*60}")
        print(f"Policy Document Extraction")
        print(f"{'='*60}")
        print(f"[INPUT] File: {self.input_file}")
        
        # Detect file type
        file_type = self.detect_file_type()
        print(f"[DETECT] File type: {file_type}")
        
        # Extract based on type
        if file_type == 'docx':
            text = self.extract_from_docx()
        elif file_type == 'pdf_text':
            text = self.extract_from_pdf_text()
        elif file_type == 'pdf_image':
            text = self.extract_from_pdf_image()
        else:
            raise ValueError(f"Unknown file type: {file_type}")
        
        return text
    
    def save_output(self, text):
        """Save extracted text to output file"""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"[OUTPUT] Saved to: {self.output_file}")
        print(f"[OUTPUT] Size: {len(text)} characters, {len(text.split())} words")
        print(f"{'='*60}\n")
    
    def process(self):
        """Run complete extraction pipeline"""
        try:
            text = self.extract_text()
            self.save_output(text)
            return True
        except Exception as e:
            print(f"\n[ERROR] {e}\n")
            return False


class RuleEvaluator:
    """Evaluate user requests against extracted rules"""
    
    def __init__(self, rules_file="rules.json"):
        """Initialize with rules"""
        if not os.path.exists(rules_file):
            raise FileNotFoundError(f"Rules file not found: {rules_file}")
        
        with open(rules_file, 'r') as f:
            self.rules = json.load(f)
    
    def evaluate(self, request):
        """Evaluate request against rules"""
        print(f"\n{'='*60}")
        print(f"Request Evaluation")
        print(f"{'='*60}")
        print(f"[REQUEST] {json.dumps(request, indent=2)}")
        
        # Validate required fields
        required_fields = ['request_id', 'request_type']
        missing_fields = [f for f in required_fields if f not in request]
        if missing_fields:
            print(f"\n[VALIDATION ERROR] Missing required fields: {missing_fields}")
            return {
                'decision': 'INVALID',
                'primary_reason': f'Missing required fields: {", ".join(missing_fields)}',
                'applicable_rules': [],
                'violations': [],
                'approvals': []
            }
        
        applicable_rules = []
        violations = []
        approvals = []
        
        # Check each rule
        for rule in self.rules:
            match, reason = self._evaluate_rule(rule, request)
            
            if match:
                applicable_rules.append(rule['rule_id'])
                
                if rule['action'] == 'REJECT':
                    violations.append({
                        'rule_id': rule['rule_id'],
                        'message': rule['message'],
                        'severity': rule.get('severity', 'MEDIUM')
                    })
                elif rule['action'] == 'ELIGIBLE':
                    approvals.append({
                        'rule_id': rule['rule_id'],
                        'allocation': rule.get('allocation'),
                        'period': rule.get('period')
                    })
                elif rule['action'] == 'REQUIRE_DOCUMENTATION':
                    violations.append({
                        'rule_id': rule['rule_id'],
                        'message': rule['message'],
                        'required_doc': rule.get('required_doc'),
                        'severity': rule.get('severity', 'MEDIUM')
                    })
        
        # Build decision
        if violations:
            decision = 'REJECT'
            primary_reason = violations[0]['message']
        elif approvals:
            decision = 'APPROVE'
            primary_reason = 'Request complies with all policies'
        else:
            decision = 'APPROVE'
            primary_reason = 'Request complies with all policies'
        
        result = {
            'decision': decision,
            'primary_reason': primary_reason,
            'applicable_rules': applicable_rules,
            'violations': violations,
            'approvals': approvals
        }
        
        self._display_result(result)
        return result
    
    def _evaluate_rule(self, rule, request):
        """Check if rule conditions match request"""
        conditions = rule.get('conditions', [])
        
        if not conditions:
            return False, "No conditions"
        
        # All conditions must match (AND logic)
        for condition in conditions:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            # Get value from request
            request_value = request.get(field)
            
            if request_value is None:
                return False, f"Field {field} not in request"
            
            # Evaluate operator
            if not self._evaluate_condition(request_value, operator, value):
                return False, f"Field {field} does not match"
        
        return True, "All conditions matched"
    
    def _evaluate_condition(self, request_value, operator, threshold):
        """Evaluate single condition with type validation"""
        try:
            # Type validation and coercion
            if request_value is None:
                return False
            
            # For numeric comparisons, ensure both values are numeric
            if operator in ['greater_than', 'less_than', 'greater_than_or_equals', 'less_than_or_equals']:
                # Check if values are numeric
                if not isinstance(request_value, (int, float)):
                    try:
                        request_value = float(request_value)
                    except (ValueError, TypeError):
                        print(f"    [TYPE ERROR] Cannot convert '{request_value}' to number for {operator}")
                        return False
                
                if not isinstance(threshold, (int, float)):
                    try:
                        threshold = float(threshold)
                    except (ValueError, TypeError):
                        print(f"    [TYPE ERROR] Threshold '{threshold}' is not numeric")
                        return False
                
                # Range validation: reject negative days/durations
                if request_value < 0:
                    print(f"    [VALIDATION] Negative value {request_value} rejected")
                    return False
            
            # Evaluate based on operator
            if operator == 'equals':
                return request_value == threshold
            elif operator == 'greater_than':
                return request_value > threshold
            elif operator == 'less_than':
                return request_value < threshold
            elif operator == 'greater_than_or_equals':
                return request_value >= threshold
            elif operator == 'less_than_or_equals':
                return request_value <= threshold
            elif operator == 'in':
                return request_value in threshold
            else:
                print(f"    [UNKNOWN OPERATOR] {operator}")
                return False
        
        except Exception as e:
            print(f"    [COMPARISON ERROR] {type(e).__name__}: {e}")
            return False
    
    def _display_result(self, result):
        """Display evaluation result"""
        print(f"\n[DECISION] {result['decision']}")
        print(f"[REASON] {result['primary_reason']}")
        
        if result['violations']:
            print(f"\n[VIOLATIONS] {len(result['violations'])}")
            for v in result['violations']:
                print(f"  ✗ {v['rule_id']}: {v['message']}")
        
        if result['approvals']:
            print(f"\n[APPROVALS] {len(result['approvals'])}")
            for a in result['approvals']:
                alloc = a.get('allocation')
                period = a.get('period', '')
                if alloc:
                    print(f"  ✓ {a['rule_id']}: {alloc} {period}")


class RuleExtractor:
    """Extract structured rules from policy text using LLM"""
    
    def __init__(self, api_key, policy_file="policy.txt", output_file="rules.json"):
        """Initialize with Gemini API"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        self.policy_file = policy_file
        self.output_file = output_file
        
        # Read policy
        if not os.path.exists(policy_file):
            raise FileNotFoundError(f"Policy file not found: {policy_file}")
        
        with open(policy_file, 'r') as f:
            self.policy_text = f.read()
    
    def extract_rules(self):
        """Extract all rules from policy text dynamically"""
        print(f"\n{'='*60}")
        print(f"Rule Extraction from Policy")
        print(f"{'='*60}")
        
        # Step 1: Detect policy types dynamically
        policy_types = self._detect_policy_types()
        
        if not policy_types:
            print("[WARNING] No policy types detected, attempting general extraction")
            policy_types = ['General Policy']
        
        print(f"[DETECTED] {len(policy_types)} policy types:")
        for ptype in policy_types:
            print(f"  - {ptype}")
        
        # Step 2: Extract rules for each detected type
        all_rules = []
        rule_counter = 1
        
        for policy_type in policy_types:
            print(f"\n[EXTRACTING] {policy_type}...")
            rules = self._extract_rules_for_type(policy_type, rule_counter)
            
            if rules:
                all_rules.extend(rules)
                rule_counter += len(rules)
                print(f"  ✓ {len(rules)} rules found")
            else:
                print(f"  - No rules extracted")
        
        print(f"\n[TOTAL] {len(all_rules)} rules extracted")
        return all_rules
    
    def _detect_policy_types(self):
        """Detect policy types dynamically from document"""
        print("[DETECTING] Policy types from document...")
        
        # Ask LLM to detect what policies are in the document
        prompt = f"""
Analyze this policy document and list all main policy types/categories mentioned.

Document excerpt (first 3000 chars):
{self.policy_text[:3000]}

Return ONLY a JSON array of policy names (strings), no explanation.
Example: ["Leave Policy", "Recruitment Policy", "Code of Conduct"]

Important: Extract the actual policy names from the document, not generic ones.

JSON array:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                return []
            
            json_str = response_text[start:end]
            policy_types = json.loads(json_str)
            
            # Filter out empty strings
            policy_types = [p.strip() for p in policy_types if p.strip()]
            
            return policy_types
        
        except Exception as e:
            print(f"  [ERROR] Policy detection failed: {e}")
            return []
    
    def _extract_rules_for_type(self, policy_type, rule_start_id):
        """Extract rules for specific policy type"""
        
        # Search policy for relevant section
        section = self._get_policy_section(policy_type)
        
        prompt = f"""
Extract all policy rules for "{policy_type}". Return ONLY valid JSON array.

Policy section:
{section[:2000]}

Example format:
[
  {{
    "rule_id": "RULE_001",
    "policy_id": "POL_{policy_type.upper().replace(' ', '_')}",
    "policy_name": "{policy_type}",
    "conditions": [{{"field": "field_name", "operator": "equals", "value": "value"}}],
    "action": "ELIGIBLE",
    "allocation": 8,
    "period": "per_annum",
    "message": "description",
    "severity": "MEDIUM"
  }}
]

Requirements:
- Return ONLY JSON array
- Valid actions: APPROVE, REJECT, ELIGIBLE, REQUIRE_DOCUMENTATION, WARN
- Valid operators: equals, greater_than, less_than, greater_than_or_equals, in
- Each rule needs: rule_id, policy_id, policy_name, conditions, action, message

JSON:"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON
            start = response_text.find('[')
            end = response_text.rfind(']') + 1
            
            if start < 0 or end <= start:
                return []
            
            json_str = response_text[start:end]
            rules = json.loads(json_str)
            
            # Update rule IDs
            for i, rule in enumerate(rules):
                policy_prefix = policy_type.split()[0][:3].upper()
                rule['rule_id'] = f"RULE_{policy_prefix}_{rule_start_id + i:03d}"
            
            return rules
        
        except Exception as e:
            print(f"  [ERROR] {e}")
            return []
    
    def _get_policy_section(self, leave_type):
        """Extract relevant policy section"""
        lines = self.policy_text.split('\n')
        section = []
        capture = False
        
        for line in lines:
            if leave_type.lower() in line.lower():
                capture = True
            
            if capture:
                section.append(line)
                if len(section) > 80:
                    break
        
        return '\n'.join(section) if section else ""
    
    def save_rules(self, rules):
        """Save rules to JSON"""
        with open(self.output_file, 'w') as f:
            json.dump(rules, f, indent=2)
        print(f"[SAVED] {self.output_file} ({len(rules)} rules)")
    
    def validate(self, rules):
        """Validate rules"""
        print(f"\n[VALIDATION]")
        
        by_policy = {}
        for rule in rules:
            policy = rule.get('policy_name', 'Unknown')
            by_policy[policy] = by_policy.get(policy, 0) + 1
        
        for policy, count in sorted(by_policy.items()):
            print(f"  {policy}: {count} rules")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python extract_policy.py <command> [options]")
        print("\nCommands:")
        print("  extract <file.pdf|.docx>          # Extract policy text")
        print("  extract <file.pdf|.docx> --rules  # Extract text + rules")
        print("  evaluate <request.json>           # Evaluate request against rules.json")
        print("\nExamples:")
        print("  python extract_policy.py extract leave-policy.docx")
        print("  python extract_policy.py extract policy.pdf --rules")
        print("  python extract_policy.py evaluate request.json")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'extract':
        if len(sys.argv) < 3:
            print("[ERROR] Missing policy file")
            sys.exit(1)
        
        input_file = sys.argv[2]
        extract_rules = '--rules' in sys.argv
        
        # Step 1: Extract policy text
        extractor = PolicyExtractor(input_file)
        success = extractor.process()
        
        # Step 2: Extract rules if requested
        if success and extract_rules:
            try:
                api_key = "AIzaSyBNA3ulr_NxSCa8S3emQk_GH-jIwwydCdc"
                rule_extractor = RuleExtractor(api_key)
                rules = rule_extractor.extract_rules()
                rule_extractor.save_rules(rules)
                rule_extractor.validate(rules)
            except Exception as e:
                print(f"\n[ERROR] Rule extraction failed: {e}")
                success = False
        
        sys.exit(0 if success else 1)
    
    elif command == 'evaluate':
        if len(sys.argv) < 3:
            print("[ERROR] Missing request file")
            sys.exit(1)
        
        request_file = sys.argv[2]
        
        try:
            # Load request
            with open(request_file, 'r') as f:
                request = json.load(f)
            
            # Evaluate
            evaluator = RuleEvaluator()
            result = evaluator.evaluate(request)
            
            # Save result
            result_file = request_file.replace('.json', '_result.json')
            with open(result_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n[SAVED] {result_file}")
            
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] {e}")
            sys.exit(1)
    
    else:
        print(f"[ERROR] Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()