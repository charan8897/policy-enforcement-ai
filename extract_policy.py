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
import shutil

# RAG imports
try:
    import chromadb
except ImportError:
    chromadb = None

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

class PolicyExtractor:
    def __init__(self, input_file):
        """Initialize with input file path"""
        self.input_file = input_file
        # self.output_file = "policy.txt"  # COMMENTED OUT - using RAG
        self.db_path = "./chroma_db"
        self.db_name = "policies"
        
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"File not found: {input_file}")
    
    def detect_file_type(self):
        """Detect if file is PDF, DOCX, TXT, or image-based PDF"""
        file_ext = Path(self.input_file).suffix.lower()
        
        if file_ext == '.txt':
            return 'txt'
        elif file_ext == '.docx':
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
    
    def extract_from_txt(self):
        """Extract text from plain text file"""
        print(f"[INFO] Detected: TXT file")
        print(f"[INFO] Using: Direct read")
        
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Text file read failed: {e}")
    
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
        if file_type == 'txt':
            text = self.extract_from_txt()
        elif file_type == 'docx':
            text = self.extract_from_docx()
        elif file_type == 'pdf_text':
            text = self.extract_from_pdf_text()
        elif file_type == 'pdf_image':
            text = self.extract_from_pdf_image()
        else:
            raise ValueError(f"Unknown file type: {file_type}")
        
        return text
    
    def save_to_rag(self, text, file_id=None):
        """Save extracted text to Chroma vector DB (RAG)"""
        if not chromadb or not RecursiveCharacterTextSplitter:
            print("[ERROR] Missing dependencies. Install with: pip install chromadb langchain")
            return False
        
        try:
            print(f"\n[RAG] Initializing vector DB...")
            client = chromadb.PersistentClient(path=self.db_path)
            collection = client.get_or_create_collection(name=self.db_name, metadata={"hnsw:space": "cosine"})
            
            print(f"[RAG] Splitting text into chunks...")
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100, separators=["\n\n", "\n", ".", " ", ""])
            chunks = splitter.split_text(text)
            
            doc_id = file_id or Path(self.input_file).stem
            print(f"[RAG] Adding {len(chunks)} chunks to vector DB...")
            ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"source": self.input_file, "chunk": i} for i in range(len(chunks))]
            collection.add(documents=chunks, ids=ids, metadatas=metadatas)
            
            print(f"[OUTPUT] Vector DB: {self.db_path}/{self.db_name}")
            print(f"[OUTPUT] Size: {len(text)} characters, {len(text.split())} words")
            print(f"[OUTPUT] Chunks: {len(chunks)}")
            print(f"{'='*60}\n")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save to RAG: {e}")
            return False
    
    # COMMENTED OUT - using RAG instead
    # def save_output(self, text):
    #     """Save extracted text to output file"""
    #     with open(self.output_file, 'w', encoding='utf-8') as f:
    #         f.write(text)
    #     
    #     print(f"[OUTPUT] Saved to: {self.output_file}")
    #     print(f"[OUTPUT] Size: {len(text)} characters, {len(text.split())} words")
    #     print(f"{'='*60}\n")
    
    def process(self):
        """Run complete extraction pipeline"""
        try:
            text = self.extract_text()
            # self.save_output(text)  # COMMENTED OUT
            return self.save_to_rag(text)  # Use RAG instead
        except Exception as e:
            print(f"\n[ERROR] {e}\n")
            return False


