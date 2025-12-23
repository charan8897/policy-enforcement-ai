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


class RuleExtractor:
    """Extract structured rules from policy text using LLM"""
    
    def __init__(self, api_key, policy_file="policy.txt", output_file="rules.json"):
        """Initialize with Gemini API"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemma-3-27b-it')
        self.policy_file = policy_file
        self.output_file = output_file
        
        # Read policy
        if not os.path.exists(policy_file):
            raise FileNotFoundError(f"Policy file not found: {policy_file}")
        
        with open(policy_file, 'r') as f:
            self.policy_text = f.read()
    
    def extract_rules(self):
        """Extract all rules from policy text"""
        print(f"\n{'='*60}")
        print(f"Rule Extraction from Policy")
        print(f"{'='*60}")
        
        # Step 1: Detect policy type
        policy_type = self._detect_policy_type()
        print(f"[DETECTED] Policy type: {policy_type}")
        
        # Step 2: Get rule categories based on policy type
        rule_categories = self._get_rule_categories(policy_type)
        print(f"[CATEGORIES] {', '.join(rule_categories)}")
        
        # Step 3: Extract rules for each category
        all_rules = []
        rule_counter = 1
        
        for category in rule_categories:
            print(f"[EXTRACTING] {category}...")
            rules = self._extract_category_rules(category, policy_type, rule_counter)
            
            if rules:
                all_rules.extend(rules)
                rule_counter += len(rules)
                print(f"  ✓ {len(rules)} rules found")
            else:
                print(f"  - No rules found")
        
        print(f"\n[TOTAL] {len(all_rules)} rules extracted")
        return all_rules
    
    def _detect_policy_type(self):
        """Detect the type of policy document"""
        text_lower = self.policy_text.lower()
        
        # Policy type detection patterns
        patterns = {
            'leave_policy': ['leave', 'casual', 'earned', 'maternity', 'paternity'],
            'travel_policy': ['overseas', 'business travel', 'travel allowance', 'daily allowance', 'flight', 'hotel'],
            'procurement_policy': ['procurement', 'vendor', 'bidding', 'purchase', 'contract'],
            'attendance_policy': ['attendance', 'attendance policy', 'working hours', 'shift'],
            'expense_policy': ['expense', 'reimbursement', 'claim', 'allowance'],
        }
        
        # Count pattern matches
        matches = {}
        for policy_type, keywords in patterns.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            matches[policy_type] = count
        
        # Return most matched policy type
        best_match = max(matches, key=matches.get)
        return best_match if matches[best_match] > 0 else 'general_policy'
    
    def _get_rule_categories(self, policy_type):
        """Get rule categories based on policy type"""
        categories_map = {
            'leave_policy': ['Casual Leave', 'Earned Leave', 'Sick Leave', 'Maternity Leave', 'Paternity Leave'],
            'travel_policy': ['Flight Class', 'Daily Allowance', 'Hotel Accommodation', 'Foreign Exchange', 'Visa'],
            'procurement_policy': ['Vendor Eligibility', 'Bidding Process', 'Contract Terms', 'Payment Terms'],
            'attendance_policy': ['Working Hours', 'Shift Timings', 'Leave Application', 'Attendance Rules'],
            'expense_policy': ['Expense Categories', 'Reimbursement Limits', 'Approval Authority', 'Documentation'],
            'general_policy': ['General Rules', 'Procedures', 'Conditions', 'Requirements']
        }
        
        return categories_map.get(policy_type, categories_map['general_policy'])
    
    def _extract_category_rules(self, category, policy_type, rule_start_id):
        """Extract rules for specific category"""
        
        # Search policy for relevant section
        section = self._get_policy_section(category)
        
        prompt = f"""
Extract all policy rules for "{category}". Return ONLY valid JSON array.

Policy section:
{section[:2000]}

Example format:
[
  {{
    "rule_id": "RULE_CL_001",
    "policy_id": "POL_{category.upper().replace(' ', '_')}",
    "policy_name": "{category} Policy",
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
                category_prefix = category.split()[0][:2].upper()
                rule['rule_id'] = f"RULE_{category_prefix}_{rule_start_id + i:03d}"
            
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
        print("Usage: python extract_policy.py <input_file.pdf|.docx> [--rules]")
        print("\nExamples:")
        print("  python extract_policy.py leave-policy.docx          # Extract text only")
        print("  python extract_policy.py leave-policy.docx --rules  # Extract text + rules")
        sys.exit(1)
    
    input_file = sys.argv[1]
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


if __name__ == "__main__":
    main()