class RuleEvaluator:
    """Evaluate user requests against extracted rules"""
    
    def __init__(self, rules_file="rules.json", db_path="rules.db", use_vector_db=True, vector_db_path="./chroma_db"):
        """Initialize with rules from Vector DB or JSON"""
        self.rules_file = rules_file
        self.db_path = db_path
        self.use_vector_db = use_vector_db
        self.vector_db_path = vector_db_path
        self.rules = []
        self.grade_evaluator = None
        
        # Try loading from vector DB first, fallback to JSON
        if use_vector_db and chromadb:
            if not self._load_rules_from_vector_db():
                print("[FALLBACK] Loading rules from JSON file")
                self._load_rules_from_file(rules_file)
        else:
            self._load_rules_from_file(rules_file)
        
        # Initialize dynamic grade evaluator
        try:
            from grade_hierarchy_manager import DynamicGradeEvaluator
            self.grade_evaluator = DynamicGradeEvaluator(db_path)
            print(f"[GRADES] Using dynamic grade hierarchy from {db_path}")
        except Exception as e:
            print(f"[WARNING] Could not load dynamic grades: {e}")
            print("[WARNING] Falling back to hardcoded grade hierarchy")
            self.grade_evaluator = None
    
    def _load_rules_from_file(self, rules_file):
        """Load rules from JSON file"""
        if not os.path.exists(rules_file):
            raise FileNotFoundError(f"Rules file not found: {rules_file}")
        
        with open(rules_file, 'r') as f:
            self.rules = json.load(f)
        print(f"[RULES] Loaded {len(self.rules)} rules from {rules_file}")
    
    def _load_rules_from_vector_db(self):
        """Load rules from Chroma vector database"""
        if not chromadb:
            return False
        
        try:
            client = chromadb.PersistentClient(path=self.vector_db_path)
            collection = client.get_or_create_collection(name="rules")
            
            # Get all rules from vector DB
            all_results = collection.get()
            
            if not all_results['ids']:
                print("[VECTOR_DB] No rules found in vector database")
                return False
            
            # Reconstruct rules from metadata
            self.rules = []
            for i, rule_id in enumerate(all_results['ids']):
                metadata = all_results['metadatas'][i]
                # Parse the rule data from JSON string in metadata
                rule_data = json.loads(metadata.get('rule_data', '{}'))
                self.rules.append(rule_data)
            
            print(f"[VECTOR_DB] Loaded {len(self.rules)} rules from Chroma vector database")
            return True
        
        except Exception as e:
            print(f"[WARNING] Failed to load rules from vector DB: {e}")
            return False
    
    def _generate_approval_reason(self, approvals, applicable_rules):
        """Generate detailed approval reason with rule info"""
        approval_rules = [a['rule_id'] for a in approvals]
        
        # Get rule details for context
        rule_details = []
        for rule in self.rules:
            if rule['rule_id'] in approval_rules:
                policy = rule.get('policy_name', 'Unknown Policy')
                message = rule['message'][:100]
                rule_details.append(f"{rule['rule_id']} ({policy}): {message}")
        
        reason = f"✓ Request APPROVED based on {len(approval_rules)} policy rule(s): "
        reason += ", ".join(approval_rules) + ". "
        
        if rule_details:
            reason += "Policy Details: " + " | ".join(rule_details[:2])
        else:
            reason += "All policy requirements satisfied."
        
        return reason
    
    def _generate_rejection_reason(self, violations, applicable_rules):
        """Generate detailed rejection reason with rule info"""
        violation_rules = [v['rule_id'] for v in violations]
        
        # Categorize violations
        high_severity = [v for v in violations if v.get('severity') == 'HIGH']
        critical_severity = [v for v in violations if v.get('severity') == 'CRITICAL']
        
        if critical_severity:
            reason = f"Request REJECTED due to CRITICAL policy violation(s): "
            reason += ", ".join([v['rule_id'] for v in critical_severity]) + ". "
            reason += f"Reason: {critical_severity[0]['message'][:100]}"
        elif high_severity:
            reason = f"Request REJECTED: {len(high_severity)} HIGH severity rule(s) violated. "
            reason += f"Primary issue - {high_severity[0]['rule_id']}: {high_severity[0]['message'][:100]}"
        else:
            reason = f"Request REJECTED due to {len(violations)} policy violation(s): "
            reason += f"{violations[0]['rule_id']}: {violations[0]['message'][:100]}"
        
        return reason
    
    def _get_policy_summary(self):
        """Get summary of policies and rules"""
        summary = {}
        for rule in self.rules:
            policy = rule.get('policy_name', 'Unknown')
            if policy not in summary:
                summary[policy] = {'count': 0, 'fields': set()}
            summary[policy]['count'] += 1
            
            for condition in rule.get('conditions', []):
                summary[policy]['fields'].add(condition.get('field'))
        
        # Convert sets to lists for JSON serialization
        return {
            policy: {
                'rule_count': info['count'],
                'condition_fields': sorted(list(info['fields']))
            }
            for policy, info in summary.items()
        }
    
    def evaluate(self, request):
        """Evaluate request against rules"""
        print(f"\n{'='*60}")
        print(f"Request Evaluation")
        print(f"{'='*60}")
        print(f"[REQUEST] {json.dumps(request, indent=2)}")
        
        # Validate required fields (request_id is always required)
        required_fields = ['request_id']
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
                elif rule['action'] in ['ELIGIBLE', 'APPROVE']:
                    approvals.append({
                        'rule_id': rule['rule_id'],
                        'allocation': rule.get('allocation'),
                        'period': rule.get('period')
                    })
                # REQUIRE_DOCUMENTATION and WARN are informational, not blocking
        
        # Build decision (Whitelist approach: only approve what's explicitly allowed)
        if violations:
            decision = 'REJECT'
            # Generate detailed reason for rejection
            primary_reason = self._generate_rejection_reason(violations, applicable_rules)
        elif approvals:
            decision = 'APPROVE'
            # Generate detailed reason for approval
            primary_reason = self._generate_approval_reason(approvals, applicable_rules)
        else:
            decision = 'REJECT'
            primary_reason = 'Request type not recognized or no applicable policy rules found'
        
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
            # Rules with no conditions always match (apply to all requests)
            # These are general rules like ELIGIBLE, REQUIRE_DOCUMENTATION, WARN
            return True, "Always applicable (no conditions)"
        
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
    
    def _grade_to_numeric(self, grade):
        """Convert grade string to numeric value for comparison"""
        # Always use dynamic grade evaluator from database
        if self.grade_evaluator:
            level = self.grade_evaluator.get_grade_level(grade)
            if level is not None:
                return level
        
        # Fallback: try numeric conversion (for numeric grades like "1", "2", etc.)
        try:
            return float(grade)
        except (ValueError, TypeError):
            # Grade not found - log warning
            print(f"    [WARNING] Grade '{grade}' not found in database")
            return None
    
    def _evaluate_condition(self, request_value, operator, threshold):
        """Evaluate single condition with type validation"""
        try:
            # Type validation and coercion
            if request_value is None:
                return False
            
            # For numeric comparisons, ensure both values are numeric
            if operator in ['greater_than', 'less_than', 'greater_than_or_equals', 'less_than_or_equals']:
                # Try grade conversion first
                request_numeric = self._grade_to_numeric(request_value)
                threshold_numeric = self._grade_to_numeric(threshold)
                
                # If grade conversion failed, try numeric conversion
                if request_numeric is None:
                    try:
                        request_numeric = float(request_value)
                    except (ValueError, TypeError):
                        print(f"    [TYPE ERROR] Cannot convert '{request_value}' to number for {operator}")
                        return False
                
                if threshold_numeric is None:
                    try:
                        threshold_numeric = float(threshold)
                    except (ValueError, TypeError):
                        print(f"    [TYPE ERROR] Threshold '{threshold}' is not numeric")
                        return False
                
                # Range validation: reject negative days/durations
                if request_numeric < 0:
                    print(f"    [VALIDATION] Negative value {request_numeric} rejected")
                    return False
                
                # Use numeric values for comparison
                request_value = request_numeric
                threshold = threshold_numeric
            
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
    
    def __init__(self, api_key, db_path="./chroma_db", db_name="policies", output_file="rules.json"):
        """Initialize with Gemini API and Chroma vector DB"""
        genai.configure(api_key=api_key)
        # Use deterministic settings: temperature=0 for consistency
        self.model = genai.GenerativeModel(
            'gemma-3-27b-it',
            generation_config=genai.types.GenerationConfig(
                temperature=0,  # Deterministic output
                top_p=0.95
            )
        )
        self.db_path = db_path
        self.db_name = db_name
        self.output_file = output_file
        
        # Initialize Chroma client
        if not chromadb:
            raise Exception("Chroma not installed. Install with: pip install chromadb langchain")
        
        self.client = chromadb.PersistentClient(path=self.db_path)
        try:
            self.collection = self.client.get_collection(name=self.db_name)
            print(f"[RAG] Connected to vector DB: {self.db_path}/{self.db_name}")
        except Exception as e:
            raise Exception(f"Vector DB not found. Run extraction first: {e}")
    
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
        """Detect policy types dynamically from RAG vector DB"""
        print("[DETECTING] Policy types from vector DB...")
        
        # Query RAG for documents
        try:
            results = self.collection.get(limit=20)
            all_text = "\n".join(results['documents'][:10])
            print(f"[DEBUG] Retrieved {len(results['documents'])} chunks from DB")
        except Exception as e:
            print(f"[ERROR] Could not query vector DB: {e}")
            return []
        
        # Ask LLM to detect what policies are in the document
        prompt = f"""STRICT POLICY DETECTION

        Document excerpt:
        {all_text[:3000]}

        TASK: Identify ONLY the distinct, major policy types/categories explicitly mentioned in this document.

        REQUIREMENTS:
        1. Extract ONLY policies that have a distinct section or heading in the document
        2. Use the EXACT policy names as they appear in the document
        3. Do NOT infer or create generic policy names
        4. List each policy name exactly as it appears (e.g., "Family and Medical Leave Act", not "Leave Policy")
        5. Each policy should have clear rules or requirements associated with it
        6. Return only substantive policies, skip trivial mentions

        Return ONLY a JSON array with exact policy names from the document, NO explanation:
        Example: ["Family and Medical Leave Act", "Americans with Disabilities Act"]

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
        """Extract rules for specific policy type using RAG"""
        
        # Search RAG for relevant chunks
        print(f"  [RAG] Querying for '{policy_type}'...")
        section = self._get_policy_section(policy_type)
        
        prompt = f"""STRICT RULE EXTRACTION FOR "{policy_type}"

    Policy document section:
    {section[:2000]}

    REQUIREMENTS - FOLLOW STRICTLY:
    1. Extract ONLY rules explicitly stated in the policy document
    2. DO NOT infer, assume, or create rules not clearly mentioned
    3. For REJECT actions: ONLY use when policy explicitly denies/prohibits something
    4. For ELIGIBLE actions: ONLY use when policy explicitly allows something
    5. For REQUIRE_DOCUMENTATION: ONLY when policy explicitly requires documentation
    6. Conditions MUST match exact field values from the policy
    7. If no clear condition in policy, use empty conditions array []
    8. Rule action must be definitively supported by policy text

    Output format (ONLY return valid JSON array, no other text):
    [
    {{
    "rule_id": "RULE_POL_001",
    "policy_id": "POL_{policy_type.upper().replace(' ', '_')}",
    "policy_name": "{policy_type}",
    "conditions": [{{"field": "field_name", "operator": "equals", "value": "exact_value"}}],
    "action": "ELIGIBLE|REJECT|APPROVE|REQUIRE_DOCUMENTATION|WARN",
    "message": "Exact quote or precise summary from policy",
    "severity": "HIGH|MEDIUM|LOW"
    }}
    ]

    Valid actions (use ONLY these, only when explicitly in policy):
    - REJECT: Policy explicitly denies/prohibits this condition
    - ELIGIBLE: Policy explicitly allows/approves this condition  
    - APPROVE: Policy explicitly approves this condition
    - REQUIRE_DOCUMENTATION: Policy explicitly requires documents
    - WARN: Policy warns about something

    Valid operators: equals, greater_than, less_than, greater_than_or_equals, in, not_equals

    CONDITIONS: Add conditions ONLY if policy explicitly states "if X then Y"
    Empty conditions [] = rule applies to all cases

    Return ONLY the JSON array:"""
        
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
            
            # Update rule IDs and add RAG chunk references
            for i, rule in enumerate(rules):
                policy_prefix = policy_type.split()[0][:3].upper()
                rule['rule_id'] = f"RULE_{policy_prefix}_{rule_start_id + i:03d}"
                # Track RAG source for traceability
                rule['_source'] = {
                    'type': 'RAG_VECTOR_DB',
                    'db_path': self.db_path,
                    'query': policy_type,
                    'note': 'Can retrieve source chunks using semantic search'
                }
            
            return rules
        
        except Exception as e:
            print(f"  [ERROR] {e}")
            return []
    
    def _get_policy_section(self, policy_type):
        """Extract relevant policy section from RAG using semantic search"""
        try:
            # Query RAG for relevant chunks
            results = self.collection.query(
                query_texts=[policy_type],
                n_results=5
            )
            
            if results['documents']:
                section = "\n".join(results['documents'][0][:5])
                return section
            else:
                print(f"[WARNING] No relevant chunks found for {policy_type}")
                return ""
        except Exception as e:
            print(f"[ERROR] RAG query failed: {e}")
            return ""
    
    def save_rules(self, rules):
         """Save rules to Vector DB (Chroma) only - no JSON"""
         # Deduplicate by rule_id
         unique_rules = {}
         for rule in rules:
              rule_id = rule.get('rule_id', '')
              if rule_id not in unique_rules:
                  unique_rules[rule_id] = rule
              else:
                  # Keep the more detailed version
                  if len(json.dumps(rule)) > len(json.dumps(unique_rules[rule_id])):
                      unique_rules[rule_id] = rule
         
         deduped_rules = list(unique_rules.values())
         
         # Add RAG metadata to each rule
         for rule in deduped_rules:
              rule['_rag_metadata'] = {
                  'vector_db': self.db_path,
                  'collection': 'rules',
                  'generated_from': 'RAG (Retrieval Augmented Generation)',
                  'note': 'Rules stored in vector DB for semantic search'
              }
         
         # Save to Vector DB (Only storage)
         self._save_rules_to_vector_db(deduped_rules)
         
         if len(deduped_rules) < len(rules):
              print(f"[SAVED] {len(rules)} → {len(deduped_rules)} rules (deduplicated, stored in vector DB)")
         else:
              print(f"[SAVED] {len(deduped_rules)} rules to vector DB")
    
    def _save_rules_to_vector_db(self, rules):
        """Save rules to Chroma vector database"""
        if not chromadb:
             print("[WARNING] chromadb not installed, skipping vector DB storage")
             return
        
        try:
             client = chromadb.PersistentClient(path=self.db_path)
             collection = client.get_or_create_collection(
                  name="rules",
                  metadata={"hnsw:space": "cosine"}
             )
             
             # Prepare documents and metadata for vector storage
             documents = []
             metadatas = []
             ids = []
             
             for rule in rules:
                  rule_id = rule.get('rule_id', '')
                  policy_name = rule.get('policy_name', 'Unknown')
                  action = rule.get('action', 'UNKNOWN')
                  message = rule.get('message', '')
                  
                  # Document text for embedding
                  doc_text = f"{rule_id}: {policy_name} - {action}. {message}"
                  
                  documents.append(doc_text)
                  ids.append(rule_id)
                  
                  metadatas.append({
                       'rule_id': rule_id,
                       'policy_name': policy_name,
                       'action': action,
                       'severity': rule.get('severity', 'MEDIUM'),
                       'rule_data': json.dumps(rule)  # Store full rule as JSON string
                  })
             
             # Clear existing rules in collection (if any exist)
             try:
                  collection.delete(where={})
             except:
                  pass  # Collection might be empty
             
             # Add new rules to vector DB
             collection.add(
                  documents=documents,
                  metadatas=metadatas,
                  ids=ids
             )
             
             print(f"[VECTOR_DB] Saved {len(rules)} rules to Chroma collection 'rules'")
        
        except Exception as e:
             print(f"[WARNING] Failed to save rules to vector DB: {e}")
    
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
        print("  extract <file.pdf|.docx> --rules  # Extract text + rules (uses cache if available)")
        print("  evaluate <request.json>           # Evaluate request against rules.json")
        print("\nOptions:")
        print("  --no-cache                        # Force regenerate rules (ignore cache)")
        print("\nExamples:")
        print("  python extract_policy.py extract leave-policy.docx")
        print("  python extract_policy.py extract policy.pdf --rules")
        print("  python extract_policy.py extract policy.pdf --rules --no-cache  # Regenerate")
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
                api_key = "AIzaSyBwRjRbssL6kxZPx55_I1yCONHdCZokM-c"
                rule_extractor = RuleExtractor(api_key)
                rules = rule_extractor.extract_rules()
                rule_extractor.save_rules(rules)
                rule_extractor.validate(rules)
                
                # Step 3: Also extract grade hierarchies for detected policies
                print(f"\n[GRADES] Extracting grade hierarchies...")
                try:
                    from grade_hierarchy_manager import GradeHierarchyExtractor
                    grade_extractor = GradeHierarchyExtractor(api_key)
                    
                    # Get unique policy types from rules
                    policy_types = set()
                    for rule in rules:
                        policy_types.add((rule.get('policy_id'), rule.get('policy_name')))
                    
                    for policy_id, policy_name in policy_types:
                        grade_extractor.extract_for_policy(policy_id, policy_name)
                    
                    grade_extractor.close()
                    print(f"[GRADES] Grade hierarchies extracted and stored in rules.db")
                except Exception as e:
                    print(f"[WARNING] Grade extraction skipped: {e}")
            
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